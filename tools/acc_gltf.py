"""挂件/配件 .1s -> glTF(气球/头戴摄像机/风镜等, §23)

配件模型结构(实测): rootRelement → Scene Root → 具名槽位节点(如 'headPhone') →
ReToonRigid(贴图名在 TexProperty)。官方挂接语义:
  - 配件以槽位节点名匹配目标树节点(如角色的 headPhone/goggle0、赛车的 balloon)。
  - 数据空间 Z-up: 导出包 zup_root RotX(-90°); 挂入已旋转父树时用其内层根。

用法: python tools/acc_gltf.py <src.1s> <out_dir> <base>
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_parse as S
import char_pose as CP
from s1_gltf import (GltfBuilder, unwrap, extract_kv, extract_qv, compose)


def mat4_to_gltf(m):
    return m.T.flatten().tolist()


def node_matrix(n):
    tr = n.get('transform')
    if tr is None:
        return np.eye(4)
    return compose(tr['basis'], tr.get('translation', (0, 0, 0)),
                   tr.get('scale', (1, 1, 1)))


def find_tex(dirs, name):
    if not name:
        return None
    stem = name.split('@')[0].split('.')[0]
    for d in dirs:
        for cand in (name, stem + '.png', stem + '@zz.png', stem + '@cn.png'):
            p = os.path.join(d, cand)
            if os.path.exists(p):
                return p
    return None


def convert(src_path, out_dir, base):
    root, _ = S.parse_auto(open(src_path, 'rb').read())
    v = unwrap(root)
    model_dir = os.path.dirname(src_path)

    B = GltfBuilder()
    B.gltf_textures = []
    B.gltf_materials = []
    B.gltf_meshes = []
    B.gltf_nodes = []
    tex_dir = os.path.join(out_dir, base + '_textures')
    os.makedirs(tex_dir, exist_ok=True)

    def get_material(tex_name):
        key = tex_name or '__default__'
        if key in B.material_idx:
            return B.material_idx[key]
        path = find_tex([model_dir], tex_name)
        if path:
            import shutil
            shutil.copy(path, os.path.join(tex_dir, os.path.basename(path)))
            B.images.append({'uri': base + '_textures/' + os.path.basename(path)})
            B.gltf_textures.append({'source': len(B.images) - 1})
            tex_idx = {'index': len(B.gltf_textures) - 1}
        else:
            tex_idx = None
        pbr = {'metallicFactor': 0.0, 'roughnessFactor': 1.0}
        if tex_idx is not None:
            pbr['baseColorTexture'] = tex_idx
            pbr['baseColorFactor'] = [1, 1, 1, 1]
        else:
            pbr['baseColorFactor'] = [0.7, 0.7, 0.7, 1.0]
        mat = {'name': key, 'doubleSided': True,
               'pbrMetallicRoughness': pbr,
               'extensions': {'KHR_materials_unlit': {}}}
        B.materials.append(mat)
        B.material_idx[key] = len(B.materials) - 1
        return len(B.materials) - 1

    def add_mesh(payload, is_rigid, name, mat_idx):
        if is_rigid:
            P, N, UV, I = extract_kv(payload)[:4]
        else:
            P, N, UV, I = extract_qv(payload)
        Pd = np.array(P, dtype='<f4')
        if not len(Pd):
            return None
        Nd = np.array(N, dtype='<f4')
        Ud = np.array(UV, dtype='<f4')
        Id = np.array(I, dtype='<u4')
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
             'indices': a_i, 'material': mat_idx, 'mode': 4}], 'name': name})
        return len(B.gltf_meshes) - 1

    def walk(n):
        n = unwrap(n)
        node = {'name': n.get('name') or n.get('className'),
                'matrix': mat4_to_gltf(node_matrix(n))}
        tex_name = None
        for s in (n.get('slots') or []):
            u = unwrap(s) if s else None
            if isinstance(u, dict) and u.get('kind') == 'texture' and u.get('name'):
                tex_name = u['name']
        if n.get('geometry') or n.get('vertexData'):
            mat_idx = get_material(tex_name)
            payload = unwrap(n['geometry']) if n.get('geometry') else unwrap(n['vertexData'])
            mi = add_mesh(payload, n.get('geometry') is not None,
                          n.get('name') or 'mesh', mat_idx)
            if mi is not None:
                node['mesh'] = mi
        B.gltf_nodes.append(node)
        idx = len(B.gltf_nodes) - 1
        for c in n.get('children') or []:
            ci = walk(c)
            if ci is not None:
                node['children'] = node.get('children', []) + [ci]
        return idx

    inner = walk(v)
    zup = {'rotation': [-0.7071067811865476, 0.0, 0.0, 0.7071067811865476],
           'children': [inner], 'name': 'zup_root'}
    B.gltf_nodes.append(zup)

    # PrsTontroller -> glTF 动画(气球浮动等; 官方 anchor/phase 循环简化为直接循环)
    animations = []
    import struct as _st
    node_of_name = {n['name']: i for i, n in enumerate(B.gltf_nodes)}

    def collect_prs(n):
        n = unwrap(n)
        for s in (n.get('slots') or []):
            u = unwrap(s) if s else None
            if isinstance(u, dict) and u.get('className') == 'PrsTontroller':
                chans = []
                name = n.get('name') or n.get('className')
                tgt = node_of_name.get(name)
                if tgt is None:
                    continue
                for which, comp in (('position', 'VEC3'), ('rotation', 'VEC4')):
                    cur = u.get(which)
                    if cur is None:
                        continue
                    cur = unwrap(cur)
                    recs = cur.get('records') or []
                    if not recs:
                        continue
                    if len(recs[0]) == 16:
                        keys = sorted(CP.decode_vec3(r) for r in recs)
                    else:
                        keys = sorted(CP.decode_rot(r) for r in recs)
                    times = np.array([k[0] / 1000.0 for k in keys], dtype='<f4')
                    vals = np.array([k[1] for k in keys], dtype='<f4')
                    bt = B.add_bv(times.tobytes(), None)
                    B.accessors.append({'bufferView': bt, 'componentType': 5126,
                                        'count': len(times), 'type': 'SCALAR'})
                    a_t = len(B.accessors) - 1
                    bv2 = B.add_bv(vals.tobytes(), None)
                    B.accessors.append({'bufferView': bv2, 'componentType': 5126,
                                        'count': len(times), 'type': comp})
                    a_v = len(B.accessors) - 1
                    chans.append({'sampler': len(chans),
                                  'target': {'node': tgt, 'path': which},
                                  '__s': {'input': a_t, 'output': a_v,
                                          'interpolation': 'LINEAR'}})
                if chans:
                    anim = {'name': 'prs', 'channels': [],
                            'samplers': [c.pop('__s') for c in chans]}
                    anim['channels'] = chans
                    animations.append(anim)
        for c in n.get('children') or []:
            collect_prs(c)

    collect_prs(v)

    gltf = {
        'asset': {'version': '2.0', 'generator': 'kartemu acc_gltf'},
        'extensionsUsed': ['KHR_materials_unlit'],
        'scene': 0,
        'scenes': [{'nodes': [len(B.gltf_nodes) - 1]}],
        'nodes': B.gltf_nodes,
        'meshes': B.gltf_meshes,
        'materials': B.materials,
        'textures': B.gltf_textures,
        'images': B.images,
        'accessors': B.accessors,
        'bufferViews': B.bufferViews,
        'buffers': [{'uri': base + '.bin', 'byteLength': len(B.bin)}],
        'animations': animations,
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, base + '.gltf'), 'w', encoding='utf-8') as f:
        json.dump(gltf, f, ensure_ascii=False)
    with open(os.path.join(out_dir, base + '.bin'), 'wb') as f:
        f.write(B.bin)
    print(f'{base}: 节点 {len(B.gltf_nodes)}, 网格 {len(B.gltf_meshes)}, '
          f'bin {len(B.bin)/1024:.0f}KB')


if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
