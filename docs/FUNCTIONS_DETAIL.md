# FUNCTIONS_DETAIL — 函数级详解增补 (2026-09-13)

> 本文是 FUNCTIONS.md 的配套详解: §A 物理 / §B-C 碰撞赛道 / §E 输入 / §G 道具 / §F 音效 / §H AI / §I-L 渲染解析数学。
> 全部行号基于当前 deob_named.js (29740 行) 逐一核实。与 FUNCTIONS.md 旧条目冲突时**以本文为准**。

## ⚠️ 全局勘误 (渲染/输入两组 agent 交叉确认)

1. FUNCTIONS.md §I 旧行号(@L110559/@215695/@175051 等)全部来自旧 dump, 当前文件无一命中;
   旧清单中 ae(v)/ex()/u1/l1/N0/uC 在当前文件**不存在**(grep 零命中), 对应物:
   l1/N0 → ca()@989 / setNodeMatrix()@2595; u1 → matPhysicsFromPresentationX90()@2602。
2. §E.3 旧键位表(ArrowUp/KeyW/Space/ControlLeft/KeyP)是错的——真实键位是 dr 表(L17233-17321)
   的 **DirectInput 扫描码**(↑0xC8 ↓0xD0 ←0xCB →0xCD, ShiftL/R 0x2A/0x36, CtrlL/R 0x1D/0x9D,
   Space 0x39, R 0x13=重置); 全局暂停键仅 Escape(L29610)。
3. §H 结论修订: 全文无 AI 对手实现, mB Coordinator(L27257-27319, 类定义; L29135 仅为工厂)与
   routeStates 全部函数均为玩家车路线进度追踪; 唯一"自动输入"是触屏 autoForward(s$ L22714)。

---

# 一、§A 物理引擎增补 (A.5/A.6/A.8/A.10/A.14/A.15 → ✅)

### A.5 applySuspension(dt, force, torque) — 悬挂 ✅
- L24056-24110(定义), 调用点 L23856(stepSubstep 内 grounded||mrContact||hwContact 分支第一步)
- 悬挂系数(tuning 工厂 zC, L14090-14105, 原始数值):
  spring = fround(fround(mass * 58.80000305175781) * 0.5)   // mass*58.8*0.5, 58.8=6g 与重力同源
  suspensionPositiveDamping = 0                              // 压缩方向无阻尼
  suspensionNegativeDamping = spring * 0.20000000298023224   // 回弹阻尼 = spring*0.2
- 坐标系(L24061-24075): force/torque/body.up 全部 P(Y-up)→内部(Z-up)变换 {x, y:-z, z:y}, 输出时逆变换
- 4 轮循环(L24076-24104):
  1. hit[i]=false → s=0
  2. 命中时: damp = compressionDelta[i]>0 ? positiveDamping(0) : negativeDamping(0.2*spring)
     s = spring*compression[i] + (compressionDelta[i]/dt)*damp   (全 fround)
  3. s>0: 沿轮法线投影到 body.up: mag = dot(normal_P, up_P) * s (点积 $$ L25090)
  4. Mt(force_P, up_P*mag); 力矩: 轮偏移表 Vc=[[1,1],[-1,1],[1,-1],[-1,-1]](L23390-23395),
     臂={rawHalfWidth*Vc[i][0], -rawHalfLength*Vc[i][1], 0}, 臂×{0,0,mag} 叉积(Xe)后 Nt(τ, 0.10000000149011612)
     —— 力臂整体缩放 0.1(L24103)
  5. 重力补偿(L24105-24110): Mt(force_P, runtime.gravity * mass) —— 悬挂函数同时负责 mass*g 入 force,
     是接地时重力抵消的唯一入口
- 早退: 系数 undefined 时 throw("P3528 suspension 系数…", L24060)

### A.6 applyDrag(force, torque, is3D) — 阻力 ✅
- L24331-24349; 调用点 L23860(每子步, 轮胎后/积分前)
- 公式: ① airFriction=tuning.airFriction; 线性项 force-=v*airFriction, torque-=ω*airFriction(L24343)
  ② 二次项(仅 is3D||wheels.grounded, L24343-24347): 路面描述符 Ke(roadDescriptor) 形如 "DFd.d"
     (length==5 && slice(0,2)=='DF' && [3]==='.') → DF=(charCodeAt(2)-48)+(charCodeAt(4)-48)*0.1; 否则 DF=1
     q(v,|v|)(速度模长缩放即 v*|v|) → Nt(liveDragFactor) → Nt(dragScale) → Nt(DF)
- liveDragFactor 三处来源: 默认 tuning.dragFactor(L24855); 跳跃路面强制 0.5 且 liveForwardAccel=6000(L23878);
  update() 每帧回写(L23488)。dragScale 默认 1, 仅 setRuntimeScales(L23747)/事件系统改。

### A.8 integrateStandardOrientation(dt) — 姿态积分 ✅
- L24327-24328(1 行); 调用点 L23866(非 3D 分支, applySlipAlignment 之后)
- 三步: ① Kp(position, v, dt)(L25082): p += v*dt 逐分量 fround
  ② visualScaleMode==1(压扁 Z)时 angularVelocity.x=0, angularVelocity.z=-0
  ③ P$(body, dt, free)(L25018-25028) 四元数法: Hy(L25188) 轴变换合成 3x3 → Zy 转四元数 q →
     Yh(L25371-25401) q' = 1/2 q⊗(0,ω), q += q'*(dt*0.5)(dt/2 半角显式), 归一化, Qy 转回矩阵 →
     bo(L25192) 写回 body.right/forward/up
  自正循环(L25020-25027): 最多 5 次迭代; free(=freeOrientationLatch||motionMode===6)或变换后 up.z>=0.5
  即接受; 否则前 3 次迭代 ω.x,ω.z *= 0.1 重试, 第 4-5 次直接置零 —— 地面模式自动扶正到 up.z>=0.5
- ω 经 Yy(L25224) 做 {x, y:-z, z:y} 轴变换进四元数空间

### A.10 applyAirState(force, torque) — 空中物理 ✅
- L24111-24124; 调用点 L23859: 非任何接地时先加重力再强制清 activeDrift/oneSubstepDrift/triggerPhase/
  steeringEnvelope(空中漂移清除实锤)
- 算法: ① 重力: 逐轴 force += m*gravity[axis]/gravityDivisor; gravity 默认 zp=-58.8;
    gravityDivisor 由 triggerEventGravity(L23757-23760)设置, 白名单 [1,1.5,2,3,3.2,5,9],
    触发时线速度/4、角速度/5(低重力跳台)
  ② 角速度阻尼: torque -= ω*30(0x1e)(L24117)
  ③ 自由姿态早退: !freeOrientationLatch && motionMode!==6 直接 return(普通跳跃不扶正)
  ④ 翻滚扶正(free/motionMode6, L24118-24124): upY<0.5(倒扣) → roll=(1-upY)*(right.y>0?90:-90) 滚转力矩;
     fwdY>0.5 → torque.x += (fwdY+1)*90; fwdY<-0.5 → torque.x -= (1-fwdY)*90
