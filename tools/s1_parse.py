"""KartRider .1s (Object47 场景图) 解析器 — 移植自 KartSim 反混淆代码。

格式: 对象图。Object47: marker u16 (0x47aa 新对象 / 0x47bb 引用) + stamp u32 + id u16。
Typed27: marker (0x27aa/0x27bb) + id u16 + 类型数据。
用法: python s1_parse.py <file.1s> [--gltf out.gltf]
"""
import json
import struct
import sys

OBJ_NEW, OBJ_REF = 0x47AA, 0x47BB
TYP_NEW, TYP_REF = 0x27AA, 0x27BB

STAMPS = {
    0x078C0249: 'ReKart', 0x0E07033C: 'Relement', 0x192A0446: 'ReToonRigid',
    0x10D40382: 'ReTriList', 0x23330523: 'ReToonSkinned', 0x186F0444: 'ReCharacter',
    0x2359054B: 'AlphaProperty', 0x1DE904DC: 'ZBufProperty', 0x224B052A: 'PrsTontroller',
    0x250D0567: 'VisTontroller', 0x2A1505C3: 'PathTontroller', 0x31AD0642: 'TontrollerGroup',
    0x1E8A04CB: 'KartSequence', 0x1DBB04B7: 'CharSequence', 0x24AB0560: 'IntTontroller',
}

# 关键帧字节数表 (ib)
IB = {
    'float': {0: 0x10, 1: 8, 2: 0x14, 3: 8},
    'vec3': {0: 0x28, 1: 0x10, 2: 0x1C, 3: 0x10},
    'rotation': {0: 0x14, 1: 0x14, 2: 0x20, 3: 0x14},
    'visibility': {3: 5},
    'integer': {3: 8},
}


class Reader:
    __slots__ = ('data', 'pos')

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def _need(self, n):
        if self.pos + n > len(self.data):
            raise EOFError(f'数据意外结束 @ {self.pos:#x} + {n}')

    def uint8(self):
        self._need(1)
        v = self.data[self.pos]
        self.pos += 1
        return v

    def uint16(self):
        self._need(2)
        v = struct.unpack_from('<H', self.data, self.pos)[0]
        self.pos += 2
        return v

    def uint32(self):
        self._need(4)
        v = struct.unpack_from('<I', self.data, self.pos)[0]
        self.pos += 4
        return v

    def float32(self):
        self._need(4)
        v = struct.unpack_from('<f', self.data, self.pos)[0]
        self.pos += 4
        return v

    def bytes(self, n):
        self._need(n)
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def vec2(self):
        return (self.float32(), self.float32())

    def vec3(self):
        return (self.float32(), self.float32(), self.float32())

    def vec3_array(self, n):
        return [self.vec3() for _ in range(n)]

    def bounds(self):
        return {'min': self.vec3(), 'max': self.vec3()}

    def uint16_triple(self):
        return (self.uint16(), self.uint16(), self.uint16())

    def string(self):
        n = self.count32('字符串', 0xF4240)
        return self.bytes(n * 2).decode('utf-16-le').rstrip('\x00')

    def count32(self, label, limit):
        v = self.uint32()
        if v > limit:
            raise ValueError(f'model.1s 的 {label} 数量无效: {v}')
        return v

    def count16(self, label, limit):
        v = self.uint16()
        if v > limit:
            raise ValueError(f'model.1s 的 {label} 数量无效: {v}')
        return v


def be_keys(r, category):
    """Be: 动画关键帧曲线"""
    key_type = r.uint32()
    count = r.count32(category + ' 关键帧', 0xF4240)
    if category == 'vec3' and key_type == 5:
        header = [r.uint32() for _ in range(4)]
        return {'kind': 'composite', 'keyType': key_type, 'declaredCount': count,
                'header': header, 'components': [be_keys(r, 'float') for _ in range(3)]}
    if category == 'rotation' and key_type == 4:
        header = [r.uint32() for _ in range(5)]
        return {'kind': 'composite', 'keyType': key_type, 'declaredCount': count,
                'header': header, 'components': [be_keys(r, 'float') for _ in range(3)]}
    size = IB[category][key_type]
    r._need(count * size)
    return {'kind': 'fixed', 'keyType': key_type, 'declaredCount': count,
            'records': [r.bytes(size) for _ in range(count)]}


def tontroller_base(r):
    """aa"""
    return {'baseWord0': r.uint32(), 'cycleMode': r.uint32(),
            'discarded': [r.uint32(), r.uint32()], 'frequency': r.float32(),
            'phase': r.uint32(), 'start': r.uint32(), 'stop': r.uint32()}


