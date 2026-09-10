"""KartRider .1s -> glTF 2.0 转换器

用法:
  python s1_gltf.py unpacked/track_village_R01/track.1s web/track
  python s1_gltf.py unpacked/DataPack2_00007/kart_/cotton1/model.1s web/kart --model

输出: <out>.gltf + <out>.bin + <out>_textures/*.png + <out>_meta.json
"""
import json
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_parse as S

TEX_ROOTS = [
    'unpacked/theme_village/texture',
    'unpacked/theme_xyy/texture',
    'unpacked/theme_common/texture',
    'unpacked/DataPack2_00007/kart_/cotton1',
]


def find_texture(name):
    if not name:
        return None
    for root in TEX_ROOTS:
        for ext in ('.png', '.dds'):
            p = os.path.join(root, name + ext)
            if os.path.exists(p):
                return p
    return None


def dds_to_png_bytes(path):
    im = Image.open(path)
    im = im.convert('RGBA')
    import io
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return buf.getvalue()


def png_bytes(path):
    # 统一转成 RGB/RGBA PNG(有些 png 是调色板,统一一下)
    im = Image.open(path)
    if im.mode not in ('RGB', 'RGBA'):
        im = im.convert('RGBA')
    import io
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return buf.getvalue()


def unwrap(x):
    if isinstance(x, dict) and 'value' in x:
        return x['value']
    return x


class GltfBuilder:
    def __init__(self):
        self.bin = bytearray()
        self.images = []       # {name, mimeType, bufferView}
        self.textures = {}     # name -> texture index
        self.materials = []    # gltf materials
        self.material_idx = {}  # key -> index
        self.meshes = []       # gltf meshes
        self.nodes = []
        self.bufferViews = []
        self.accessors = []

    def add_bv(self, data, target):
        off = len(self.bin)
        self.bin += data
        while len(self.bin) % 4:
            self.bin += b'\0'
        self.bufferViews.append({'buffer': 0, 'byteOffset': off,
                                 'byteLength': len(data), 'target': target})
        return len(self.bufferViews) - 1

    def add_accessor(self, bv, ctype, count, mins, maxs):
        acc = {'bufferView': bv, 'componentType': ctype, 'count': count, 'type': 'VEC3'}
        if mins is not None:
            acc['min'] = mins
            acc['max'] = maxs
        self.accessors.append(acc)
        return len(self.accessors) - 1

    def get_texture(self, name, out_dir, base):
        if name in self.textures:
            return self.textures[name]
        path = find_texture(name)
        if path is None:
            return None
        data = dds_to_png_bytes(path) if path.endswith('.dds') else png_bytes(path)
        tex_dir = os.path.join(out_dir, base + '_textures')
        os.makedirs(tex_dir, exist_ok=True)
        fname = name + '.png'
        with open(os.path.join(tex_dir, fname), 'wb') as f:
            f.write(data)
        bv = self.add_bv(struct.pack('<I', len(data)), None)
        # 简化:外部文件引用
        img_idx = len(self.images)
        self.images.append({'uri': base + '_textures/' + fname})
        tex_idx = len(self.textures)
        self.textures[name] = tex_idx
        self.textures = {**self.textures}  # 保持顺序无所谓
        self.gltf_textures.append({'source': img_idx})
        return tex_idx

    def get_material(self, tex_name, out_dir, base, cull=2, alpha=None, mtl=None):
        key = tex_name or '__default__'
        if key in self.material_idx:
            return self.material_idx[key]
        # 官方 Wb(): D3D cull 1=NONE(双面) 2=CW(正面) 3=CCW(背面); 默认 2
        side_map = {1: 'DOUBLE', 2: 'SINGLE', 3: 'BACK'}
        mat = {'name': key, 'doubleSided': side_map.get(cull if cull in side_map else 2, 'SINGLE') != 'SINGLE'}
        t = self.get_texture(tex_name, out_dir, base)
        # 官方语义: 只有 AlphaProperty.alphaTestEnable 才做 alphaTest,
        # 贴图 alpha 通道不一定是透明度(可能是涂装/遮罩), 不可凭通道猜测
        if alpha and alpha.get('alphaTestEnable'):
            mat['alphaMode'] = 'MASK'
            mat['alphaCutoff'] = round(alpha.get('alphaRef', 128) / 255.0, 4)
        # Mtl mode 0/1 = 不受光(官方 basic stage 无光照), mode 2 = diffuse/emissive 受光
        mode = (mtl or {}).get('mode', 0)
        if mode in (0, 1):
            mat['extensions'] = {'KHR_materials_unlit': {}}
        pbr = {'metallicFactor': 0.0, 'roughnessFactor': 1.0}
        if mode == 2 and mtl:
            d = mtl.get('diffuse', 0xFFFFFFFF)
            pbr['baseColorFactor'] = [((d >> 16) & 255) / 255.0, ((d >> 8) & 255) / 255.0,
                                      (d & 255) / 255.0, ((d >> 24) & 255) / 255.0]
        if t is not None:
            pbr['baseColorTexture'] = {'index': t}
        else:
            pbr.setdefault('baseColorFactor', [0.7, 0.7, 0.7, 1.0])
        mat['pbrMetallicRoughness'] = pbr
        idx = len(self.materials)
        self.materials.append(mat)
        self.material_idx[key] = idx
        return idx


