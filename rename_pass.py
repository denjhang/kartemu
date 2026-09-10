"""把 deob_pretty.js 重命名成可读版 deob_named.js
- vendor 导入别名 → three.js/P3528 运行时真名(经 Node 实际加载 vendor 鉴定)
- 逆向已确认的顶层函数 → 语义名(保留原名注释)
输出: deob_named.js, SYMBOLS.md
"""
import re
import json

src = open('deob_pretty.js', encoding='utf-8').read()

# ---- vendor 导入别名 → 真名(Node 鉴定: 原型链指纹 + 用法) ----
ALIAS = {
    '_0x44fcd1': 'Group',            # G  Fi  new+add, Object3D 族
    '_0x175d18': 'BufferGeometry',   # B  cn  getIndex/setIndex/setAttribute
    '_0x34a38e': 'CONST_e_0',
    '_0x55d456': 'CONST_f_1',
    '_0x22c87d': 'Mesh',             # M  $t  updateMorphTargets/raycast
    '_0x426eae': 'CONST_N_str',
    '_0x4ad06b': 'ShaderMaterialB',  # S  en  shader 族
    '_0x22b18c': 'Vector2B',         # V  ct  width/height/setX/setY
    '_0x1cbee0': 'Vector2',          # b  Xe
    '_0x389954': 'Vector3',          # c  G   set/setX/setZ/setComponent
    '_0x34d48d': 'Matrix4',          # d  ut  makeBasis/lookAt/multiplyMatrices
    '_0x58452c': 'CONST_2_DoubleSide',
    '_0x59e52c': 'CONST_5_AdditiveBlending',
    '_0xbf1a41': 'CONST_A_cls',
    '_0x2baaa6': 'CONST_0', '_0x2f5547': 'CONST_1', '_0x4521b6': 'CONST_5',
    '_0x3173b3': 'CONST_7', '_0x6e950f': 'CONST_6',
    '_0x39fb65': 'CONST_210', '_0x54fd9e': 'CONST_4',
    '_0x2c2674': 'CONST_2', '_0x35be81': 'CONST_0b', '_0x10f846': 'CONST_210b',
    '_0x14c7e8': 'CONST_208', '_0xcaeee9': 'CONST_207', '_0x2fa5b7': 'CONST_206',
    '_0x2ed97b': 'CONST_205', '_0x4205b3': 'CONST_204', '_0x37475b': 'CONST_203',
    '_0xc5628d': 'CONST_202', '_0x14771e': 'CONST_201',
    '_0x212e31': 'CONST_Z_200',
    '_0x2a0f74': 'CONST_u_1', '_0x42d0e3': 'CONST_v_0',
    '_0x2f6c3a': 'ShaderMaterial',   # R  md  uniforms/vertexShader 用法
    '_0x3e661c': 'CONST_35048',
    '_0x5e3785': 'TextureLoaderX',   # x  ao  width/height/image 族
    '_0x54c834': 'CONST_1023',
    '_0x34b8cb': 'CONST_U_1009', '_0x5caba7': 'CONST_1000',
    '_0x4786c8': 'CONST_H_cls',
    '_0x303f61': 'PerspectiveCamera',# P  Gt  setFocalLength/getFilmWidth
    '_0x35ffa4': 'MeshBasicMaterial',# I  Gs  new {color,map,transparent}
    '_0x4d057b': 'RenderTargetLike', # T  mt  width/height/image
    '_0x56fbef': 'LoaderB',          # J  _d  load/parse/setPath
    '_0x2cd6a4': 'CONST_K_str',
    '_0x3eb6c5': 'Box3',             # Q  di  setFromObject/setFromPoints
    '_0x1875a4': 'CONST_W_1001',
    '_0x46cea7': 'LoaderC',          # X  vd  parse/load
    '_0x3a7301': 'CONST_Y_number',
    '_0x477733': 'CONST_33777_DXT1',
    '_0x4380e6': 'CONST_dollar_cls',
    '_0x45705c': 'LoaderD',          # a0 xd
    '_0x5d5b39': 'CONST_1002', '_0x3395eb': 'CONST_1006', '_0x47a8d8': 'CONST_1007',
    '_0x5c1960': 'CONST_1004', '_0x1c8e27': 'CONST_1008', '_0x2e1a02': 'CONST_1005',
    '_0x171d8d': 'CONST_33778_DXT3', '_0x1555cf': 'CONST_33779_DXT5',
    '_0x5b8fd4': 'RenderTarget',     # a9 fd  depthTexture/setSize → 见 ac
    '_0x109b87': 'LoaderE',          # aa ks getWorldDirection
    '_0x34b3c5': 'CONST_ab_number',
    '_0x3a0963': 'RenderTarget2',    # ac En texture/depthTexture/setSize
    '_0x4c0b7': 'Quaternion',        # ad fi
    '_0x3df6d8': 'MaterialC',        # ae so
    '_0x21ec00': 'Object3DSub',      # af dd
    '_0x36c1e8': 'Matrix3',          # ag He setFromMatrix4/multiply/extractBasis
    '_0x4d3221': 'EulerLike',        # ah Sd
    '_0x4e629a': 'HashMD5',          # ai _  append/appendBinary/end/getState
    '_0x21ec00b': 'x',
    '_0x5b57a6': 'ClassAj',          # aj Md
    '_0x1d2075': 'CONST_ak_srgblinear',
    '_0x594027': 'Matrix3B',         # al gd coordinateSystem/outputColorSpace
    '_0x5a458c': 'CONST_am_1',
    '_0x3f4bfd': 'OptionsObj',       # an object
}

