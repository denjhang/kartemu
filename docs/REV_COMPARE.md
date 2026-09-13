# 深度逆向对照: 官方语义 vs kart.html 当前实现 (2026-09-13)

> 四个方向并行逆向的成果整合: 动画映射/补间、物理/漂移/喷气、音频系统、速度表/仪表。
> 全部结论带 deob_named.js 行号实锤。本文是kartemu 下一步"逐模块增量迁移"的对照基准。
> 基础章节见 UNDERSTOOD.md §24(动画)/§25-26(物理碰撞)/§29(流程UI)/§32(音效); 本文补深补细。

---

## 〇、总差异速查表(按迁移优先级)

| 模块 | 官方核心语义 | kart.html 现状 | 差距等级 |
|---|---|---|---|
| 动画状态映射 | 每帧由物理量重判; f45/f46 倒车按 steer 符号直选; f41/f42 是循环保持态 | 手写 3 相位倒车机 + f43/f44(官方比赛表不用); f41/f42 LoopOnce | ★ 核心语义错 |
| 动画补间 | 自研快照+定时混合: enterBlend 50-400ms 分档, 24通道 pos lerp + 四元数 nlerp; 一次性动作 span 后自动以 returnBlend 淡回(pending 抢占限制) | 仅 f41/f42 crossfade 0.16s, 其余硬切; 无回落系统 | ★ 缺整套 |
| 碰撞动画分级 | 强度>30→f47(锁1s); 15-30→f48; ≤15 忽略 | 撞柱一律 f47 0.5s | ★★ |
| 物理积分 | 力/质量 + 2ms 定点子步; 重力 58.8; 无速度硬顶(二次阻力平衡) | 标量 speed + 硬 cap 9/20; 重力 18 | ★★ |
| 漂移 | drift-start→triggerPhase(关后轮抓地点火)→activeDrift(envelope+slip 削弱)→松键 driftDecay 尾滑→集气提交 | 无 | ★★ 缺整套 |
| 集气 | 双条: 主 gauge(漂移 latSpeed²×dt 时间加权 ×3/×1.5/÷2t + 行驶充能 + 撞墙回充) + instant gauge; 满槽→氮气槽→大喷 | 无 | ★★ 缺整套 |
| 大/小喷 | physicsState 状态机(1起步/2连喷/3大喷/0xa双喷/0x12play), boostAccelFactor 乘推力+限时 | Ctrl 按住即 boost | ★★ |
| 速度表 | 表显 km/h=\|v\|×3.6; 3位补零数字+19格条(满350), ≥15格变高段色; key 缓存节流 | 无 | ★★ |
| 音频 | 全套 WebAudio(见§四), 引擎音 playbackRate 随速度 | 无 | ★★ |
| 车辆动画 | 前轮=steer×3×spin 后轮=spin(一致); +悬挂压缩-0.5z、extWheel 槽 | 前两项一致; 缺悬挂/extWheel | ★★★ |
| 表情/换脸 | 每条动画带 face map, 状态切换换脸 | 无 | ★★★ |

---

## 一、动画映射与补间 (agent 报告全文)

### 1.1 三个比赛用状态机类
官方按 `characterAniType`/展示模式实例化三种 player(选择点 L29292):
`_0x199f4c = _0x420bb5 ? XB(...) : _0x3c0fcb===0x1 ? YB(...) : HB(...)`

| 类 | 行号 | 工厂 | 用途 | 初始状态 |
|---|---|---|---|---|
| lh | L2863 | HB L29658 | 普通卡丁车骑乘(characterAniType=0 主路径) | currentState=0x3(f40) |
| v1 | L2901 | XB L29674 | 联动展示(变身载具角色) | 0x0(f08) |
| u0 | L2924 | YB L29689 | characterAniType=1(f10 系) | baseState=0x3/mappedState=0x19 |
| dd | L2887 | L19959/19977 | 单动作预览(garage/ready) | 唯一动作 |

