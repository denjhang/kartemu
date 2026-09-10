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
