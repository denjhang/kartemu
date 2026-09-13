# Kartemu 深度逆向笔记(UNDERSTOOD)

本文档记录对 KartSim(https://kart.iii.moe/ ,民间 H5 复刻版跑跑卡丁车)主 bundle 的系统性逆向结论,
以及自制克隆(kartemu)推进过程中的全部关键发现。所有结论均直接从反混淆源码 `deob_full.js`
(本地分析用,不入库)对照验证,标注了函数名/字节偏移。

---

## 1. 总体架构

- Vite 打包的单页应用,`vendor-BNZ-sAvg.js` 提供 three.js r178 等依赖,主 bundle ~1.5MB。
- 主类 `UB`(bundle 尾部,class UB @1453783):管理 Ready/赛道选择/车库/比赛全流程。
- 资源层:`/__p3528/resources` 清单 + `/__p3528/archive-index`(zlib 压缩,45MB JSON,
  1622 个 .rho + 4 个 .rho5 DataPack,共 114,362 个文件的元数据:路径/dataIndex/dataKey/size)。
- 渲染层:three.js,但坐标系约定特殊(见 §3)。
- 物理层:完全自研(非物理引擎),定点 float32(`h()` 即 Math.fround 包装),子步长 ≤2ms。

## 2. 资源格式(详见 FORMATS.md)

- `.rho`:块表容器,文件名派生密钥 `adler32(UTF16LE(name)) - 0xa6ee7565`,
  XOR 密钥流(seed=dataKey^0x8473fbc1,逐个 -0x7b8c043f,16×u32LE=64字节),
  Adler-32 校验 **初始 a=0**(非标准),flags bit2=zlib / bit4=加密。→ `rho_unpack.py`
- `.rho5`:region 密钥(KR/CN/TW)、文件名字符和定位表偏移、AES T-table 变体 PRNG
  (dk 类,T0-T3 由 S-box(b) 构建,gk 需按 JS 语义符号扩展字节,解密为 u32 减法流),
  MD5 校验。→ `rho5_unpack.py`
- `.1s`:Object47/Typed27 对象图(marker 0x47aa/new、0x47bb/ref、0x27aa/0x27bb),
  ClassStamp → 类(ReKart=0x78c0249, Relement, ReToonRigid, ReTriList, ReTriStrip,
  ReToonSkinned, ReCharacter, TrackContainer=0x28f90598, ToRoad, TexProperty, …)。
  → `s1_parse.py`(赛道/模型双模式自动识别)
- `.kap`:AI 路径;`track.bml`/`course`:官方路线 XML(<course><road name start end final reverse/>).

## 3. 坐标系(本次最重要的发现)

存在三个空间:

| 空间 | 定义 | up 轴 | 使用者 |
|---|---|---|---|
| **D(数据空间)** | .1s 文件原始坐标 | **+Z** | 资产、场景图、渲染呈现 |
| **P(物理空间)** | `ae(D)=(x, z, -y)`,即 RotX(-90°) | **+Y** | 车辆物理、碰撞网格、路线运行时 |
| outline 空间 | `u1 = Rx(+90°)·matrixWorld` | -Y | 仅卡通描边 shader 内部 |

证据链:
- `ae()` @215695: `{x:v[0], y:v[2], z:-v[1]}` — 物理空间转换,ReTriList 顶点/ToRoad 帧
  全部经它进入物理(k0 碰撞注册、Oa 路线帧)。
- `ex()` @175051(路线图构建):`up = normalize(cross(forward,(0,0,1)))` 再
  `up = normalize(cross(right, forward))` ⇒ 物理空间 up=+Z→(ae 后)+Y。
- `completeCheckpointPose` @1204xxx:把路线帧(已 ae)转回呈现空间用的是
  `(x, -z, y)` = P→D 的逆变换 ⇒ **呈现空间=原始数据空间 D**,官方 three 场景是 Z-up 的,
  赛道场景根节点**不做任何旋转**(节点矩阵直接由 `l1` 设置)。
- 赛车导入 `importVehicle1s` @111784:`root.rotation.x = -Math.PI/2` ⇒
  **车辆 model.1s 是 Y-up 建模**,放进 Z-up 呈现世界需转 -90°。人物同理。
- `l1/N0/uC` 三胞胎(@110559/@291134/@714822,语义相同):
  `matrix.set(basis[0][0]*sx, basis[0][1]*sy, basis[0][2]*sz, tx, basis[1][0]*sx, …)`
  —— basis **行**优先,scale 按列分量相乘,平移原样,`matrixAutoUpdate=false`。

> 自制克隆的工程决策:为迁就 three.js 生态(Y-up),我们的导出器统一走
> W = RotX(-90°)·D(与官方 P 同一旋转),顶点烘焙 + 根节点四元数 [-√2/2,0,0,√2/2]。
> 这是官方世界的整体刚体旋转,不引入镜像;物理/相机全部在同一空间即可。
> (此前误用 RotX(+90°),得到 up=-Y 的世界,是一系列"贴地失败/位置漂移"的根因,已修正。)

## 4. 赛道场景图与渲染语义

- `fx` @194885:TrackContainer = name + scene(Relement 根)+ trackObjects[]。
- `on/vx`:Relement 节点 = name, children[], transform{basis×3, position, scale},
  bounds0, serializedBoundsOverride, cullingTraversalMode, bounds1, rawScalar,
  nodeEnabled, **11 个 slot**,additionalProperty(sa 二进制 XML)。
- 材质描述符在场景树中**父→子继承**(k0 中 `_0x57f386=_0x398332` 初值继承)。
- slot 种类:`texture`(TexProperty:textureOp/name/addressU/V/filters/uvControllers×5/
  alphaController/property)、`backface`(kx:`cull: uint32`,含义 0/2/3=无/剔除背面/剔除正面,
  k0 中 `cull===3` 时交换三角 j,k 两点)、alpha/zbuf 等。
- 渲染在 D 空间直接进行;相机由 KartSim 自行按 D 空间摆放(见 §6)。

## 5. ReTriStrip / 面向 / 镂空(贴图"绿地毯"问题根因)

- 官方 k0 对 strip 的展开是**奇偶交替交换**:
  `even: (a,b,c); odd: (a'=b, b'=a, c)`(indices[i] 与 indices[i+1] 互换),
  再叠加 backface `cull===3` 时交换后两点(reversedTriangleCount 统计)。
- 我们的导出器最初按 list 顺序展开 strip ⇒ 三角形绕序整体错误,配合
  `doubleSided=true`,所有背面都被画出:大树(ReTriStrip,v_tree_set 等 68 棵,
  顶点坐标数百、节点 scale≈0.05)的叶片平面正反两面都渲染,
  从路上看就是一整片"绿地毯"挡住赛道。
- 修复方向:strip 展开加奇偶交换;BackFace cull 映射为 three.js side
  (FrontSide/DoubleSide);带 alpha 通道的贴图(树叶/栅栏/广告牌)用 alphaMode=MASK。
- 数值检验:68 棵树按官方 l1 语义变换后,到 ToRoad 中心线最小距离全部 ≥21m
  ⇒ 官方语义下树不在路面上,证明错在导出绕序/双面,而非树的位置。

## 6. 路线 / 起点 / 门(ToRoad)

- `yx` @197950:ToRoad = cyclic + records[];record = {name, positions[],
  gateIndices[](检查门:每门 3 个 position 索引,ix() @181665 用两门拼出两三角形
  + storedForward 作法线), surface(表面标签:rail/rain/snow/warpnext/shake/wave/
  lensflare/空), surfaceIndices[], frames[{position, storedForward, up}]}。
- `ex` @175051:读 TrackObject "track" 的 sa 属性 `<course>`,按 <road> 引用 ToRoad
  (start/end/final/reverse),构建 section 图(有 branch 分支、闭环),帧全部过 ae。
- 起点 = 第一 section 首帧:`position - forward*0.05`,`up` 由 forward 叉乘重构。
- 官方跑圈/检查点 = gate 三角形与卡丁车位置相交判定(updateLapTiming)。

## 7. 车辆/人物加载与动画

- `Pa` @114837:解析 model.1s → {model, animations}。
- `importVehicle1s` @111784:单一 baseColor 贴图(0.png)y1() 整体赋给所有材质;
  根 rotation.x=-π/2;`rb` 构建 ReKart 子场景;`Zs(rootBounds)` 得 footprint;
  `ba` = KartSequence 动画播放器。
- KartSequence(Yv @20495):55 通道,每通道 {PRSTontroller, VisTontroller};
  PRSTontroller 含 Be 曲线(vec3/rotation/float,keyType 4/5 复合关键帧)。
- CharSequence(Zv @21260):24 通道 + rootChannel + map[],人物动作系统。
- 车上挂点:UB 中 attachmentNodes/attachmentSlot(人物/宠物/装备挂载)。
- 人物贴图注意:character_dao/0.png、1.png 几乎全透明(alpha=0 占 99.99%),
  身体实际颜色走 **palette/characterColorIds 机制**(ReToonSkinned secondaryReference
  调色板对象 + UB 中 characterColorIds),不能直接拿 0.png 当 baseColor。

## 8. 物理(对照自研实现)

- 定点 float32:`h()=Math.fround`;所有状态 {x,y,z} 数组运算,子步 ≤0.002s(`stepSubstep`)。
- 结构:body{position, forward, up, right, linearVelocity, angularVelocity},
  wheels[4]{compression, hit…},runtime(大量调校缓存)。
- 轮子探测 `probeWheels`:4 轮从 body 沿 -up 射线查询 `rayQuery`(Z$ 均匀网格
  4m×4m,cell key=(x>>2)+','+(z>>2),三角形按 minX/maxX/minZ/maxZ 注册,法线 y<0 时翻转绕序)。
- 调校参数直连 kartspec.csv(如 driftSlipFactor, frontGripFactor/rearGripFactor,
  driftEscapeForce, chargeBoostBySpeed, autoChargeLowSpeed 等,见 @1236900 漂移积分)。
- 特殊路面:'MR'/'HW' 接触、dirt/점프(跳跃)/bcharge(充电带)等 surface 标签调校。
- 重生:`completeCheckpointPose` 按 gate 帧重摆 body 并清速度。

## 9. 比赛流程 / 相机

- raceLifecycle(lg):phase = ready→countdown(3-2-1-GO,-6000ms 准备/-3000 数字/0 出发)
  →racing→finish→result;togglePause 带 effectiveTime 补偿。
- 相机:driveCameraman(尾随)/surroundCameraman(环绕)/readyCamera/warpNextCamera;
  countdown "2" 时 switch-drive-camera。fairyFovFactor 等 FOV 特效。
- 雨雪(ReRain/ReSnow)、镜头光晕(ToDummy "lensflare" 唯一 owner)、warpnext 传送带等
  都由 ToRoad.surface 标签触发(aB 准入账本逐一审计 producer→consumer)。

## 10. 自制克隆现状(kartemu web 原型)

- `server.py` 本地镜像 + 静态原型服务(127.0.0.1:8088)。
- `s1_gltf.py`:.1s → glTF(赛道 57 材质组全贴图;支持 ReTriList/ReTriStrip/
  ReToonRigid/ReToonSkinned(绑定姿态)/ReCharacter;alpha 通道→MASK)。
- `web/index.html`:three.js 驾驶原型,W/S/A/D+空格漂移,追尾相机,
  ?cam= 自由相机;车/人模型与贴图管线打通。
- 已验证:赛道整体渲染、起点贴地(R 原点射线检测 below=0)、板车 cotton1 可见。
- 已知待修(按 §5/§8):strip 绕序+背面剔除重做;碰撞仅地面射线,需按 Z$ 网格 +
  墙面障碍重做;转向符号按官方 `integrateStandardOrientation` 校准(用户反馈左右颠倒);
  人物调色板贴图;漂移手感对齐 kartspec。

## 11. 工具链(全部入库)

| 文件 | 用途 |
|---|---|
| rho_unpack.py | .rho 解包(块表来自 archive-index.json) |
| rho5_unpack.py | .rho5 解包(T-table PRNG,MD5 校验) |
| s1_parse.py | .1s 解析(Object47/Typed27 图,赛道+模型双模式) |
| s1_gltf.py | .1s → glTF 2.0 导出器 |
| extract_fn.py | 从 bundle 按函数名/类名提取源码(花括号配平,支持默认参数) |
| extract_kartspec.py | 车辆物理参数表提取 |
| downloader.py / server.py | 镜像下载 / 本地服务 |
| FORMATS.md / README.md / UNDERSTOOD.md | 文档 |

> 注意:study_*.js、deob_*.js、string_table.json 为官方 bundle 的提取/反编译产物,
> rho/贴图/模型等资源均为官方资产,按法律风险要求一律不入 git 库。

## 12. 反编译产物(2026-09-10)

- `deob_pretty.js`(32235 行):字符串 100% 内联后的整包格式化版,语法校验通过。
- `deob_named.js`:在 pretty 基础上做语义重命名(628 处 vendor 导入别名 → three.js 真名,
  867 处函数名 → 逆向确认的语义名),并剥除死掉的混淆器脚手架
  (字符串数组 `_0x5090`、解码器 `_0x5f4c`、洗牌 IIFE、32 处死别名)。均不入库。
- `SYMBOLS.md`(入库):1673 个顶层符号索引(行号/类型/原名/语义名)+
  106 个类的全部方法/属性清单。
- `rename_pass.py`(入库):重命名映射表与生成脚本(映射表本身即逆向成果)。
- vendor-BNZ-sAvg.js(500KB)经 Node 实际加载鉴定:three.js r178 全量 +
  P3528 运行时辅助库,78 个导出已逐一指纹识别
  (Group/Vector3/Matrix4/Mesh/BufferGeometry/PerspectiveCamera/ShaderMaterial/
  Box3/Quaternion/Matrix3/MD5/DXT 常量等),记录于 rename_pass.py 的 ALIAS 表。
- 动态懒加载 chunk:`LocalTimeAttackParameters-CnGQYfTA.js`(kartspec 参数运行时),
  未深挖,后续按需。

## 13. reference/ 参考项目盘点(用户 2026-09-10 提供, 不入库)

| 项目 | 内容 | 对本项目价值 |
|---|---|---|
| kartrider_model_1s_to_obj | 他人写的 model.1s→OBJ(Python, 直接解 Object47 字节流) | ⭐⭐⭐ 独立实现交叉验证我们的 s1_parse;其 `v=1.0-v` 是为 OBJ(左下原点)翻转,反证 **.1s UV 是 D3D 左上原点** → glTF 同为左上原点,官方 flipY=false 直传 v,我们去掉 1-v 翻转的修正得到旁证 |
| KartSpec-main | 内存抓取的 kartspec **参数 schema**(92 项带类型)+ 包加密常量 | ⭐⭐⭐ 与我们 kartspec.csv 前 74 列逐名核对一致(mass=100 等),列名权威化;多出的 18 项是新版参数 |
| KartRider-P236 / P5136 | 韩服官方客户端协议(5136)的 C# 测试服务端(登录/房间/道具/背包) | ⭐⭐ 对"脱离官方客户端"的 H5 克隆不直接可用;若将来做协议兼容/道具系统参考 |
| Launcher_GF/HF/TF/V2 | 各区服启动器源码(AFL), PIN/BML/网络会话 | ⭐ 同上,协议侧 |
| GoKart-master | 古老 C# 服务端模拟器 | ⭐ 历史参考 |
| KartRiderDemoEditor | 录像(demo)编辑器 | ⭐⭐ 将来做幽灵/录像回放时参考其格式 |
| kart-patcher | 跨区客户端补丁/安装器 | ⭐ 不需要 |
| kartrider.api.net / open-api-docs / game-analysis | Nexon API(战绩查询)与其数据分析 | ⭐ 与离线克隆无关 |

结论:model_1s_to_obj 与 KartSpec 立即有用(已用于交叉验证);协议类项目留作道具/多人系统阶段的参考。

## 14. 渲染管线修正落地(2026-09-10 第二轮)

导出器已按官方语义修正并验证:
1. **UV 不翻转**:官方 B0() 对 PNG/DDS 一律 flipY=false 且 v 原样传入;glTF 同为左上原点。
   此前的 1.0-v 翻转是"贴图放飞自我"的根因之一(kartrider_model_1s_to_obj 的 1-v 是为 OBJ 左下原点,反证了我们最初的错误)。
2. **ReTriStrip 奇偶展开**(官方 HS()):偶数步 (a,b,c),奇数步 (b,a,c),跳过退化三角形。
3. **BackFace cull → side**(官方 Wb()):cull 1=DoubleSide、2=FrontSide(默认,继承链初始值 2)、3=BackSide;
   世界矩阵 det<0 时翻面(官方 createTrackMesh 传 determinant()<0 作为 flip 标志)。
4. **顶点色**:vertexData.diffuseColors u32 → COLOR_0(官方 qS(): r=(>>>16), g=(>>>8), b, a=(>>>24)),
   basic stage 中 texel*vPrimary 调制。
5. **alphaTest 只认 AlphaProperty**(blendEnable/alphaTestEnable/compare/alphaRef;
   alphaRef/255 → glTF alphaCutoff,实测 0x7F→0.498)。贴图 alpha 通道不一定是透明度
   (板车 0.png 的 alpha 是涂装遮罩,误加 MASK 会把整车 discard 成隐形)。
6. **Mtl mode 0/1 → KHR_materials_unlit**(官方 basic stage 无光照);mode 2 用 diffuse 调色。
   注意:GLTFLoader 只为顶层 extensionsUsed 声明过的扩展实例化处理器,材质级引用必须在
   文件级 `extensionsUsed` 声明,否则报 "Cannot read properties of undefined (reading 'getMaterialType')"。
7. track.1s 的 AlphaProperty 走模型解析器分支输出(className 字段、无 kind),
   slot_state 需按 `alphaTestEnable in dict` 识别(194 个实例)。

效果:城镇高速公路起点段渲染与官方观感一致(树叶镂空/路灯/旗帜/广告牌/警示墩/远桥),
赛车与人物上车可见;人物体色待调色板机制(characterColorIds)落地。

## 15. 人物调色板落地(2026-09-10)

- 官方机制(deob_named.js Jl 类):`etc_/itemTable.kml`(UTF-16 XML,位于 DataPack1)定义
  `<character name='dao' orgColorId='6'/>` → `<dye id='6' base='255 19 121 219' high='255 0 252 255' .../>`
  (A R G B 字节序)。渲染时 body 材质乘 primary/high 颜色 uniform。
- 导出器 `--character` 模式:节点名 body 的网格单独成组(`0_body`),
  材质 = 0.png × baseColorFactor(19,121,219);脸/手等其余节点保持原色。
- 实测:皮蛋上车,官方蓝。后续可扩展 dye 高光双色与 uniform 换装。

## 16. 转向符号校准(2026-09-10)

- three.js 右手系 +Y-up 中,+yaw 使 +Z 转向 +X,而对沿 +Z 前进的相机而言 +X 在屏幕**左侧**
  ⇒ 原型 `steer=(right-left)*max` 导致左右颠倒(用户实测反馈吻合)。
- 修正为 `steer=(left-right)*max`。页面内模拟按键实测:按 D 1.2s 横向位移 +2.2m(屏幕右),判定通过。
- 官方姿态积分 `integrateStandardOrientation` = Kp(位置积分) + P$(按 angularVelocity
  旋转 body.forward/up/right 正交基);转向力矩符号由漂移/抓地力积分(@1236900 一带)
  经 frontGrip/rearGrip 决定,克隆阶段以屏幕方向校准等价实现。

## 17. 车辆/人物模型系统完整语义(2026-09-10 深挖)

### 17.1 三种内容,三种空间约定(关键!)
| 内容 | 数据空间 | 根旋转 | 依据 |
|---|---|---|---|
| 赛道 track.1s | Z-up | `rotation.x=-π/2`(convertClientCoordinates 默认开, @6397) | track root |
| 车辆 model.1s | **Z-up, 前方=-Y** | `rotation.x=-π/2`(importVehicle1s @2630) | cotton1 rootBounds y=±0.85(前后) z=0~0.81(高); handle z=0.57 高处 y=-0.38 前方; 轮 z≈0.14 贴地 |
| 人物 model.1s | **Y-up, 前方=+Z** | **无**(convertClientCoordinates:false, @13286) | dao z=-0.39~1.83(坐姿腿前伸深度), y=-0.77~0.66(身高) |
⇒ 我们的导出器:**车辆保留根 Rx(-90°);人物必须去掉根旋转**(当前 Bug 根源)。
u1=Rx(+90°) 仅用于 toon 描边 pass 的矩阵换算,不是场景根变换。

### 17.2 车辆层级与挂点(cotton1 实测)
```
ReKart root (children[6] = 人物挂点, t=(0,-0.067,0.349))
├─0 seat (ReToonRigid)
├─1 handle  t=(0,-0.379,0.566)
├─2 wheel0  t=( 0.460,-0.435,0.144)  ← 前轮(转向轮)
├─3 wheel1  t=(-0.460,-0.435,0.144)  ← 前轮
├─4 wheel2  t=( 0.434, 0.497,0.171)  ← 后轮
├─5 wheel3  t=(-0.434, 0.497,0.171)  ← 后轮
├─6 (空名)  t=(0,-0.067,0.349)       ← 人物挂点(官方 add 人物 object 到此)
└─7 port0   t=(0.198,0.822,0.231)
```
- 官方挂载代码: `renderScene.bySource.get(root.children[6]).add(character.object)`(@29570 附近)。
- iparam.xml 的 `attachments[]`(名字→节点映射)用于道具: slot2/3=尾灯, slot16=气球。
- 人物缩放 = param XML `OnCharacterSize` 属性,缺省 1(cotton1 无 → 1.0)。
- 车辆资产清单: model.1s + f00~f03.1s(4 个 KartSequence 动画)+ param/iparam.xml +
  0.png/1.png + shadow.png。**cotton1 没有 f0X 动画、没有 model.jfp**(最老车,无动画),
  车轮转动/转向由运行时 wheelPresentation(t1 类)直接旋转 wheel 节点。

### 17.3 车辆世界摆放(O$ 类 'player-kart')
```
root.position = physics.state  (呈现空间坐标)
root.quaternion = setFromRotationMatrix(makeBasis(right, up, forward))  ← 列
modelMount.scale = visualScale (压扁/拉伸特效)
```
即把物理 body 正交基直接作为局部→世界旋转, 局部 +Z=前方、+Y=上方。

### 17.4 人物链路
- 资产: model.1s + body 贴图(0.png=调色板占位, 加载时 Fw/Dw 与 primaryColor/highColor
  合成最终贴图!)+ face 贴图 fXX.png(+overlay) + 动画 **character_common.rho** 的 fXX.1s
  (特殊人物可用 motionFolder 覆盖)。
- 状态→动作映射(v1 类): 0:f00, 8:f45, 9:f46, 10:f47, 11:f48, 12:f49, 13:f50,
  14:f51, 18:f11, 19:f54(linked 另有 f54 门控)。
- 每帧: 动画集求值 → 24 骨骼矩阵数组 → ① 蒙皮 body(ReToonSkinned) ② 次级蒙皮节点
  ③ 刚性附件复制骨骼矩阵: face→bone5(×2)、head→bone5、handL→bone9、handR→bone14
  (matrix = boneMatrix × (localMatrix 存在时))。
- 人物颜色: 玩家配色 slot2(车身色)/slot70(人物色) → Un(x, id, 0x46) → dye base/high。

### 17.5 克隆待办(按此清单执行)
1. 导出器: 人物模式去掉根旋转(车辆保留)。
2. 人物挂到 kart child[6] 位置(呈现系 (0,0.349,0.067)), scale=1。
3. 骑乘姿态: 解析 character_common.rho 的 f00/f45 CharSequence, 求值到 24 骨骼,
   用骨骼矩阵驱动蒙皮(或先静态取 f45 骑乘帧的姿态矩阵烘焙)。
4. 车轮: 前轮(wheel0/1)按转向角转 Y, 四轮按行驶距离转 X(转速/半径)。
5. 身体贴图合成(可选): 按 Dw 算法用 primaryColor/highColor 上色 0.png。

## 18. 人物渲染管线完整逆向(已数值验证, 2026-09-10)

### 18.1 绑定姿态 ≠ 渲染姿态
dao model.1s 的绑定姿态是"横躺"的(骨架局部上轴=+X), 官方从不渲染绑定姿态——
每帧必播 CharSequence 动画(f00 待机/f45 驾驶...), 由动画把骨架摆正。
⇒ 静态导出绑定姿态必然"躺平", 这就是人物渲染 Bug 的本质。

### 18.2 CharSequence(fXX.1s) 结构(类 CharSequence, stamp 0x1dbb04b7)
- header[3] = {cachedMin, cachedMax, spanMs}(f45: 0/333/334, 循环 334ms)
- **channels[24]**: 每骨骼一个 PRSTontroller(position 曲线 + rotation 曲线)
  - position = vec3 keyType1 fixed: 记录 16B = time u32 + xyz f32×3
  - rotation = rotation keyType1 fixed: 记录 20B = time u32 + **(w,x,y,z) f32×4**
    (官方 R1: value=[f8,f12,f16,f4], 即文件首 float 是 w!)
  - 采样 = 线性插值(R1 对四元数 nlerp)
- rootChannel = IntTontroller(脸部状态机索引); map[] = 状态映射表
- C1() 校验: 必须 24 通道 + rootChannel 为 IntTontroller

### 18.3 骨骼矩阵合成(官方 Sr/mm)
```
pose[i]  = w0(quat_i, trans_i)        # 4x4, 列向量约定, 行主 3x4 存储
world[0] = pose[0]
world[i] = world[parent[i]] × pose[i] # mm(): 标准 A×B
skin[i]  = world[i] × inverseBind[i]  # inverseBind 3x4 行主来自 model.1s bones
v'       = w0·skin[bone0]·v + (1-w0)·skin[bone1]·v   # fm(), bone1=255 表示无第二骨骼
```
- 骨骼层级(model.1s bones[].parentIndex): 0=骨盆, 1-5=脊柱→头, 6-10/11-15=左右臂,
  16-19/20-23=左右腿; 刚性附件(脸→bone5, 手→bone9/14)直接复制 world 矩阵×local。

### 18.4 数值验证(pose_eval.py)
f45.1s @100ms 求值 + 蒙皮 → 顶点云 X ±0.80(左右) / Y -0.59~+0.80(直立身高 1.39) /
Z -0.22~+1.50(坐姿腿前伸 1.72)——标准 Y-up 直立坐姿, 全链公式正确。

### 18.5 人物正确渲染的实施清单
1. 导出器 --character: 蒙皮顶点用 skin[] 烘焙(取 f45 任意帧或全骨骼静态姿态),
   刚性件(face/head/hand)按对应 world 矩阵烘焙; 根节点不加旋转(已改)。
2. 挂点: kart 根 child[6] 呈现系坐标 (0, 0.349, 0.067)(已接)。
3. 身体贴图: 0.png 为调色板占位, 官方加载时按 primaryColor/highColor 合成(Fw/Dw),
   需复刻该合成或先用整片 dye 色近似(当前做法)。
4. 脸部: fXX.png + overlay 合成(sC), 状态由 rootChannel IntTontroller 驱动。
5. 动画循环(可选): 逐帧求值 f45 的 334ms 循环即可获得驾驶摆动。

## 19. 人物渲染落地(2026-09-10)

按 §18 清单实施完成:
- `char_pose.py`: CharSequence 采样/骨骼链/蒙皮矩阵求值模块(§18 公式的可复用实现)。
- 导出器 `--character`: body 蒙皮顶点按 f45 骑乘姿态烘焙(extract_jv_baked),
  刚性件(face→bone5, handL/R→bone9/14)按 world 矩阵烘焙, 脸部用 f00.png。
- 实测(游戏内侧视图): 皮蛋以官方骑乘姿态(前倾握把)坐在板车挂点上, 比例正确。
- 遗留: 广告牌背面渲染为实心橙(cull 方向/alpha 待查); 人物动画循环(可选);
  官方 body 贴图合成(Fw/Dw primaryColor/highColor, 当前用 dye6 蓝近似)。

## 20. 人物骨骼蒙皮 glTF + 完整装配语义(2026-09-10, 修正 §18/§17 局部错误)

### 20.1 空间约定修正(重要!)
- **人物 model.1s 数据本身是 Z-up**(与赛道/车辆一致)。此前"人物 Y-up、不加旋转"的结论错误。
- 官方 `Bw` 装配: `convertClientCoordinates: (context === "card")` ——
  仅立绘(card 肖像, 参见 deob_named.js L19945)才给根加 `rotation.x = -π/2`;
  赛车场景**不加**, 因为人物挂在赛车已旋转的子树(child[6])里, 由父级完成 Z-up→Y-up。
- ⇒ **独立渲染人物必须自带 RotX(-90°) 根节点**;在赛车内挂载时不加(父级已有)。
  漏加即"躺平一坨 + 脸漂在旁边"(本次头/脸错位的根因)。

### 20.2 官方装配(Bw, deob_named.js L13282-13412)
- 递归 `_0x13bd99` 建 three 树: ReToonSkinned→YT(蒙皮几何), ReToonRigid→静态网格,
  其它 Relement→Group;每个节点 setNodeMatrixUC(自身 transform)。
- **刚性挂接表(每帧更新)**:
  - root.children[1](face): `matrix = skin[5] × 自身matrix`(local 在装配时快照)
  - root.children[2](head): `matrix = skin[5] × 自身matrix`
  - root.children[3]: `matrix = skin[5]`(丢弃自身 transform!)
  - root.children[4](handL): `matrix = skin[9]`(丢弃)
  - root.children[5](handR): `matrix = skin[14]`(丢弃)
  注意乘的是 **world[bone]**(YT.update 的返回值是 world 矩阵数组 _0x53cd32,
  不是 skin——skin 只用于顶点蒙皮);元素子树后代的 transform 保留。
  ⇒ glTF 挂 bone 节点下的局部矩阵 = 纯 m_walked(曾误乘 inverseBind 导致脸挂到屁股)。
- 脸贴图传播: `name==='face'` 的子树全部用 face 贴图(f00_0.tga→f00_0.png→f00.tga→f00.png,
  官方 nC 的回退顺序),其余用 body 合成贴图(Fw/Dw)。

### 20.3 官方蒙皮几何(YT 类, L13005-13064)
- 顶点按 **wedge** 去重(position 每 wedge 一个, 由其 skinVertexIndex 的顶点蒙皮得出)。
- `update(pose)`: world[0]=pose[0]; world[i]=mm(world[parent], pose[i])(仅 enabled 骨骼);
  **skin[i] = mm(world[i], inverseBind)**; fm() 双骨骼线性混合(bone1=0xffff 表示无)。
- 构造时初始 pose = bones[].localBind —— **localBind 链 ≠ inv(inverseBind) 链**
  (实测 |bind_world×ib − I| 最大 2.0, 两者不自洽, 官方绑定语义只认 inverseBind)。

### 20.4 官方动作求值(Sr, L3074-3136)
- 每通道: position 缺失 → [0,0,0]; rotation 缺失 → identity 四元数。
- position 记录 16B(time+xyz)线性插值; rotation 记录 20B, value=[f8,f12,f16,f4]=(x,y,z,w),
  插值 g0()(slerp)。时间经 pl(): anchor/phase/frequency 变换(循环控制)。
- rootChannel = Int(脸部状态索引, 直接取左端关键帧值)。

### 20.5 glTF 骨骼蒙皮导出(char_gltf.py, 全链数值验证)
- 骨架: 24 关节节点, 局部静止矩阵 = inv(world_rest[parent]) @ inv(inverseBind)
  (保证静止时 jointMatrix=I;localBind 弃用)。刚性 face 挂 bone5 下,
  local = inverseBind[5] × m_walked(与官方 skin[5]×m 等价, 已证)。
- 蒙皮: JOINTS_0/WEIGHTS_0 **必须 VEC4**(VEC2 → three.js 读到 undefined 关节崩溃)。
- 动画: character_common 全部 32 个 fXX.1s → glTF 剪辑(60Hz 重采样,
  旋转曲线按官方 slerp 语义由 mixer 插值), 状态映射 0:f00/8:f45/9:f46/.../19:f54。
- 根: zup_root RotX(-90°)(独立渲染), 赛车内挂载时去掉该根(用 char_root)。
- **数值验证**: 按 glTF 规范独立重算(解析 dao.gltf+dao.bin), f00@0.5s 与官方
  eval_pose 逐顶点对拍, body 最大偏差 3.6e-5, face 矩阵偏差 2e-5 —— 全链闭环。
- 浏览器实测: 皮蛋站立(f00)+骑乘前倾握把(f45)姿态、脸部贴图、dye6 蓝全部正确。

### 20.6 身体贴图合成(官方 Fw/Dw, L13426-13460, 可选增强)
- body 0.png 与 high 贴图逐像素: high 像素 (255,0,255) 跳过;body RGB>0x7f 处取 highColor,
  否则取原色;与 primaryColor 做.dst 255 混合: `Tr(a,b,m) = a*(255-m)/255 + b*m/255`,
  再与 high 的 RGB 按 high alpha 混合, 输出 alpha=255。当前克隆用整片 dye 蓝近似。

### 20.7 body 贴图合成落地(2026-09-10)
- 0.png 的 alpha 是连续涂装遮罩(实测 0..255 连续),直接当透明度用 → 身体半透明。
- `compose_body_texture()`(char_gltf.py)按 §20.6 算法离线合成:
  body=0.png, high=1.png, dye6 primary=(19,121,219) high=(0,252,255),
  输出不透明 0_body.png 替换材质贴图。实测:皮蛋蓝身+白高光/手套/鞋,与官方一致。

## 21. KartRider-Tools v1.2.2 逆向(2026-09-10, PyInstaller 解包)

### 21.1 解包
- `KartRider-Tools.exe`(136MB)= **PyInstaller + Python 3.13**(cookie 尾部
  `MEI\014\013\012\013\016` + python313.dll)。CArchive TOC 条目为**大端**
  `[elen(u32)][pos(u32)][dlen(u32)][ulen(u32)][cflag(u8)][type(c1)][name]`,
  且**步长 = elen(不含 4 字节长度域)**——与常见 pyinstxtractor 假设不同。
- 解出 301 项 → `reference/kt_extract/`;PYZ.pyz(5.6MB,580 模块)→
  `reference/kt_pyz/`。核心库 `karttools.*`(marshal,3.13 字节码),
  代码树+常量 dump 见 `reference/kt_karttools_dump.txt`。
- 附带 `KartRiderTools.pypv` 是 Cinema 4D SEA 加密容器,非明文。
- rho 解密不在 Python 内,由外部 `RhoLoader.exe`(.NET/WPF)完成,
  输出目录约定 `_rhoOut`/`_rho5Out`(rho5 的目录名会加尾下划线,如 `kart_`)。

### 21.2 与本项目逆向结论的交叉验证
- `parsers/animation.py`:fXX.1s = 6B magic + 6B pad + u32 start + u32 end +
  N×KartObject(PRSTontroller),每骨骼一条 —— 与 §18.2 一致。
- `parsers/model.py`:kart 与 character 的 mesh/dummy 节点头**布局不同**
  (同为 138B/130B 但字段语义不同)——与 s1_parse 两套解析器对应。
  Bone 数据结构 = (index, parent, inv_bind_matrix, local_matrix),
  SkinWeight = 双骨骼 indices/weights —— 与 §18.3/§20.3 一致。
- `parsers/kart_params.py`:param.xml 根 `<BodyParam>` CamelCase 属性
  (ForwardAccelForce/DragFactor/SteerConstraint/Port0/FirePort0...)。
  与 DataPack2 kartspec/param 对应,可作为克隆物理参数第二来源。
- 该工具自身参考了 `_REF/KartRider_Importer V2.1/Import_Kart.py`
  (3ds Max 导入器)——社区已有成熟格式知识链。
- 结论:其对 .1s 的理解与本项目独立逆向一致,可作交叉验证;无新密码学内容。

### 21.3 贴图索引串号修复(2026-09-10)
- 症状: 身体被整片刷成脸部贴图(橙色+眼睛满身), 用户观察到"外设道具/摄像机贴进去了"。
- 根因: `s1_gltf.py get_texture()` 用 `len(self.textures)`(字典大小)当
  glTF 贴图数组索引; char_gltf 手工追加合成贴图(不进该字典)后字典与数组失步,
  之后注册的 f00 拿到错误索引 → body/face 材质互串。
- 修复: 索引改为 `len(self.gltf_textures)`(数组真实长度)。
- 脸贴图说明: dao 的 f00.png 是橙底脸(橙=皮肤), 官方 nC 优先找 f00_0
  (带遮罩变体, 本地未解出), plain f00.png 即官方兜底路径, 用法正确。

## 22. 赛车层级化渲染与轮子演示(2026-09-10)

### 22.1 官方装配(sl/ca, deob_named.js L943-998)
- `sl()` 递归建树: 每节点一个 three Group, `ca()/ab()` 设置局部矩阵
  (basis 行 × scale 列 + 平移, 与 setNodeMatrixUC 相同语义), 层级完整保留。
- 几何: ReToonRigid→sb()(逐面展开 position/normal/uv), ReTriList→ob()。
- 赛车贴图: **无 Fw/Dw 合成**(那是人物 body/high 专用), 直接用模型目录 0.png;
  alpha 通道是涂装遮罩, 无 AlphaProperty.alphaTestEnable 时渲染不透明。
- cotton1 层级(实测与 §17.2 一致): seat/handle(0,-0.379,0.566)/
  wheel0(0.46,-0.435,0.144)/wheel1(-0.46,·)/wheel2(0.434,0.497,0.171)/wheel3/
  child[6] 人物挂点(0,-0.067,0.349)/port0; 车体 bbox X±0.81 Y±0.91 Z0..0.81。

### 22.2 轮子/转向演示(wheelPresentation, L2196-2242)
- 绑定: mainWheels = children[2..5].child[0](ReToonRigid); handle = children[1].child[0]。
- 每帧 update(state, timeMs):
  - `steerVisual = steering × -3`; 转向矩阵 = `i1(-steerVisual)` = RotZ(steering×3);
    `Ra(handle, 转向矩阵)` = 替换 handle basis。
  - 自转 `mainAngle += dt × |v|(水平速度)`(advanceAngles, 注意负向回绕);
    `hd(a)` = RotX(a)。
  - 前轮(i<2) basis = `r1(转向, RotX(mainAngle))`(转向∘自转), 后轮 = RotX(mainAngle)。
  - 轮子平移 = 自身 translation + [0,0,wheelCompression](悬挂压缩, 默认 0)。
  - 外接轮(extWheels attachments[8/9])与外接转向([10/11])同理。
- `ca(obj, transform, translation, basis, scale)`: 官方组合 = 平移/缩放来自源
  transform, **basis 整体替换**。

### 22.3 实现(tools/kart_gltf.py + web/kart.html)
- kart_gltf.py: 层级化 glTF(每节点 local matrix, 6 网格), 0.png 转 RGB 不透明,
  根 zup_root RotX(-90°)。
- kart.html: 转向滑杆×车速驱动轮子(官方矩阵语义: 前轮 steer∘spin, handle 只 steer),
  人物(char_root, 不带 zup 旋转)挂 ReKart children[6], f45 骑乘循环动画。

### 22.4 赛车贴图合成(tu/CC/Dw, L13860-13964)——修正 22.1
- 赛车贴图**同样有加载期合成**(之前"无合成"结论错误):
  `tu(archive, modelDir, t1Name, plateItemId, primary, high)`:
  - t1Name 来自 kartspec/param.xml 的 `t1ImageName`(默认 '1')→ 1.png = 涂装模板;
  - **0.png = 全白底图 + alpha 涂装遮罩**(直接用就是纯白);
  - 无 2.png(副色层)→ 走 Dw(0.png, 1.png, primary, high)(与人物 body 相同算法);
    有 2.png → CC():t1 像素 (255,0,255,255) 跳过、(0,255,255,255) 用 secondColor
    系(source 换 2.png),其余同 Dw。
  - 之后 RC() 叠号牌/号码(蓝 (0,0,255,255) / 白 (0,255,255,255) 标记像素)。
- 颜色来源: itemTable.kml `<kart name='cotton1' orgColorId='4'>` →
  `<color id='4' base='255 58 174 25' high='255 210 255 0'>`(녹색/绿)。
  ⇒ 板车官方配色 = 绿底黄高光,不是白色!
- kart_gltf.py 已实现该合成(复用 char_gltf.compose_body_texture)。

## 23. 挂件/配件系统与完全体装配(2026-09-10)

### 23.1 赛车挂件槽位(visualConfig.attachments, eu() L14019-14036)
17 槽: [0..1]=port0/1, [2..7]=fire0..5, [8..9]=extwheel0/1, [10..11]=extsteer0/1,
[12..15]=lamp0..3, [16]=BalloonPort(默认名 'balloon')。名字来自 param.xml
Port0/FirePort0/... 属性;attachmentNodes = 按名字在模型树找节点。
- **气球(o0)**: 若无 'balloon' 节点则自动创建于 wheel2/wheel3 平移中点。
- 配件模型 = stuff.rho `balloon/<名>/balloon.1s` 等,结构:
  rootRelement→Scene Root→具名槽位节点→ReToonRigid(tex 名在 TexProperty,
  同目录解析,含 @zz/@cn 本地化变体)。

### 23.2 人物槽位与配件
- dao 模型 head 子树内建空槽位 Relement: goggle0/goggle1/muffler/headBand/
  headPhone/pet;handL/handR 下有 handGearL/R —— 配件按槽位名挂接
  (如 headPhone/headCamera01.1s = 头戴摄像机, goggle/2010고글.1s = 风镜)。
- 头饰"整装"则走 costume/model/*.1s 全模型替换(76 套在手)。
- char_gltf.py 现已**完整镜像元素树**(空槽位节点也导出并按 Bw 挂骨骼),
  配件可按名挂载。

### 23.3 号牌/车号(RC/$C/PC, L13909-13933)
- 合成后贴图上的标记像素: 蓝 (0,0,255,255) = 号牌槽(整块替换 45x20 号牌图),
  白 (0,255,255,255) = 车号(叠 number.png 数字集, primary 上色)。
- cotton1: 1.png 上蓝色标记 y27-46 x52-96(45x20)→ 已实现号牌替换
  (stuff2_plate.rho texture/2009@zz.png);车号需 stuff2_ 的
  kart_/common/number.png(该包索引为空, 暂缺)。
- 默认号牌 = 45x20 白底 'SIM'(plateBold BM 字体, 未实现文字渲染)。

### 23.4 实现(tools/acc_gltf.py + web/kart.html)
- acc_gltf.py: 配件 .1s → glTF(层级+TexProperty 贴图+@zz 回退+zup_root)。
- s1_parse.py: 模型解析器补充 Tex/Toon/BackFace/Mtl/Wire 槽位 stamp
  (配件模型槽位含这些属性; TexProperty 注册于函数定义后)。
- kart.html 完全体: 车+人+摄像机+风镜+气球, 各自 checkbox;
  挂点实测 camera→headPhone / goggle→goggle0 / balloon→后轮中点 / 人物→child[6]。

### 23.5 反馈修正四项(2026-09-10)
1. **人物驾驶动画**: f45 是"骑上"过渡(带头部转动), 常驻驾驶应播 **f46**
   (官方状态 9 = f46 驾驶循环, 334ms, 躯干轻微摆动头固定)。
2. **配件贴图全白**: `server.py` 的 /web/ 分支未做 URL 百分号解码,
   韩文/特殊字符文件名(2010고글@zz.png、카메라.png)404 → 材质回退白色。
   修复: translate_path 先 unquote。
3. **气球浮动**: 官方气球分两种 —— `balloon.1s`(静态)与 `balloon_ani.1s`
   (Object01 带 **PrsTontroller**, position 通道 z 0.37→0.81 缓升回落,
   1400ms 循环, 19 键)。acc_gltf.py 已支持 PrsTontroller → glTF 动画;
   气球本体 0..1.13 高, 叠加浮动后飘在车后上方。绳为视觉近似
   (官方资产未含绳模型, 加 0.4m 细黑圆柱)。
4. **车头车号**: 1.png 白标 (0,255,255,255) 两处(x48/x151 y98) = 官方 PC
   车号锚点; number.png 数字集缺失(stuff2_ 索引为空), 用 PIL 等效绘制
   绿底白字数字。cotton1 默认编号 1。

### 23.6 第三轮反馈修正(2026-09-10)
1. **车号对中**: 数字应画在车头徽章圆圈中心。官方白标只是锚点, 圆圈在模板
   1.png 上(亮色圆盘); overlay_number 改为: 取锚点 16px 邻域亮色像素质心为
   圆心, 10x17 格子居中画数字(dye 绿), 不再覆盖锚点像素。
2. **气球位置**: 복주머니(balloon_ani) 是贴车的大福袋, 不是悬浮圆气球;
   换回 2008 圆气球(球径 1.03), 球底抬到人物头顶上方约半头(z=1.03),
   按官方 balloon_ani 的 1400ms 节奏 ±0.2 上下浮动, 细绳(视觉近似)连回
   o0 锚点(后轮中点)。
3. **人物动作选择**: f45 会转头(骑上过渡), 默认改 f00 正常待机,
   页面提供 f00/f46/f45 下拉切换。
4. **页面空白事故**: 编辑时误删 for...of 的 `of` → 模块语法错误整页不执行。
   教训: 改完页面必须 `node --input-type=module --check` 过一遍再交付。

## 24. 人物驾驶状态机完整语义 + 键盘驾驶(2026-09-10)

### 24.1 官方状态选择(deob L2882/2919/2942 + f0/fd/T1)
优先级从高到低:
1. **强碰撞**(collisionStrength>30): 状态 0xa(10)=**f47**, 锁定 1s(lastStrongCollisionMs)
2. **轻碰**(15<强度≤30)/ **落地**(landingTrigger): 0xb(11)=**f48**
3. **加速中** m0()(instantAccel 或 boosterState 1..11/13..16): 前进=**0x12(18)=f11(后仰)**;
   boosterState==0x12(连喷终段)且反向 → 0xe(14)=f51
4. **变身**(visualScaleMode≠0): 0xe=f51(摩托 0x13=f54)
5. |forwardSpeed| < Kr: **0x0=f00 待机**; 速度≈0 但有转向 → fd(): 0x3=f40 / 0x4=f41 / 0x5=f42
6. 前进: fd(rawSteer, tireTransient, reverse) —— **tireTransient≠0(漂移)=f40**;
   steer>0 → f41(非倒车)/f42(倒车侧); steer<0 → 反之; 直行 → 表 0x8/0x9(f45/f46)
7. 倒车(speed<-Kr): 保持基础态(玩家手动观察, 实测 f50=扭头看后)
- 脸部表情: os(sequence.map[state]) 由 rootChannel 整数索引驱动, 随状态换脸。
- 状态→charAniType=1 映射表 A1: 3→25(f40) 4→26(f41) 5→27(f42) 8→30 9→31
  10→32(f47) 11→33(f48) 12→34 13→35 14→36 19→19(f54)

### 24.2 kart.html 键盘驾驶实现
- ↑/W 油门 · ↓/S 倒车 · ←→/AD 转向 · **Ctrl 喷火(N2O)**
- 状态机按 24.1 简化版自动切换: f47 碰撞(撞柱 1s)/f11 喷火后仰/
  f00 待机/f50 倒车看后/f41|f42 转向摇头/f46 直行(下拉可锁手动)
- 喷火: 车尾双锥 additive 火焰(官方 booster 语义); 场地障碍柱触发碰撞;
  追逐相机跟随车。

### 24.3 直行动作修正(f40, 数值验证)
- 症状: 前进时皮蛋频繁"回头/站起来"。录制状态序列证明状态机稳定(f00→f46
  一次切换), 问题在剪辑内容本身。
- 数值验证(bone5 头部旋转通道范围): **f40 rotX ±0.01(头几乎不动)= 官方
  直行骑乘循环**(fd() 直行返回 0x3=f40);f41 rotX 0.01(34ms 单帧转向姿态);
  f50 rotZ 0..0.37(21° 扭头=倒车看后);f11 头固定(后仰);
  f45 rotX -0.05..+0.71 / f46 rotX 0..-0.80(95°!)—— 都是带大幅头部动作的
  "骑上过渡"系列, 不能当直行循环用。
- 修正: 直行 f46 → **f40**;倒车仍 f50;转向仍 f41/f42。

### 24.4 气球官方浮动曲线与惯性(2026-09-10)
- **官方 balloon_ani PrsTontroller 完整 19 键解出**: cycleMode=0(**单次播放**,
  stop=3100ms), z 0.375→0.481(0..1400ms 缓升)→0.381(1400..3100ms 回落落定)。
  即"出场升起→缓缓落定"的一次性曲线, 幅度仅 ±0.05, 不是永久正弦。
  落定后叠加轻微残余抖动(±0.008)。
- **惯性(克隆近似, 官方无对应代码)**: 气球位置用欠阻尼弹簧
  (stiffness=6, damping=3.5)跟随"车后上方目标点", 目标点随车速后移
  (speed/20×0.5) → 行驶时气球拖后、转弯时甩向外侧, 绳每帧锚点→球底斜拉。

### 24.5 气球空气阻力语义查证 + 克隆惯性 bug 修复(2026-09-11)
- **官方源码查证(deob_named.js)**: 气球节点在官方**没有任何空气阻力/风/惯性代码**。
  - `o0()` @L2244-2254: `new Group(); name='balloon'; matrix.makeTranslation(后轮中点);
    matrixAutoUpdate=false; matrixWorldNeedsUpdate=true` —— **节点 local matrix 永不变**,
    每帧只重新算 world(跟着父节点 ReKart root)。
  - 玩家 kart `update()` @L25480-25490: 只写 root.position/quaternion、modelMount.scale、
    `animation.update()`(动画状态机)、`wheelPresentation.update()`(轮/方向盘);
    **没有任何代码每帧写入 balloon 节点的 position/quaternion**。
  - 关键词 `wind`/`air.*resist`/`drag` 作用于气球 —— **零命中**。
    `dragFactor` @L14107 仅车辆物理, 与气球无关。
  - 结论: **官方气球就是静态钉在车身后轮中点的**, "受空气阻力"是用户预期,
    非官方代码语义。`balloon_ani` 是气球本体的姿态动画(z 升起→落定, §24.4),
    不是空气动力学。
- **§24.4 克隆惯性的实现 bug**: 旧实现 `rekart.add(balloonNode)` 把气球挂在 kartRoot
  子树下, target 又写在 kartRoot 局部 `(0, 1.15 - 0.5·speedK, 1.8 + ...)` ——
  弹簧只在局部 y 方向小幅振荡, 车转弯时 kartRoot 整体旋转, 气球作为子节点同步旋转,
  **没有任何"世界空间拖拽"视觉**。这是"气球钉死"的根因, 与官方无关(官方本就静态)。
- **修复方案(克隆近似, 官方无对应代码)**:
  1. 气球从 `rekart` 解耦到 `scene` 根(世界空间), 模型朝向: balloonNode 不旋转,
     innerRoot(bal) 本身已是 Y-up 内层姿态(acc_gltf.py zup_root RotX(-90°) 已转)。
  2. 每帧世界坐标 target:
     - anchor_world = `rekart.localToWorld(__anchor.clone())` (后轮中点世界位置)
     - 车头单位向量 fwd = `(sin(heading), 0, cos(heading))`
     - 风阻反向偏移 drag = `-fwd · sign(speed) · min(|speed|·k_drag, maxDrag)`
       (车前进时气球拖后, 倒车时拖前)
     - 转弯甩动 swing = `right · (-dHeading · k_swing)`, right = `fwd × (0,1,0)`
       (左转 dHeading>0 → 气球甩右)
     - target = anchor_world + (0, height, 0) + drag + swing + (0, lift·2, 0)
  3. 弹簧-阻尼(欠阻尼 stiffness=6, damping=3.5)跟随 target。
  4. 绳: anchor_world → 气球世界位置(每帧重算两端)。

## 25. 物理引擎完整逆向(2026-09-11)

### 25.1 物理主循环(stepSubstep, L23844-L23867)
- 子步约束: `dt ∈ (0, 0.002]` 秒, 用 `h()=Math.fround` 定点 float32。
- motionMode: 0=标准地面, 1=rail(轨道), 2/3=full3D(飞行/MR/HW)。
- 每子步执行序列:
  1. `updateStateTimer(dt)` — 状态计时
  2. `updateDriftLifecycleTimers(dt)` — 漂移生命周期
  3. `scanSpecialRoad(ctx)` — MR/HW 特殊路面探测 (L23883)
  4. `rebuildBodyState(force, torque)` — 清零 staged 外力,投影局部速度 (L23881)
  5. `probeWheels(ctx, is3D)` — 4 轮射线探测 (L23914)
  6. `applyResetSurfaceRequest()` — '리셋' 路面触发重生
  7. (非飞行) `applySuspension` → `applyLongitudinal` → `applySteeringAndTires`
  8. `applyRoadConsumers` — 路面消费者 (bcharge 充电带等)
  9. `applyBoosterChargeSurface` — bcharge 路面直接加 gauge
  10. (飞行) `applyAirState` — 空中物理
  11. `applyDrag` — 阻力
  12. `integrateVelocity(dt, force, torque, extra)` — 速度积分
  13. `accumulateDriftGauge` / `accumulateSpeedGauge` — gauge 累积
  14. `resolvePrimaryCollision` → `resolveStaticObstacles` → `resolveTrackEvents`
  15. `applySupplementalWheelRecovery` — 未触地轮补探 (L23936)
  16. `applySlipAlignment` — 打滑对齐
  17. `integrateStandardOrientation(dt)` — 姿态积分

### 25.2 纵向动力学(applyLongitudinal, L24125-L24167)
- 局部投影: `localForwardSpeed = dot(velocity, forward)`, `localRightSpeed = dot(velocity, right)`
- 前驱方向(投影到地面): `driveDir = hwContact ? -specialNormal·10 : cross(right, avgNormal)`
- **加速**: `force = driveDir · liveForwardAccel · driveScale · forward_input`
  - `liveForwardAccel` 来自 kartspec (ForwardAccelForce)
  - `driveScale` 为外部输入缩放
  - physicsState=1(起步)用 `startForwardAccelSpeed` 替代
  - physicsState 1..11(booster)时 `boostAccelFactor` 乘子
  - physicsState=2(漂移) `driftBoostMulAccelFactor` 额外乘
  - physicsState=10(双喷) `dualMulAccelFactor`
  - `instantAccelerationActive` 时 `instAccelFactor` (低速×2)
  - `oneSubstepDrift` 时直接用 `driftEscapeForce`(漂移逃脱力)
- **倒车**: `backwardAccel · driveScale · reverse_input`(负方向), 0.2s 累积延迟
- **滑行制动**: `slipBrake`(侧滑)/ `gripBrake`(抓地) × 水平速度
- **重力补偿**: forward.y>0.5 时加 90N 前推, <-0.5 时减(上下坡)

### 25.3 转向与轮胎(applySteeringAndTires, L24168-L24257)
- **转向角计算**:
  - `rawSteer` = 输入(-1..1), `steeringInverted` 可反转
  - `maxAngle = rad(maxSteerDeg)` (kartspec)
  - `steeringAngle = rawSteer · maxAngle`
  - 速度敏感衰减: `scale = exp(-(|localForwardSpeed|/steerConstraint) · steeringExponentialScale)`
  - 最终 `steeringAngle = scale · rawSteer · maxAngle`
  - `steeringEnvelope`: 平滑过渡(当前值→目标值取小)

- **漂移判定**:
  - `lateralRatio = localRightSpeed / speed` (侧向速度比)
  - `angularDrift = (angularVelocity.y · Pr) / speed` (角速度/速度)
  - 漂移触发: `|localRightSpeed| > |localForwardSpeed|·1.2` 且 `speed>15`
  - `triggerPhase`: 漂移触发阶段, 持续 `driftTrigTime` (kartspec)
  - `activeDrift`: 正式漂移
  - `driftDecay`: 漂移衰减(2×triggerTimer)
  - `tireEnvelope`: 漂移深度(0→1 渐进)

- **轮胎力**:
  - 前轮力: `F_front = G · (frontGripFactor + offset) · (steerAngle·dirSign - lateralRatio - angularDrift)`
  - 后轮力: `F_rear = G · (rearGripFactor + offset) · (-lateralRatio + angularDrift)`
  - 漂移时乘 `driftSlipFactor · tireEnvelope`
  - dirt 路面: grip factor 从 `_s` 表查偏移, 额外 `_s[0]` 速度平方根衰减
  - 正常(非漂移): `F = G·grip·(steer - lateral - angular)`, 无 slipFactor

- **力矩合成**:
  - 侧向力 = `(F_front + F_rear) · right_dir`
  - 偏航力矩 = `Pr·F_front - Pr·F_rear` (前后轮力臂相反)
  - 滚转力矩 = `-(F_front+F_rear)·driftLeanFactor` (车身侧倾)
  - `cornerDrawFactor`: 非漂移转弯时的额外回正力

### 25.4 N2O/加速器系统(L24371-L24394)
- **gauge 累积**:
  - `chargeBoostBySpeed`: 行驶时自动充能(需 `autoChargeLowSpeed` 以上 + 接地 + physicsState=0)
  - 漂移累积: `driftGaugeWindow` 开启时 `pendingGauge` → `committedGauge`
  - bcharge 路面: 直接 `committedGauge += 1.6`(上限 driftMaxGauge)
  - `tachometerIncGauge`: 行驶充能标志
- **booster 状态**:
  - `startNormalBooster`: physicsState=3, 设 `stateRemainingMs` + `boostTime`
  - `activateChargerIfReady` / `updateChargerExpiry`: charger 使用次数与过期
  - boosterState 1..11/13..16 = 各种加速来源
  - boosterState=0x12(18) = 连喷终段
- **状态→动画映射** (L3026-L3043):
  - boosterState≠0 → f11 后仰
  - 连喷反向 → f51
  - 强碰撞 → f47, 落地 → f48
  - |speed|<Kr → f00 待机
  - 直行 → f40, 转向 → f41/f42

### 25.5 悬挂/轮子物理(probeWheels, L23914-L23935)
- 4 轮从 body 沿 -up 射线(距离 2×di≈0.2m)
- 每轮计算: `compression` (0..2·di), `compressionDelta`, `normals[i]`
- `grounded`: 任意轮触地
- `averageNormal`: 触地轮法线均值(车身姿态基准)
- `roadDescriptor`: 路面标签(dirt/slip/bcharge/점프/리셋等)
- `obstacleRayHit`: 障碍物命中
- `contactRisingEdge`: 本帧新触地 → `landingMotionTrigger`
- MR/HW 接触时射线查询模式不同(3D vs 2D)

### 25.6 碰撞响应(L24505-L24535)
- OBB 碰撞检测后:
  - 法向速度衰减: `linearVelocity -= normal · dot(velocity, normal) · responseFactor`
  - 高障碍物(墙面) vs 普通碰撞区分
  - `collisionResponseMagnitudeB6C` / `collisionMotionStrength` 计算
  - 高强度(>30)→ f47 强碰撞动画, 15-30 → f48 轻碰

### 25.7 特殊路面(L23883-L23913)
- MR(磁轨): 前向加 10N, 用多点采样(9-25 点)取平均法线
- HW(半管): 类似 MR 但 -10N, body.up 直接设为法线
- dirt/slip: grip factor 从 `_s` 表查偏移
- 점프(跳跃): liveForwardAccel=6000, liveDragFactor=0.5
- 리셋(重置): 设置 `railResetRequest` → 触发重生
- bcharge(充电带): committedGauge 直接 +=1.6

## 26. 碰撞系统完整逆向(2026-09-11)

### 26.1 Z$ 碰撞网格构建(L26491-L26539)
- 输入: 三角形数组 `{a, b, c, normal, roadDescriptor, auxiliaryDirection}`
- 预处理: 每三角形计算 `minX/maxX/minZ/maxZ` bounds
- **法线 y<0 时翻转绕序**: `[a, c, b]` 替换 `[a, b, c]`
- **4m×4m 均匀网格注册**:
  - 遍历三角形 bounds 范围, 每 4m × 4m cell 检查三角形是否与 cell AABB 相交 (`Q$` 函数)
  - cell key = `(x>>2) + ',' + (z>>2)` (注意: y=-z 坐标变换, key 用 -z)
  - cells = `Map<key, triangleIndex[]>`
- **拒绝动态 roadDescriptor** (movingSurface): 静态网格不含移动物体

### 26.2 rayQuery 射线查询(L26540-L26575)
- 参数: `origin, direction, allowWall` (allowWall=false 时跳过法线 |y|<0.65 的墙面)
- 计算 ray AABB, 遍历覆盖的 cells, 收集候选三角形(Set 去重)
- 三角形相交测试: `Fu(triangle, origin, direction)` → 返回 fraction(t 值)
- 选择最近命中(fraction 最小)
- 返回: `{point, normal, fraction, roadDescriptor, auxiliaryDirection, surfaceVelocity:{0,0,0}}`

### 26.3 queryObb OBB 查询(L26576-L26606)
- 参数: OBB `{center, halfExtents, axes}`
- 用 OBB 在 X/Z 平面的投影确定 cell 范围
- 遍历 cells 收集候选三角形(Set 去重)
- 三角形-OBB 相交测试: `Bu(triangle, obb)` (SAT 分离轴)
- 返回: 命中三角形数组(每项含质心点、法线、roadDescriptor)

### 26.4 多层碰撞面合并(L26098-L26103)
- 同时查询: `movingSurface`(动态) + `surface`(静态) + `obstacleSurface`(障碍)
- 按 `fraction`(命中距离)选择最近碰撞结果

### 26.5 probeWheels 轮子探测(L23914-L23935, §25.5 已详述)
- 未触地轮子补探(L23936): 对未命中轮子在 body 位置上方 1m 处再射, 判断是否仍被支撑

### 26.6 检查点/门系统(gateTrisFromRecord, L4272-L4284)
- 从 ToRoad record 的 `gateIndices` 取 2 组(每组 3 个 position 索引)
- 构建正向/反向门三角形(正反方向)
- 门三角形法线 = `frames[0].storedForward` (或反向取负)
- `final` 标记: 最后一个 record 的 gate 用于终线

### 26.7 重生系统(L23700-L23722)
- `completeCheckpointPose`: 按 gate 帧重置 body.position/forward/up
- 可选清零 linearVelocity / angularVelocity
- 调用点(L29091): 从当前 section 准备 reset pose → commit route state → 重新同步 presentation

## 27. 赛道构建完整逆向(2026-09-11)

### 27.1 TrackContainer 解析(parseTrackContainer, L4533-L4558)
- 读取 `TrackContainer` 对象: name + scene(Relement 根节点) + trackObjects[]
- 校验所有 trackObjects 均为 TrackObject 类型
- scene 子树包含所有渲染网格(ReTriList/ReTriStrip/ReToonRigid 等)

### 27.2 ToRoad 路线解析(parseToRoad, L4641-L4675)
- `cyclic`: 是否环形路线
- `records[]`: 每条 record 包含:
  - `name`: 路段名
  - `positions[]`: 位置点数组(vec3)
  - `gateIndices[]`: 检查门索引(每门 3 个 position 索引, 至少 2 门)
  - `surface`: 表面标签
  - `surfaceIndices[]`: 表面索引(与 frames 对应)
  - `frames[]`: `{position, storedForward, up}` — 路线帧

### 27.3 Section 图构建(buildRouteGraph, L4101-L4270)
- 输入: trackObjects 数组(含 TrackObject "track" + ToRoad 对象)
- 从 TrackObject "track" 的 sa 属性解析 `<course>` XML
- `<course>` 子元素:
  - `<road name="..." start="..." end="..." final="..." reverse="...">` — 引用 ToRoad
  - `<branch>` — 分支, 含多个 alternative 子树
- **section 数据结构**:
  - `{sequenceIndex, frames[], length, surface, outgoing[], incoming[]}`
  - outgoing/incoming = `{gate, section}` (gate 三角形 + 连接目标 section)
- **road 展开**:
  - start/end 指定 ToRoad records 范围
  - reverse=true 时反向遍历 records, 帧翻转(reverseFrame)
  - 帧全部经 `roadFrameToPhysics`(ae 变换)
  - `routeLength(frames)` 计算总长
- **branch 处理**:
  - 每个 `<alternative>` 递归调用构建子 section 列表
  - 分支入口 gate 连接到父 section, 出口连接到后续 section
  - 第一个 alternative 的帧用于主 section
- **闭环处理**: `_0x5a85ea=true` 时将首 section 入口连接到末 section

### 27.4 起点/发车位置(L4251-L4268)
- `start = firstSection.frames[0]` 经 `physicsToPresentation` 转换
- `position = frame.position - forward · 0.05` (后退 5cm)
- `up = normalize(cross(forward, (0,0,1)))` 再 `normalize(cross(right, forward))`
- 返回: `{sections, firstSection, lastSection, start:{position, forward, up}}`

### 27.5 跑圈/计时(updateRacing + updateLapTiming, L27412-L27444)
- `currentLap` / `totalLaps` 由 coordinator 维护
- `routeProgress > finishThreshold` 时触发 finish
- `updateLapTiming`: 圈号变更时记录 `lapStartedAtMs`, 计算单圈时间与最佳圈
- 最终圈: `finalLapShown` 标志 + "final-lap" 事件
- 完赛流程: finish → switch-surround-camera → play-result-bgm → show-result → return-to-ready

### 27.6 赛道表面标签
- 从 ToRoad record.surface 读取
- 标签种类: rail(轨道)/rain(雨)/snow(雪)/warpnext(传送)/shake(震动)/wave(波浪)/lensflare(光晕)/dirt(泥地)/slip(湿滑)/bcharge(充电)/점프(跳跃)/리셋(重置)
- 在碰撞中被 rayQuery 返回的 `roadDescriptor` 携带
- 物理引擎根据标签调整行为(dirt grip 降低, bcharge 充能等)

## 28. AI 系统逆向(2026-09-11)

### 28.1 关键发现
- **H5 版本无 .kap 文件解析代码**: 搜索 deob_named.js 中 "kap" 无命中。
  推测 H5 版 KartSim 仅实现 TimeAttack(计时赛)单人模式, 不含 AI 对手。
- 无 "opponent"/"rival"/"bot"/"npc" 关键词命中。
- **路线跟踪系统存在**但用于玩家跑圈判定, 非AI导航:
  - `routeStates` WeakMap (L26047): 存储每辆车的路线状态 (section, lap, distance)
  - `updateRoute` (L26248): 更新车辆在路线图中的位置
  - `sampleRoute` (L26203): 采样未来路径点(用于迷你地图/进度条)
  - `mB` Coordinator (L29136): 路线更新协调器

### 28.2 路线状态管理(routeStates, L26047-L26336)
- `routeStates = new WeakMap()` — 以 vehicle 实例为键
- 每个状态: `{section, sectionDistance, lap, ...}`
- `updateRoute(vehicle, body, routeGraph)`:
  - 在当前 section 内投影 body.position 到 frames
  - 超过 section 末尾时推进到 outgoing section
  - 更新 lap 计数(过门时)
- `resetRouteState(vehicle)`: 重置到 firstSection

### 28.3 mB Coordinator(L29136)
- `createCoordinator()` 实例化 `mB` 类
- `run()` 方法: 每帧调用, 更新所有车辆的路线状态 + 处理路面标签
- 不是 AI 决策器, 只是路线跟踪协调

### 28.4 结论
- H5 版 KartSim 是**纯 TimeAttack 单人计时赛**, 不含 AI 对手。
- 若克隆需要 AI 对手, 需自行实现:
  - 路径跟踪算法(建议 Pure Pursuit, 前瞻距离 ∝ 速度)
  - AI 难度分级(反应延迟/精度/速度上限)
  - 道具使用策略(如实现道具系统)

## 29. 比赛流程 + UI 逆向(2026-09-11)

### 29.1 GameApp 主类(L28428-L28530)
- 构造函数初始化: renderer(WebGL), scene, camera(50° FOV/0.1-700m), hud, input, touchControls
- 挂件系统: driveCameraman, surroundCameraman, warpNext, lightFactor, cameraShake, cameraWave
- 比赛状态: raceLifecycle(lg), raceCameraMode="ready"
- 资源: rhoLibrary, p3528Resources, activePhysics, activeTrack, activeCoordinator
- 渲染挂件: activeKartEffects/Trails/DriftEffects/MotionBlur/ZetAir/ShockWave/Exhaust/Crash/Charger
- 环境: activeRain/RainAudio/Snow/Admission/Selection
- UI: activeGameplayUi/Action2D/Result/TimeAttackReady/Taskbar/Settings/TrackSelect/Garage/Pause
- 音频: activeKartAudio/RaceBgm/AudioContext/InterfaceAudio/CountdownAudio
- localStorage: timeAttackRecords(Map), timeAttackReadyOptions(speed=7/booster=0/showGhost=true)
- 主循环: `frame` = requestAnimationFrame 回调, `updateAndRender` 计算有效时间 → 更新物理/赛道/驾驶/相机

### 29.2 比赛生命周期(raceLifecycle / lg, L27347-L27459)
- **phase 状态机**:
  - 0: ready(初始)
  - 1: countdown(倒计时)
  - 2: racing(比赛中)
  - 3: finishAccepted(完赛已确认)
  - 4: result(结算)
  - 5: paused(暂停)
- **countdown 子状态**(L27392-L27411):
  - substate 0→1: startAtMs-6000ms → "countdown-prepare"(准备)
  - substate 1→2: startAtMs-3000ms → "countdown-number 3" + "switch-drive-camera"
  - substate 2→3: startAtMs-2000ms → "countdown-number 2"
  - substate 3→4: startAtMs-1000ms → "countdown-number 1"
  - substate 4→phase 2: startAtMs+0ms → "release-race" + "countdown-go"
- **startAtMs**: `effectiveTime + 7000ms` (7秒倒计时, 含1秒准备)
- **startBooster 窗口**: `|time - startAtMs| ≤ 100ms` (起喷窗口)

### 29.3 暂停/恢复(L27376-L27383)
- togglePause: phase 2↔5 (racing↔paused)
- `pausedTotalMs`: 累计暂停时长
- `effectiveTime(rawMs)`: `rawMs - pausedTotalMs - (paused ? rawMs-pauseAnchor : 0)`
  即暂停时冻结有效时间

### 29.4 圈数计时(L27436-L27443)
- `timedLap`: 已计时的圈数
- 每圈完成: `lapTime = now - lapStartedAtMs`, 更新 `bestLapMs`
- 最终圈: `currentLap == totalLaps` → "final-lap" 事件

### 29.5 完赛流程(L27412-L27459)
1. `routeProgress > finishThreshold` → finish 事件 + switch-surround-camera + play-result-bgm
2. +3000ms → phase 3 (finishAccepted)
3. +3000ms → phase 4, "show-result" (elapsedMs, bestMs, isNewRecord)
4. +8000ms → "return-to-ready"

### 29.6 HUD 更新(L28644-L28656)
- 向 activeGameplayUi 传入: currentLap, totalLaps, elapsedMs, bestMs, speedSlots, boostRatio
- speedSlots: 速度档位显示
- boostRatio: 加速器进度条

### 29.7 相机系统
- driveCameraman (im 类, L12390): 尾随相机, countdown "3" 时切换
- surroundCameraman (wB 类, L27481): 环绕相机, 完赛时切换
- readyCamera: 准备阶段静态相机
- warpNextCamera (xmlAttr$ 类): 传送带相机
- fairyFovFactor: FOV 特效(L23267-L23303)
- cameraShake / cameraWave: 震动/波浪效果

## 30. 道具系统逆向(2026-09-11)

### 30.1 关键发现
- H5 版 KartSim **道具系统非常有限**, 仅实现 booster/charger 相关逻辑:
  - boosterTypes: 1=普通/2=漂移/3=加速器/0xD=区域/0xE=跳跃区/0xF=交付/0x10=磁铁/0x12=播放
  - 道具音效: `sound_/item/magnet/using.ogg` (磁铁, L25562)
- **无传统道具**(飞弹/水炸弹/香蕉皮/蘑菇/乌云等)代码
- **赛道道具有**: itemCube(道具箱)、obstacle(障碍)、event(事件) — L4071-L4094
  - `onlyItemGame` 模式标志控制道具参与
- UI 层有 itemBox 组件(L19221): 道具/物品展示窗口, 含分类 tab、搜索

### 30.2 booster 特效加载(L6826-L6933)
- 按 `boosterTypes`、`attachments`、`boosterWaveType` 解析 `effect/...` 资源
- 挂载到 kart 根节点
- 状态机: `dualVisual`、`exceedActive`, 按状态显示/隐藏特效

### 30.3 结论
- H5 版 KartSim 以 TimeAttack 为核心, 道具系统仅保留 booster/charger
- 完整道具系统需自行实现(参考跑跑卡丁车经典道具设计)

## 31. 输入系统逆向(2026-09-11)

### 31.1 输入抽象层(n$ 类, L22630-L22708)
- 事件: keydown/keyup(全局) + focusin(焦点切换时取消输入)
- 状态: `keyboardActions`(Set) + `touchActions`(Set) + `transitions`(数组)
- `keyMap`: 键码→动作映射表(可自定义)
- `drain()`: 排空 records → 生成 transitions(去重: keyboard 优先于 touch)
- `isKeyboardRepeat`: 用 `releasedKeys` Set 区分真释放与自动重复
- `cancelAll()` / `cancelGameplayInput()`: 焦点丢失/暂停时清空
- `setEnabled(bool)`: 比赛阶段控制

### 31.2 触摸/移动端(u$ 类, L23000-L23117)
- `touchCapable = navigator.maxTouchPoints > 0`
- `usingTouch`: 基于粗指针检测 + 手动切换
- 虚拟按键: pointerdown/pointerup/cancel/lostpointercapture
- 多点触控: pointers Map<pointerId, action>
- **自动前进**: `autoForward` 选项, 触屏时自动按住 Forward
- 全屏支持: requestFullscreen / exitFullscreen
- 暂停按钮: touch 控件内

### 31.3 键码映射(L17381-L17452)
- 默认 keyMap `an`:
  - Forward: ArrowUp / KeyW
  - Reverse: ArrowDown / KeyS
  - Left: ArrowLeft / KeyA
  - Right: ArrowRight / KeyD
  - Drift: ShiftLeft / ShiftRight
  - Boost: Space / ControlLeft
  - Pause: Escape / KeyP
- F6/F7/F8: 调试开关(路面声/音效/BGM)

### 31.4 输入→物理映射
- `rawSteer = (left ? 1 : 0) - (right ? 1 : 0)` (±1)
  - `steeringInverted` 可反转
  - `maxAngle = rad(maxSteerDeg)` (kartspec)
  - 速度衰减: `exp(-(|v|/steerConstraint)·steeringExponentialScale)`
- `forward = forwardInput ? 1 : 0`
- `reverse = reverseInput ? 1 : 0`
- 漂移: driftInput 触发 `delayedDriftRequest` → 下一子步 `triggerPhase`
- boost: boostInput 触发 `instantAccelerationActive`

### 31.5 输入到动画
- 人物状态机(v1 类)基于: forwardSpeed, rawSteer, boosterState, collisionStrength
- 转向输入 → f41(右转)/f42(左转) 头部转动
- 倒车 → f50 扭头看后
- 加速 → f11 后仰

## 32. 音效系统逆向(2026-09-11)

### 32.1 音频配置(cu, L17591-L17602)
- `bgmEnabled` / `bgmVolume` (0-1): 背景音乐开关/音量
- `fxEnabled` / `fxVolume` (0-1): 音效开关/音量
- `enableRoadSound`: 路面声效
- `boostBlur` / `dualBoostAuto`: 加速模糊/双喷自动
- `toonLine` / `shadow`: 描边/阴影
- `keyMap`: 按键映射
- localStorage key: `kartrider-web:p3528:game-options-v1`

### 32.2 音频管理(L17641-L17706)
- `Qm` WeakMap: AudioContext → {options, sounds:Set, bgmTransition}
- `Zt(context, source, group, gain)`: 注册声音源(group="bgm"/"parseTrackContainer"(fx))
- `hu(sound)`: 根据 group 的 enabled/volume 更新 gain
- `Pe(gainNode, volume, time)`: 设置音量(对数尺度, -10000dB→0dB)
- `py(param, value, time)`: setValueAtTime 的对数封装

### 32.3 引擎音效($u 类, L25541-L25628)
- 资源: `sound_/parseTrackContainer/kart/engine_<type>/motor.ogg` (fallback: engine_common)
- 加载: decodeAudioData → AudioBuffer
- `start()`: createBufferSource + createGain, playbackRate=0.25 初始, loop=true
- `update(ms, state)`: 每 64ms 更新
  - `U$(state)` → {pitch, gain} 根据 physicsState/速度计算
  - pitch = playbackRate, gain = 音量
- 其他音效: crash.ogg / shock.ogg / drift.ogg / reset.flac
- booster 音效: boosterStart/boosterDrift/booster/boosterZone/boosterJumpZone/boosterDelivery/boosterPlay
- dualBooster / charger / exceed 音效

### 32.4 碰撞音效(L25643-L25668)
- `playCollision()`: 播放 crash.ogg
- `playSteeringCollision()`: 播放 crash.ogg (转向碰撞, 音量降低)
- `playLandingShock()`: 播放 shock.ogg (落地)
- `playReset()`: 播放 reset.flac (重生)

### 32.5 BGM 系统(ea 类, L28176-L28274)
- 资源:
  - `sound_/bgm/main/single.ogg`: 准备阶段
  - `sound_/bgm/main/game_win.ogg`: 胜利
  - `sound_/bgm/main/game_lose.ogg`: 失败
  - `sound_/bgm/<theme>/`: 赛道主题 BGM (ogg 格式, 多首随机选)
- `selectRace()`: 加载赛道 BGM
- `playReady()`: 播放准备音乐
- `playResult(isWin)`: 播放胜负音乐
- 淡入淡出: 16 步 × 100ms, `transitionStep` 0→15, incoming/outgoing 线性交叉
- `restart()`: 随机选一首赛道 BGM 重新播放

### 32.6 倒计时音效(L28271-L28274)
- `count_n.flac`: 数字音效(3/2/1)
- `count_go.flac`: GO 音效
- `lab_count.flac` / `final_lab.flac`: 最终圈音效

### 32.7 路面音效
- `road/road.bml`: 路面音效配置表(BML XML)
- `road/<name>.flac`: 各路面音效文件
- 按 `enableRoadSound` 开关控制

### 32.8 音频生命周期(L29509-L29580)
- 比赛开始时: 创建/复用 AudioContext → 加载赛道 BGM + 车辆音效 + 倒计时音效 + 事件音效 → `activeKartAudio.start()`
- 暂停: `setPaused(true)` → 停止效果源
- 恢复: `context.resume()`

## 33. 深度逆向对照: 动画补间/漂移集气喷气/音频/仪表 (2026-09-13)

四方向并行逆向成果, 完整报告见 **docs/REV_COMPARE.md**(含总差异速查表与迁移顺序建议)。要点:
- 动画: f41/f42 官方是循环保持非一次性; 倒车直接 f45/f46 按 steer 符号(无 f43/f44); 补间=快照+定时混合(enterBlend 50-400ms 分档, pos lerp + 四元数 nlerp), 一次性动作 span 后自动 returnBlend 淡回(pending 抢占限制); 碰撞按强度分级(>30 f47 锁1s / 15-30 f48 / 更小忽略); 表情 face map 随状态换。
- 物理: 重力 58.8; 2ms 定点子步; 无速度硬 cap(力 vs |v|^2*drag 平衡); 轮胎侧向力 980*grip; 漂移=triggerPhase(关后轮抓地点火)->activeDrift(envelope+slip 削弱)->driftDecay 尾滑; 自动甩尾触发 |lat|>1.2|fwd| 且 v>15m/s。
- 集气: 漂移集气=dt*侧向速度^2, 时间加权 前0.2s x3 / 0.2-0.5s x1.5 / 之后 /(2t); 满槽填氮气槽(值6); 大喷=消耗槽首 physicsState=3 限时; 连喷=尾窗内重按前进(state 2); 双喷 state 0xa(engineGrade>6)。
- 音频: 每源 gain->destination 无总线; 引擎 loop motor.ogg, 64ms 节流, rate=speed*3/256+0.25(cap 1.5); BGM 16 步 x 100ms crossfade; 全资源路径规则见 REV_COMPARE §三。
- 仪表: 表显 km/h=|v|*3.6; 3 位补零 + 19 格条(满 350, >=15 格高段色); key 缓存节流; 无 DOM HUD 全纹理 quad; 无转速表。