def sn(r, g, cls):
    """节点通用结构"""
    node = {'className': cls, 'name': r.string()}
    node['children'] = [g.read_object(r) for _ in range(r.count32('子节点', 0x30D40))]
    node['transform'] = {'basis': [r.vec3() for _ in range(3)],
                         'translation': r.vec3(), 'scale': r.vec3()}
    node['bounds0'] = r.bounds()
    node['serializedBoundsOverride'] = r.uint8()
    node['cullingTraversalMode'] = r.uint32()
    node['bounds1'] = r.bounds()
    node['rawScalar'] = r.float32()
    node['nodeEnabled'] = r.uint8()
    node['slots'] = [(g.read_object(r) if r.uint8() else None) for _ in range(11)]
    node['additionalProperty'] = g.read_typed(r, parse_sa) if r.uint8() else None
    return node


def sa(r, depth=0, counters=None):
    counters = counters or {'nodes': 0, 'attributes': 0}
    counters['nodes'] += 1
    raise NotImplementedError('sa 附加属性树(待按需补全)')


def parse_kv(r, g=None):
    """刚性网格"""
    positions = r.vec3_array(r.count32('刚性顶点', 0x1E8480))
    normals = r.vec3_array(r.count32('刚性法线', 0x1E8480))
    texcoords = [{'rawWord': r.uint16(), 'normalIndex': r.uint16(), 'u': r.float32(), 'v': r.float32()}
                 for _ in range(r.count32('刚性纹理坐标', 0x1E8480 * 3))]
    faces = [{'texcoord': r.uint16_triple(), 'adjacent': r.uint16_triple(),
              'position': r.uint16_triple(), 'winding': r.uint8(), 'outlineOpenEdge': r.uint8()}
             for _ in range(r.count32('刚性面', 0x1E8480))]
    return {'positions': positions, 'normals': normals, 'texcoords': texcoords, 'faces': faces}


def parse_qv(r, g):
    """TriList 几何"""
    vcount = r.count16('辅助模型顶点', 0xFFFF)
    positions = r.vec3_array(vcount) if r.uint8() else None
    normals = r.vec3_array(vcount) if r.uint8() else None
    colors = [r.uint32() for _ in range(vcount)] if r.uint8() else None
    uv_sets = r.count16('每顶点 UV 集', 0x10)
    uvs = [[r.vec2() for _ in range(uv_sets)] for _ in range(vcount)]
    prop = g.read_object(r) if r.uint8() else None
    indices = [r.uint16() for _ in range(r.count16('辅助模型索引', 0xFFFF))]
    return {'vertexCount': vcount, 'positions': positions, 'normals': normals,
            'colors': colors, 'uvSets': uv_sets, 'uvs': uvs, 'property': prop,
            'indices': indices}


def parse_jv(r, g=None):
    """蒙皮几何"""
    verts = [{'position': r.vec3(), 'normal': r.vec3(), 'bone0': r.uint16(),
              'bone1': r.uint16(), 'weight0': r.float32(), 'weight1': r.float32()}
             for _ in range(r.count32('skin vertices', 0xFFFF))]
    wedges = [{'skinVertexIndex': r.uint32(), 'u': r.float32(), 'v': r.float32()}
              for _ in range(r.count32('skin wedges', 0xFFFF))]
    tris = []
    for _ in range(r.count32('skin triangles', 0xFFFF)):
        w = r.uint16_triple()
        extra = r.bytes(6)
        adj = struct.unpack_from('<3H', extra)
        pos = r.uint16_triple()
        tris.append({'wedge': w, 'adjacent': adj, 'position': pos,
                     'winding': r.uint8(), 'unknown13': r.uint8()})
    bones = [{'inverseBind': [r.float32() for _ in range(12)],
              'localBind': [r.float32() for _ in range(12)],
              'parentIndex': r.uint16(), 'enabled': r.uint8(), 'reserved': r.uint8()}
             for _ in range(r.count32('skin bones', 0xFFFF))]
    return {'vertices': verts, 'wedges': wedges, 'triangles': tris, 'bones': bones}


def kart_sequence(r, g):
    out = {'className': 'KartSequence', 'cached': [r.uint32() for _ in range(3)]}
    out['channels'] = []
    for i in range(0x37):
        prs = g.read_object(r)
        vis = g.read_object(r)
        out['channels'].append((prs, vis))
    return out


def char_sequence(r, g):
    header = [r.uint32() for _ in range(3)]
    channels = [g.read_object(r) for _ in range(0x18)]
    root = g.read_object(r)
    m = [r.uint32() for _ in range(r.count32('character animation map', 0xF4240))]
    return {'className': 'CharSequence', 'header': header, 'channels': channels,
            'root': root, 'map': m}


