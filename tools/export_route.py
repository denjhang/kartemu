"""导出赛道路线数据 (course XML + ToRoad 原始 D 空间记录)
供 web/runtime/track.js 的 buildRouteGraph 使用。
输出: web/track/route.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_parse as S


def sa_to_json(node):
    """递归把 parse_sa 产物转为纯 JSON (已是 dict, 但确保 list/tuple→list)"""
    if isinstance(node, dict):
        return {k: sa_to_json(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [sa_to_json(v) for v in node]
    return node


def main():
    track_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "unpacked", "track_village_R01", "track.1s"
    )
    if not os.path.exists(track_path):
        print(f"track.1s not found: {track_path}", file=sys.stderr)
        sys.exit(1)

    with open(track_path, "rb") as f:
        data = f.read()

    # 解析赛道
    g = S.GameReader()
    v = S.parse_trackcontainer(S.StreamReader(data), g)

    # 找 course XML
    course = None
    for obj in v.get("trackObjects", []):
        if obj.get("kind") == "TrackObject" and obj.get("name") == "track":
            prop = obj.get("property") or {}
            for ch in prop.get("children", []):
                if ch.get("name") == "course":
                    course = ch
                    break
            break

    if course is None:
        print("warning: TrackObject 'track' 缺少 <course> 子元素", file=sys.stderr)

    # 收集 ToRoad 原始 D 空间数据
    to_roads = []
    for obj in v.get("trackObjects", []):
        if obj.get("kind") == "ToRoad":
            to_roads.append({
                "kind": "ToRoad",
                "name": obj.get("name"),
                "cyclic": obj.get("cyclic"),
                "records": [{
                    "name": r["name"],
                    "positions": [list(p) for p in r["positions"]],
                    "gateIndices": [list(g_) for g_ in r["gates"]],
                    "surface": r.get("surface"),
                    "surfaceIndices": [list(s) for s in r.get("surfaceIndices", [])],
                    "frames": [{
                        "position": list(f["position"]),
                        "storedForward": list(f["forward"]),
                        "up": list(f["up"]),
                    } for f in r["frames"]],
                } for r in obj.get("records", [])],
            })

    route = {
        "source": track_path,
        "course": sa_to_json(course) if course else None,
        "toRoads": to_roads,
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "track", "route.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(route, f, ensure_ascii=False, separators=(",", ":"))

    print(f"route data exported: {out_path}")
    print(f"  toRoads: {len(to_roads)}")
    total_records = sum(len(r["records"]) for r in to_roads)
    print(f"  total records: {total_records}")
    print(f"  course: {'present' if course else 'missing'}")


if __name__ == "__main__":
    main()
