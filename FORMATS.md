# KartRider 资源格式逆向笔记

来源:KartSim 反混淆代码(`deob_full.js`,由 `deobfuscate.py` 生成)+ 运行时验证。
本文件是自研解包器/转换器的完整依据。

## 1. .rho 容器(已破解,解包器: rho_unpack.py)

- 文件头 0x100 字节:0x00-0x22 为 UTF-16LE `"Rh layer spec 1.0"/"1.1"`,
  `iu()` 读取;档案密钥 = `ZC(文件名去.rho)` = `adler32(UTF16LE(name)) - 0xa6ee7565`
- 块表位于 0x100(`Pm`),每项 `mc=0x20` 字节,1.1 版每项经 `$m`(字CBC流密码,
  1024 项表 `_C()`,自逆)加密;1.0 用 `Kw` XOR 头部密钥
- 块项字段(u32LE×8):`index, offset(*0x100), storedSize, logicalSize,
  processingFlags, checksum, rawWords[2]`
- 头部魔数:内部版本码 `0x10000+version`,头尾标识 `0xfc1f9778`
- 实际解包无需解析头部:`archive-index.json` 已含每个包的 key/块表/文件表

### 文件数据读取(函数 jw/HC)
1. 块 = blocks[dataIndex];读 offset..offset+storedSize
2. flags&2 → zlib inflate(XC)
3. flags&4 → XOR 解密(ga):64 字节密钥流 = 16×u32LE,
   seed = dataKey^0x8473fbc1,逐项 -0x7b8c043f(mod 2^32)
4. flags&1 → 校验:**Adler-32 但初始 a=0**(非标准!rn 函数)
5. 文件实际大小大于主块输出时,追加续块 dataIndex+1(明文,HC/ek)
6. flags&8:未公开算法(KartSim 也直接报错),当前语料未遇到

### 目录
树形,根节点 index=0xffffffff,目录块用 `dataKey = archiveKey+0x2593a9f1` 解密,
条目由 `ik`(二进制 reader)读出 path/dataIndex/dataKey/size/fileProperty。

## 2. .1s 模型/场景(Object47 图)

分块容器,块头 `[0xaa47? 实测文件前缀 aa47][stamp:u32][...][长度][UTF-16LE 名]`。
本质是**序列化对象图**:

- 读取原语(类 `rl`):uint8/uint16/uint32/float32/vec3/vec3Array/bounds{min,max}/
  string(u32 长度+UTF-16LE)/count32(标签,上限)/bytes
- **Object47**:marker u16(`0x47aa`=新对象 / `0x47bb`=引用)+ id u16 + ClassStamp u32
- **Typed27**:marker u16(`0x27aa`=新 / `0x27bb`=引用)+ id u16 + 类型化数据

### ClassStamp 表(he)
```
ReKart        0x078c0249   Relement     0x0e07033c
ReToonRigid   0x192a0446   ReTriList    0x10d40382
ReToonSkinned 0x23330523   ReCharacter  0x186f0444
AlphaProperty 0x2359054b   ZBufProperty 0x1de904dc
PrsTontroller 0x224b052a   VisTontroller0x250d0567
PathTontroller0x2a1505c3   TontrollerGroup 0x31ad06xx
KartSequence  ...          CharSequence ...
IntTontroller ...
```

### 节点通用结构(sn)
```
name:string, children:count32(子节点)→Object47[],
transform{basis:vec3×3, translation:vec3, scale:vec3},
bounds0, serializedBoundsOverride:u8, cullingTraversalMode:u32,
bounds1, rawScalar:f32, nodeEnabled:u8,
slots:11×(u8 存在标志→Object47), additionalProperty:(u8→sa())
```

### 网格(Kv,Typed27 "刚性")
```
positions:vec3Array(count32("刚性顶点"))
normals :vec3Array(count32("刚性法线"))
texcoords:count32("刚性纹理坐标",×3) → 每项{rawWord:u16, normalIndex:u16, u:f32, v:f32}
faces   :count32("刚性面") → 每项{texcoordIndices:u16×3, positionIndices:u16×3}
```
即:顶点池+UV 池(UV 项带法线索引)+ 三角索引(位置索引与 UV 索引分离)。

### 对象类型
- `ReToonRigid`:sn 节点 + sortDepthBias:f32 + geometry(Typed27→Kv)
- `ReTriList`:sn + sortDepthBias + vertexData(Typed27→qv)
- `ReToonSkinned`:sn + sortDepthBias + geometry(Typed27→jv 蒙皮)
  + 可选 secondaryReference
- `ReKart`:sn + sortDepthBias + rootBounds + simpleShadow f32×4
- `ReCharacter`:sn + characterScalar:f32
- `KartSequence`:cached min/max/span u32×3 + **0x37(55)通道**,
  每通道 {PRSTontroller, VisTontroller} —— 车辆全部动画
- `CharSequence`:header u32×3 + **0x18(24)通道** + rootChannel + map[] —— 人物动画
- `PRSTontroller`:base(aa) + 可选 position/rotation/scale 关键帧曲线(Be) + u32×6
- `VisTontroller`:base + visibility 曲线;`IntTontroller`:base + integer 曲线
- `AlphaProperty`:blendEnable u8, srcBlend u32, dstBlend u32, alphaTestEnable u8,
  alphaFunc u32, alphaRef u8