class Graph:
    def __init__(self):
        self.objects = {}
        self.typed = {}

    def read_object(self, r):
        marker = r.uint16()
        if marker == OBJ_REF:
            ref = r.uint16()
            if ref not in self.objects:
                raise ValueError(f'引用未知 Object47 id {ref}')
            return {'ref': ref, 'value': self.objects[ref]}
        if marker != OBJ_NEW:
            raise ValueError(f'Object47 marker {marker:#x} 无效 @ {r.pos - 2:#x}')
        stamp = r.uint32()
        obj_id = r.uint16()
        cls = STAMPS.get(stamp, f'Unknown_{stamp:08x}')
        pos0 = r.pos
        parser = getattr(self, 'PARSERS', PARSERS).get(stamp)
        if parser is None:
            raise ValueError(f'不支持的 ClassStamp {stamp:#x} ({cls}) @ {pos0:#x}')
        value = parser(r, self)
        self.objects[obj_id] = value
        return {'id': obj_id, 'value': value}

    def read_typed(self, r, fn):
        marker = r.uint16()
        if marker == TYP_REF:
            ref = r.uint16()
            if ref not in self.typed:
                raise ValueError(f'引用未知 Typed27 id {ref}')
            return {'ref': ref, 'value': self.typed[ref]}
        if marker != TYP_NEW:
            raise ValueError(f'Typed27 marker {marker:#x} 无效 @ {r.pos - 2:#x}')
        tid = r.uint16()
        value = fn(r, self)
        self.typed[tid] = value
        return {'id': tid, 'value': value}


def _p_rekart(r, g):
    n = sn(r, g, 'ReKart')
    n['sortDepthBias'] = r.float32()
    n['rootBounds'] = r.bounds()
    n['simpleShadow'] = [r.float32() for _ in range(4)]
    return n


def _p_relement(r, g):
    return sn(r, g, 'Relement')


def _p_retoonrigid(r, g):
    n = sn(r, g, 'ReToonRigid')
    n['sortDepthBias'] = r.float32()
    n['geometry'] = g.read_typed(r, parse_kv)
    return n


def _p_retrilist(r, g):
    n = sn(r, g, 'ReTriList')
    n['sortDepthBias'] = r.float32()
    n['vertexData'] = g.read_typed(r, parse_qv)
    return n


def _p_retoonskinned(r, g):
    n = sn(r, g, 'ReToonSkinned')
    n['sortDepthBias'] = r.float32()
    n['geometry'] = g.read_typed(r, parse_jv)
    n['secondary'] = g.read_object(r) if r.uint8() else None
    return n


def _p_recharacter(r, g):
    n = sn(r, g, 'ReCharacter')
    n['characterScalar'] = r.float32()
    return n


def _p_alpha(r, g):
    return {'className': 'AlphaProperty', 'blendEnable': r.uint8(),
            'srcBlend': r.uint32(), 'dstBlend': r.uint32(),
            'alphaTestEnable': r.uint8(), 'alphaFunc': r.uint32(), 'alphaRef': r.uint8()}


def _p_zbuf(r, g):
    return {'className': 'ZBufProperty', 'mode': r.uint32(), 'enabled': r.uint8()}


def _p_prs(r, g):
    n = {'className': 'PrsTontroller', 'base': tontroller_base(r)}
    n['position'] = g.read_typed(r, lambda rr, gg: be_keys(rr, 'vec3')) if r.uint8() else None
    n['rotation'] = g.read_typed(r, lambda rr, gg: be_keys(rr, 'rotation')) if r.uint8() else None
    n['scale'] = g.read_typed(r, lambda rr, gg: be_keys(rr, 'vec3')) if r.uint8() else None
    n['firstLastCache'] = [r.uint32() for _ in range(6)]
    return n


def _p_vis(r, g):
    n = {'className': 'VisTontroller', 'base': tontroller_base(r)}
    n['visibility'] = g.read_typed(r, lambda rr, gg: be_keys(rr, 'visibility'))
    return n


def _p_path(r, g):
    n = {'className': 'PathTontroller', 'base': tontroller_base(r)}
    n['vec3Keys'] = g.read_typed(r, lambda rr, gg: be_keys(rr, 'vec3')) if r.uint8() else None
    n['floatKeys'] = g.read_typed(r, lambda rr, gg: be_keys(rr, 'float')) if r.uint8() else None
    n['tail'] = (r.uint32(), r.uint32(), r.uint16(), r.uint32(), r.uint16(), r.bytes(5))
    return n


def _p_group(r, g):
    return {'className': 'TontrollerGroup', 'value': r.string()}


def _p_kartseq(r, g):
    return kart_sequence(r, g)


def _p_charseq(r, g):
    return char_sequence(r, g)


def _p_int(r, g):
    n = {'className': 'IntTontroller', 'base': tontroller_base(r)}
    n['keys'] = g.read_typed(r, lambda rr, gg: be_keys(rr, 'integer'))
    return n