- 纯跳跃滞空只有线性 airFriction, 无二次阻力(applyDrag 的 grounded 条件)

### A.14 状态/动画相关函数 ✅ (逐个)
- updateStateTimer(dt) L24395-24396: 秒转毫秒入口(round(dt*1000))
- updateStateTimerMilliseconds(ms) L24399-24404: stateRemainingMs<=0 且 physicsState∉{0,2} → 归 0
  (state2 连喷由 B44 计时器管); 否则递减, 减到 0 即 physicsState=0(所有限时喷气统一出口);
  boostTime = physicsState∈[1,0xb] ? remaining*0.001 : 0(动画用)
- updateDriftLifecycleTimers(dt) L24397-24398(每子步最先, L23850): B50(连喷窗口)>0 递减;
  B44>0 或 physicsState===2 时 B44 递减, B44<=0 且 state===2 → physicsState=0(连喷到期)
- setRoadActionState(id, ms) L24329-24330: physicsState∈[0xd,0x10] 时拒绝, 否则 physicsState=id;
  stateRemainingMs=ms; boostTime=0。调用: MZ→0x10/3000ms(L24290), BS→0xd/1000(L24301),
  JM→0xe/1000(L24307), DJ→0xf/1000(L24318)
- scanSpecialRoad(ctx) L23883-23884: scanSpecialRoadPrefix(ctx,'MR',-2) || (ctx,'HW',-10)。
  Prefix 版: 车头前方 +forward*halfLength+up*di 处向 -up 射 2*di; 命中后按速度分档取采样数
  (≤50km/h→25 点, ≤100→18, ≤180→14, 否则 10), 沿车头矩形 zigzag 打射线, 法线平均 → specialNormal,
  直接改写 body.up/body.forward(HW 再算 right); gravity=specialNormal*jc*6(jc=-9.8); 未命中清 mr/hwContact
  且 gravity 复位
- applyResetSurfaceRequest L23876-23877: 路面 '리셋'(韩文重置) → railResetRequest=true
- applyRoadConsumers(dt, force) L24258-24320 四种路面消费者:
  BH…(L24260-24281): 解析 BH<spd> <x y z>(各3字符), dir=normalize(pos-BH点), v+=dir*(spd/|dir|)*25(0x19)
    且 y 清零 —— 往 BH 点水平吸引
  MZ…(L24282-24291): v=(MZ点-pos, y=0)*spd, setRoadActionState(0x10,3000) —— 磁悬浮吸附
  BSd.d(L24292-24302): boost=(char[2]-48)*10000+(char[4]-48)*1000 再 *3; force=auxDir*boost - v̂*boost*0.7;
    state 0xd/1000
  JM…/DJ…(L24303-24319, roadCooldown 0.3s 节流): JM a.b/c.d → v+=up*Xc(slope)+auxDir*Xc(..),
    Xc(L25418)=(数字1-48)*20+(数字2-48)*2; DJ x/y/z → v={x,z:-y,y:z}; state 0xe/0xf/1000+自由姿态
- applyBoosterChargeSurface L23870-23873: 路面 bcharge → committedGauge+=1.6/子步(2ms 子步=每秒+800)
- applySlipAlignment L24321-24326: forwardOneShot && 路面 slip && B44>0 → 速度一半对齐车头切向;
  末尾 forwardOneShot=false
- updateTachometerIncGauge L23874-23877: 行驶自动充能总开关(chargeBoostBySpeed≠0 && driftMaxGauge≠1
  && 接地 && physicsState===0 && !漂移窗 && kmh>=autoChargeLowSpeed)
- updateInstantAccelerationGauge(dt) L24669-24680: 激活时 instantGauge-=1000*dt(1 秒烧完);
  否则按 chargeInstAccelGaugeByGrip(state0)/ByBoost 速率按满槽比例充
- updateInstantWallCharge(nowMs) L24681-24698: 撞墙回充 instant gauge, 冷却+掉速阈值双门槛
- updateResetGaugeRefill(dt, nowMs) L24704-23723: 重生/撞墙后集气回填, 前 0.5s 内 2 倍速灌入,
  之后一次性补齐; beginResetInitiation(L23698-23699)设 resetRefillInitial=1.01
- updateCollisionGaugeOwners(obstacle) L24631-24632: 碰撞时 beginWallCollision+beginInstantWallCharge

### A.15 漂移相关函数 ✅ (逐个)
- handleDrivingCommand(cmd, snapshot) L23576-23601; 上层分发 L29019-29075(仅 Racing 透传 L29057):
  drift-start(L23578): driftDecay<=0 才允许(activeDrift=true, triggerPhase=true,
    driftTailLatch=localForwardSpeed>0); 未接触地面 → delayedDriftRequest=true(触地补触发)
  drift-stop(L23581) → stopDrift()
  use-item-or-booster(L23584) → startNormalBooster+armDualBooster
  instant-acceleration(L23587): instantGauge>=MinUsable → instantAccelerationActive=true
  forward-down(L23590): forwardOneShot=true; 连喷: B50>0 → B50=0, B44=driftBoostTick/1000||0.5,
    physicsState=2, stateRemainingMs=0
  forward-up(L23593): physicsState∉[0xd,0x10] → physicsState=0
  reverse/reset/unsupported → no-op
- updateDriftChord(down, emit, key) L17212-17224(输入类): down 需 rawDriftHeld && rawSteer!==0 才发
  drift-start{direction: sign(rawSteer)} + derivedDriftHeld=true; up 发 drift-stop{active: rawDriftHeld}
- stopDrift L23733-23738: dirt 路面且 activeDrift 且 roadTransient<=0 时
  roadTransient=10*(bodySpeed/120)^2; 无条件 activeDrift=false, delayedDriftRequest=false;
  不清 triggerPhase/driftGaugeWindow(窗口继续集气)。hardCancelControls(L23739)才额外清
- accumulateDriftGauge(dt, is3D) L24358-24368: 守卫 接地 && driftGaugeWindow && fwdSpeed>=0;
  driftMaxGauge===1 直接 pending=1; 否则 inc=rs^2*dt(侧向速度平方), is3D*2; �- startNormalBooster(snapshot) L24382-24386: 守卫 state∈{0,0x12} && forward>0 && speedSlots[0]===6;
  消耗槽(shift+push(-1)), state=3, stateRemainingMs=normalBoosterTime; 未锁赛 resultBoosterCount++/
  charger 计数 + activateChargerIfReady(L24387-24392)
- startRaceBooster L23690-23693: state===0 且起步窗 -> state=1, startBoosterTimeSpeed
- startPlayBooster L23696-23697: raceMotionLocked && rawDriftHeld -> state=0x12, 1000ms
- armDualBooster L24412 / refreshDualBoosterReady L24414-24429 / classifyDualBoosterReady L24430
  (太晚+50ms=3 / 太早=2 / 低速=4 / 就绪=6 / auto=7 / 手动=8) / updateDualBooster L24405-24411
  (state6 且进窗 -> physicsState=0xa, dualBoosterState=5, dualMode=3)