### 1.2 状态→动画映射 (b1 L2949 / x1 L2963 / S1 L2980 + HB L29658)

| 状态 | 动画 | enterBlendMs | returnBlendMs | span |
|---|---|---|---|---|
| 0x3 | f40 骑乘循环 | 150ms | — | 循环 |
| 0x4 | f41 转向姿态 | 400ms | — | **循环保持** |
| 0x5 | f42 另一侧转向 | 400ms | — | **循环保持** |
| 0x8 | f45 | 150ms | — | 循环 |
| 0x9 | f46 | 150ms | — | 循环 |
| 0xa | f47 强碰撞 | 50ms | 150ms | header[2] 一次性 |
| 0xb | f48 轻碰/落地 | 50ms | 150ms | header[2] 一次性 |
| 0xc | f49 胜利 | 50ms | 50ms | **override 5000ms** (d0 L2976) |
| 0xd | f50 失败 | 50ms | 50ms | override 5000ms |
| 0xe | f51 变身/倒加速后仰 | 100ms | — | 循环 |
| 0x13 | f54 摩托变身(可选) | 100ms | — | 循环 |

v1/XB: 0x0=f08@150, 0x12=**f11**(喷火后仰, 反向才 f51) (L29674-29687, L3027)。
u0/YB: 0x19..0x24 全 f10@150; 映射表 A1 L3002/M1 L3016 (3→f40, 4→f41, 5→f42, 10→f47, 12→f49, 13→f50, 14→f51...)。
`oe(anim,ms)` L2987 = 仅 enterBlend; `Li(anim,enter,return,span?)` L2994 = 一次性带回落。

### 1.3 状态选择函数(优先级高→低) `lh.selectMotion` L2882

```
① 强碰撞后 1000ms 内(0x3e8) → 锁定当前状态
② landingTrigger → 0xb (f48)
③ collisionHit: 强度≤15 忽略; 15<强度≤30 → 0xb(f48); >30 → 0xa(f47)+记 lastStrongCollisionMs
④ 常规 f0 (L3037):
   m0(m)(=instantAccelerationActive || boosterState 1..11 || 13..16) → 变身 ? f54 : f51
   |forwardSpeed| < 0.3(Kr, L2752) → fd(rawSteer, tireTransient, reverse)
   forwardSpeed <= -0.3(倒车) → reverse ? 保持 : rawSteer<0 ? 0x9(f46) : 0x8(f45)
   否则 → fd
   fd (L3046): tireTransient≠0 → 0x3(f40 漂移/直行)
               steer>0 → reverse?0x5:0x4 ; steer<0 → reverse?0x4:0x5 ; 直行 → 0x3
```
胜负: `pendingCharacterFinishMotion = resultBeatTarget ? 0xc : 0xd` + `setRaceMotionLocked` (L28708), finishMotion 在 selectMotion 之前无条件提交(最高优先级)。

### 1.4 补间系统: `la`(CharSequence 播放器, L2753-2854) —— 无 crossfade/mixer
- 状态切换(request L2801→beginTarget L2827): 当前 outputSamples 24通道快照为 transitionSource, 目标 t=0 采样为 transitionTarget, blendMs=enterBlendMs。
- 每帧 update(L2805): elapsed≤blendMs 时 evaluateBlend(L2848): alpha=elapsed/blendMs, 24通道逐个混合——translation 线性, rotation 用 g0(L3191, **nlerp** 带半角修正)。完成后直接采样目标动画(Sr L3074; k1 位置线性 L3092 / R1 旋转 nlerp L3111)。
- 无骨骼层级: 24 个 PRS 通道直接输出 pose 写节点矩阵; 循环模式 pl(L3143): 0 loop/1 pingpong/2 clamp。
- **每帧采样驱动**, 状态机每帧重判, 同状态不重入(submitMotion L2884 有 === 判断)。
- 表情: 每条动画带 IntTontroller 根通道(P1 L3127, keyType 3 整数阶梯)+face map(os L3031), 状态切换即换脸。

