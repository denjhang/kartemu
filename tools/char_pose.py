"""CharSequence 姿态求值(逆向 §18, 已由 pose_eval.py 数值验证)"""
import numpy as np
import s1_parse as S


def unwrap(o):
    return o['value'] if isinstance(o, dict) and 'value' in o else o


def decode_vec3(rec):
    t = int.from_bytes(rec[0:4], 'little')
    return t, np.frombuffer(rec[4:16], dtype='<f4')


def decode_rot(rec):
    # 官方 R1(): 文件序 (w,x,y,z)
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
    fn = decode_vec3 if size == 16 else decode_rot
    keys = sorted((fn(r) for r in curve['records']), key=lambda k: k[0])
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    for a, b in zip(keys, keys[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]) / (b[0] - a[0])
            return a[1] * (1 - f) + b[1] * f
    return keys[-1][1]


def eval_pose(seq, t_ms):
    """CharSequence -> 24 个骨骼局部矩阵(官方 Sr)"""
    out = []
    for ch in seq['channels']:
        prs = unwrap(ch)
        pos = unwrap(prs['position'])
        rot = unwrap(prs['rotation'])
        tv = sample_channel(pos, t_ms) if pos.get('records') else np.zeros(3)
        rq = sample_channel(rot, t_ms) if rot.get('records') else np.array([0, 0, 0, 1.0])
        out.append(quat_matrix(rq, tv))
    return out


def load_sequence(path):
    root, _ = S.parse_auto(open(path, 'rb').read())
    return unwrap(root)


def skin_matrices(bones, pose):
    """官方 mm 链 + inverseBind -> 蒙皮矩阵"""
    world = {}
    skin = {}
    for i, b in enumerate(bones):
        world[i] = pose[0] if i == 0 else world[b['parentIndex']] @ pose[i]
        ib = np.eye(4)
        ib[:3, :] = np.array(b['inverseBind']).reshape(3, 4)
        skin[i] = world[i] @ ib
    return world, skin
