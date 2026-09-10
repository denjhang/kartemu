"""CharSequence 姿态求值验证器(逆向 §18 的可执行证明)
用法: python pose_eval.py unpacked/character_common/f45.1s [t_ms]
流程(官方 Sr/mm/fm 语义):
  1. 24 个 PRSTontroller 通道在 t 采样 → (quat, trans) → w0 → 4x4 局部矩阵
  2. world[0]=pose[0]; world[i]=world[parent[i]] × pose[i]
  3. skin[i] = world[i] × inverseBind[i]
  4. vertex' = w0*skin[bone0]*v + w1*skin[bone1]*v
预期: 输出顶点云应为 Y-up 直立坐姿(人物呈现空间), 而非绑定姿态的横躺。
"""
import sys
import numpy as np
import s1_parse as S


def unwrap(o):
    return o['value'] if isinstance(o, dict) and 'value' in o else o


def decode_vec3(rec):
    t = int.from_bytes(rec[0:4], 'little')
    v = np.frombuffer(rec[4:16], dtype='<f4')
    return t, v


def decode_rot(rec):
    # 官方 R1(): value = [f8, f12, f16, f4] → (x,y,z,w), 文件序 (w,x,y,z)
    t = int.from_bytes(rec[0:4], 'little')
    f = np.frombuffer(rec[4:20], dtype='<f4')
    w, x, y, z = f
    return t, np.array([x, y, z, w])


def quat_matrix(q, t):
    x, y, z, w = q
    m = np.eye(4)
    m[0, 0] = 1 - 2 * (y * y + z * z); m[0, 1] = 2 * (x * y - w * z); m[0, 2] = 2 * (x * z + w * y)
    m[1, 0] = 2 * (x * y + w * z); m[1, 1] = 1 - 2 * (x * x + z * z); m[1, 2] = 2 * (y * z - w * x)
    m[2, 0] = 2 * (x * z - w * y); m[2, 1] = 2 * (y * z + w * x); m[2, 2] = 1 - 2 * (x * x + y * y)
    m[:3, 3] = t
    return m


def sample_channel(curve, t):
    size = len(curve['records'][0])
    if size == 16:   # vec3 keyType1
        keys = [decode_vec3(r) for r in curve['records']]
    else:            # rotation keyType1 (20B)
        keys = [decode_rot(r) for r in curve['records']]
    keys.sort(key=lambda k: k[0])
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    for a, b in zip(keys, keys[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]) / (b[0] - a[0])
            return a[1] * (1 - f) + b[1] * f
    return keys[-1][1]


def main(path):
    data = open(path, 'rb').read()
    root, _ = S.parse_auto(data)
    seq = unwrap(root)
    t_ms = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    pose = []
    for ch in seq['channels']:
        prs = unwrap(ch)
        pos = unwrap(prs['position'])
        rot = unwrap(prs['rotation'])
        tv = sample_channel(pos, t_ms) if pos.get('records') else np.zeros(3)
        rq = sample_channel(rot, t_ms) if rot.get('records') else np.array([0, 0, 0, 1.0])
        pose.append(quat_matrix(rq, tv))

    # 骨骼来自 dao model.1s
    mdata = open('unpacked/character_dao/model.1s', 'rb').read()
    mroot, _ = S.parse_auto(mdata)
    mr = unwrap(mroot)
    body = unwrap(mr['children'][0])
    geo = unwrap(body['geometry'])
    bones = geo['bones']

    world = {}
    skin = {}
    for i, b in enumerate(bones):
        if i == 0:
            world[i] = pose[0]
        else:
            p = b['parentIndex']
            world[i] = world[p] @ pose[i]
        ib = np.eye(4)
        ib[:3, :] = np.array(b['inverseBind']).reshape(3, 4)
        skin[i] = world[i] @ ib

    verts = geo['vertices']
    out = []
    for v in verts[:2000]:
        p0 = np.append(v['position'], 1.0)
        sk = skin[v['bone0']] * v['weight0']
        b1 = v['bone1']
        if b1 < 255:
            sk = sk + skin[b1] * (1 - v['weight0'])
        out.append(sk @ p0)
    out = np.array(out)
    print(f'姿态 t={t_ms}ms  顶点云范围(前2000):')
    for ax, name in enumerate('XYZ'):
        print(f'  {name}: {out[:, ax].min():+.3f} ~ {out[:, ax].max():+.3f}')
    print('判定: Y 跨度应为身高(直立), Z 为前后(坐姿腿前伸)')


if __name__ == '__main__':
    main(sys.argv[1])
