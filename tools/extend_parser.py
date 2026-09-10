# -*- coding: utf-8 -*-
"""向 s1_parse.py 追加赛道模式支持"""

addition = '''

# ==================== 赛道模式 (track.1s) ====================

TRACK_STAMPS = {
    0x28F90598: 'TrackContainer', 0x0E07033C: 'Relement', 0x14FC03F8: 'ReTriStrip',
    0x10D40382: 'ReTriList', 0x192A0446: 'ReToonRigid', 0x189F0442: 'ReBillboard',
    0x0CF20300: 'ReCamera', 0x1953044C: 'TrackObject', 0x07DE0249: 'ToRoad',
    0x1A790496: 'TexProperty', 0x2359054B: 'AlphaProperty', 0x32390645: 'BackFaceProperty',
    0x1A560492: 'MtlProperty', 0x1DE904DC: 'ZBufProperty', 0x1F4B04FC: 'WireProperty',
    0x1F9C0505: 'ToonProperty', 0x224B052A: 'PrsController', 0x250D0567: 'VisController',
    0x2FFF062B: 'FloatController', 0x24AB0560: 'IntController', 0x30670634: 'ColorController',
    0x30E9063B: 'MorphController', 0x2A1505C3: 'PathController', 0x31AD0642: 'TontrollerGroup',
    0x19AA0481: 'FogProperty', 0x0AA802CF: 'ToDummy', 0x1CF80490: 'ToBlackPlane',
    0x07D40250: 'ToMesh', 0x195B0452: 'ToEventMesh', 0x1140038E: 'ToMinimap',
    0x14B603D1: 'ToItemCube', 0x0A8E02B3: 'ToLucci', 0x2E6105E0: 'ToMovableObject',
}


def parse_sa(r):
    """二进制 XML 属性树"""
    name = r.string()
    text = r.string()
    nattr = r.uint32()
    attrs = [{'name': r.string(), 'value': r.string()} for _ in range(nattr)]
    nchild = r.uint32()
    children = [parse_sa(r) for _ in range(nchild)]
    return {'name': name, 'text': text, 'attributes': attrs, 'children': children}


def _track_node(r, g, cls):
    n = {'kind': 'node', 'className': cls}
    n['name'] = r.string()
    n['children'] = [g.read_object(r) for _ in range(r.uint32())]
    n['transform'] = [r.vec3(), r.vec3(), r.vec3()]
    n['position'] = r.vec3()
    n['scale'] = r.vec3()
    n['bounds0'] = r.bounds()
    n['serializedBoundsOverride'] = r.uint8()
    n['cullingTraversalMode'] = r.uint32()
    n['bounds1'] = r.bounds()
    n['rawScalar'] = r.float32()
    n['nodeEnabled'] = r.uint8()
    n['slots'] = [(g.read_object(r) if r.uint8() else None) for _ in range(11)]
    n['additionalProperty'] = parse_sa(r) if r.uint8() else None
    return n


def _p_trackcontainer(r, g):
    name = r.string()
    scene = g.read_object(r)
    objs = [g.read_object(r) for _ in range(r.uint32())]
    return {'kind': 'track', 'name': name, 'scene': scene,
            'trackObjects': [o['value'] for o in objs]}


def _p_trackobject(r, g):
    name = r.string()
    prop = parse_sa(r) if r.uint8() else None
    return {'kind': 'TrackObject', 'name': name, 'property': prop}


def _p_toroad(r, g):
    base = _p_trackobject(r, g)
    cyclic = r.uint8() != 0
    records = []
    for _ in range(r.uint32()):
        rec_name = r.string()
        positions = r.vec3_array(r.uint32())
        gates = [r.uint16_triple() for _ in range(r.uint32())]
        surface = r.string()
        surface_idx = [r.uint16_triple() for _ in range(r.uint32())]
        frames = [{'position': r.vec3(), 'forward': r.vec3(), 'up': r.vec3()}
                  for _ in range(r.uint32())]
        records.append({'name': rec_name, 'positions': positions, 'gates': gates,
                        'surface': surface, 'surfaceIndices': surface_idx, 'frames': frames})
    return {'kind': 'ToRoad', 'name': base['name'], 'property': base['property'],
            'cyclic': cyclic, 'records': records}


def _p_texproperty(r, g):
    n = {'kind': 'texture', 'textureOp': r.uint32()}
    n['name'] = g.read_object(r)['value']['text'] if r.uint8() else None
    n['addressU'] = r.uint32()
    n['addressV'] = r.uint32()
    n['minFilter'] = r.uint32()
    n['magFilter'] = r.uint32()
    n['mipFilter'] = r.uint32()
    n['maxAnisotropy'] = r.uint32()
    n['uvControllers'] = [(g.read_object(r) if r.uint8() else None) for _ in range(5)]
    n['scalar'] = r.float32()
    n['alphaController'] = g.read_object(r) if r.uint8() else None
    n['property'] = g.read_object(r) if r.uint8() else None
    return n


def _p_mtl(r, g):
    n = {'kind': 'material', 'mode': r.uint32(), 'ambient': r.uint32(),
         'diffuse': r.uint32(), 'specular': r.uint32(), 'power': r.float32(),
         'reserved': r.uint8(), 'emissive': r.uint32()}
    n['controllers'] = [(g.read_object(r) if r.uint8() else None) for _ in range(4)]
    return n


def _p_tomesh(r, g):
    name = r.string()
    prop = parse_sa(r) if r.uint8() else None
    n_idx = r.uint16()
    indices = [r.uint16() for _ in range(n_idx)]
    n_pos = r.uint16()
    positions = r.vec3_array(n_pos)
    return {'kind': 'ToMesh', 'name': name, 'property': prop,
            'indices': indices, 'positions': positions}


def _p_toeventmesh(r, g):
    n = _p_tomesh(r, g)
    n['kind'] = 'ToEventMesh'
    n['eventName'] = r.string()
    return n


def _p_tominimap(r, g):
    name = r.string()
    prop = parse_sa(r) if r.uint8() else None
    return {'kind': 'ToMinimap', 'name': name, 'property': prop,
            'centerX': r.float32(), 'centerY': r.float32(), 'scale': r.float32(),
            'canvasWidth': r.uint32(), 'canvasHeight': r.uint32(), 'padding': r.uint32()}


def _p_toblackplane(r, g):
    name = r.string()
    prop = parse_sa(r) if r.uint8() else None
    return {'kind': 'ToBlackPlane', 'name': name, 'property': prop,
            'vertices': [r.vec3() for _ in range(4)], 'planeNormal': r.vec3(),
            'edgeEnabled': [r.uint8() for _ in range(4)]}


def _p_generic_transform(r, g, kind, with_ordinal=False):
    name = r.string()
    prop = parse_sa(r) if r.uint8() else None
    transform = {'basis': [r.vec3() for _ in range(3)], 'position': r.vec3(), 'scale': r.vec3()}
    ordinal = r.uint32() if with_ordinal else None
    return {'kind': kind, 'name': name, 'property': prop, 'transform': transform,
            'instanceOrdinal': ordinal}


def _p_recamera(r, g):
    n = _track_node(r, g, 'ReCamera')
    n['camera'] = {'projectionMode': r.uint8(), 'fov': r.float32()}
    return n


def _p_rebillboard(r, g):
    n = _track_node(r, g, 'ReBillboard')
    n['orientationMode'] = r.uint32()
    return n


def _track_mesh(r, g, cls):
    n = _track_node(r, g, cls)
    n['sortDepthBias'] = r.float32()
    n['vertexData'] = g.read_typed(r, parse_qv)
    return n


def _track_rigid(r, g):
    n = _track_node(r, g, 'ReToonRigid')
    n['sortDepthBias'] = r.float32()
    n['geometry'] = g.read_typed(r, parse_kv)
    return n


TRACK_PARSERS = {
    0x28F90598: _p_trackcontainer,
    0x0E07033C: lambda r, g: _track_node(r, g, 'Relement'),
    0x10D40382: lambda r, g: _track_mesh(r, g, 'ReTriList'),
    0x14FC03F8: lambda r, g: _track_mesh(r, g, 'ReTriStrip'),
    0x192A0446: _track_rigid,
    0x189F0442: _p_rebillboard,
    0x0CF20300: _p_recamera,
    0x1953044C: _p_trackobject,
    0x07DE0249: _p_toroad,
    0x1A790496: _p_texproperty,
    0x2359054B: _p_alpha,
    0x32390645: lambda r, g: {'kind': 'backface', 'cull': r.uint32()},
    0x1A560492: _p_mtl,
    0x1DE904DC: _p_zbuf,
    0x1F4B04FC: lambda r, g: {'kind': 'wire', 'enabled': r.uint8()},
    0x1F9C0505: lambda r, g: {'kind': 'toon', 'flags': [r.uint8(), r.uint8()],
                              'words': [r.uint32() for _ in range(9)]},
    0x224B052A: _p_prs,
    0x250D0567: _p_vis,
    0x2FFF062B: lambda r, g: {'kind': 'float-controller', 'base': tontroller_base(r),
                              'keys': g.read_typed(r, lambda rr, gg: be_keys(rr, 'float'))},
    0x24AB0560: _p_int,
    0x30670634: lambda r, g: {'kind': 'color-controller', 'base': tontroller_base(r),
                              'keys': g.read_typed(r, lambda rr, gg: be_keys(rr, 'float'))},
    0x2A1505C3: _p_path,
    0x31AD0642: _p_group,
    0x19AA0481: lambda r, g: {'kind': 'fog-property', 'selector': r.uint32(),
                              'mode': r.uint32(), 'color': r.uint32(),
                              'start': r.float32(), 'end': r.float32(), 'density': r.float32()},
    0x0AA802CF: lambda r, g: _p_generic_transform(r, g, 'ToDummy'),
    0x1CF80490: _p_toblackplane,
    0x07D40250: _p_tomesh,
    0x195B0452: _p_toeventmesh,
    0x1140038E: _p_tominimap,
    0x14B603D1: lambda r, g: _p_generic_transform(r, g, 'ToItemCube', True),
    0x0A8E02B3: lambda r, g: _p_generic_transform(r, g, 'ToLucci', True),
    0x2E6105E0: lambda r, g: _p_generic_transform(r, g, 'ToMovableObject'),
}


def parse_auto(data):
    """按根 stamp 自动选择 模型/赛道 模式"""
    stamp = struct.unpack_from('<I', data, 2)[0]
    g = Graph()
    if stamp == 0x28F90598:
        g.PARSERS = TRACK_PARSERS
    r = Reader(data)
    root = g.read_object(r)
    return root, g
'''

src = open('s1_parse.py', encoding='utf-8').read()
old = """        cls = STAMPS.get(stamp, f'Unknown_{stamp:08x}')
        pos0 = r.pos
        parser = PARSERS.get(stamp)"""
new = """        cls = STAMPS.get(stamp, f'Unknown_{stamp:08x}')
        pos0 = r.pos
        parser = getattr(self, 'PARSERS', PARSERS).get(stamp)"""
assert old in src
src = src.replace(old, new)
src = src.replace("    root, g = parse(data)", "    root, g = parse_auto(data)")
src += addition
open('s1_parse.py', 'w', encoding='utf-8').write(src)
print('s1_parse.py 已扩展')
