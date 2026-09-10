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

    def get_material(self, tex_name, out_dir, base):
        key = tex_name or '__default__'
        if key in self.material_idx:
            return self.material_idx[key]
        mat = {'name': key, 'doubleSided': True}
        t = self.get_texture(tex_name, out_dir, base)
        # 镂空贴图(树叶/栅栏/广告牌)走 alphaTest, 否则整片遮挡视线
        path = find_texture(tex_name)
        if path is not None:
            try:
                im = Image.open(path)
                if im.mode in ('RGBA', 'LA', 'PA') or 'transparency' in im.info:
                    im = im.convert('RGBA')
                    lo = im.getchannel('A').getextrema()[0]
                    if lo < 250:
                        mat['alphaMode'] = 'MASK'
                        mat['alphaCutoff'] = 0.5
            except Exception:
                pass
        if t is not None:
            mat['pbrMetallicRoughness'] = {'baseColorTexture': {'index': t},
                                           'metallicFactor': 0.0, 'roughnessFactor': 1.0}
        else:
            mat['pbrMetallicRoughness'] = {'baseColorFactor': [0.7, 0.7, 0.7, 1.0],
                                           'metallicFactor': 0.0, 'roughnessFactor': 1.0}
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
    """刚性网格 -> 展开的 positions/normals/uvs/indices"""
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
            uvs.append((tc['u'], 1.0 - tc['v']))
        indices.extend((start, start + 1, start + 2) if not f.get('winding')
                       else (start, start + 2, start + 1))
    return positions, normals, uvs, indices


def extract_qv(vd):
    positions = vd.get('positions') or []
    normals = vd.get('normals') or []
    uvs = vd.get('uvs') or []
    idx = vd.get('indices') or []
    P = []
    N = []
    UV = []
    I = []
    for i in idx:
        P.append(positions[i])
        N.append(normals[i] if normals else (0, 1, 0))
        uv = uvs[i][0] if uvs and uvs[i] else (0, 0)
        UV.append((uv[0], 1.0 - uv[1]))
    for t in range(0, len(idx), 3):
        I.extend((t, t + 1, t + 2))
    return P, N, UV, I


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
            UV.append((w['u'], 1.0 - w['v']) if w else (0, 0))
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

    def mesh_material(n):
        # 从 slots 找纹理/材质对象
        for s in n.get('slots') or []:
            s = unwrap(s)
            if isinstance(s, dict):
                kind = s.get('kind')
                if kind == 'texture':
                    return s.get('name')
                if kind == 'material':
                    pass
        # 从附加属性/property 找
        return None

    def collect_mesh(n, parent_m):
        kind = n.get('className') or n.get('kind')
        m = parent_m @ node_matrix(n)
        geo = None
        if n.get('vertexData') is not None:
            vd = unwrap(n['vertexData'])
            geo = extract_qv(vd)
        elif n.get('geometry') is not None:
            geo = extract_kv(unwrap(n['geometry']))
        if geo:
            P, N, UV, I = geo
            tex = mesh_material(n)
            key = tex or '__default__'
            groups.setdefault(key, []).append((m, P, N, UV, I, n.get('name')))
        for c in n.get('children', []):
            collect_mesh(unwrap(c), m)

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
                    P, N, UV, I = extract_kv(geo)
                # 车辆/人物模型只有一套贴图(0.png),官方 y1() 直接整体赋 baseColor map
                key = '0' if find_texture('0') else '__default__'
                groups.setdefault(key, []).append((m, P, N, UV, I, n.get('name')))
            for c in n.get('children', []) or []:
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
        mat_idx = B.get_material(None if key == '__default__' else key, out_dir, base)
        pos_arr = []
        nrm_arr = []
        uv_arr = []
        idx_arr = []
        for (m, P, N, UV, I, name) in items:
            nm = normal_matrix(m)
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
        mesh['primitives'][0]['attributes'] = {'POSITION': a_p, 'NORMAL': a_n, 'TEXCOORD_0': a_u}
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
