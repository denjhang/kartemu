# 项目记忆(Kartemu)

> 本文档是跨会话的"项目记忆":用户的硬性要求 + 当前正在做什么 + 已确认结论。
> 每次会话开始先读这里;新的重要结论必须写回这里。

## 用户硬性要求(不可违背)

1. **先逆向,后实现**:任何渲染/物理修复前,必须先把对应官方代码语义逆向清楚并写入
   UNDERSTOOD.md,禁止边猜边调。用户多次强调:"老老实实搞逆向"、"你先逆向工程,写入记忆"。
2. **代码是唯一事实来源**:禁止打开 KartSim 游戏做视觉对比("看代码是瞎猜?")。
   不查 CDN,所有代码本地都有。
3. **git 纪律**:自制工具必须全部开源入库(用户明确要求"涉及到的自制工具全部开源",
   打包成 exe 不开源是被批评的行为);kartemu 产物和官方 rho 资源绝不上传(mirror/、unpacked/、*.rho、
   deob_*.js、web/track|kart|character/ 等,见 .gitignore);只提交自研工具/文档/代码。
   完成一个阶段就 commit 并更新文档。
4. **禁止编造用户说过的话**。用户从未说"上下颠倒"。
5. KartRider-Tools 是闭源,不得参考;逆向靠自己。
6. 做完一个任务再做下一个(例如"先单独搞定人物渲染,再做赛车")。

## 总体目标

完整逆向 KartSim(kart.iii.moe),产出合法独立克隆 kartemu:
1 条赛道(城镇高速公路)、1 辆车(板车 cotton1)、1 个人物(皮蛋 dao),
运行时不接触 .rho 档案(使用 unpacked 资产导出物)。

## 当前任务(用户最新指令)

**恢复原版 kart.html 可用状态** —— 已完成(2026-09-12, commit c6f7ce8/0ce2c8e):
黑屏事故已修复(见下节复盘),原版手调完全体(板车+皮蛋+挂件)恢复正常渲染,
three.js 已全部本地化,运行时零 CDN。

**背景**:2026-09-12 凌晨的 ES module 化迁移(kart.html 重构 + web/runtime/ 模块)
因依赖链断裂全部回滚(git checkout 恢复 kart.html,删除 web/runtime/ 等)。
回滚后发生黑屏事故(见下节)。迁移任务本身待环境稳定后**增量**重做
(教训:逆向成果应逐模块合入,不可一次性重写)。

**下一步**:按 FUNCTIONS.md 补齐剩余函数签名(台式机),或增量重启物理/赛道迁移。

## 2026-09-12 黑屏事故复盘(完整经过)

**现象**:回滚迁移代码后,用户打开 kart.html 报"原版也没有任何模型"——纯色背景,
无 3D 内容,UI 停在"加载中…"。用户认为 AI 把原版代码搞坏了。

**排查过程(全部实锤)**:
1. `git status` 确认 kart.html 与提交版本**完全一致**——代码没坏;
2. 资产完好:dao.gltf 内 char_root/f00-f54 全部动画在位,kart.gltf 内 ReKart/zup_root 在位;
3. 服务器 curl 测试 5 个 GLTF + bin 全部 200;
4. 浏览器实测复现关键差异:**同一文件,`localhost:8000/kart.html` 正常,
   `127.0.0.1:8000/kart.html`(纯 URL 无参数)黑屏**。

**根因(三层叠加,缺一不可)**:
1. **浏览器磁盘缓存毒化**:Chrome 缓存按源(origin)分区,localhost 与 127.0.0.1
   是两个独立分区。`127.0.0.1:8000/kart.html` 纯 URL 命中了早期实验页面的缓存
   (铁证:截图里出现了当前文件中根本不存在的"官方状态机(HB 11剪辑)"下拉框
   和"首次按键启动音效"提示——那是已回滚的实验版 UI)。
   纯导航/带 no-cache 头/F5 均无法击穿该缓存条目。
2. **CDN 挂起**:旧缓存页面的 importmap 从 jsdelivr 加载 three.js,国内网络下
   请求挂起 → `import` 永不返回 → 整个 module 不执行 → 停在"加载中…",
   `window.__scene` 为 undefined,什么都渲染不出来。
3. **原版代码隐患**:rAF 循环先于模型加载启动;模型加载失败时 kart.html:326
   每帧抛 `TypeError: window.__setCharAnim is not a function`,把同一循环里
   后面的 `renderer.render()` 拦断 → 连网格背景都不画(黑屏且无任何提示)。
4. **次要因素**:遗留的单线程 `serve.py`(http.server,8:41 启动占用 8000 端口)
   在多标签页并发请求时偶发 `net::ERR_ABORTED`,加重了加载失败概率。