### 1.5 一次性回落机制 (armReturn L2819 + updatePending L2839)
1. 进入带 returnBlendMs 的状态时记 pending={target:上一个循环动作, returnBlendMs, thresholdMs=enterBlendMs+span(span=spanOverrideMs??header[2])}
2. 超 thresholdMs 自动 beginTarget(旧动作, enterBlendMs=returnBlendMs) → **播完自动淡回原循环**
3. acceptsMotion(L2804): pending 期间只有带 returnBlendMs 的动作可抢占
4. f47 额外硬锁: 触发后 1000ms 内 selectMotion 维持现状(L2882)

### 1.6 车辆动画 (t1 wheelPresentation, L2180-2255)
- handle=ReKart child[1].child0; 主轮=child[2..5].child0; extWheel/extSteer=attachment 槽 8-11(L2308)
- 转向: `steerRot = i1(steering*-3)` 绕 Z; handle+前2轮同用(L2210-2212)
- 滚动: advanceAngles L2233, mainAngle += dt*0.001*速度模长(hypot(vx,vy,vz) L2349), 2π 回绕+Inf 保护; 前2轮=steerRot×spin, 后2轮=spin(L2217)
- 悬挂: visualCompression = wheelCompression-0.5(Jb) 沿 z 平移(L2207/2219)
- extWheel 转速(L2226): type0 恒速/type1 车速×extWheelSpeed/type2 仅漂移铁轨转
- 矩阵写入保留 translation/scale 只换旋转, matrixAutoUpdate=false

### 1.7 与 kart.html 差异(摘要)
① f41/f42 官方是循环保持, 当前 LoopOnce 语义错; ② 官方无 f43/f44(倒车直接 f45/f46 按 steer 符号), 当前手写 3 相位机多余; ③ 缺一次性回落系统(span 后自动淡回+pending 抢占限制); ④ 补间只覆盖 f41/f42, 官方所有切换都有分档 enterBlend(50-400ms); ⑤ 缺 f48 轻碰/落地、强度分级、1s 碰撞锁; ⑥ 缺表情换脸; ⑦ 车轮滚动用滑块值非物理车速; ⑧ 缺悬挂压缩。车轮转向系数 steer*3 与 handle/轮子树结构一致。

---

## 二、物理 / 漂移 / 集气 / 喷气 (agent 报告全文)

### 2.1 全局物理常量 (L23396-23425, 原始值)

| 常量 | 值 | 语义 |
|---|---|---|
| di | 0.5 | 轮子射线半长, 探测距离 1.0m |
| 重力 zp | **-58.8 m/s²** | 约 6 倍地球重力, kart 手感来源 |
| Pr | 0.5 | 轮距力臂系数 |
| ue | **980** | 轮胎侧向力基底 F=980·grip·(转向项−侧滑项) |
| Np | [2, 0.5] | dirt/slip 非漂移衰减二次式 |
| _s | 6×11 表 | dirt/slip 参数(非漂移 dirt=[340,-1,-1,1,...0.6]; 漂移 dirt=[120,0,0,1,...0.85]; 非漂移 slip=[180,0,0,0.5,...]; 漂移 slip=[120,-2,-2,1,...]) |
| A$ | 0.18 | 补轮触地 vy+=0.18 |
| jc | -9.8 | MR/HW 重力=specialNormal·jc·6 |
| Gp | 0.3 | 路面动作冷却 |
| Kc | **0.002 s** | 物理子步上限(L23846 报错文本确认) |

### 2.2 主循环 stepSubstep (L23845-23869)
每帧 elapsed 切成 ≤2ms 子步(L23488-23491), 每子步跑完整 17 步序列。空中强制清漂移(L23859); delayedDriftRequest 延迟到触地(L23856); 表显速度 `cachedDisplaySpeedKmh = |v|×3.6`(L24750)。

