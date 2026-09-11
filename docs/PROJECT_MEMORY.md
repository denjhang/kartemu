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

**单独把人物渲染做扎实** —— 已完成(2026-09-10):
根因 = 人物数据是 Z-up,独立渲染必须自带 RotX(-90°)(官方 Bw 仅 card 立绘加,
赛车内靠父级子树转换;详见 UNDERSTOOD.md §20)。char_gltf.py 已修正,
浏览器实测站立(f00)/骑乘(f45)姿态、脸部、调色板全部正确,全链数值闭环(≤4e-5)。

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

1. [已完成] 人物单独渲染(char_gltf.py + character.html, §20)。
2. [已完成] 全方位逆向(§25-§32, 2026-09-11):物理引擎/碰撞系统/赛道构建/AI/比赛流程UI/道具/输入/音效。
3. 广告牌背面实心橙(cull 方向/alpha)。
4. 碰撞重做(官方 Z$ 4m 均匀网格 rayQuery + 墙障碍, §26 已逆向, 待实现)。
5. 物理引擎实现(§25 已逆向, 待用 JS 重新实现: stepSubstep/applyLongitudinal/applySteeringAndTires)。
6. 比赛流程实现(§29 已逆向: raceLifecycle 状态机 + HUD + 相机)。
7. 可选:官方 body 贴图合成(Fw/Dw,§20.6 已完整逆向算法);车辆轮子动画。
8. 把 index.html 的骑乘人物换成新的骨骼蒙皮版(挂到赛车子树时去掉 zup_root 旋转)。
9. [已完成] KartRider-Tools v1.2.2 解包(§21)。

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
- 本地静态服务:`python server.py` → http://127.0.0.1:8088(/web/ 前缀映射项目 web/)。

## 交付检查流程(硬性, 2026-09-10 两次白屏事故后)

页面类改动完成后必须依次通过, 缺一不可:
1. `node --input-type=module --check`(语法);
2. 浏览器打开后 evaluate 冒烟: `__scene/info 文本/canvas 数量` 正常;
3. 模拟一次真实交互(按键/点击)再截图确认渲染循环没死。
常见根因: 动画循环引用了 .then 回调内块级作用域变量(加载完成前每帧 ReferenceError)。