def compose(basis, pos, scale):
    """官方 l1/N0/uC 语义: 行 i = basis[i] 各分量分别乘 scale[0..2], 平移原样。
    Z-up 数据 -> Y-up 呈现空间由根节点 RotX(-90°) 统一完成:
    官方物理 ae()=(x,z,-y)、赛车导入 rotation.x=-PI/2 均为同一约定 (up=+Y)。"""
    m = np.eye(4)
    for i in range(3):
        for j in range(3):
            m[i, j] = basis[i][j] * scale[j]
    m[:3, 3] = pos
    return m


ROT_XM90 = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)  # RotX(-90°) 3x3 = 官方 ae()


def rot_x90(v):
    return ROT_XM90 @ np.asarray(v, dtype=np.float64)


def normal_matrix(m):
    n = np.linalg.inv(m[:3, :3]).T
    return n


def extract_kv(geo):
    """刚性网格 -> 展开的 positions/normals/uvs/indices
    UV 注意: 官方 PNG/DDS 均 flipY=false 且 v 原样传入(与 glTF 左上角原点一致), 不得翻转!"""
    positions, normals, uvs, indices = [], [], [], []
    P, N, T = geo['positions'], geo['normals'], geo['texcoords']
    for f in geo['faces']:
        start = len(positions)
        for k in range(3):
            tc = T[f['texcoord'][k]]
            p = P[f['position'][k]]
            nrm = N[tc['normalIndex']] if tc['normalIndex'] < len(N) else (0, 1, 0)
            positions.append(p)
            normals.append(nrm)
            uvs.append((tc['u'], tc['v']))
        indices.extend((start, start + 1, start + 2) if not f.get('winding')
                       else (start, start + 2, start + 1))
    return positions, normals, uvs, indices


def expand_strip(indices):
    """官方 HS(): ReTriStrip -> 三角形表, 奇偶交替交换前两点, 跳过退化三角形"""
    out = []
    for i in range(len(indices) - 2):
        if i % 2 == 0:
            a, b = indices[i], indices[i + 1]
        else:
            a, b = indices[i + 1], indices[i]
        c = indices[i + 2]
        if a != b and b != c and a != c:
            out.extend((a, b, c))
    return out