- `ZBufProperty`:mode u32, enabled u8

### 动画曲线(Be/aa)
`aa` = Tontroller 公共头;Be(reader, 类型∈vec3/rotation/float/visibility/integer)
为关键帧数据(具体键值布局待提取,在 deob_full.js 中搜 `"vec3"))` 调用处)。

## 3. 已确认的资源映射

| 内容 | 位置 |
|---|---|
| 城镇高速公路(经典 R01) | `track_village_R01.rho` → track.1s(网格913KB)+ track_cn/track_rvs/rvs_d + skydome.1s + xt_minimap/bigmap/trackCard/Thumb.png |
| 皮蛋(Dao) | `character_dao.rho` → 299 文件:178 png(含 face/costume)+118 .1s(骨骼/动画/模型)+3 bml |
| 板车 cotton1 | DataPack2(rho5)→ `kart_/cotton1/param@cn.xml, 0.png, 1.png, model.1s, f00.1s...` |
| 车辆物理参数 | `kartspec.csv`(1418 车×2 速度×74 参数,源 cn3229) |

## 4. rho5(DataPack1-4)待逆向
- 已知:`archive-index.json` 的 rho5 节点含 name/region/parts(分卷+id)/files(路径)
- 分卷文件 `DataPackX_XXXXX.rho5` 需按 parts 顺序拼接/索引;
  解析器在 deob_full.js 搜 `Rho5`(如 `'Rho5\x20payload\x20path\x20is\x20empty.'`)

## 5. 反混淆工具链
```
deob_array.js deob_iife.js deob_decoder.js  # 从 index-DICvPz5y.js 切出
string_table.json                            # 5374 条字符串(索引0x194起)
deobfuscate.py  -> deob_full.js              # 1.52MB 可读代码(仅14处未还原)
```
关键代码定位:`jC`=rho头解析,`jw/HC`=文件数据,`ga/Kw/$m`=解密,`rn`=Adler32(初始0),
`ZC`=文件名派生密钥,`rl`=Object47 reader,`sn`=节点,`Kv`=刚性网格,
`Yv/Zv`=车/人动画序列,`UB`=游戏主类(three.js 场景+输入+loadP3528Resources)。

## 6. track.1s 赛道模式(已破解,s1_parse.py 已支持)

根 stamp = TrackContainer(0x28f90598)。与 model.1s 的差异:

- 节点类: TrackContainer/Relement/ReTriList/ReTriStrip/ReToonRigid/ReBillboard/
  ReCamera(布局见 study_track_parsers.js)
- **节点尾部(vx)**: transform=basis[3]×vec3 + position + scale, bounds0, u8, u32,
  bounds1, f32, u8 nodeEnabled, 11×(u8→slot 对象), u8→additionalProperty
- **所有属性字段(sa 属性树)都带 Typed27 包装**(marker 0x27aa + id u16)
- TrackObject 家族: `name:string + u8→property(sa)` 为公共头(mr)
- `ToRoad`(行驶路线!): cyclic u8 + records[]:
  每条 = {name, positions:vec3[](中心线), gates:[u16×3](门/检查点索引),
  surface:string(材质名), surfaceIndices:[u16×3], frames[]:{position,forward,up}}
  —— 这就是 AI 行驶线和圈数检查点的原始数据
- `ToMesh/ToEventMesh`: name+prop + u16 索引数+索引 + u16 位置数+位置
- 材质: MtlProperty(mode/ambient/diffuse/specular/power/emissive+4控制器),
  TexProperty(textureOp+名字+寻址/过滤+5个UV控制器+scalar+alpha+property)
- 城镇高速实测: 1343 对象,476 节点,375 网格,34030 顶点;
  TrackObjects = 7 条 ToRoad(正向 RoadObj01/04/08/09 + 倒计 rvs 3 条)
  + ToMinimap + ToDummy'start'(起点) + 4 个音效挂点

## 7. rho5 已破解(rho5_unpack.py)

- 区域密钥 `ru = {KR:'y&errfV6GRS!e8JL', CN:'d$Bjgfc8@dH4TQ?k', TW:'t5rHKg-g9BA7%=qD'}`
- 头/表偏移由**文件名小写字符码和 S** 派生: header=S%312+30, table=header+S*3%212+42
- 密码: AES T-table 变体 PRNG(dk 类,128 字节密钥,4 字节字减法流)。
  注意 T0-T3 用 S-box(表构造细节见 rho5_unpack.py/_nu),字节**符号扩展**进 word
- 文件表项: pathLen u32 + path(UTF-16) + recordChecksum u32 + pipelineFlags u32 +
  offsetBlocks u32 + decompressedSize u32 + compressedSize u32 + md5[16]
- 载荷起点 = 512 对齐(表尾) + offsetBlocks*0x400
- 载荷 flags: &4 前 0x400 字节解密, &2 全量解密, &1 zlib;最终 MD5 校验
- 板车 cotton1 已解出: model.1s(根=ReKart)+ 0/1.png + shadow.png + param.xml
  (BodyParam: ForwardAccelForce=10.0 BackwardAccelForce=50.0 DescStability=30)
