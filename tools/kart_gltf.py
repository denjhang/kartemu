"""赛车 model.1s -> 层级化 glTF 2.0(官方 sl/ca 装配语义, §22)

与 s1_gltf.py --model 的"烘焙成一个网格"不同, 这里保留节点层级:
  - 每个节点一个 glTF node, 局部矩阵 = 官方 ca() 语义(basis 行 × scale 列 + 平移)
  - ReToonRigid/ReTriList 几何挂在各自节点上
  - 根 ReKart(Z-up) 包 zup_root RotX(-90°), 赛车内使用时由父级完成则去掉
  - 贴图: 赛车无 Fw/Dw 合成(那是人物专用), 直接用 0.png;
    alpha 通道是涂装遮罩非透明度, 输出强制不透明
  - 命名保留官方语义: seat/handle/wheel0..3/port0/child6(人物挂点),
    轮子自转轴 = 数据空间 X(hd), 前轮转向 = 数据空间 Z(i1), 见 web/kart.html

用法: python tools/kart_gltf.py unpacked/DataPack2_00007/kart_/cotton1/model.1s web/kart kart
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_parse as S
from s1_gltf import (GltfBuilder, unwrap, extract_kv, extract_qv, compose)
from char_gltf import compose_body_texture


def mat4_to_gltf(m):
    return m.T.flatten().tolist()


def node_matrix(n):
    tr = n.get('transform')
    if tr is None:
        return np.eye(4)
    return compose(tr['basis'], tr.get('translation', (0, 0, 0)),
                   tr.get('scale', (1, 1, 1)))


# itemTable.kml: <kart id='11' name='cotton1' orgColorId='4'> → color id=4 녹색
COTTON1_PRIMARY = (58, 174, 25)
COTTON1_HIGH = (210, 255, 0)
PLATE_PATH = 'unpacked/stuff2_plate/texture/2009@zz.png'


def overlay_plate(comp_path, plate_path):
    """官方 RC/$C: 合成图上蓝色标记像素 (0,0,255,255) = 号牌槽, 整块替换为 45x20 号牌"""
    from PIL import Image
    import numpy as np
    im = Image.open(comp_path).convert('RGBA')
    a = np.array(im)
    blue = np.all(np.stack([a[..., 0] == 0, a[..., 1] == 0, a[..., 2] == 255,
                            a[..., 3] == 255]), axis=0)
    if not blue.any() or not plate_path:
        return False
    ys, xs = np.where(blue)
    plate = Image.open(plate_path).convert('RGBA').resize((45, 20))
    pa = np.array(plate)
    a[ys.min():ys.min() + 20, xs.min():xs.min() + 45] = pa
    Image.fromarray(a).save(comp_path)
    return True


def convert(src_path, out_dir, base):
    root, _ = S.parse_auto(open(src_path, 'rb').read())
    v = unwrap(root)
    assert v.get('className') == 'ReKart', '根节点不是 ReKart'

    B = GltfBuilder()
    B.gltf_textures = []
    B.gltf_materials = []
    B.gltf_meshes = []
    B.gltf_nodes = []

    tex_dir = os.path.join(out_dir, base + '_textures')
    os.makedirs(tex_dir, exist_ok=True)
    src_tex = None
    for cand in ('cotton1/0.png', '0.png'):
        p = os.path.join(os.path.dirname(src_path), cand)
        if os.path.exists(p):
            src_tex = p
            break
    if src_tex:
        # 官方 tu(): 无 2.png 时走 Dw(0.png=底图, t1=涂装模板, primary, high);
        # 0.png 是全白底+alpha 涂装遮罩, 不合成则纯白
        t1 = os.path.join(os.path.dirname(src_path), '1.png')
        compose_body_texture(src_tex, t1 if os.path.exists(t1) else None,
                             COTTON1_PRIMARY, COTTON1_HIGH,
                             os.path.join(tex_dir, '0.png'))
        if os.path.exists(PLATE_PATH):
            overlay_plate(os.path.join(tex_dir, '0.png'), PLATE_PATH)
        B.images.append({'uri': base + '_textures/0.png'})
        B.gltf_textures.append({'source': 0})
        mat = {'name': 'kart', 'doubleSided': True,
               'pbrMetallicRoughness': {
                   'baseColorTexture': {'index': 0},
                   'metallicFactor': 0.0, 'roughnessFactor': 1.0},
               'extensions': {'KHR_materials_unlit': {}}}
        B.materials.append(mat)

    def add_mesh(geo_kind, payload, name):
        if geo_kind == 'rigid':
            P, N, UV, I = extract_kv(payload)[:4]
        else:
            P, N, UV, I = extract_qv(payload)
        Pd = np.array(P, dtype='<f4')
        Nd = np.array(N, dtype='<f4')
        Ud = np.array(UV, dtype='<f4')
        Id = np.array(I, dtype='<u4')
        if not len(Pd):
            return None
        pmn = Pd.min(axis=0).tolist()
        pmx = Pd.max(axis=0).tolist()
        bv_p = B.add_bv(Pd.tobytes(), 34962)
        bv_n = B.add_bv(Nd.tobytes(), 34962)
        bv_u = B.add_bv(Ud.tobytes(), 34962)
        bv_i = B.add_bv(Id.tobytes(), 34963)
        a_p = B.add_accessor(bv_p, 5126, len(P), pmn, pmx)
        a_n = B.add_accessor(bv_n, 5126, len(N), None, None)
        B.accessors.append({'bufferView': bv_u, 'componentType': 5126,
                            'count': len(UV), 'type': 'VEC2'})
        a_u = len(B.accessors) - 1
        B.accessors.append({'bufferView': bv_i, 'componentType': 5125,
                            'count': len(I), 'type': 'SCALAR'})
        a_i = len(B.accessors) - 1
        B.gltf_meshes.append({'primitives': [
            {'attributes': {'POSITION': a_p, 'NORMAL': a_n, 'TEXCOORD_0': a_u},
             'indices': a_i, 'material': 0, 'mode': 4}], 'name': name})
        return len(B.gltf_meshes) - 1

    def walk(n):
        n = unwrap(n)
        node = {'name': n.get('name') or n.get('className'),
                'matrix': mat4_to_gltf(node_matrix(n))}
        if n.get('geometry'):
            payload = unwrap(n['geometry'])
            mi = add_mesh('rigid', payload, n.get('name') or 'mesh')
            if mi is not None:
                node['mesh'] = mi
        elif n.get('vertexData'):
            mi = add_mesh('trilist', unwrap(n['vertexData']), n.get('name') or 'mesh')
            if mi is not None:
                node['mesh'] = mi
        B.gltf_nodes.append(node)
        idx = len(B.gltf_nodes) - 1
        for c in n.get('children') or []:
            ci = walk(c)
            if ci is not None:
                node['children'] = node.get('children', []) + [ci]
        return idx

    kart_root = walk(v)
    # 官方 O$ 挂点: child[6](无几何 Relement) = 人物挂点; 保留在层级里
    zup = {'rotation': [-0.7071067811865476, 0.0, 0.0, 0.7071067811865476],
           'children': [kart_root], 'name': 'zup_root'}
    B.gltf_nodes.append(zup)
    scene_nodes = [len(B.gltf_nodes) - 1]

    gltf = {
        'asset': {'version': '2.0', 'generator': 'kartemu kart_gltf'},
        'extensionsUsed': ['KHR_materials_unlit'],
        'scene': 0,
        'scenes': [{'nodes': scene_nodes}],
        'nodes': B.gltf_nodes,
        'meshes': B.gltf_meshes,
        'materials': B.materials,
        'textures': B.gltf_textures,
        'images': B.images,
        'accessors': B.accessors,
        'bufferViews': B.bufferViews,
        'buffers': [{'uri': base + '.bin', 'byteLength': len(B.bin)}],
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, base + '.gltf'), 'w', encoding='utf-8') as f:
        json.dump(gltf, f, ensure_ascii=False)
    with open(os.path.join(out_dir, base + '.bin'), 'wb') as f:
        f.write(B.bin)
    n_mesh = len(B.gltf_meshes)
    print(f'{base}: 节点 {len(B.gltf_nodes)}, 网格 {n_mesh}, bin {len(B.bin)/1024:.0f}KB')


if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