- updateModeInventory(氮气槽) L23725-23730: 满槽消费 -> 第一个 -1 槽填 6, state.nitro=值为6的槽数

---

# 二、§B 碰撞 / §C 赛道 增补 (B.6-B.11, C.6, C.8 -> ✅)

### B.6 resolveTrackEvents(ctx) ✅
- L24614-24623; 调用 L23866。queryEventObb(secondaryCollisionBox()) 命中后:
  scalePercent -> triggerEventScale(白名单 100/320, 缩放比=值/100, 非法 throw, L23749-23756);
  gravity -> triggerEventGravity(白名单 [1,1.5,2,3,3.2,5,9], 触发时速度/4 角速度/5, L23757-23760);
  effect -> trackEventEffectRequests.push({effect, atMs})
- secondaryCollisionBox() L24624-24630: center=pos+up*rawHeight, halfExtents=[hw*sx, hl*sy, 0.7*height]

### B.7 queryEventObb / queryObstacleObb ✅
- queryObstacleObb L26058: 委托 obstacleSurface(Jp 网格, commitObstacleSnapshot L26080, <=8 个障碍,
  registerObstaclePair 半径=modelRadius*4)
- queryEventObb L26091-26097: 遍历 activeEventRuntimes(commitEventSnapshot L26089, <=8 个 UR),
  UR.firstOverlap(L16842): 需 isCollisionReady + animator.firstOverlap(三角形级 jR SAT L16889) +
  state.firstOverlap(L16868, armed 一次性消耗), 返回 {effect, scalePercent, gravity, sound};
  effect 带 consumeEffect 节流(tickMs 冷却 L16851)

### B.9 Fu(triangle, origin, direction) 三角形-射线 ✅
- L26688-26703, 标准 Moller-Trumbore(fround, epsilon Zh=0.0001 L25969):
  e1=b-a, e2=c-a; p=dir x e2, det=e1.p; |det|<1e-4 -> undefined;
  u=(origin-a).p/det, u 超出 [0,1] -> undefined; q=(origin-a) x e1, v=dir.q/det, u+v>1 -> undefined;
  t=(e2.q)/det, t∈[0,1] 返回 t。辅助: qt 减 L26849 / Qo 叉积 L26869 / Ne 点积 L26865

### B.10 Bu(triangle, obb) 三角形-OBB SAT ✅
- L26657-26686。预处理: 三顶点平移到 OBB 局部(eB 点积 L26711)。轴集合:
  ① 9 条叉积轴(三边 x 三单位轴, L26667-26675, 投影测试 tB L26705: 区间 vs sum(he[i]*|axis[i]|))
  ② 3 条 OBB 主轴(顶点 min/max vs ±he, L26676-26680)
  ③ 1 条三角形法线轴(n=e20 x (c-a), OBB 角点区间与平面带相交, L26681-26685)
  全通过 -> true。调用点 Z$.queryObb

### B.11 Q$(三角形-AABB) ✅
- Q$ L26627-26629 = !ig(tri,box) && ig(box,tri); ig L26631-26638 逐边;
  J$ L26640-26655: 点-半平面分类(X/Z 平面, 叉积符号 0/1/-1)。用于 Z$ 网格 4m cell 归属(B.1)

### C.6 roadFrameToPhysics / physicsToPresentation ✅
- dataToPhysicsVec L5262-5268: 数据 [x0,x1,x2] -> 物理 {x:x0, y:x2, z:-x1}(勘误: 旧文"经 ae 变换"不准确)
- roadFrameToPhysics L4287-4293: position/forward/up 三字段各过 dataToPhysicsVec
- physicsToPresentation L4309-4316: 逆变换 (x,y,z)->(x,-z,y); reverseFrame L4318: storedForward 取反
- rx(L4295-4307) 分支帧原样拷贝(分支帧此前已换算, L4211)

### C.8 routeLength / routeProgress ✅
- routeLength L4325-4329: sum(dist3) 逐步 fround; dist3/len3 L4331-4344
- updateRoute L26248-26313: 状态 {section, lap, localDistance, completedDistance, distance}(WeakMap L26047)
  前进扫描: 对当前 section 的 outgoing 用 th(gate, pos, vel)(L26786, 相对门三角形射线测试 og, 按 vel.gate.normal
  符号 +-1)判过门 -> completedDistance += section.length 切段; 圈数: 新 section==firstSection 或过 gate.final
  且 lap==lapTarget -> lap+=1(L26267); 后退扫描对称(L26280-26303); 迭代>sections.length*2 抛错防死循环;
  localDistance = projectSectionDistance(L26320-26335, 沿 frames 投影 clamp [0, section.length])
- routeProgress 即 lap 计数(非距离): updateDriving L28662 传 routeProgress=routeState.lap;
  终点触发 countdownSubstate===4 && routeProgress>finishThreshold(L27414)

---

# 三、§E 输入系统 -> ✅

> 类: n$(键盘 L22627-22709) / u$(触摸 L22960-23117) / 键盘状态机 nP(L17113-17228) /
> 自动前进 s$(L22714-22748) / 布局编辑器 a$(L22756-22896) / 物理子步 k$(L23465)

### E.1 动作枚举 ft(L17097-17112) 与绑定表 dr(L17233-17321) ✅
- ft: SteerLeft=0 SteerRight=1 Forward=2 Reverse=3 Drift=4 UseItemOrBooster=5 ReorderItems=6
  SecondaryItem=7 GaugeState=8 DisplayMode=9 Help=0xa Reset=0xb ModeImpulsePositive=0x19/Negative=0x1a
- dr: 22 个绑定 {index, action, defaultKeyCode}, 键码为 DirectInput 扫描码:
  0xCB(←)SteerLeft / 0xCD(→) / 0xC8(↑)Forward / 0xD0(↓)Reverse / 0x2A(ShiftL)Drift /
  0x1D(CtrlL)UseItemOrBooster / 0x38(AltL)ReorderItems / 0x2C(Z)SecondaryItem / 0x39(Space)GaugeState /
  0x13(R)Reset / 小键盘 0x4B/0x4D/0x48/0x50 副方向 / 0x36(ShiftR) / 0x9D(CtrlR) / 0xB8(AltR) /
  0x2C(Z)ModeImpulsePositive / 0x2D(X)Negative / 0x17(I)DisplayMode / 0x3B(F1)Help
- an(L17322)=index->扫描码映射; cy(L17326-17451) 扫描码->显示名/可否绑定; sP(L17452-17568)
  KeyboardEvent.code->扫描码反查; oP(L17582) 自定义键位校验(恰 22 绑定); vo(L22618) code->动作数组
  (一键多动作); X5(L22550) 键位占用检测。F6/F7/F8=road/fx/bgm 开关(dy L17604); 暂停仅 Escape(L29610)