**修复(commit c6f7ce8)**:
- three.js 0.178.0 全套本地化到 `web/lib/`(three.module.js/three.core.js/
  OrbitControls/GLTFLoader/BufferGeometryUtils 共 5 文件);
- kart/index/character.html 的 importmap 改指向 `./lib/three/`(逻辑零改动);
- kart.html 动画状态机加一行加载保护(`&& window.__setCharAnim`),
  模型未就绪时跳过状态机,不再拦断渲染;加载成功后行为完全不变;
- 新 `web/serve.py`:ThreadingHTTPServer(多线程)+ no-store 响应头,端口 8000,
  替换遗留单线程服务,杜绝并发 ERR_ABORTED 与缓存残留;
- 删除遗留空文件 kart_new.html。
- `py_compile` + `node --check` 语法检查通过。

**验证结果**:`http://localhost:8000/kart.html` → "完全体就绪",板车+皮蛋+
头戴摄像机+风镜+气球全部渲染(截图确认;画面中彩虹圆柱是原版代码里
MeshNormalMaterial 的碰撞测试障碍柱,非故障);index.html 赛道页正常;
网络请求全部本地,零 CDN。

**遗留注意事项**:
- **今后统一用 `http://localhost:8000/kart.html`**(localhost 分区缓存干净);
- `127.0.0.1:8000/kart.html` 纯 URL 的毒缓存条目仍在浏览器里(自动化工具无法
  强刷);如必须用 127.0.0.1,手动按一次 **Ctrl+Shift+R** 即永久修复,
  之后 serve.py 的 no-store 头保证不再被缓存;
- trae-preview 注入的 `/@vite/client` 404 无害,可忽略。

## 人物渲染当前状态(截至 2026-09-10)

- `char_gltf.py`:骨骼蒙皮 glTF 导出器(24 骨骼节点 + skin + 32 个动画剪辑)。
  - **已数值验证**:rest 局部矩阵 = inv(world_rest[parent]) @ inv(inverseBind);
    蒙皮语义与官方 skin=world(pose)@inverseBind 完全一致(f45@100ms 顶点偏差 0;
    页面运行时对拍 X/Z 差 <1mm)。
  - **JOINTS_0/WEIGHTS_0 必须 VEC4**(VEC2 会让 three.js 读到 undefined 关节)。
  - localBind 与 inverseBind **不自洽**(|bind_world@ib - I| 最大 2.0),官方
    从不用 localBind 链做绑定,逆向结论:弃用 localBind。
  - 刚性件挂接: local = 纯 m_walked(官方 world[bone]×local;YT.update 返回 world 数组,非 skin)。
  - 根节点 zup_root RotX(-90°): 独立渲染必须有;赛车内挂载时应去掉(父级已有)。
- `web/character.html`:独立查看页(OrbitControls + AnimationMixer + 32 动画按钮,
  自动取景)。当前 body 渲染正确,face 漂浮。
- `s1_gltf.py --character`:旧的单帧 f45@100ms 烘焙导出(曾用于 index.html 骑乘,
  视觉正确),保留作参照。

## 关键逆向结论速查(详见 UNDERSTOOD.md)

- 三空间:D(数据 Z-up)、P(物理=ae(D)=(x,z,-y))、轮廓(u1=Rx(+90°)·world)。
- 赛道/车辆根 rotation.x=-π/2;人物 model.1s 本身 Y-up,**不加旋转**
  (convertClientCoordinates:false)。
- cull:1=双面 2=CW正面 3=CCW背面;det<0 世界矩阵翻面。
- UV:官方 flipY=false + v 原样;glTF 同为左上原点,**不翻 v**。
- alphaTest 只认 AlphaProperty.alphaTestEnable;cotton1 0.png 的 alpha 是涂装遮罩。
- CharSequence:24 通道 PRS;rotation 记录 20B,文件序 (w,x,y,z);线性插值;
  官方**始终播放动画**,缺省通道 pos=0/rot=identity。
- 官方蒙皮:v' = w0·skin[bone0]·v + (1-w0)·skin[bone1]·v,bone1=255 表示无。
- 官方刚性挂接(§18 早先结论,待本次复核):face/head→bone5,handL→9,handR→14。
- 棉花糖骨架:0=seat,1=handle,2/3=前轮,4/5=后轮,6=人物挂点(0,-0.067,0.349),7=port0。
- 转向:右手系 (left-right) 输入;+yaw 朝屏幕左。
- .rho/.rho5 解密已验证(P236 RhoCrypto 对拍一致)。

## 待办队列