def extract_qv(vd, is_strip=False):
    """赛道 vertexData -> 展开顶点。官方 KS(): uv=uvs[*][0] 原样, diffuseColors 顶点色参与调制"""
    positions = vd.get('positions') or []
    normals = vd.get('normals') or []
    uvs = vd.get('uvs') or []
    colors = vd.get('colors')
    idx = expand_strip(vd.get('indices') or []) if is_strip else (vd.get('indices') or [])
    P = []
    N = []
    UV = []
    C = []
    I = []
    for i in idx:
        P.append(positions[i] if i < len(positions) else (0, 0, 0))
        N.append(normals[i] if normals and i < len(normals) else (0, 1, 0))
        uv = uvs[i][0] if uvs and uvs[i] else (0, 0)
        UV.append((uv[0], uv[1]))
        if colors is not None:
            u32 = colors[i]
            # 官方 qS(): r=(>>>16&255), g=(>>>8&255), b=( &255), a=(>>>24&255)
            C.append((((u32 >> 16) & 255) / 255.0, ((u32 >> 8) & 255) / 255.0,
                      (u32 & 255) / 255.0, ((u32 >> 24) & 255) / 255.0))
    for t in range(0, len(P), 3):
        I.extend((t, t + 1, t + 2))
    return P, N, UV, I, (C if colors is not None else None)


def extract_jv(geo):
    """蒙皮网格按绑定姿态展开: 每三角角点复制(position 索引 + wedge 的 UV)"""
    verts = geo['vertices']
    wedges = geo['wedges']
    P, N, UV, I = [], [], [], []
    for tri in geo['triangles']:
        start = len(P)
        for k in range(3):
            w = wedges[tri['wedge'][k]] if tri['wedge'][k] < len(wedges) else None
            v = verts[tri['position'][k]]
            P.append(v['position'])
            N.append(v.get('normal') or (0, 1, 0))
            UV.append((w['u'], w['v']) if w else (0, 0))
        I.extend((start, start + 1, start + 2))
    return P, N, UV, I