### E.2 n$ 键盘类(L22627-22709) ✅
- 构造: keydown/keyup(window, passive:false)+focusin; 字段 records[]/transitions[]/releasedKeys Set/
  keyboardActions Set/cancelled/enabled/keyMap=an; r$=0x1f(31)=record 上限
- drain()(L22643-22656): 键盘 record 经 vo 展开动作 append; 返回 {transitions, cancelled} 并复位
- onKeyDown(L22679): 目标非输入框(Nc L22711)才处理; 命中映射 preventDefault; 非自动重复才入队
- isKeyboardRepeat(L22689): e.repeat && !releasedKeys.delete(code) 区分真释放与自动重复
- append(L22699): touch 正按住同动作则不产 transition(touch 优先); cancelGameplayInput(L22692)
  清全部并 cancelled=true(下游 physics.cancelControls, L29072)

### E.3 u$ 触摸类(L22960-23117) ✅
- DOM: pad 修饰键组 Drift/UseItemOrBooster/GaugeState + 方向组 Forward(带 AUTO)/SteerLeft/Reverse/SteerRight
- bindButton(L23032): pointerdown->preventDefault+useVirtualInput+setPointerCapture+pointers.set;
  同动作多指针只报一次 onAction(true); 最后一个指针释放才 onAction(false)
- autoForward=d$()(localStorage kartsim.auto-forward); drivingPadVisible(L23064) 联动暂停/菜单
- 模式切换: useVirtualInput(L23073)/onTouch(L23105) 任意 touch 启用; 键盘命中动作 -> usingTouch=false
- a$ 布局编辑器: localStorage kartsim.touch-layout, 校验 x,y∈[0,1] w,h∈[44,144](L22931-22952)
- s$ 自动前进(L22714-22748): setRaceState(available, armed=Countdown|Racing 且非起步喷窗 L29074);
  isActive=engaged && reverse===0; apply(L22726) engage 时强制 forward=1; 键盘 forward-down 取消 armed

### E.4 键盘状态机 nP(L17113-17228) ✅
- 字段: held 标志/forwardSource/reverseSource/rawSteer/swapForwardReverse/invertSteering/
  actionMarkerWord/forwardBatchGate/driftPressCount(0xffff 回绕)/driftReleaseMarker
- dispatch(L17128): Forward 批处理门(gate 置位时只更新 forwardBatchDown 并 break)
- dispatchOne(L17169-17211): SteerLeft down->setRawSteer(1), up->rightHeld?-1:0; Right 对称;
  Forward/Reverse 写 source+位标志(Qe(word,0x1,0x2 / 0x4,0x8))+cb forward-down/up 等;
  Drift down: driftPressCount=(+1)&0xffff; UseItemOrBooster->{kind:'use-item-or-booster'};
  Reset->{kind:'reset'}; GaugeState->{kind:'instant-acceleration'}; Reorder/Secondary -> unsupported-action
- updateDriftChord(L17212): 见 A.15; setRawSteer(L17225): 位标志 左0x10/0x20 右0x40/0x80 互斥对
- snapshot()(L17140-17152): {forward, reverse(经 swap), steer=rawSteer*(invert?-1:1), rawSteer,
  steeringInverted, rawDriftHeld, derivedDriftHeld, actionMarkerWord}; getDriftEdgeMetadata(L17164) =
  {pressCount, released}(连喷/双喷窗判定)

### E.5 输入->物理链路 ✅
- drainDrivingInput(nowMs, dt)(L29070-29075): input.drain() -> cancelled 联动 drivingInput.cancel()+
  autoForward.cancel()+physics.cancelControls()+灯光复位 -> autoForward.setRaceState -> dispatch
  (cb 经 autoForward.dispatch -> handleDrivingCommand)
- handleDrivingCommand(L29019)= handleBaseDrivingCommand(L29028: drift/forward/reverse ->
  physics.handleDrivingCommand(cmd, getDrivingSnapshot()) + activeLampFlares.setInputPair 前后灯)
  + handleTimeAttackDrivingCommand(L29045: 起步喷窗内 forward-down->startRaceBooster(),
  forward-down 再 startPlayBooster; reset->initiateSpeedReset(true))
- getDrivingSnapshot()(L29026)= autoForward.apply(drivingInput.snapshot())
- mB.run(L27296-27308): 注入 input, core 依次跑 GoTrack->GoCourse->GoPlayKart->GoItemObstacle[]->
  GoItemEventObject[]; GoPlayKart.slot12(L27272) 内 kart.update(nowMs, input, track) —— 物理步进唯一入口;
  缺快照直接 throw(L27274)
- k$.update(L23483-23491): clock.advance()(L23340) 把帧时长切 2ms 定点子步(单帧<=500ms);
  每片 stepSubstep(sliceMs*0.001, input, track)
- 快照消费: applyLongitudinal input.forward/reverse; applySteeringAndTires rawSteer*(invert?-1:1) +
  速度衰减 exp(-(|v|/steerConstraint)*steeringExponentialScale)(L24179-24180); 空闲快照常量 x$(L23380)

---

# 四、§G 道具系统 -> ✅

> 关键结论: H5 版无传统对抗道具(水弹/水雷/导弹/香蕉/乌云/磁铁本体均无运行时代码), 仅保留
> booster/charger 体系、赛道 itemCube/obstacle/event 数据通道、音效/特效资源位。

### G.1 数据通道 ✅
- tx(root, mode)(L4056-4085): object type 属性分 itemCube/obstacle/event; time-attack 跳过 itemCube
- auditTrackObject(L27053-27170): ToItemCube -> item 模式 cube-grant-unclosed(发放未实现 L27109);
  banana/ltejump/mine/waterMine 类型名存在但一律 excluded-nonboost-item-runtime(L27126);
  obstacle -> TimeAttack snapshot(pair capacity 8); event -> 特效+独立音
- UI itemBox(drawItemBox L19227)是车库装备窗口, 与比赛道具无关

### G.2 event 道具 ✅
- resolveTrackEvents(L24614, 见 B.6): scale(100/320)/gravity(白名单, 速度/4 角速度/5)/effect 请求
- GameApp 消费(L28581): consumeTrackEventEffectRequests -> activeTrackEventEffects.trigger

### G.3 obstacle ✅
- resolveStaticObstacles(L24505-24613): normal.y>0.65 高障碍->速度反射+angular response(L24645);
  低障碍->applyCollisionDriftGaugePreserve(false)(charger 激活保留 100% 集气); |响应|>10 -> crash 特效;
  pressMode hard-stop -> activateHardPress(L24643, 压扁+500ms); directional -> 2000ms(L24641)
- 自动重生: advanceAutomaticResetTimer(L24637): 低/高碰撞 1s、障碍 0.4s 累计 -> initiateSpeedReset(false)

### G.4 booster/charger ✅
- (详见 A.14/A.15) state: 0无/1起步/2连喷/3大喷/0xa双喷/0xd..0x10 区域跳跃交付磁铁/0x12起步道具喷
- charger: activateChargerIfReady(L24387) uses/count 达标激活, expiry=now+chargerSystemUseTime;
  加成: 漂移集气 x driftGaugeFactor、低速集气 +Added、碰撞保 100%、超负荷充能 +Added