### 2.3 漂移完整语义
- **进入**: ①按键: 按住漂移键+方向非零 → drift-start, direction=sign(rawSteer)(L17212-17224); ②自动甩尾: |localRightSpeed|>|localForwardSpeed|×1.2 且 speed>15m/s(54km/h) → oneSubstepDrift(L24200); 泥地: 侧滑比>0.85。
- **triggerPhase(点火)**: 前轮只受纯转向拖拽力 F=-980·frontGrip·steerAngle·driftTrigFactor, 后轮力=0, 轮胎摩擦关闭——车被"甩"进去(L24201); triggerTimer 倒数 driftTrigTime, driftDecay=triggerTimer×2; 归零后开集气窗 driftGaugeWindow(L24203)。
- **维持(activeDrift)**: tireEnvelope 0→1 渐进(envelope+=(1-e)×0.001/scale); 侧向力乘 driftSlipFactor×tireEnvelope——后轮抓地系统性削弱是漂移维持侧滑的原因(L24225); driftDecay 递减=尾滑阶段。
- **退出**: 松键 stopDrift(L23733); 松前进再按前进=连喷(driftLifecycleB50>0 时 physicsState=2, L23590-23591); 低速≤5m/s 清漂移提交集气(L24242); 空中清(L23859)。

### 2.4 集气 (committedGauge+pendingGauge, 上限 driftMaxGauge)
- **漂移集气** accumulateDriftGauge(L24358-24368): 基础=dt×**localRightSpeed²**(侧向速度平方!), 时间加权: 前0.2s×3 / 0.2-0.5s×1.5 / 之后÷(2×elapsed)——短连漂效率最高。
- **行驶充能** accumulateSpeedGauge(L24369-24378): chargeBoostBySpeed 且接地且 physicsState=0 且不在漂移窗且 kmh≥autoChargeLowSpeed。
- **提交** commitDriftGauge(L24379-24381); **碰撞保护** pending×=driftGaguePreservePercent(L24658); **撞墙集气**: 高速撞墙掉速大→按 Δv 线性回充(L24722-24746)。
- **氮气槽**: gauge 满→消费整条, 空槽填 6; state.nitro=值为6的槽个数(L23726-23730)。

### 2.5 喷气族 (physicsState ≡ boosterState, 同一变量)
| state | 语义 | 代码 |
|---|---|---|
| 1 | 起步喷 startRaceBooster(用 startForwardAccelSpeed 替代加速度) | L23690-23693 |
| 2 | 连喷(漂移尾窗内重按前进), ×driftBoostMulAccelFactor | L23590/L24138 |
| 3 | 大喷 startNormalBooster: 消耗 speedSlots[0]==6, physicsState=3, 时限 normalBoosterTime | L24382-24386 |
| 0xa | 双喷(engineGrade>6), ×dualMulAccelFactor | L24405-24419 |
| 0x12 | boosterPlay/连喷终段姿态(1000ms) | L23696-23697 |
| - | 瞬间加速 exceed: instantGauge 1 秒烧完, kmh 低时效果×2 | L23587/L24139/L24672 |

加速度乘子: physicsState 1..11 全部乘 boostAccelFactor(L24134-24136); transform 车在动画槽 2/4/5/6 用 transAccelFactor 替代。特效波纹映射(L6989-6991): state 2 -> driftBoostWave, 1/13/14/19 -> baseBoosterWave, 3/4/5/6/8/9/12/17 -> boosterWave。

### 2.6 速度上限本质
无硬 cap。applyDrag(L24331-24349): 总阻力 = v*airFriction + v*|v|*liveDragFactor*dragScale*DF 路面系数; 终端速度 = 推力与 |v|^2*drag 平衡, boost 提推力则极速自然升高。倒车(L24152-24166): reverse 累积 >0.2s 才施加 backwardAccel(防误触); 滑行制动 grip/slipBrake 按速度与车头点积选择。碰撞(L24505-24556): 地面反弹 0.7; 墙面 -1.5 法向 + 切向滑动 + 擦墙过弯补偿(角速度 +6~8*steer)。