def convert(src_path, out_dir, base, model_mode=False):
    data = open(src_path, 'rb').read()
    root, g = S.parse_auto(data)
    v = unwrap(root)

    os.makedirs(out_dir, exist_ok=True)
    B = GltfBuilder()
    B.gltf_textures = []
    B.gltf_materials = []
    B.gltf_meshes = []
    B.gltf_nodes = []
    B.gltf_scenes_nodes = []

    # 材质键 -> 累积 primitive
    groups = {}

    meta = {'source': src_path, 'roads': [], 'minimap': None, 'start': None}

    def node_matrix(n):
        tr = n.get('transform')
        if tr is None:
            return np.eye(4)
        if isinstance(tr, dict):  # 模型模式 {basis, translation, scale}
            basis = tr['basis']
            pos = tr.get('translation', (0, 0, 0))
            scale = tr.get('scale', (1, 1, 1))
        else:                     # 赛道模式 [vec3, vec3, vec3]
            basis = tr
            pos = n.get('position', (0, 0, 0))
            scale = n.get('scale', (1, 1, 1))
        return compose(basis, pos, scale)

    def slot_state(n, st):
        """官方语义: texture/backface/alpha/material 描述符全部父->子继承"""
        tex, cull, alpha, mtl = st
        for s in n.get('slots') or []:
            s = unwrap(s)
            if not isinstance(s, dict):
                continue
            k = s.get('kind')
            if k == 'texture' and s.get('name'):
                tex = s['name']
            elif k == 'backface':
                cull = s.get('cull', cull)
            elif k == 'alpha' or 'alphaTestEnable' in s:  # AlphaProperty(两种解析器字段形态)
                alpha = s
            elif k == 'material':
                mtl = s
        return (tex, cull, alpha, mtl)

    def collect_mesh(n, parent_m, st=(None, 2, None, None)):
        kind = n.get('className') or n.get('kind')
        m = parent_m @ node_matrix(n)
        st = slot_state(n, st)
        tex, cull, alpha, mtl = st
        if n.get('vertexData') is not None:
            vd = unwrap(n['vertexData'])
            is_strip = kind == 'ReTriStrip'
            P, N, UV, I, C = extract_qv(vd, is_strip)
            key = tex or '__default__'
            groups.setdefault(key, []).append(
                (m, P, N, UV, I, n.get('name'), C, cull if cull is not None else 2, alpha, mtl))
        elif n.get('geometry') is not None:
            P, N, UV, I = extract_kv(unwrap(n['geometry']))
            key = tex or '__default__'
            groups.setdefault(key, []).append(
                (m, P, N, UV, I, n.get('name'), None, cull if cull is not None else 2, alpha, mtl))
        for c in n.get('children', []):
            collect_mesh(unwrap(c), m, st)

    if model_mode or v.get('className') == 'ReKart':
        # 模型模式:根是 sn 节点
        def walk_model(n, parent_m):
            n = unwrap(n)
            m = parent_m @ node_matrix(n)
            if n.get('geometry'):
                geo = unwrap(n['geometry'])
                if 'vertices' in geo:  # ReToonSkinned (jv) — 按绑定姿态静态导出
                    P, N, UV, I = extract_jv(geo)
                else:
                    P, N, UV, I = extract_kv(geo)[:4]
                # 车辆/人物模型只有一套贴图(0.png),官方 y1() 直接整体赋 baseColor map
                key = '0' if find_texture('0') else '__default__'
                groups.setdefault(key, []).append(
                    (m, P, N, UV, I, n.get('name'), None, 1, None, None))
            for c in n.get('children') or []:
                walk_model(c, m)
        walk_model(v, np.eye(4))
    else:
        collect_mesh(unwrap(v['scene']), np.eye(4))
        # 赛道元数据
        for obj in v.get('trackObjects', []):
            if obj.get('kind') == 'ToRoad':
                for rec in obj.get('records', []):
                    zframes = [{'position': rot_x90(f['position']).tolist(),
                                'forward': rot_x90(f['forward']).tolist(),
                                'up': rot_x90(f['up']).tolist()}
                               for f in rec['frames']]
                    meta['roads'].append({
                        'name': rec['name'], 'objName': obj.get('name'), 'surface': rec.get('surface'),
                        'cyclic': obj.get('cyclic'),
                        'positions': [rot_x90(p).tolist() for p in rec['positions']],
                        'gates': rec['gates'], 'frames': zframes})
            elif obj.get('kind') == 'ToMinimap':
                meta['minimap'] = {k: obj[k] for k in
                                   ('centerX', 'centerY', 'scale', 'canvasWidth', 'canvasHeight')}
            elif obj.get('name') == 'start' and obj.get('kind') == 'ToDummy':
                meta['start'] = {'transform': obj.get('transform')}

    # 生成 glTF
    scene_nodes = []
    for key, items in groups.items():
        first = items[0]
        mat_idx = B.get_material(None if key == '__default__' else key, out_dir, base,
                                 cull=first[7], alpha=first[8], mtl=first[9])
        pos_arr = []
        nrm_arr = []
        uv_arr = []
        col_arr = []
        idx_arr = []
        for (m, P, N, UV, I, name, C, cull, alpha, mtl) in items:
            nm = normal_matrix(m)
            mirrored = np.linalg.det(m[:3, :3]) < 0  # 官方: det<0 时翻面(Wb 的 flip 标志)
            base_i = len(pos_arr)
            for p in P:
                w = m @ np.array([p[0], p[1], p[2], 1.0])
                pos_arr.append((w[0], w[1], w[2]))
            for nn in N:
                t = nm @ np.array(nn)
                ln = np.linalg.norm(t)
                nrm_arr.append((t / ln) if ln > 1e-9 else (0, 1, 0))
            for uv in UV:
                uv_arr.append(uv)
            if C is not None:
                col_arr.extend(C)
            if mirrored:
                # 官方 Wb(): det<0 翻面 → 每三角交换后两点
                for t in range(0, len(I), 3):
                    idx_arr.extend((base_i + I[t], base_i + I[t + 2], base_i + I[t + 1]))
            else:
                for i in I:
                    idx_arr.append(base_i + i)
        mesh = {'primitives': [{'attributes': {'POSITION': 0, 'NORMAL': 1, 'TEXCOORD_0': 2},
                                'indices': 3, 'material': mat_idx, 'mode': 4}]}
        # 一个 mesh 一个 primitive,accessors 独立
        Pdata = np.array(pos_arr, dtype='<f4')
        Ndata = np.array(nrm_arr, dtype='<f4')
        UVdata = np.array(uv_arr, dtype='<f4').flatten()
        Idata = np.array(idx_arr, dtype='<u4')
        pmn = Pdata.reshape(-1, 3).min(axis=0).tolist()
        pmx = Pdata.reshape(-1, 3).max(axis=0).tolist()
        bv_p = B.add_bv(Pdata.tobytes(), 34962)
        bv_n = B.add_bv(Ndata.tobytes(), 34962)
        bv_u = B.add_bv(UVdata.tobytes(), 34962)
        bv_i = B.add_bv(Idata.tobytes(), 34963)
        a_p = B.add_accessor(bv_p, 5126, len(pos_arr), pmn, pmx)
        a_n = B.add_accessor(bv_n, 5126, len(nrm_arr), None, None)
        acc_uv = {'bufferView': bv_u, 'componentType': 5126, 'count': len(uv_arr), 'type': 'VEC2'}
        B.accessors.append(acc_uv)
        a_u = len(B.accessors) - 1
        acc_i = {'bufferView': bv_i, 'componentType': 5125, 'count': len(idx_arr), 'type': 'SCALAR'}
        B.accessors.append(acc_i)
        a_i = len(B.accessors) - 1
        attrs = {'POSITION': a_p, 'NORMAL': a_n, 'TEXCOORD_0': a_u}
        if col_arr:
            Cdata = np.array(col_arr, dtype='<f4')
            bv_c = B.add_bv(Cdata.tobytes(), 34962)
            B.accessors.append({'bufferView': bv_c, 'componentType': 5126,
                                'count': len(col_arr), 'type': 'VEC4'})
            attrs['COLOR_0'] = len(B.accessors) - 1
        mesh['primitives'][0]['attributes'] = attrs
        mesh['primitives'][0]['indices'] = a_i
        B.gltf_meshes.append(mesh)
        node = {'mesh': len(B.gltf_meshes) - 1, 'name': key}
        B.gltf_nodes.append(node)
        scene_nodes.append(len(B.gltf_nodes) - 1)

    root_node = {'rotation': [-0.7071067811865476, 0.0, 0.0, 0.7071067811865476],
                 'children': scene_nodes, 'name': 'zup_root'}
    B.gltf_nodes.append(root_node)
    root_idx = len(B.gltf_nodes) - 1
    gltf = {
        'asset': {'version': '2.0', 'generator': 'kartemu s1_gltf'},
        # GLTFLoader 只为 extensionsUsed 声明过的扩展实例化处理器, 材质级使用必须在此声明
        'extensionsUsed': ['KHR_materials_unlit'],
        'scene': 0,
        'scenes': [{'nodes': [root_idx]}],
        'nodes': B.gltf_nodes,
        'meshes': B.gltf_meshes,
        'materials': B.materials,
        'textures': B.gltf_textures,
        'images': B.images,
        'accessors': B.accessors,
        'bufferViews': B.bufferViews,
        'buffers': [{'uri': base + '.bin', 'byteLength': len(B.bin)}],
    }
    with open(os.path.join(out_dir, base + '.gltf'), 'w', encoding='utf-8') as f:
        json.dump(gltf, f, ensure_ascii=False)
    with open(os.path.join(out_dir, base + '.bin'), 'wb') as f:
        f.write(B.bin)
    with open(os.path.join(out_dir, base + '_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False)
    print(f'{base}: 材质组 {len(groups)}, 网格 {len(B.gltf_meshes)}, bin {len(B.bin)/1048576:.1f}MB, '
          f'贴图 {len(B.images)}')
    print('  未找到贴图:', [k for k in groups if k != '__default__'
                          and find_texture(k) is None][:10])


if __name__ == '__main__':
    src, out, base = sys.argv[1], sys.argv[2], sys.argv[3]
    convert(src, out, base, model_mode='--model' in sys.argv)