### G.5 道具音效联动 ✅
- $u.load(L25555-25564) 状态码音效表: 1=boosterStart/2=boosterDrift/3=booster/0xd=boosterZone/
  0xe=boosterJumpZone/0xf=boosterDelivery/0x10=item/magnet/using.ogg(磁铁, 唯一 item 音效)/0x12=boosterPlay
- 引擎>6 另有 dualBoosterReady/dualBooster/charger/exceed(L25565-25568)
- playCollision 节流 2000ms; playSteeringCollision 中断引擎音; playLandingShock gain=strength*0.04

### G.6 动画/特效联动 ✅
- Rl.load(L6826-6916): effect/booster|boosterFlare/<type>/*.1s + boosterDual(_S)/boosterDualReady(_S)
  + 四种 boosterWave/exceedWave; Rl.setState(L6917): dualVisual none|ready|dual
- 每帧(L28577-28589): kartView.update 返回动画槽 -> setAnimationSlot(0..6)(L23761); 压扁
  setVisualScaleMode(L24438)+updateVisualScale(L24448, pn 表插值 <=600ms 恢复)

### G.7 未找到的道具功能 ✅(明确列出)
- 水弹/水雷/导弹/香蕉/乌云/磁铁本体/道具箱发放(cube-grant-unclosed)均无运行时代码;
  ReorderItems/SecondaryItem 有键位(dr index 6/7)但 dispatchOne 落入 unsupported-action(L17205),
  GameApp 无处理分支。道具模式准入 onlyItemGame(L4088) 审计预留, H5 仅实现 TimeAttack/速度赛

---

# 五、§F 音效系统 -> ✅ (函数级增补, 全景见 REV_COMPARE §三)

> 基础设施: Qm(ctx->状态 WeakMap L17637) / Nh(gain->sound L17638) / my(param->音量 L17639)

### F.1 核心函数 ✅
- ts(context) L17679: 取/建条目 {options: cu, sounds: Set, bgmTransition: false}
- Zt(ctx, source, group='parseTrackContainer', gain) L17663: 注册总入口, source->gain->destination,
  ended 时自动注销+disconnect。调用点: $u 全部/ea(group bgm)/Nu/_u/uu/du
- hu(sound) L17688: 按 group 选 bgm/fx 开关音量, 写 py
- Pe(param, volume, time) L17695: 带记忆音量设置(外部改音量唯一入口; 引擎/BGM 淡化都走它)
- py(param, value, time) L17702: dB=trunc(-log(1/v)*1000), setValueAtTime(10^(dB/2000)) 量化复刻 float32
- dn(ctx, options) L17641: 应用新设置, 跳过 bgmTransition 中的 bgm 组
- Jm(ctx, on) L17651: bgmTransition 标志; 置 false 时 bgm 组 volume 归 1
- hP(ctx) L17659: enableRoadSound 查询; $n(src, loop) L17887: loop 设置+loopEnd 溢出修复

### F.2 $u 类(单卡全套, L25497-25828) ✅
- static load(L25541): motor=engine_<type|common>/motor.ogg(数量!=1 抛错); booster 状态表 L25555-25564;
  engineGrade>6 才加载 dual/charger; transforming 经 W$(L25883) 车种回退; road.bml 经 V$(L25842);
  boosterDeliveryEnabled 排除 castle_I01/nymph_I01/I02(L25604); decode 并行, 失败关自建 ctx
- start(L25613): 幂等; resume(); motor $n(loop)+rate 0.25+gain 0
- update(ms, speed)(L25619): motorInterrupted 重启; 节流 64ms(0x40); U$ 映射(L25894):
  pitch=x<128 ? x*3/256+0.25 : 1.5; gain=x<64 ? x*3/256+0.25 : 1
- playCollision(L25643): !source && strength>0 且距上次>2000ms(G$ L25838); gain=N$(L25830)=
  min(1, max(0.1, strength*0.1)); playSteeringCollision(L25652) 先杀 motor(motorInterrupted=true);
  playLandingShock(L25661) gain=clamp(value*0.04, 0.1, 1)
- setState/updateStateSource(L25669/25696): 状态变化换 stateBuffers(0xa 走 dual 通道, 0xF 未启用不换);
  dualSourceMode 0 无/1 ready/3 active(L25704-25727)
- setDriftActive(L25755): drift.ogg loop 开关; setExceed(L25671 单发)/setCharger(L25680 幂等)/
  setTransformingState(L25689, 需 chargeBoostBySpeed!=0)
- 路面音: updateRoad(L25763): selectRoad 失败返回; 音量 _$(L25834) 三段线性 volume0~volume100;
  spacing 配置 true 时 updateSpacedRoad(L25775) 间隔=buffer.length*5/speed 重播
- dispose(L25803)/stopEffectSources(L25805) 停全部

### F.3 ea BGM 类(L28163-28220) ✅
- static load(L28176): rh 唯一取 bgm/main/{single,game_win,game_lose}.ogg; 主题 BB(L28222,
  bgmTheme||theme||folder 前缀 yg 表||texTheme); vg(L28250) 取 theme 与 theme2 合并按 sourceOrdinal 排序
- restart(L28185) 随机曲 start(buf, loop=true, fade=true); playReady/playResult(win|lose, 不淡化)
- start(L28194): fade 时旧曲挂 retiring, 新 gain=0, Jm(true), setInterval(advanceTransition, 100ms);
  advanceTransition(L28202) step>=16 收尾; FB(L28231) = {incoming: step*0.0625, outgoing: (15-step)*0.0625}

### F.4-F.7 ✅
- Nu 倒计时/圈数(L28277-28314): count_n/count_go/lab_count/final_lab.flac; play(buffer) L28307
- _u 界面点击(L28326-28348): interface/click.flac; activeClick 占用期忽略
- uu 赛道事件特效+音(L17710-17828): 模板池 item/eventObject/<model>.1s(dP 计数 L17830, spare 池克隆);
  音效 tp(L17867) soundType 0/1 或 2+distance>=0 才加载, mP(L17859) 两目录三扩展找唯一源,
  ep 小写 key; playSound(L17809) 同名同时只播一个; trigger(L17735) 弹克隆+reset(seed)
- du 独立环绕音(L17894-17947): gy(L17949) 校验 panning/spacing/timeLine 未实现即抛错;
  update 100ms 节流(L17909); updateSound(L17922) 距离超 minRadius stop, 音量 xP 距离衰减
- V$(bytes) L25842: road.bml 解析, <road><sound name filename spacing spacingLen=5 volume0=0 volume100=1>
- 生命周期: prepareStartupReady L29169(新建 ctx+dn+ea/_u), 进比赛装 $u/Nu/uu/du(L29222);
  restartRace L29141 resetRace+restart; 暂停 L28658 setPaused(true)(motor 保留继续响)

---

# 六、§H AI 系统 -> ✅ (结论修订)

### H.1 结论: 无 AI, 仅"自动前进"辅助 ✅
- 全文检索 bot/opponent/npc/autopilot/ai 无任何 AI 对手实现; mB Coordinator(类定义 L27257-27319,
  L29135 仅为工厂 createCoordinator)与 routeStates 全部函数均为玩家车路线进度追踪, 不含转向/速度/道具决策
- 唯一自动输入 = 触屏 autoForward(s$ L22714-22760): setRaceState(racing, notStartBoost);
  isActive=engaged && reverse===0(L22724); apply(L22726)=engaged 时强制 forward=1;
  键盘 forward-down 取消 armed(L22732)。接线 L29022-29027/L29075。这是 UI 辅助, 不是 AI
- 不存在"AI 车与玩家车物理输入差异": 整局只有一辆物理车(GoPlayKart 单实例 L27263)

### H.2 routeStates 相关(Track 类方法, L26047-26336) ✅
- 状态字段: {section, lap, localDistance, completedDistance, distance, resetAux68/74/80/8C}
- requireRouteState L26316(缺失抛错); resetRouteState L26142(以 data.lastSection 初始,
  completedDistance=-section.length 表示未过起点; placeAtStart L29137 调用)
- projectSectionDistance L26320: 逐 frame 找第一个"位置在其 forward 后方"的帧, 累加帧间距+末段投影
  clamp [0, section.length]; reset/associate/refresh/updateRoute 共用
- updateRoute L26248: 前向循环(th 门判定 >0 过门, 容忍下一段门), surface 变化发
  "<surface>:out:next"/":in:next" 标签; 圈数: 进 firstSection 或 gate.final+lapTarget -> lap+=1;
  后向循环对称; 环保护 counter>sections.length*2 抛"未收敛"
- associateRoute L26156: 全图最近线段搜索(需在该段 up 半球内), 丢轨重定位
- refreshRouteProjection L26194: 仅当前 section 内重投影
- sampleRoute L26203: 前瞻采样(沿 outgoing[branch] 前进 ahead 米, 循环去重 L26216, 插值 Jc L26234),
  返回 {surface, sampled, point, direction, up} —— 用于小地图/UI, 非 AI 导航
- prepareCurrentSectionReset L26106 / commitCurrentSectionReset L26117

### H.3 mB Coordinator(L27257-27319) ✅
- constructor(L27258): 准入校验; 调度对象 yn(name, active, category) L27321: GoTrack(cat0)/GoCourse(cat1)/
  GoPlayKart(cat2)/GoItemObstacle[]/GoItemEventObject[](cat3, 容量2)
- GoItemObstacle.slot12 -> track.updateObstacles; slot13 -> registerObstaclePair; commit -> commitSnapshot
- GoPlayKart.slot12 -> kart.update(obj, input, track) 物理步进唯一入口; GoCourse.slot13 ->
  runOuterRoutePass + state.trackProgress; commit -> previousPosition 拷贝
- run(ms, input) L27296: 注入 input -> core.run(ms)(finally 清) -> 校验 schedule 与 route 必须产生
- synchronizePositionAnchor L27309(reset 后重锚); handleRouteSurfaceTag L29076 消费端(未闭合 tag 抛错)

### H.4 补 AI 建议(修订版)
- 物理输入面闭合于 kart.update(obj, input, track); 实现 AI 只需伪造同结构 input 注入 mB.run 第二参
- 可复用: sampleRoute(ahead) 作 Pure Pursuit 前瞻点源; getRouteState().distance 作圈进度;
  th(gate, prev, cur) 作防作弊校验

---

# 七、§I 渲染与场景图 -> ✅ (重写, 旧行号全部作废)

### I.0 顶层 .1s 入口 ✅
- oa(bytes) @280: 解析 model.1s -> nl(bytes)+ObjGraphReader.readObject, 根必须 Relement 派生(Wu @820)
- Nv(bytes) @304: 车辆动画 .1s(根 KartSequence); Wg @314: 人物动画 .1s(根 CharSequence @317)
- ObjGraphReader_class @323: 引用标记 Y1/新对象标记 X1(u32 ClassStamp+u16 id);
  ClassStamp 表 @254-262: Relement 0xe07033c, ReToonRigid 0x192a0446, ReTriList 0x10d40382,
  ReToonSkinned 0x23330523, CharSequence 0x1dbb04b7 等(完整 he 映射 @254-300); decoder 注册 @331-346

### I.1 场景节点解析 ✅
- parseSceneNodeCommon @408: name -> 子节点(count32 递归) -> transform{basis 3xvec3, translation, scale} ->
  bounds0 -> serializedBoundsOverride(u8) -> cullingTraversalMode(u32) -> bounds1 -> rawScalar(f32) ->
  nodeEnabled(u8) -> 11 个 slot(u8 判空+readObject) -> additionalProperty
- parseReKart @445: +sortDepthBias/rootBounds/simpleShadow(4xf32); parseReCharacter @454: +characterScalar
- parseReToonRigid @461: +geometry(parseRigidGeometry); parseReTriList @469: +parseTriListVertexData
- parseReToonSkinned @477: parseSkinnedGeometry @490: vertices{pos,normal,bone0/1 u16,weight0/1 f32}/
  wedges{skinVertexIndex u32,u,v}/triangles{wedge u16x3, adjacent(u16@0,2,4), position u16x3, winding,
  unknown13}/bones{inverseBind 12xf32, localBind 12xf32, parent u16, enabled, reserved}, 0xffff=无邻接
- parseRigidGeometry @551: positions/normals/texcoords{rawWord u16, normalIndex u16, u, v}/faces
- 赛道版 createTrackDecoders @4525(TrackContainer/ReTriStrip/ReBillboard/ReCamera/ToRoad/各 Property/
  各 Controller); parseReTriStrip @4723; parseReBillboard @4733(orientationMode u32)

### I.2 矩阵/变换写入 ✅
- ca(obj, transform, ...) @989: matrix.set(basis 行优先 x scale 按列乘, translation),
  matrixAutoUpdate=false, matrixWorldNeedsUpdate=true(旧文档 l1/N0/uC 的对应物)
- Ra(handle, basis) @2321; setNodeMatrix @2595(不置 matrixWorldNeedsUpdate)
- matPhysicsFromPresentationX90 @2602: makeRotationX(PI/2).multiply(m)(旧 u1 对应物)
- Wu @820 节点类名白名单 ReKart/Relement/ReCharacter/ReToonRigid/ReTriList/ReToonSkinned

### I.3 strip 展开 ✅
- OutlinePass_class @1834 内 @2047-2050: i>=2 起, even: (i-2,i-1,i), odd: (i-1,i-2,i)(交换前两点)
- 容量 @1866 Uint16Array; pushStrip 越界抛 "Toon outline strip capacity exceeded"
- 顶点着色器 @1843: positionD3D(预投影 rhw)->NDC 反变换, additive blending

### I.4 材质构建 ✅
- resolveAlphaZbufInherit @2472: slot[3]=AlphaProperty, slot[0xa]=ZBufProperty, 父->子继承;
  默认 {blendEnable:0, srcBlend:2, dstBlend:1, alphaTestEnable:0, alphaFunc:8, alphaRef:0}/{mode:4, enabled:1}
- createTrackMesh @1700: ShaderMaterialB("KartRider basic texture stage"), uniforms baseMap/
  textureEnabled/lightingEnabled(mode==2)/textureOperation(仅 op 1|4)/alphaTestEnabled/alphaFunction/
  alphaReference(=alphaRef/255)/uvOffsetScale/uvRotation/lightFactor/materialColor;
  alphaPass 按 D3DCMPFUNC 1..7 分支; depthFunc=Ub(zFunc), side=Wb(cull)
- D3D 映射: Wb(cull) @1775(cull 1=DoubleSide, 3vs2 按翻转选 Front/Back); Ub(zFunc) @1785(1 Never..8 Always);
  Ju(blend) @1800(1..0xb); rgbaFromU32 @2591(ARGB); applyBaseTextureAll @2741(ReKart slot4:
  blendEnable!=0 抛"尚未映射", alphaFunc!=5(GREATER) 抛错, alphaTest=alphaRef/255)

### I.5 渲染循环 ✅
- GameApp @28427(文件尾 new GameApp @29741); 构造 @28433: input/touchControls/frame=rAF 绑定
- frame @28553: 同一毫秒去重; updateAndRender @28560: FPS 指数平滑 fps+=(1/max(dt,0.001)-fps)*(1-exp(-3dt));
  开赛后: raceLifecycle.effectiveTime -> track.updateMovingRoads -> updateDriving -> kartView.update
  (animSlot->physics.setAnimationSlot) -> driveCameraRuntime -> Kb(visualScaleMode) @1827 ->
  kartView.root.updateMatrixWorld -> 各特效(rain/snow/motionBlur/shockWave/exhaust/crash/charger/drift/
  trails/lampFlares) -> track.updateRender -> KB(renderer, uiPass, hh+render, skydome, motionBlur);
  dispose @28535

### I.6 批处理/动画播放 ✅
- OutlinePass 单 Mesh+setDrawRange, frustumCulled=false, renderOrder=1; 场景候选 tS @5493/eS @5543
  (tri-list/tri-strip/toon-rigid 分类)/iS @5549 未闭合 issue; nodeEnabled=0 整树省略
- KartAnimPlayer @1007: clips 由 lb @1074 构建; 状态 0..6; 通道名表 ch @1003 = 56 骨骼槽 mod0..mod6b1;
  applyClip 逐通道 hb @1070 -> ca 写矩阵 -> db 可见性

---

# 八、§J 资源解析 -> ✅

### J.1 .rho 解档 ✅
- rhoFilenameKey(name) @14377 = adler32_init0(UTF16LE(去掉 .rho)) - 0xa6ee755 >>> 0; adler32 @14382
- ga(data, dataKey) @14410 XOR 密钥流: seed=dataKey^0x8473fbc1, 16xu32LE 各 -0x7b8c043f, 64 字节,
  Kw @14418 逐字节 data[i]^key[i%64]
- $m(data, seed) @14394 二级解密(flag 0x10 族): T-table 四字节查表 XOR, out=u32^k^prevSum;
  flag 0x08 抛 RHO_SECONDARY_CIPHER @14360; XC @14364 flag bit2 -> zlib inflate; YC @14372 adler32 校验
- 目录读取器 ik @14463: readUint32/readCount/readUtf16Null(UTF16LE NUL 终止)/assertFinished

### J.2 .rho5 解档 ✅
- region 密钥表 ru @14630: {KR:"y&errfV6GRS!e8JL", CN:"d$Bjgfc8@dH4TQ?k", TW:"t5rHKg-g9BA7%=qD"}
- ak(name, region): header 种子=(lower(name)+key) 逐字节 (char&0xff)+i&0xff x 0x80; ck @14670 table 种子
  倒序字符 x(2+i%3); hk @14685 FNV-1a(0x811c9dc5, imul 0x1000193); lk(md5, key, path) MD5 逐位派生密钥
- class dk @14674: AES T-table 变体 PRNG(state Uint32Array(16)); uk(data, key) 按 4 字节 LE out=word-nextWord;
  MD5 校验失败抛 RHO5_MD5(L15018-15035)

### J.3 .1s 动画 ✅
- parseCharSequence @678: header 3xu32 -> 24 个 channel(PRSTontroller) -> rootChannel(IntTontroller) ->
  map(count32 x u32 表情映射)
- parsePrsTontroller @696: base=parseAnimBase + 可选 position/rotation/scale(readTyped BeCurve) +
  firstLastCache 6xu32; parseIntTontroller @714 / parseVisTontroller @722 / parsePathTontroller @730
- parseBeCurve @748: keyType 5(vec3 composite)/4(rotation composite)/其余 fixed(记录字长表 ib @789)
- 求值: Sr @3074 / k1 @3092 / R1 @3111 / P1 @3127 / ml @3139 / pl @3143(cycleMode 0 循环 1 往返 2 clamp)
  / gl @3160 / p0 @3170 / $1 @3175 / g0 @3191

### J.4 .bml 二进制 XML ✅
- parseBML @188 -> parseBinaryXML @195: name:string+text:string+u32 属性数(<=0x186a0) x {name,value}
  +u32 子节点数(<=0xf4240) 递归; depth<=0x80; 尾部剩余字节必须 0; xmlAttr @222; ah @226 上限守卫
- 用例: timeInfo@cn.bml @12157, boostGauge*.bml @12173, tacho.bml @10379, lampFlare.bml @8668, minimap @12798

### J.5 贴图 ✅
- decodeImage @5580: 自实现 PNG 解码器(zlib inflate + Adam7 @5653/Cd @5669)
- DXT: hS @5747(DXT1 8B/DXT3、DXT5 16B); uS @5770 565->4 色表(DXT1 c0<=c1 第 4 色透明); kd @5780
  R5G6B5 扩展; dS @5787 DXT3 alpha/DXT5(fS @5797 8 值插值); mS @5810 索引展开
- 纹理统一配置 @2369: flipY=false, generateMipmaps=false; kart 贴图 PNG Blob->loadKartTexture @2717

### J.6 GLTF 导出对接点 ✅
- parseModel1s @2691: model<=180MB, anim 各<=64MB; buildVehicleScene @893(sl @943 递归 THREE 树,
  返回 {object, nodes:Map(name->source), bySource})
- VehicleImporter @2612; ReKart 根 rotation.x=-PI/2 见 l0 @2371; jr @2720 统一 dispose;
  皮肤调色板 @13084; 蒙皮顶点装配 @13025

### J.7 归档索引 ✅
- class ou @15211: files/archives/byPath/byCanonicalPath/byExactCanonicalPath/canonicalPrefixCache,
  canonicalCandidates(path) 统一取资源入口; aaa.pk 读取器 class sk @14573

---

# 九、§K 数学库 -> ✅

### K.0 fround 包装(同名多份!) ✅
- h(x) @25424 物理 {x,y,z} 族; U(x) @26881 碰撞族; V(x) @3236 CharSequence 族; j(x) @1289 KartAnimPlayer 族;
  se(x) @1285 = x>>>0; Yp @25430 NaN 传递加法
- 勘误: 旧 §K.1 称 qc(v) 为拷贝——错误, qc 是归一化

### K.1 {x,y,z} 向量族 ✅
- de 清零 @25046; xe 加 @25050; fe 减 @25058; q 缩放 @25066; Mt 原地累加 @25074; Kp 原地累加缩放 @25082;
  je 原地减 @25078; Nt 原地缩放 @25086; $$ 点积 @25090 / Ct @25094; Kt 长度 @25098
- qc @25102 归一化(零向量返回 {1,1,1}!); B$ @25115 同; F$ @25128(零返回拷贝)
- Xe @25154 标准叉积; Hc @25137 D 空间叉积(先 (x,-z,y) 变换叉积再逆映射); qp @25168 按轴缩放;
  D$ @25178 sqrt(x^2+y^2+z^2)

### K.2-K.3 ✅
- 数组向量: dist3 @4331/len3 @4339/v_sub @4347/v_add/v_scale/v_cross/v_normalize @4347-4363;
  triNormal @4521; fi @26609 = trunc(x*0.25)(网格单元), Ws @26613 = fi*4
- Fu @26688 MT / Bu @26657 SAT / Q$ @26627 / J$ @26640 半平面(见 B.9-B.11)

### K.4 坐标变换 ✅
- physicsToPresentation @4309 = (x, z, -y); roadFrameToPhysics @4287; dataToPhysicsVec @5262;
  reverseFrame @4318; routeLength @4325
- hd(a) @2325 绕 X 3x3([1][2]=+sin 注意); i1(a) @2335 绕 Z 3x3; r1(A,B) @2345 3x3 乘法;
  n1 @2349 sqrt(x^2+y^2+z^2); w0(quat,trans) @3210 四元数->行优先 3x4; y0 @3214 四元数点积

### K.5 四元数插值 g0 @3191 (nlerp 变体, 带曲率校正!) ✅
1. d = dot(qa,qb); w = (1 - d*0.82279688)^2 * 0.58549219(两个魔数)
2. ease: t>0.5 ? 1-((2(1-t)-3)(w(1-t))+1+w)(1-t) : ((2t-3)(wt)+1+w)t(三次平滑)
3. 分量线性 r[i]=(qb[i]-qa[i])e+qa[i]; 模方 n2
4. 归一化 = rsqrt 多项式逼近: k=(n2-0.95906597)(-0.53251559)+1.0214351, n2<=0.91521198 再来一次、
   <=0.6521197 第三次(md @3206, Quake III rsqrt 魔数族); 返回 r*k
- $1(poseA, poseB, t) @3175: translation lerp + y0<0 取反 qb(最短弧) 再 g0; B1 @3230 float 位读取

### K.6 CharSequence 求值锚点 ✅
- k1 @3092 position(keyType 1, u32 time+3xf32); R1 @3111 rotation(记录 w@4,x@8,y@12,z@16, 返回 [x,y,z,w]);
  P1 @3127 root 整型(keyType 3 step 函数); pl @3143(anchor 锁定+frequency 缩放+cycleMode);
  Sr @3074 逐通道 {translation, rotation} -> {pose: w0[], samples, root}

---

# 十、§L 顶层函数索引 ✅ (当前文件行号; grep "^function |^class " 全量提取)

- IO: fetch 包装 @114 / $xmlAttr @230 / nl @293 / ObjGraphReader_class @323 / ik @14463 / sk(aaa.pk) @14573 /
  Zx @5358 / Yx @5297 / ou(归档索引) @15211 / class at(Rho 错误) @14196 / class At(RHO5) @14779
- 解析: parseBML @188 / parseBinaryXML @195 / oa @280 / Nv @304 / Wg @314 / parseSceneNodeCommon @408 /
  parseReKart @445 / parseReCharacter @454 / parseReToonRigid @461 / parseReTriList @469 / @4718(track) /
  parseReToonSkinned @477 / parseSkinnedGeometry @490 / parseRigidGeometry @551 / parseCharSequence @678 /
  parsePrsTontroller @696 / parseBeCurve @748 / createTrackDecoders @4525 / parseTrackContainer @4533 /
  parseToRoad @4641 / parseTrackNode @4692 / parseReTriStrip @4723 / parseReBillboard @4733 /
  parseTexProperty @4827 / parseAlphaPropTrack @4866 / parseBackFaceProperty @4878 / parseMtlProperty @4885 /
  parseZBufPropTrack @4911 / parseToonProperty @4926 / parseFogProperty @5082
- 路线: buildRouteGraph @4101 / gateTrisFromRecord @4272 / collectRoadTriangles @4369 /
  roadFrameToPhysics @4287 / physicsToPresentation @4309 / reverseFrame @4318 / routeLength @4325
- 碰撞: Y$ @26354 / Jp @26436 / Z$ @26491 / Bu @26657 / Fu @26688 / Q$ @26627 / ig @26631 / tB @26705 /
  eB @26711 / Ao @26715 / Us @26719 / rg @26723 / extractCollisionData @4037 / tx @4056
- 渲染/表现: buildVehicleScene @893 / ca @989 / KartAnimPlayer @1007 / OutlinePass_class @1834 /
  t1(wheelPresentation) @2180 / Ra @2321 / hd @2325 / i1 @2335 / r1 @2345 / l0(ReKart 装配) @2365 /
  resolveAlphaZbufInherit @2472 / makeMatConfig @2495 / VehicleImporter @2612 / parseModel1s @2691 /
  applyBaseTextureAll @2741 / la(过渡混合) @2753 / Sr @3074 / k1 @3092 / R1 @3111 / g0 @3191 / w0 @3210 /
  tS @5493 / decodeImage @5580 / hS(DXT) @5747
- 加密: XC @14364 / YC @14372 / rhoFilenameKey @14377 / adler32_init0 @14382 / $m @14394 / ga @14410 /
  Kw @14418 / class ik @14463 / ru(region 密钥) @14630 / class dk @14674 / class Nk @15052
- 流程/输入: lg(raceLifecycle) @27346 / wB(surroundCameraman) @27481 / ea(BGM) @28163 /
  GameApp @28427(frame @28553, updateAndRender @28560, 文件尾 new GameApp @29741)

### 未找到(已搜索, 明确说明)
- ae(v)/ex()/u1/completeCheckpointPose/l1/N0/uC: 当前文件 grep 零命中, 系旧 dump 遗留条目
- 物理无同名顶层函数(stepSubstep 等以 k$/Y$/Jp/Z$ 类方法形式存在, 见 §A)