# ---- 逆向确认的顶层函数/类 → 语义名 ----
FUNCS = {
    'l1': 'setNodeMatrix', 'u1': 'matPhysicsFromPresentationX90',
    'N0': 'composeMatrixNew', 'uC': 'setNodeMatrixUC',
    'rn': 'adler32_init0', 'ZC': 'rhoFilenameKey',
    'rl': 'ObjGraphReader_class', 'sn': 'parseSceneNodeCommon',
    'Kv': 'parseRigidGeometry', 'qv': 'parseTriListVertexData',
    'jv': 'parseSkinnedGeometry', 'Yv': 'parseKartSequence',
    'Zv': 'parseCharSequence', 'Hv': 'parseAlphaProperty',
    'Xv': 'parseZBufProperty', 'Qv': 'parsePrsTontroller',
    'tb': 'parseVisTontroller', 'eb': 'parsePathTontroller',
    'Jv': 'parseIntTontroller', 'aa': 'parseAnimBase',
    'Be': 'parseBeCurve', 'Vv': 'parseReToonRigid', 'Wv': 'parseReTriList',
    'Uv': 'parseReToonSkinned', 'Gv': 'parseReCharacter', '_v': 'parseReKart',
    'sa': 'parseBinaryXML',
    'fx': 'parseTrackContainer', 'on': 'parseTrackNode', 'vx': 'parseTrackNodeBody',
    'yx': 'parseToRoad', 'dx': 'createTrackDecoders', 'xx': 'parseReTriStrip',
    'bx': 'parseReTriList', 'Ax': 'parseReBillboard', 'kx': 'parseBackFaceProperty',
    'Tx': 'parseTexProperty', 'Cx': 'parseAlphaPropTrack', 'Px': 'parseZBufPropTrack',
    'Rx': 'parseMtlProperty', 'Bx': 'parseToonProperty', '_x': 'parseFogProperty',
    'mx': 'parseToBlackPlane', 'px': 'parseToMinimap', 'wx': 'parseToMovableObject',
    'gx': 'parseToEventMesh', 'R0': 'parseToMesh', 'Na': 'parseToDummyLike',
    'mr': 'parseTrackObject', 'El': 'isRelement', 'qx': 'isTrackObject',
    'd1': 'isVehicleElement', 'h1': 'rgbaFromU32',
    'Pa': 'parseModel1s', 'rb': 'buildVehicleScene', 'Tn': 'collectVehicleNodes',
    'Zs': 'boundsToFootprint', 'ba': 'KartAnimPlayer', 'w1': 'vehiclePostSetup',
    'y1': 'applyBaseTextureAll', 'g1': 'loadKartTexture',
    '_0x2432da': 'buildVehicleObject', '_0x5d9cc9': 'collectNamedNodeMap',
    '_0xb8796c': 'updateHierarchyCulling', '_0x101bcc': 'disposeVehicleLib',
    'ld': 'resolveAlphaZbufInherit', 'ud': 'makeMatConfig',
    'oi': 'setRenderOrderDepthBias', 'hl': 'createToonLineMaterial',
    'll': 'applyMatConfig', 'e0': 'createTrackMesh',
    'dl': 'OutlinePass_class', 'c1': 'buildOutlineGeometry',
    'k0': 'collectRoadTriangles', 'ex': 'buildRouteGraph',
    'ix': 'gateTrisFromRecord', 'Oa': 'roadFrameToPhysics', 'Ad': 'reverseFrame',
    'nx': 'physicsToPresentation', 'ae': 'dataToPhysicsVec', 'ux': 'triNormal',
    'mh': 'v_cross', 'Jr': 'v_normalize', 'hr': 'v_sub', 'Or': 'v_add',
    'ri': 'v_scale', 'sx': 'dist3', 'ox': 'len3', 'Md': 'routeLength',
    'aB': 'auditTrackObjects', 'dB': 'auditTrackObject', 'uB': 'auditFlash',
    'hB': 'buildAdmissionLedger', 'kB': 'findLensflarePos',
    'J1': 'extractCollisionData', 'ZB': 'resolveStartupSelection',
    'QB': 'modelStem', 'sh': 'recordKey',
    'UB': 'GameApp', 'fl': 'VehicleImporter',
    'D2': 'solidPanelMaterial', 'v': 'xmlAttr', 'gt': 'xmlText',
    'ii': 'parseXML', 'lt': 'parseBML', 'bt': 'decodeImage',
    'Z$': 'CollisionGrid', 'Ye': 'rayExtend',
}

count_a = count_f = 0
for alias, name in ALIAS.items():
    pat = re.compile(r'\b' + re.escape(alias) + r'\b')
    src, n = pat.subn(name, src)
    count_a += n
for fn, name in FUNCS.items():
    pat = re.compile(r'\b' + re.escape(fn) + r'\b')
    src, n = pat.subn(name, src)
    count_f += n

open('deob_named.js', 'w', encoding='utf-8', newline='\n').write(src)
print(f'import alias replacements: {count_a}, function replacements: {count_f}')

# ---- SYMBOLS.md ----
syms = []
for line in open('symbols_raw.txt', encoding='utf-8'):
    l, t, n = line.rstrip('\n').split('\t')
    renamed = FUNCS.get(n) or (n if not n.startswith('_0x') else '')
    syms.append((int(l), t, n, renamed))
with open('SYMBOLS.md', 'w', encoding='utf-8') as f:
    f.write('# P3528 主 bundle 全量顶层符号索引(deob_pretty.js / deob_named.js 行号)\n\n')
    f.write('| 行号 | 类型 | 原名 | 语义名 |\n|---:|---|---|---|\n')
    for l, t, n, r in syms:
        f.write(f'| {l} | {t} | `{n}` | {r or ""} |\n')
print('symbols:', len(syms))
