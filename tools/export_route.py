"""导出赛道路线数据(真实地图数据, 供 web/kart.html 使用)

流程:
  1. parse_auto 解析 unpacked/track_village_R01/track.1s (TrackContainer)
  2. 从 TrackObject 'track' 的 property 取 <course> XML (road 段顺序)
  3. 每段 road: 在对应 ToRoad 的 records 里按名定位 start/end record(环形走), 逐帧拼接
  4. 每帧 D(Z-up) -> P(Y-up): [x,y,z] -> [x, z, -y]
  5. 按指定间距线性重采样(position/forward 均插值, forward 归一)
输出: web/track/route.json = {lapLength, spacing, frames: [{p:[x,y,z], f:[x,y,z]}...]}
"""
import json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_parse as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPACING = 10.0


def sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return [a[i] / l for i in range(3)]


def d2p(v):
    """D(Z-up) -> P(Y-up): [x,y,z] -> [x, z, -y]"""
    return [v[0], v[2], -v[1]]


def main():
    track_path = os.path.join(ROOT, 'unpacked', 'track_village_R01', 'track.1s')
    data = open(track_path, 'rb').read()
    root, _g = S.parse_auto(data)

    tos, course = {}, None

    def walk(o):
        nonlocal course
        if isinstance(o, dict):
            if o.get('kind') == 'ToRoad':
                tos[o.get('name')] = o
            if o.get('kind') == 'TrackObject' and o.get('name') == 'track':
                for ch in ((o.get('property') or {}).get('value', {}) or {}).get('children', []):
                    if ch.get('name') == 'course':
                        course = ch
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(root)
    assert course, 'course XML 未找到'

    roads = []
    for node in course.get('children', []):
        if node.get('name') != 'road':
            continue
        roads.append({a['name']: a['value'] for a in node.get('attributes', [])})

    # 拼接: 每段 road 按 record 名环形定位 start..end(含端点), 段内逐帧
    chain = []   # [(record_name, frame_idx)] 去重用
    frames_d = []  # D 空间帧 [{position, forward}]
    for r in roads:
        recs = tos[r['name']]['records']
        n = len(recs)
        si = next(i for i, rec in enumerate(recs) if rec['name'] == r['start'])
        ei = next(i for i, rec in enumerate(recs) if rec['name'] == r['end'])
        i = si
        while True:
            rec = recs[i]
            key = (r['name'], i)
            if key not in chain:
                chain.append(key)
            for fr in rec['frames']:
                frames_d.append({'p': fr['position'], 'f': fr['forward']})
            if i == ei:
                break
            i = (i + 1) % n
        print(f"road {r['name']} {r['start']}..{r['end']}: 累计 {len(frames_d)} 帧")

    # 转 P 空间
    pts = [d2p(f['p']) for f in frames_d]
    fwds = [norm(d2p(f['f'])) for f in frames_d]
    raw_len = sum(math.dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))
    print(f"原始帧 {len(pts)}, 环长 {raw_len:.1f}")

    # 重采样(环形): 沿折线每 SPACING 取一点, forward 用两端帧插值归一
    out_p, out_f = [], []
    seg_lens = [math.dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    total = sum(seg_lens)
    step = 0.0
    i = 0
    guard = 0
    while step < total and guard < 1_000_000:
        guard += 1
        # 走到 step 所在段
        acc = 0.0
        j = 0
        while acc + seg_lens[j] < step:
            acc += seg_lens[j]
            j = (j + 1) % len(pts)
            if j == 0 and acc > total:
                break
        t = (step - acc) / seg_lens[j]
        a, b = pts[j], pts[(j + 1) % len(pts)]
        fa, fb = fwds[j], fwds[(j + 1) % len(pts)]
        p = [a[k] + (b[k] - a[k]) * t for k in range(3)]
        f = norm([fa[k] + (fb[k] - fa[k]) * t for k in range(3)])
        out_p.append([round(v, 2) for v in p])
        out_f.append([round(v, 4) for v in f])
        step += SPACING

    lap = len(out_p) * SPACING
    print(f"重采样: {len(out_p)} 帧 @ {SPACING}u, 圈长 {lap:.0f}")

    out = os.path.join(ROOT, 'web', 'track', 'route.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({'lapLength': round(lap, 1), 'spacing': SPACING,
               'frames': [{'p': out_p[i], 'f': out_f[i]} for i in range(len(out_p))]},
              open(out, 'w', encoding='utf-8'), separators=(',', ':'))
    print('written:', out)


if __name__ == '__main__':
    main()