0. [新] 深度逆向对照完成(2026-09-13): docs/REV_COMPARE.md, 动画映射/补间、物理/漂移/集气/喷气、音频、速度表/仪表四方向,
   含总差异速查表 + 迁移顺序建议(动画映射修正 -> 力阻力物理 -> 速度表 -> 漂移集气 -> 喷气族 -> 音频)。
   后续实现按该顺序逐模块合入, 每步跑通 kart.html。

1. [已完成] 人物单独渲染(char_gltf.py + character.html, §20)。
2. [已完成] 全方位逆向(§25-§32, 2026-09-11):物理引擎/碰撞系统/赛道构建/AI/比赛流程UI/道具/输入/音效。
3. [已完成] 函数级交接文档(2026-09-11):`docs/FUNCTIONS.md`,核心模块已详述,剩余模块列行号索引。
4. [已完成,后回滚] 2026-09-12 凌晨曾一次性迁移到 web/runtime/ 模块
   (physics/char_anim/input/sound/碰撞等),因依赖链断裂整体回滚。
   **重做时必须逐模块增量合入**:每合一个模块跑通 kart.html 再合下一个。
   工具 `tools/export_route.py`(赛道 ToRoad 路线导出, commit 0ce2c8e)已保留入库。
5. 广告牌背面实心橙(cull 方向/alpha)。
6. 碰撞重做(官方 Z$ 4m 均匀网格 rayQuery + 墙障碍, §26 已逆向, 待实现)。
7. 物理引擎实现(§25 已逆向, 待用 JS 重新实现: stepSubstep/applyLongitudinal/applySteeringAndTires)。
8. 比赛流程实现(§29 已逆向: raceLifecycle 状态机 + HUD + 相机)。
9. 可选:官方 body 贴图合成(Fw/Dw,§20.6 已完整逆向算法);车辆轮子动画。
10. 把 index.html 的骑乘人物换成新的骨骼蒙皮版(挂到赛车子树时去掉 zup_root 旋转)。
11. [已完成] KartRider-Tools v1.2.2 解包(§21)。
12. (台式机继续)补齐 FUNCTIONS.md 中 📌 / ⏳ 标记的函数签名,按行号在 deob_named.js 查找。

## 目录布局(2026-09-10 起)

- 自研工具全部在 `tools/`(15 个 .py);文档在 `docs/`;前端在 `web/`。
- `tools/server.py` 的 ROOT 已改为**项目根**(相对自身上两级),从任何位置启动都行。
- README 已匿名化且**不再包含维护备注**(代理等运维信息只记录在本文件)。

## 基础设施备注(2026-09-10)

- **GitHub 推送**:`github.com:443` 直连超时,本机 `127.0.0.1:7892` 代理可用:
  `git -c http.proxy=http://127.0.0.1:7892 push origin main`(未写入全局配置)。
  远端 https://github.com/denjhang/kartemu.git。
- **大文件清理(已完成)**:早期 commit 曾带入 mirror/*.rho 等官方资源(约 1.2GB),
  已用 `git filter-branch --index-filter` 重写全部历史剔除
  (mirror/ unpacked/ kartspec.csv deob_full.js aria2c.exe archive-index.*
  web/track|kart|character),reflog expire + gc 后仓库 352KB。
  **教训:任何官方资产在 add 前必须先查 .gitignore 是否覆盖**。
- 本地静态服务(两套,用途不同):
  - `python tools/server.py` → http://127.0.0.1:8088(官方镜像,/web/ 前缀映射项目 web/);
  - `python web/serve.py` → http://127.0.0.1:8000(web/ 开发服务,多线程+no-store;
    **用 localhost 打开**,127.0.0.1 有历史毒缓存,见黑屏事故复盘)。
- three.js 已本地化:`web/lib/three/`(0.178.0),页面 importmap 一律指向
  `./lib/three/`,禁止再引 CDN。

## 交付检查流程(硬性, 2026-09-10 两次白屏事故 + 2026-09-12 黑屏事故后)

页面类改动完成后必须依次通过, 缺一不可:
1. `node --input-type=module --check`(语法);
2. 浏览器打开后 evaluate 冒烟: `__scene/info 文本/canvas 数量` 正常;
3. 模拟一次真实交互(按键/点击)再截图确认渲染循环没死。
常见根因:
- 动画循环引用了 .then 回调内块级作用域变量(加载完成前每帧 ReferenceError);
- rAF 循环先于异步加载启动, 加载失败时每帧 TypeError 拦断 renderer.render()
  → 黑屏无提示。循环内对加载产物(如 __setCharAnim)必须先判存在;
- 浏览器缓存毒化: 验证时**必须带 cache-buster 参数或用 localhost 源**,
  否则测到的可能是旧缓存页面(2026-09-12 事故:127.0.0.1 纯 URL 命中
  早期实验页缓存, 页面从 CDN 拉 three.js 挂起, 黑屏误判为"代码坏了")。