PARSERS = {
    0x078C0249: _p_rekart, 0x0E07033C: _p_relement, 0x192A0446: _p_retoonrigid,
    0x10D40382: _p_retrilist, 0x23330523: _p_retoonskinned, 0x186F0444: _p_recharacter,
    0x2359054B: _p_alpha, 0x1DE904DC: _p_zbuf, 0x224B052A: _p_prs,
    0x250D0567: _p_vis, 0x2A1505C3: _p_path, 0x31AD0642: _p_group,
    0x1E8A04CB: _p_kartseq, 0x1DBB04B7: _p_charseq, 0x24AB0560: _p_int,
}


def parse(data: bytes):
    g = Graph()
    r = Reader(data)
    root = g.read_object(r)
    return root, g


def summarize(node, depth=0, max_depth=4):
    v = node.get('value', node) if isinstance(node, dict) else node
    if not isinstance(v, dict):
        return '  ' * depth + str(v)[:80]
    line = '  ' * depth + f"{v.get('className')} name={v.get('name')!r}"
    if 'geometry' in v and isinstance(v['geometry'], dict):
        geo = v['geometry']['value'] if 'value' in v['geometry'] else v['geometry']
        if 'faces' in geo:
            line += f" [刚性 vt={len(geo['positions'])} tc={len(geo['texcoords'])} f={len(geo['faces'])}]"
    if 'vertexData' in v and isinstance(v['vertexData'], dict):
        geo = v['vertexData']['value'] if 'value' in v['vertexData'] else v['vertexData']
        line += f" [TriList v={geo['vertexCount']} idx={len(geo['indices'])} uv={geo['uvSets']}]"
    out = [line]
    if depth < max_depth:
        for c in v.get('children', []) or []:
            out.append(summarize(c, depth + 1, max_depth))
    return '\n'.join(out)




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


def parse_sa(r, g=None):
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
    n['additionalProperty'] = g.read_typed(r, parse_sa) if r.uint8() else None
    return n


def _p_trackcontainer(r, g):
    name = r.string()
    scene = g.read_object(r)
    objs = [g.read_object(r) for _ in range(r.uint32())]
    return {'kind': 'track', 'name': name, 'scene': scene,
            'trackObjects': [o['value'] for o in objs]}


def _p_trackobject(r, g):
    name = r.string()
    prop = g.read_typed(r, parse_sa) if r.uint8() else None
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
    n['name'] = g.read_typed(r, lambda rr, gg: rr.string())['value'] if r.uint8() else None
    n['addressU'] = r.uint32()
    n['addressV'] = r.uint32()
    n['minFilter'] = r.uint32()
    n['magFilter'] = r.uint32()
    n['mipFilter'] = r.uint32()
    n['maxAnisotropy'] = r.uint32()
    n['uvControllers'] = [(g.read_object(r) if r.uint8() else None) for _ in range(5)]
    n['scalar'] = r.float32()
    n['alphaController'] = g.read_object(r) if r.uint8() else None
    n['property'] = g.read_typed(r, parse_sa) if r.uint8() else None
    return n


def _p_mtl(r, g):
    n = {'kind': 'material', 'mode': r.uint32(), 'ambient': r.uint32(),
         'diffuse': r.uint32(), 'specular': r.uint32(), 'power': r.float32(),
         'reserved': r.uint8(), 'emissive': r.uint32()}
    n['controllers'] = [(g.read_object(r) if r.uint8() else None) for _ in range(4)]
    return n


def _p_tomesh(r, g):
    name = r.string()
    prop = g.read_typed(r, parse_sa) if r.uint8() else None
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
    prop = g.read_typed(r, parse_sa) if r.uint8() else None
    return {'kind': 'ToMinimap', 'name': name, 'property': prop,
            'centerX': r.float32(), 'centerY': r.float32(), 'scale': r.float32(),
            'canvasWidth': r.uint32(), 'canvasHeight': r.uint32(), 'padding': r.uint32()}


def _p_toblackplane(r, g):
    name = r.string()
    prop = g.read_typed(r, parse_sa) if r.uint8() else None
    return {'kind': 'ToBlackPlane', 'name': name, 'property': prop,
            'vertices': [r.vec3() for _ in range(4)], 'planeNormal': r.vec3(),
            'edgeEnabled': [r.uint8() for _ in range(4)]}


def _p_generic_transform(r, g, kind, with_ordinal=False):
    name = r.string()
    prop = g.read_typed(r, parse_sa) if r.uint8() else None
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


if __name__ == '__main__':
    path = sys.argv[1]
    data = open(path, 'rb').read()
    root, g = parse_auto(data)
    print(f'解析完成: {len(g.objects)} 个对象')
    print(summarize(root, max_depth=3))