### 2.7 与 kart.html 差异(摘要)
当前 L493-528: accel=6 / maxSpeed=9 / boostMax=20 / steerRate=3, Ctrl 即 boost, 无漂移无集气无氮气槽, 硬 cap, 跳跃重力 18。核心差距: 力+二次阻力模型、2ms 定点子步、漂移状态机(triggerPhase/activeDrift/decay)、双集气条、physicsState 喷气族、转向角速度衰减 exp(-|v|/steerConstraint)。

---

## 三、音频系统

### 3.1 音频图
每源一条私有链: BufferSource -> GainNode -> ctx.destination(Zt L17663-17677), 无共享总线; 逻辑分组 group='parseTrackContainer'(FX)/'bgm'; AudioContext 复用不重建。
音量: hu(L17688-17693) 按 group 乘 bgmVolume/fxVolume, 关闭则 0; 写入用 10^(trunc(-log(1/v)*1000)/2000) 量化(复刻 32 位浮点, py L17702-17706)。设置持久化 localStorage "kartrider-web:p3528:game-options-v1"(L17603); 热键 F6/F7/F8 切 road/fx/bgm。

### 3.2 BGM (ea L28170-28220)
- 资源: sound_/bgm/main/{single,game_win,game_lose}.ogg + 按赛道主题 sound_/bgm/<theme>[2]/*.ogg(随机选曲, DB 按 sourceOrdinal 排序)。
- 过渡: crossfade 16 步 x 100ms setInterval(Jm L17651 期间禁 dn() 覆盖 bgm 音量), incoming=step*0.0625, outgoing=(15-step)*0.0625, 约 1.6s(L28194-28209, FB L28231-28237)。

### 3.3 引擎音 (kart 音频类 $u L25530-25828)
- 资源: sound_/parseTrackContainer/kart/engine_<EngineSound|common>/motor.ogg, loop 采样非合成; 初始 rate=0.25 gain=0。
- update 节流 64ms(L25622), 映射 U$(L25894-25900):
  pitch = speed<128 ? speed*0.01171875(=3/256)+0.25 : 1.5
  gain  = speed<64  ? speed*3/256+0.25 : 1

### 3.4 音效触发表
| 音效 | 资源 | 触发/参数 |
|---|---|---|
| 碰撞 | kart/crash.ogg | strength>0 且距上次>=2000ms; gain=clamp(strength*0.1, 0.1, 1) |
| 转向撞墙 | crash.ogg | 先停引擎源(motorInterrupted), update 重启 |
| 落地 | kart/shock.ogg | gain=clamp(strength*0.04, 0.1, 1) |
| 复位 | etc/reset.flac | 撞墙复位流程 |
| 漂移 | kart/drift.ogg loop | physics.state.drifting 开关 |
| 状态音 | engine_*/{boosterStart,boosterDrift,booster,boosterZone,boosterJumpZone,boosterDelivery,boosterPlay}.ogg | setState 状态变化切换单次播放(L25555-25563 状态 ID 表) |
| 双喷 | engine_*/dualBoosterReady.ogg(0x6 loop) / dualBooster.ogg(0xa loop) | engineGrade>6 |
| exceed/charger/变身 | exceed.ogg / charger.ogg / transforming.ogg | 对应 set 方法 |
| 路面 | road/road.bml + road/*.flac | enableRoadSound 门控(默认关); 音量按速度 volume0~volume100 插值; spacing 项间隔重放 |
| 倒计时/圈数 | etc/count_n/count_go/lab_count/final_lab.flac | coordinator 事件 countdown-number/countdown-go/lap/final-lap |
| UI 点击 | interface/click.flac | UI 回调 |
| 赛道事件音/环绕音 | surround/ + item/eventObject/ (ogg/wav/flac) | track marker: 距离衰减 maxRadius->minVolume; panning/spacing/timeLine 官方未实现会抛错 |

### 3.5 AudioContext 解锁
进入选择界面创建(L29172); 所有用户交互回调 ctx.resume()(L28780/28844/28909/28962/29006); 引擎 start() 内也 resume(L25615); 退出统一 close(L28536)。

### 3.6 最小可用实现清单
资源最小集: bgm main/single.ogg + 一个主题曲、engine_common/motor.ogg、kart/{crash,drift}.ogg、engine_common/booster.ogg、etc/count_n+count_go.flac、interface/click.flac。
节点: 1 个 AudioContext + 每 source 一个 gain; 引擎 64ms 节流 rate/gain 映射照抄; BGM 16 步 crossfade; 首次交互 resume。

---

## 四、速度表 / 仪表 / HUD

### 4.1 速度来源与换算
表显 km/h = |linearVelocity| x 3.6 (L24750, fround 3.5999999); 无其他系数。调试 HUD 同公式佐证(L18303)。

### 4.2 数字读数 X0 (L9169-9178)
kmh = trunc(speed).toString().padStart(3,'0')   // "007" 三位补零
seg = trunc(speed * 19/350)                      // 19 格条(0x13), 满格 = 350 km/h
条字符: i<seg ? (seg<0xf ? '1' : '2') : '0'      // >=15 格(约 268km/h)用高段色 '2'

### 4.3 渲染与节流
- 无 DOM HUD: XML Window/Panel/CharPanel 树 -> 纹理 quad -> THREE Mesh 批处理 -> 渲染进主 drawing buffer(L28616-28628, autoClear=false 叠加)。
- MqTacho key 缓存(L9272-9297): key = "wxh:kmh:speedGauge:preserve", 变化才重建几何, 否则只 render。
- kmh/kmh2 双层: displaySpeed >= autoChargeLowSpeed 切 kmh2 + side1..5 侧栏动画(100ms 递进)(L9964-10009)。

### 4.4 集气条 UI
- mainRatio = committedGauge / max(driftMaxGauge,1)(L24666); instantRatio = instantGauge/instAccelGaugeLength(L23643)。
- usable/full/exceed 三态提示(L23650-23656, 层名 instAccelGaugeUsable/On)。
- 条绘制 = 水平裁剪 uv.right = lerp(left,right,ratio)(Ch L10939), x0.99 防溢出。
- 满槽脉冲: ratio 变化重启 1s 计时, alpha = |sin(t*0.0025)|*255(L10785); GameplayUi 满帧闪 alpha = |sin(t*0.005)|(L12084)。
- 每帧 update({body,currentLap,totalLaps,elapsedMs,bestMs,speedSlots,boostRatio})(L28644-28656); 计圈/圈速也是 CharPanel 纹理数字(L12111+)。

### 4.5 转速表
未找到(rpm/needle/revolution 等全搜过); "Tachometer"即速度表; 引擎音由 hypot(v) 驱动, 无独立转速量。

### 4.6 最小实现建议
数字+19格条: kmh=trunc(|v|*3.6); String(kmh).padStart(3,'0'); fill=trunc(kmh*19/350); fill>=15 变色; 与上帧相同则跳过 DOM/纹理写(key 缓存语义)。集气条: div 宽度百分比 + usable 呼吸闪烁, 满帧闪 alpha=|sin(t*0.005)|。

---

## 五、迁移顺序建议(逐模块, 每步跑通 kart.html 再合下一个)

1. 动画映射修正(改动小收益大): f41/f42 改循环保持; 倒车删 f43/f44 相位机改 f45/f46 按 steer 符号直选; 补间统一分档 enterBlend(先统一 150ms crossfade); 一次性动作加 span 回落。
2. 物理模型: 标量 speed -> 力+二次阻力(去硬 cap), 重力 58.8, 转向角速度衰减; 2ms 子步可后置。
3. 速度表: 纯显示无依赖, 先做(配合物理改造即时可见)。
4. 漂移+集气: triggerPhase -> activeDrift -> decay 状态机; 集气 latSpeed^2*dt 时间加权; 氮气槽。
5. 喷气族: physicsState 状态机替代 Ctrl 即喷。
6. 音频: 最小集(engine+crash+drift+booster+count) -> 再扩 BGM/路面音。
