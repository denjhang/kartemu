"""人物 model.1s -> 骨骼蒙皮 glTF 2.0(官方 §18 语义的忠实落地)

与 s1_gltf.py --character 的单帧烘焙不同, 这里导出真正的骨架:
  - 24 根骨骼 = glTF 节点层级, 局部绑定矩阵来自 localBind
  - body 蒙皮网格带 JOINTS_0/WEIGHTS_0(官方双骨骼线性混合, bone1=255 表示无)
  - 刚性件(脸/头/手)挂到对应骨骼节点下, 局部矩阵 = inv(bind_world[bone]) * m
  - character_common/fXX.1s 全部导出为 glTF 动画剪辑(官方始终播放动画)

用法: python char_gltf.py unpacked/character_dao/model.1s web/character dao
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_parse as S
import char_pose as CP
from s1_gltf import (GltfBuilder, find_texture, unwrap, extract_kv, compose)

BONE_OF_CHILD = {1: 5, 2: 5, 3: 5, 4: 9, 5: 14}  # 官方 Bw(): face/head->bone5, handL->9, handR->14
SAMPLE_HZ = 60.0


def m34_rows_to_m4(flat):
    m = np.eye(4)
    m[:3, :] = np.array(flat, dtype=np.float64).reshape(3, 4)
    return m


def mat4_to_gltf(m):
    """行主 4x4 -> glTF 列主数组"""
    return m.T.flatten().tolist()


def node_matrix(n):
    tr = n.get('transform')
    if tr is None:
        return np.eye(4)
    basis = tr['basis']
    pos = tr.get('translation', (0, 0, 0))
    scale = tr.get('scale', (1, 1, 1))
    return compose(basis, pos, scale)


def channel_curve(prs, which):
    c = CP.unwrap(prs.get(which)) if prs.get(which) is not None else None
    if not isinstance(c, dict) or not c.get('records'):
        return None
    return c


def sample_curve(curve, t_ms):
    size = len(curve['records'][0])
    fn = CP.decode_vec3 if size == 16 else CP.decode_rot
    return CP.sample_channel(curve, t_ms) if False else _sample(curve, fn, t_ms)


def _sample(curve, fn, t_ms):
    keys = sorted((fn(r) for r in curve['records']), key=lambda k: k[0])
    if t_ms <= keys[0][0]:
        return keys[0][1]
    if t_ms >= keys[-1][0]:
        return keys[-1][1]
    for a, b in zip(keys, keys[1:]):
        if a[0] <= t_ms <= b[0]:
            f = (t_ms - a[0]) / (b[0] - a[0])
            return a[1] * (1 - f) + b[1] * f
    return keys[-1][1]


def tr(a, b, m):
    # 官方 Tr: a*(255-m)/255 + b*m/255
    return min(255, (a * (255 - m)) // 255 + (b * m) // 255)


def compose_body_texture(body_path, high_path, primary_rgb, high_rgb, out_path):
    """官方 Fw/Dw body 贴图合成(UNDERSTOOD §20.6):
    body 的 alpha 通道是涂装遮罩(非透明度);high 的 (255,0,255) 像素跳过;
    body 亮区(RGB>0x7f)取 highColor, 否则取原色; 与 primaryColor 混合后
    再与 high 的 RGB 按 high alpha 混合; 输出不透明。"""
    from PIL import Image
    body = Image.open(body_path).convert('RGBA')
    bp = body.load()
    hp = Image.open(high_path).convert('RGBA').load() if high_path else None
    w, h = body.size
    out = Image.new('RGBA', (w, h))
    op = out.load()
    for y in range(h):
        for x in range(w):
            br, bg, bb, ba = bp[x, y]
            if hp is not None:
                hr, hg, hb, ha = hp[x, y]
                if (hr, hg, hb) == (255, 0, 255):
                    op[x, y] = (br, bg, bb, 255)
                    continue
            else:
                hr = hg = hb = ha = 0
            bright = br > 0x7f or bg > 0x7f or bb > 0x7f
            r0 = tr(primary_rgb[0], high_rgb[0] if bright else br, ba)
            g0 = tr(primary_rgb[1], high_rgb[1] if bright else bg, ba)
            b0 = tr(primary_rgb[2], high_rgb[2] if bright else bb, ba)
            op[x, y] = (tr(r0, hr, ha), tr(g0, hg, ha), tr(b0, hb, ha), 255)
    out.save(out_path)


def convert(src_path, out_dir, base, anim_dir='unpacked/character_common'):
    root, _ = S.parse_auto(open(src_path, 'rb').read())
    v = unwrap(root)

    # 找 body 蒙皮几何 + 收集刚性件
    body_geo = None
    rigid = []  # (m_walked, top_idx, geo, name)

    def walk(n, m, top_idx):
        n = unwrap(n)
        m = m @ node_matrix(n)
        if n.get('geometry'):
            geo = unwrap(n['geometry'])
            if 'vertices' in geo:
                body_geo = geo  # noqa
                rigid.append((m, geo, 'skin', top_idx, n.get('name')))
            else:
                rigid.append((m, geo, 'rigid', top_idx, n.get('name')))
        for i, c in enumerate(n.get('children') or []):
            walk(c, m, i if top_idx == 0 else top_idx)

    walk(v, np.eye(4), 0)
    sk = [r for r in rigid if r[2] == 'skin']
    assert sk, '未找到蒙皮几何'
    body_geo = sk[0][1]
    bones = body_geo['bones']

    B = GltfBuilder()
    B.gltf_textures = []
    B.gltf_materials = []
    B.gltf_meshes = []
    B.gltf_nodes = []
    B.gltf_scenes_nodes = []

    # ---- 骨架节点 ----
    # 官方蒙皮语义: skin = world(pose) @ inverseBind, 顶点存于绑定空间。
    # glTF 静止时 jointMatrix 必须为 I => world_rest = inv(inverseBind),
    # 局部矩阵按链反推(localBind 与 inverseBind 不自洽, 弃用)。
    def ib_m4(b):
        m = np.eye(4)
        m[:3, :] = np.array(b['inverseBind'], dtype=np.float64).reshape(3, 4)
        return m

    world_rest = {i: np.linalg.inv(ib_m4(b)) for i, b in enumerate(bones)}
    bind_world = world_rest  # 刚性件挂接用同一参考系
    joint_nodes = []

    for i, b in enumerate(bones):
        p = b['parentIndex']
        local = world_rest[i] if (i == 0 or p >= 255 or p == i) \
            else np.linalg.inv(world_rest[p]) @ world_rest[i]
        node = {'name': f'bone{i}', 'matrix': mat4_to_gltf(local)}
        B.gltf_nodes.append(node)
        joint_nodes.append(len(B.gltf_nodes) - 1)
    for i, b in enumerate(bones):
        p = b['parentIndex']
        if 0 < i and p < 255 and p != i:
            B.gltf_nodes[p]['children'] = B.gltf_nodes[p].get('children', []) + [joint_nodes[i]]

    # ---- body 蒙皮网格 ----
    verts, wedges, tris = body_geo['vertices'], body_geo['wedges'], body_geo['triangles']
    P, N, UV, J, W = [], [], [], [], []
    I = []
    for tri in tris:
        start = len(P)
        for k in range(3):
            w = wedges[tri['wedge'][k]] if tri['wedge'][k] < len(wedges) else None
            vt = verts[tri['position'][k]]
            P.append(vt['position'])
            N.append(vt.get('normal') or (0, 1, 0))
            UV.append((w['u'], w['v']) if w else (0, 0))
            b0 = vt['bone0']
            b1 = vt['bone1'] if vt['bone1'] < 255 else b0
            # glTF 规范: JOINTS_0/WEIGHTS_0 必须为 VEC4
            J.append((b0, b1, 0, 0))
            W.append((vt['weight0'], 1.0 - vt['weight0'], 0.0, 0.0))
        I.extend((start, start + 1, start + 2))

    mat_body = B.get_material('0_body', out_dir, base, cull=1)
    # 官方 Fw/Dw 合成 body 贴图(dye6: base=19,121,219 / high=0,252,255),
    # 输出不透明合成图替换材质贴图(0.png 的 alpha 是涂装遮罩, 直接用会半透明)
    tex_dir = os.path.join(out_dir, base + '_textures')
    os.makedirs(tex_dir, exist_ok=True)
    comp_path = os.path.join(tex_dir, '0_body.png')
    compose_body_texture(find_texture('0'), find_texture('1'),
                         (19, 121, 219), (0, 252, 255), comp_path)
    B.images.append({'uri': base + '_textures/0_body.png'})
    B.gltf_textures.append({'source': len(B.images) - 1})
    B.materials[mat_body]['pbrMetallicRoughness']['baseColorTexture'] = {
        'index': len(B.gltf_textures) - 1}
    B.materials[mat_body]['pbrMetallicRoughness'].pop('baseColorFactor', None)
    Pdata = np.array(P, dtype='<f4')
    Ndata = np.array(N, dtype='<f4')
    UVdata = np.array(UV, dtype='<f4')
    Jdata = np.array(J, dtype='<u2')
    Wdata = np.array(W, dtype='<f4')
    Idata = np.array(I, dtype='<u4')
    pmn = Pdata.min(axis=0).tolist()
    pmx = Pdata.max(axis=0).tolist()
    bv_p = B.add_bv(Pdata.tobytes(), 34962)
    bv_n = B.add_bv(Ndata.tobytes(), 34962)
    bv_u = B.add_bv(UVdata.tobytes(), 34962)
    bv_j = B.add_bv(Jdata.tobytes(), 34962)
    bv_w = B.add_bv(Wdata.tobytes(), 34962)
    bv_i = B.add_bv(Idata.tobytes(), 34963)
    a_p = B.add_accessor(bv_p, 5126, len(P), pmn, pmx)
    a_n = B.add_accessor(bv_n, 5126, len(N), None, None)
    B.accessors.append({'bufferView': bv_u, 'componentType': 5126, 'count': len(UV), 'type': 'VEC2'})
    a_u = len(B.accessors) - 1
    B.accessors.append({'bufferView': bv_j, 'componentType': 5123, 'count': len(J), 'type': 'VEC4'})
    a_j = len(B.accessors) - 1
    B.accessors.append({'bufferView': bv_w, 'componentType': 5126, 'count': len(W), 'type': 'VEC4'})
    a_w = len(B.accessors) - 1
    B.accessors.append({'bufferView': bv_i, 'componentType': 5125, 'count': len(I), 'type': 'SCALAR'})
    a_i = len(B.accessors) - 1

    # inverseBind (行主 3x4) -> 列主 4x4
    ibm = np.array([m34_rows_to_m4(b['inverseBind']).T.flatten() for b in bones], dtype='<f4')
    bv_ib = B.add_bv(ibm.tobytes(), None)
    B.accessors.append({'bufferView': bv_ib, 'componentType': 5126, 'count': len(bones), 'type': 'MAT4'})
    a_ib = len(B.accessors) - 1

    B.gltf_meshes.append({'primitives': [{
        'attributes': {'POSITION': a_p, 'NORMAL': a_n, 'TEXCOORD_0': a_u,
                       'JOINTS_0': a_j, 'WEIGHTS_0': a_w},
        'indices': a_i, 'material': mat_body, 'mode': 4}], 'name': 'body'})
    body_node = {'mesh': 0, 'skin': 0, 'name': 'body'}
    B.gltf_nodes.append(body_node)

    skeleton_root = {'name': 'char_root', 'children': [joint_nodes[0], len(B.gltf_nodes) - 1]}
    B.gltf_nodes.append(skeleton_root)
    # 官方 Bw: convertClientCoordinates = (context === 'card'), 即仅立绘加 RotX(-90°);
    # 赛车内不加是因为挂在赛车已旋转(rot.x=-PI/2)的子树里, 由父级完成转换。
    # 人物模型数据本身是 Z-up, 独立渲染必须自带 RotX(-90°)。
    zup_root = {'rotation': [-0.7071067811865476, 0.0, 0.0, 0.7071067811865476],
                'children': [len(B.gltf_nodes) - 1], 'name': 'zup_root'}
    B.gltf_nodes.append(zup_root)
    scene_nodes = [len(B.gltf_nodes) - 1]

    # ---- 刚性件挂骨骼 ----
    for m, geo, kind, top_idx, name in rigid:
        if kind == 'skin':
            continue
        key = 'f00' if top_idx == 1 else '0'
        mat_idx = B.get_material(key, out_dir, base, cull=1)
        pp, nn, uuvv, ii = extract_kv(geo)[:4]
        Pd = np.array(pp, dtype='<f4')
        Nd = np.array(nn, dtype='<f4')
        Ud = np.array(uuvv, dtype='<f4')
        Id = np.array(ii, dtype='<u4')
        pmn2 = Pd.min(axis=0).tolist() if len(Pd) else [0, 0, 0]
        pmx2 = Pd.max(axis=0).tolist() if len(Pd) else [0, 0, 0]
        b1 = B.add_bv(Pd.tobytes(), 34962)
        b2 = B.add_bv(Nd.tobytes(), 34962)
        b3 = B.add_bv(Ud.tobytes(), 34962)
        b4 = B.add_bv(Id.tobytes(), 34963)
        aa1 = B.add_accessor(b1, 5126, len(pp), pmn2, pmx2)
        aa2 = B.add_accessor(b2, 5126, len(nn), None, None)
        B.accessors.append({'bufferView': b3, 'componentType': 5126, 'count': len(uuvv), 'type': 'VEC2'})
        aa3 = len(B.accessors) - 1
        B.accessors.append({'bufferView': b4, 'componentType': 5125, 'count': len(ii), 'type': 'SCALAR'})
        aa4 = len(B.accessors) - 1
        B.gltf_meshes.append({'primitives': [{'attributes': {'POSITION': aa1, 'NORMAL': aa2,
                                                              'TEXCOORD_0': aa3},
                                              'indices': aa4, 'material': mat_idx, 'mode': 4}],
                              'name': name or key})
        bone = BONE_OF_CHILD.get(top_idx)
        # 官方 _0x54c179: object.matrix = YT.update()返回的 world[bone] × local。
        # YT.update 返回的是 world 数组(非 skin) => glTF 子节点局部矩阵 = 纯 m_walked
        node = {'mesh': len(B.gltf_meshes) - 1, 'name': name or key,
                'matrix': mat4_to_gltf(m)}
        B.gltf_nodes.append(node)
        parent = joint_nodes[bone] if bone is not None else scene_nodes[0]
        B.gltf_nodes[parent]['children'] = B.gltf_nodes[parent].get('children', []) + \
            [len(B.gltf_nodes) - 1]

    # ---- 动画剪辑 ----
    animations = []
    if anim_dir and os.path.isdir(anim_dir):
        for fn in sorted(os.listdir(anim_dir)):
            if not fn.endswith('.1s') or not fn.startswith('f'):
                continue
            try:
                seq = CP.load_sequence(os.path.join(anim_dir, fn))
            except Exception as e:
                print('  跳过', fn, e)
                continue
            span = seq['header'][2] if len(seq['header']) > 2 else 0
            if isinstance(seq, dict) and seq.get('className') == 'CharSequence' and span:
                pass
            else:
                continue
            n_samples = max(int(span * SAMPLE_HZ / 1000.0), 2)
            times = [span * k / (n_samples - 1) / 1000.0 for k in range(n_samples)]
            channels = []
            for i, ch in enumerate(seq['channels']):
                prs = CP.unwrap(ch)
                if not isinstance(prs, dict):
                    continue
                pos = channel_curve(prs, 'position')
                rot = channel_curve(prs, 'rotation')
                for curve, path, comp in ((pos, 'translation', 'VEC3'), (rot, 'rotation', 'VEC4')):
                    if curve is None:
                        continue
                    size = len(curve['records'][0])
                    vals = []
                    for t in times:
                        val = _sample(curve, CP.decode_vec3 if size == 16 else CP.decode_rot,
                                      t * 1000.0)
                        vals.extend(val.tolist())
                    vd = np.array(vals, dtype='<f4')
                    tdat = np.array(times, dtype='<f4')
                    bt = B.add_bv(tdat.tobytes(), None)
                    B.accessors.append({'bufferView': bt, 'componentType': 5126,
                                        'count': len(times), 'type': 'SCALAR'})
                    a_t = len(B.accessors) - 1
                    bvv = B.add_bv(vd.tobytes(), None)
                    B.accessors.append({'bufferView': bvv, 'componentType': 5126,
                                        'count': len(times), 'type': comp})
                    a_v = len(B.accessors) - 1
                    channels.append({'sampler': len(channels), 'target': {'node': joint_nodes[i],
                                                                          'path': path},
                                     '__s': {'input': a_t, 'output': a_v,
                                             'interpolation': 'LINEAR'}})
            if not channels:
                continue
            anim = {'name': fn[:-3], 'channels': [],
                    'samplers': [c.pop('__s') for c in channels]}
            anim['channels'] = channels
            animations.append(anim)
            print('  动画', fn[:-3], f'{span}ms', len(channels), '通道')

    gltf = {
        'asset': {'version': '2.0', 'generator': 'kartemu char_gltf'},
        'extensionsUsed': ['KHR_materials_unlit'],
        'scene': 0,
        'scenes': [{'nodes': scene_nodes}],
        'nodes': B.gltf_nodes,
        'meshes': B.gltf_meshes,
        'skins': [{'joints': joint_nodes, 'inverseBindMatrices': a_ib,
                   'skeleton': joint_nodes[0]}],
        'materials': B.materials,
        'textures': B.gltf_textures,
        'images': B.images,
        'accessors': B.accessors,
        'bufferViews': B.bufferViews,
        'animations': animations,
        'buffers': [{'uri': base + '.bin', 'byteLength': len(B.bin)}],
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, base + '.gltf'), 'w', encoding='utf-8') as f:
        json.dump(gltf, f, ensure_ascii=False)
    with open(os.path.join(out_dir, base + '.bin'), 'wb') as f:
        f.write(B.bin)
    print(f'{base}: 骨骼 {len(bones)}, 蒙皮顶点(corner) {len(P)}, 刚性件 '
          f'{sum(1 for r in rigid if r[2] == "rigid")}, 动画 {len(animations)}, '
          f'bin {len(B.bin) / 1048576:.1f}MB')


if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
