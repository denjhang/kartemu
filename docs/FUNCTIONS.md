# Kartemu 函数级交接文档(FUNCTIONS)

> 本文档以**函数为单位**记录 `deob_named.js` 中所有关键函数的:
> 签名 / 参数 / 返回值 / 调用关系 / 用法要点 / 所在行号。
> 用于在台式机上继续逆向与实现。
>
> - 源文件:`deob_named.js`(29741 行,106 类,1344 函数,3027 顶层符号)
> - 顶层符号索引见 [SYMBOLS.md](./SYMBOLS.md)
> - 模块级结论见 [UNDERSTOOD.md](./UNDERSTOOD.md) §25-§32
> - **函数级详解增补见 [FUNCTIONS_DETAIL.md](./FUNCTIONS_DETAIL.md)(2026-09-13, 全 § 逐函数吃透, 含勘误, 与旧条目冲突以它为准)**
> - 项目记忆与待办见 [PROJECT_MEMORY.md](./PROJECT_MEMORY.md)
>
> ## 阅读约定
>
> - **行号** = `deob_named.js` 中的 1-based 行号(与 SYMBOLS.md 对齐)
> - 混淆参数名 `_0x...` 已根据上下文标注语义名,如 `_0x30e332`(dt)
> - `h(x)` = `Math.fround` 包装的 float32 定点运算
> - 坐标系:D=数据Z-up / P=物理Y-up(ae 变换)/ outline=描边
> - 标注 ✅=已详述 / 📌=已索引待补 / ⏳=仅列清单
> - **2026-09-13**: 全部 📌/⏳ 小节已在 FUNCTIONS_DETAIL.md 中补齐为 ✅(§A.5/A.6/A.8/A.10/A.14/A.15、
>   §B.6-B.11、§C.6/C.8、§E、§F、§G、§H、§I、§J、§K、§L), 并含重要勘误(§I 旧行号作废、§E 键位表更正、
>   §H 无 AI 实现结论修订)

---

## 目录

- [§A. 物理引擎](#a-物理引擎) ✅
- [§B. 碰撞系统](#b-碰撞系统) ✅
- [§C. 赛道构建](#c-赛道构建) ✅
- [§D. 比赛流程 + UI](#d-比赛流程--ui) ✅
- [§E. 输入系统](#e-输入系统) ✅ →[详解](./FUNCTIONS_DETAIL.md)
- [§F. 音效系统](#f-音效系统) ✅ →[详解](./FUNCTIONS_DETAIL.md)
- [§G. 道具系统](#g-道具系统) ✅ →[详解](./FUNCTIONS_DETAIL.md)
- [§H. AI 系统](#h-ai-系统) ✅ →[详解](./FUNCTIONS_DETAIL.md)
- [§I. 渲染与场景图](#i-渲染与场景图) ✅ →[详解](./FUNCTIONS_DETAIL.md)
- [§J. 资源解析](#j-资源解析) ✅ →[详解](./FUNCTIONS_DETAIL.md)
- [§K. 数学库/工具](#k-数学库工具) ✅ →[详解](./FUNCTIONS_DETAIL.md)
- [§L. 顶层函数索引](#l-顶层函数索引) ✅ →[详解](./FUNCTIONS_DETAIL.md)

---

## §A. 物理引擎

> 类:`k`(F1 的父类?)与 `F1` 实例方法的物理相关部分。
> 关键属性:`body` / `runtime` / `wheels` / `tuning`。
> 详见 UNDERSTOOD.md §25。

### A.1 `stepSubstep(dt, x$, ctx)` — 物理主循环 ✅

- **行号**:L23845-L23870
- **类**:`k`(物理 body)
- **参数**:
  - `dt`(float32):子步时长,约束 `0 < dt ≤ 0.002` 秒,否则 throw
  - `x$`(Z$ 碰撞网格):用于 rayQuery / queryObb
  - `ctx`:扫描上下文,含 specialRoad / 特殊路面信息
- **返回**:无(更新 this.body/runtime/wheels 状态)
- **调用序列**(每子步):
  1. `updateStateTimer(dt)` — 状态计时(L23850)
  2. `updateDriftLifecycleTimers(dt)` — 漂移生命周期
  3. `scanSpecialRoad(ctx)` — MR/HW 特殊路面探测(L23850)
  4. `rebuildBodyState(force, torque)` — 清零外力,投影局部速度(L23850, 输出 `_0x2deb99`=force, `_0x5e2856`=torque)
  5. `probeWheels(ctx, is3D)` — 4 轮射线探测(L23850)
  6. `applyResetSurfaceRequest()` — 리셋 路面触发重生
  7. 若 `is3D`(飞行/MR/HW):`applyFull3DRail(dt, x$, ctx, force, torque)`
  8. 若接地/MR/HW 接触(非飞行):
     - `applySuspension(dt, force, torque)`
     - `applyLongitudinal(dt, input, force)` — 非驱动抑制时
     - `applySteeringAndTires(dt, input, force, torque)` — 非驱动抑制时
  9. `applyRoadConsumers(dt, force)` — bcharge 充电带等(L23858)
  10. `applyBoosterChargeSurface()` — bcharge 直接加 gauge
  11. 若飞行:`applyAirState(force, torque)`(L23859)
  12. `updateTachometerIncGauge(is3D)`(L23860)
  13. `applyDrag(force, torque, is3D)` — 阻力
  14. 非 3D:`captureRail(dt, ctx)` + `returnToStandard(dt, ctx)`
  15. `integrateVelocity(dt, force, torque, extraForce)` — 速度积分
  16. `updateInstantAccelerationGauge(dt)`
  17. `accumulateDriftGauge(dt, is3D)` / `accumulateSpeedGauge(dt, is3D)`
  18. `updateResetGaugeRefill(dt, currentMs)`
  19. 若 3D:`integrateFull3D(dt)`,否则:
      - `resolvePrimaryCollision(ctx, x$)` — OBB 碰撞
      - `updatePrimaryAutomaticResetTimers(collision, dt)`
      - `resolveStaticObstacles(ctx)` — 障碍
      - `updateObstacleAutomaticResetTimer(obstacle, dt)`
      - `resolveTrackEvents(ctx)`
      - `applySupplementalWheelRecovery(ctx)` — 未触地轮补探
      - `applySlipAlignment()` — 打滑对齐
      - `integrateStandardOrientation(dt)` — 姿态积分
      - `updateCollisionGaugeOwners(obstacle)`
- **调用点**:L23844 `this["stepSubstep"](h(h(_0x247077) * h(0.001)), _0x55cdfa, _0x8b687a)`
  - 外部传毫秒,乘 0.001 转秒,再 fround
- **用法**:
  ```js
  // 外部循环按固定 2ms 子步推进
  for (let remaining = frameMs; remaining > 0; remaining -= 2) {
    body.stepSubstep(Math.fround(Math.min(2, remaining) * 0.001), collisionMesh, ctx);
  }
  ```

### A.2 `applyLongitudinal(dt, input, force)` — 纵向动力学 ✅

- **行号**:L24125-L24167
- **类**:`k`
- **参数**:
  - `dt`:子步时长(秒,float32)
  - `input`:驾驶输入,含 `forward`(0/1)/`reverse`(0/1)
  - `force`:累积外力向量(修改 in-place)
- **返回**:无(改 `force`,设 runtime.reverseAccumulator)
- **局部投影**(从 runtime 读):
  - `localForwardSpeed` = dot(velocity, forward)
  - `localRightSpeed` = dot(velocity, right)
- **驱动方向** `driveDir`:
  - `hwContact && !grounded`: `q(specialNormal, -10)`(HW 接触未接地)
  - 否则:`cross(right, averageNormal)`(地面投影)
- **前进加速**(`input.forward > 0`):
  - `baseAccel = liveForwardAccel · driveScale`
  - `physicsState=1`(起步):用 `startForwardAccelSpeed` 替代
  - `physicsState 1..11`:乘 `boostAccelFactor`(或 `transAccelFactor` 当 `useTransformBooster`)
  - `physicsState=2`(漂移):额外 ×`driftBoostMulAccelFactor`
  - `physicsState=10`(双喷):额外 ×`dualMulAccelFactor`
  - `instantAccelerationActive`:×`instAccelFactor`(低速×2)
  - `oneSubstepDrift`:直接用 `driftEscapeForce`(漂移逃脱)
  - 若 `localForwardSpeed < 0`(倒着走):额外反向力 `body.forward · min(bodySpeed,5) · negativeForwardScale`
- **倒车**(`input.reverse > 0`):
  - `reverseAccumulator += dt`,达 0.2s 后生效
  - 反向力 `driveDir · -backwardAccel · driveScale · input.reverse`
- **滑行制动**(不前进不倒车):
  - 接地且 |侧速|<0.2:用 `gripBrake`
  - 否则用 `slipBrake`
  - 力 = `horizontalSpeed · brakeFactor`
- **重力补偿**:未在此函数内,见 `applyDrag`

### A.3 `applySteeringAndTires(dt, input, force, torque)` — 转向与轮胎 ✅

- **行号**:L24168-L24257
- **类**:`k`
- **参数**:
  - `dt`:子步时长
  - `input`:含 `rawSteer`(-1..1)
  - `force`:累积外力(修改)
  - `torque`:累积力矩(修改)
- **早退**:`driveSteeringSuppressed=true` 时直接返回
- **转向角**:
  - `maxAngle = rad(maxSteerDeg)`(来自 tuning)
  - `scale = exp(-|localForwardSpeed|/steerConstraint · steeringExponentialScale)` 速度衰减
  - `steeringAngle = scale · rawSteer · maxAngle`
  - `steeringEnvelope` 平滑(取当前→目标较小值)
- **漂移判定**:
  - `lateralRatio = localRightSpeed / speed`(侧向速度比)
  - `angularDrift = (angularVelocity.y · Pr) / speed`(角速度/速度)
  - 触发: `|localRightSpeed| > |localForwardSpeed|·1.2` 且 `speed > 15`
  - `triggerPhase`(触发期)持续 `driftTrigTime`
  - `activeDrift` 正式漂移
  - `tireEnvelope`(0→1 渐进)
- **轮胎力**(地面力 G):
  - 前轮 `F_front = G · (frontGripFactor + offset) · (steerAngle·dirSign - lateralRatio - angularDrift)`
  - 后轮 `F_rear = G · (rearGripFactor + offset) · (-lateralRatio + angularDrift)`
  - 漂移时 × `driftSlipFactor · tireEnvelope`
  - dirt 路面:从 `_s` 表查偏移,额外 `_s[0]` 速度平方根衰减
- **力矩合成**:
  - 侧向力 = `(F_front + F_rear) · right`
  - 偏航力矩 = `Pr·F_front - Pr·F_rear`(前后力臂相反)
  - 滚转力矩 = `-(F_front+F_rear)·driftLeanFactor`(车身侧倾)
  - `cornerDrawFactor`:非漂移转弯额外回正力
- **依赖属性**:`tuning.maxSteerDeg/steerConstraint/steeringExponentialScale/frontGripFactor/rearGripFactor/driftSlipFactor/driftLeanFactor/cornerDrawFactor` 等

### A.4 `probeWheels(ctx, is3D)` — 轮子探测 ✅

- **行号**:L23914-L23935
- **类**:`k`
- **参数**:
  - `ctx`:扫描上下文(含 specialRoad)
  - `is3D`:是否 3D 模式(MR/HW)
- **返回**:无(写 `this.wheels` 的 `grounded/compression/normals[i]/averageNormal/roadDescriptor/obstacleRayHit/contactRisingEdge`)
- **行为**:
  - 4 轮从 body 沿 -up 射线(距离 2·di ≈ 0.2m)
  - 每轮:`compression`(0..2·di), `compressionDelta`, `normals[i]`
  - `grounded` = 任意轮触地
  - `averageNormal` = 触地轮法线均值(车身姿态基准)
  - `roadDescriptor` = 路面标签
  - `contactRisingEdge` = 本帧新触地 → 触发 `landingMotionTrigger`
  - MR/HW 接触时射线查询模式不同
- **补探**:`applySupplementalWheelRecovery(ctx)`(L23936)对未触地轮在 body 上方 1m 再射

### A.5 `applySuspension(dt, force, torque)` — 悬挂 📌

- **行号**:L24089-L24124(近似)
- **类**:`k`
- **参数**:同 applyLongitudinal
- **行为**:每轮基于 compression/compressionDelta 计算弹簧+阻尼力,合到 force/torque
- **待补**:完整公式(可参考 UNDERSTOOD.md §25.5)

### A.6 `applyDrag(force, torque, is3D)` — 阻力 📌

- **行号**:L24270-L24300(近似)
- **类**:`k`
- **参数**:force/torque/is3D
- **行为**:基于 `liveDragFactor` 与 body 速度,水平+竖直方向阻力
- **待补**:公式与 `liveDragFactor` 来源

### A.7 `integrateVelocity(dt, force, torque, extraForce)` — 速度积分 ✅

- **行号**:L23860 调用,实现待定位
- **类**:`k`
- **行为**:
  - `linearVelocity += (force + extraForce) · dt / mass`
  - `angularVelocity += (torque · invInertia) · dt`
  - `bodySpeed = |linearVelocity|`
- **待补**:完整实现行号

### A.8 `integrateStandardOrientation(dt)` — 姿态积分 📌

- **行号**:L23866 调用,实现待定位
- **类**:`k`
- **行为**:基于 averageNormal + 角速度,更新 body 朝向(forward/right/up)
- **用法**:仅在非 3D 模式调用

### A.9 `rebuildBodyState(force, torque)` — 清零外力 ✅

- **行号**:L23850 调用,L23881 实现
- **行为**:
  - `force.set(0,0,0)` / `torque.set(0,0,0)`
  - 投影 body 速度到局部空间,写 runtime.localForwardSpeed/localRightSpeed/localUpSpeed
- **用法**:每子步开头清零,后续 apply* 函数累积

### A.10 `applyAirState(force, torque)` — 空中物理 📌

- **行号**:L24258-L24269(近似)
- **类**:`k`
- **行为**:飞行时只加重力 + 空气阻力,无轮子

### A.11 `accumulateDriftGauge(dt, is3D)` / `accumulateSpeedGauge(dt, is3D)` — Gauge 累积 📌

- **行号**:L23860 调用,实现 L24371-L24394
- **行为**:见 UNDERSTOOD.md §25.4

### A.12 `applyBoosterChargeSurface()` — bcharge 路面充能 ✅

- **行号**:L24394-L24400(近似)
- **行为**:`committedGauge += 1.6`(上限 `driftMaxGauge`)

### A.13 `startNormalBooster()` — 启动普通加速 ✅

- **行号**:L24401-L24420(近似)
- **行为**:`physicsState=3`,设 `stateRemainingMs` + `boostTime`

### A.14 状态/动画相关函数 📌

- `updateStateTimer(dt)` L23850:physicsState 计时
- `updateDriftLifecycleTimers(dt)`:漂移生命周期
- `scanSpecialRoad(ctx)` L23883:MR/HW 特殊路面探测
- `applyResetSurfaceRequest()`:리셋 路面触发重生
- `applyRoadConsumers(dt, force)`:路面消费者(bcharge 充电带等)
- `applySlipAlignment()`:打滑对齐
- `applySupplementalWheelRecovery(ctx)`:未触地轮补探
- `updateCollisionGaugeOwners(obstacle)`:碰撞 gauge 归属

### A.15 漂移相关 📌

- `commitDriftGauge()`:pendingGauge → committedGauge
- `classifyDualBoosterReady()` / `refreshDualBoosterReady()`:双喷准备
- `armDualBooster()` / `enterDualBooster()`:双喷启动
- `updateDualBooster()`:双喷更新

---

## §B. 碰撞系统

> 类:`Z$`(网格) / `Bu` / `Fu`(三角形相交) / `k`(查询入口)
> 详见 UNDERSTOOD.md §26。

### B.1 `Z$.constructor(triangles)` — 网格构建 ✅

- **行号**:L26491-L26539
- **类**:`Z$`
- **参数**:
  - `triangles`: `{a, b, c, normal, roadDescriptor, auxiliaryDirection}[]`
- **预处理**:
  - 每三角形计算 `minX/maxX/minZ/maxZ` bounds
  - **法线 y<0 时翻转绕序**: `[a, c, b]` 替换 `[a, b, c]`
- **4m×4m 均匀网格**:
  - 遍历三角形 bounds,每 4m × 4m cell 检查三角形是否与 cell AABB 相交(用 `Q$` 函数)
  - cell key = `(x>>2) + ',' + (z>>2)`(注意:y=-z 坐标变换)
  - `cells = Map<key, triangleIndex[]>`
- **拒绝动态**:`movingSurface` 的三角形不进静态网格
- **属性**:`this.triangles` / `this.cells`

### B.2 `Z$.rayQuery(origin, direction, allowWall)` — 射线查询 ✅

- **行号**:L26540-L26575
- **类**:`Z$`
- **参数**:
  - `origin`:射线起点(P 空间)
  - `direction`:方向(归一化)
  - `allowWall`:是否允许墙面命中(false 时跳过 `|normal.y|<0.65` 的三角形)
- **返回**:`{point, normal, fraction, roadDescriptor, auxiliaryDirection, surfaceVelocity:{0,0,0}}` 或 null
- **流程**:
  1. 计算 ray AABB,遍历覆盖的 cells
  2. 收集候选三角形(Set 去重)
  3. `Fu(triangle, origin, direction)` 三角形相交测试 → 返回 fraction(t)
  4. 选择最小 fraction 的命中
- **用法**:`probeWheels` 内对每轮位置调用

### B.3 `Z$.queryObb(obb)` — OBB 查询 ✅

- **行号**:L26576-L26606
- **类**:`Z$`
- **参数**:`obb = {center, halfExtents, axes}`
- **返回**:命中三角形数组 `[{centroid, normal, roadDescriptor, ...}]`
- **流程**:
  1. OBB 在 X/Z 平面投影确定 cell 范围
  2. 收集候选三角形(Set 去重)
  3. `Bu(triangle, obb)` SAT 分离轴测试
- **用法**:`resolvePrimaryCollision` / `resolveStaticObstacles` / `resolveTrackEvents` 内调用

### B.4 `resolvePrimaryCollision(ctx, x$)` — 主碰撞 ✅

- **行号**:L24505-L24535
- **类**:`k`
- **参数**:
  - `ctx`:扫描上下文
  - `x$`:Z$ 网格
- **返回**:碰撞结果(用于 `updatePrimaryAutomaticResetTimers`)
- **行为**:
  - OBB 碰撞检测后:
  - 法向速度衰减:`linearVelocity -= normal · dot(velocity, normal) · responseFactor`
  - 区分高障碍物(墙面) vs 普通碰撞
  - `collisionResponseMagnitudeB6C` / `collisionMotionStrength` 计算
  - 高强度(>30)→ f47 强碰撞动画, 15-30 → f48 轻碰
- **相关**:`applyHighObstacleAngularResponse()` / `applyWallObstacleAngularResponse()` 处理角响应

### B.5 `resolveStaticObstacles(ctx)` — 障碍物碰撞 ✅

- **行号**:L24536-L24570(近似)
- **类**:`k`
- **参数**:`ctx`
- **返回**:障碍碰撞结果
- **行为**:OBB 对 obstacleSurface 网格的查询
- **相关**:`commitObstacleSnapshot()` / `updateObstacleAutomaticResetTimer()`

### B.6 `resolveTrackEvents(ctx)` — 赛道事件 📌

- **行号**:L24571-L24600(近似)
- **类**:`k`
- **参数**:`ctx`
- **行为**:查询 event 三角形,触发 trackEventEffectRequests

### B.7 `queryEventObb(obb)` / `queryObstacleObb(obb)` 📌

- **行号**:见 SYMBOLS.md class k
- **行为**:对 event / obstacle 单独网格的 OBB 查询(可能内部委托 Z$.queryObb)

### B.8 `completeCheckpointPose(...)` — 重生姿态 ✅

- **行号**:L23700-L23722
- **行为**:按 gate 帧重置 `body.position / forward / up`,可选清零 `linearVelocity / angularVelocity`
- **调用点**:L29091(从当前 section 准备 reset pose → commit route state → 重新同步 presentation)

### B.9 `Fu(triangle, origin, direction)` — 三角形-射线相交 📌

- **行号**:见 SYMBOLS.md(顶层函数)
- **返回**:fraction(t 值)或 -1
- **待补**:完整算法(Möller–Trumbore 变体)

### B.10 `Bu(triangle, obb)` — 三角形-OBB SAT 📌

- **行号**:见 SYMBOLS.md
- **返回**:boolean
- **待补**:完整 SAT 轴列表

### B.11 `Q$(triangle, cellAabb)` — 三角形-AABB 相交 📌

- **行号**:见 SYMBOLS.md
- **返回**:boolean
- **用法**:Z$ 构建时判断三角形归哪个 cell

---

## §C. 赛道构建

> 类:`fx`(TrackContainer 解析) / 顶层 `parseToRoad` / `buildRouteGraph`
> 详见 UNDERSTOOD.md §27。

### C.1 `parseTrackContainer(obj)` — TrackContainer 解析 ✅

- **行号**:L4533-L4558
- **参数**:`obj`(Object47/Typed27 节点)
- **返回**:`{name, scene, trackObjects[]}`
  - `scene`:Relement 根节点(场景图)
  - `trackObjects[]`:赛道对象(含 TrackObject "track" + ToRoad 对象)
- **校验**:所有 trackObjects 均为 TrackObject 类型
- **scene 子树**:含所有渲染网格(ReTriList/ReTriStrip/ReToonRigid 等)

### C.2 `parseToRoad(obj)` — ToRoad 路线解析 ✅

- **行号**:L4641-L4675
- **参数**:`obj`
- **返回**:ToRoad 对象,含:
  - `cyclic`:是否环形
  - `records[]`:每条 record
    - `name`:路段名
    - `positions[]`:位置点数组(vec3)
    - `gateIndices[]`:检查门索引(每门 3 个 position 索引,至少 2 门)
    - `surface`:表面标签
    - `surfaceIndices[]`:表面索引(与 frames 对应)
    - `frames[]`:`{position, storedForward, up}` 路线帧

### C.3 `buildRouteGraph(trackObjects)` — Section 图构建 ✅

- **行号**:L4101-L4270
- **参数**:`trackObjects` 数组
- **输入解析**:
  - 从 TrackObject "track" 的 `sa` 属性解析 `<course>` XML
  - `<course>` 子元素:
    - `<road name="..." start="..." end="..." final="..." reverse="...">` — 引用 ToRoad
    - `<branch>` — 分支,含多个 alternative 子树
- **section 数据结构**:
  - `{sequenceIndex, frames[], length, surface, outgoing[], incoming[]}`
  - `outgoing/incoming = {gate, section}`(gate 三角形 + 连接目标 section)
- **road 展开**:
  - start/end 指定 ToRoad records 范围
  - reverse=true 时反向遍历 records,帧翻转(reverseFrame)
  - 帧全部经 `roadFrameToPhysics`(ae 变换)
  - `routeLength(frames)` 计算总长
- **branch 处理**:
  - 每个 `<alternative>` 递归调用构建子 section 列表
  - 分支入口 gate 连接到父 section,出口连接到后续 section
  - 第一个 alternative 的帧用于主 section
- **闭环处理**:`_0x5a85ea=true` 时将首 section 入口连接到末 section

### C.4 起点/发车位置 ✅

- **行号**:L4251-L4268
- **行为**:
  - `start = firstSection.frames[0]` 经 `physicsToPresentation` 转换
  - `position = frame.position - forward · 0.05`(后退 5cm)
  - `up = normalize(cross(forward, (0,0,1)))` 再 `normalize(cross(right, forward))`
  - 返回:`{sections, firstSection, lastSection, start:{position, forward, up}}`

### C.5 `gateTrisFromRecord(record)` — 门三角形构建 ✅

- **行号**:L4272-L4284
- **参数**:`record`(ToRoad record)
- **行为**:
  - 从 record 的 `gateIndices` 取 2 组(每组 3 个 position 索引)
  - 构建正向/反向门三角形
  - 门三角形法线 = `frames[0].storedForward`(或反向取负)
  - `final` 标记:最后一个 record 的 gate 用于终线

### C.6 `roadFrameToPhysics(frame)` / `physicsToPresentation(v)` 📌

- **行号**:见 SYMBOLS.md
- **行为**:
  - `roadFrameToPhysics`:把 D 空间帧经 `ae` 变换到 P 空间
  - `physicsToPresentation`:P→D 逆变换 `(x, -z, y)`
- **用法**:赛道帧进入物理前转换,展示时反向

### C.7 `updateRacing(...)` / `updateLapTiming(...)` — 跑圈计时 ✅

- **行号**:L27412-L27444
- **行为**:见 UNDERSTOOD.md §27.5
  - `routeProgress > finishThreshold` 触发 finish
  - 每圈记录 lapStartedAtMs,计算单圈时间与最佳圈
  - 最终圈:`finalLapShown` + "final-lap" 事件

### C.8 `routeLength(frames)` / `routeProgress` 计算 📌

- **行号**:见 SYMBOLS.md
- **行为**:帧累计长度 / 当前位置在 section 的进度

---

## §D. 比赛流程 + UI

> 类:`GameApp`(主) / `lg`(raceLifecycle) / `im`(driveCameraman) / `wB`(surroundCameraman)
> 详见 UNDERSTOOD.md §29。

### D.1 `GameApp` 主类 ✅

- **行号**:L28428-L28530
- **构造**:初始化 renderer/scene/camera(50° FOV, 0.1-700m)/hud/input/touchControls
- **挂件**:`driveCameraman` / `surroundCameraman` / `warpNext` / `lightFactor` / `cameraShake` / `cameraWave`
- **状态**:`raceLifecycle(lg)` / `raceCameraMode="ready"`
- **资源**:`rhoLibrary` / `p3528Resources` / `activePhysics` / `activeTrack` / `activeCoordinator`
- **渲染挂件**:`activeKartEffects/Trails/DriftEffects/MotionBlur/ZetAir/ShockWave/Exhaust/Crash/Charger`
- **环境**:`activeRain/RainAudio/Snow/Admission/Selection`
- **UI**:`activeGameplayUi/Action2D/Result/TimeAttackReady/Taskbar/Settings/TrackSelect/Garage/Pause`
- **音频**:`activeKartAudio/RaceBgm/AudioContext/InterfaceAudio/CountdownAudio`
- **localStorage**:`timeAttackRecords(Map)`,`timeAttackReadyOptions(speed=7/booster=0/showGhost=true)`
- **主循环**:`frame = requestAnimationFrame` 回调,`updateAndRender` 计算有效时间 → 更新物理/赛道/驾驶/相机

### D.2 `raceLifecycle` (lg) 状态机 ✅

- **行号**:L27347-L27459
- **phase**:
  - 0:ready(初始)
  - 1:countdown(倒计时)
  - 2:racing(比赛中)
  - 3:finishAccepted(完赛已确认)
  - 4:result(结算)
  - 5:paused(暂停)
- **countdown 子状态**(L27392-L27411):
  - 0→1:`startAtMs-6000ms` → "countdown-prepare"
  - 1→2:`startAtMs-3000ms` → "countdown-number 3" + "switch-drive-camera"
  - 2→3:`startAtMs-2000ms` → "countdown-number 2"
  - 3→4:`startAtMs-1000ms` → "countdown-number 1"
  - 4→phase 2:`startAtMs+0ms` → "release-race" + "countdown-go"
- **startAtMs**:`effectiveTime + 7000ms`(7 秒倒计时,含 1 秒准备)
- **startBooster 窗口**:`|time - startAtMs| ≤ 100ms`(起喷窗口)

### D.3 `togglePause()` / `effectiveTime(rawMs)` — 暂停/恢复 ✅

- **行号**:L27376-L27383
- **行为**:
  - `togglePause`:phase 2↔5(racing↔paused)
  - `pausedTotalMs`:累计暂停时长
  - `effectiveTime(rawMs) = rawMs - pausedTotalMs - (paused ? rawMs-pauseAnchor : 0)`
    即暂停时冻结有效时间

### D.4 完赛流程 ✅

- **行号**:L27412-L27459
- **步骤**:
  1. `routeProgress > finishThreshold` → finish 事件 + switch-surround-camera + play-result-bgm
  2. +3000ms → phase 3(finishAccepted)
  3. +3000ms → phase 4, "show-result" (elapsedMs, bestMs, isNewRecord)
  4. +8000ms → "return-to-ready"

### D.5 `updateHud()` — HUD 更新 ✅

- **行号**:L28644-L28656
- **行为**:向 `activeGameplayUi` 传入 `currentLap / totalLaps / elapsedMs / bestMs / speedSlots / boostRatio`
- **speedSlots**:速度档位显示
- **boostRatio**:加速器进度条

### D.6 相机系统 ✅

- **类**:`im`(driveCameraman) / `wB`(surroundCameraman)
- **行为**:
  - `driveCameraman`(im 类,L12390):尾随相机,countdown "3" 时切换
  - `surroundCameraman`(wB 类,L27481):环绕相机,完赛时切换
  - `readyCamera`:准备阶段静态相机
  - `warpNextCamera`(xmlAttr$ 类):传送带相机
  - `fairyFovFactor`:FOV 特效(L23267-L23303)
  - `cameraShake` / `cameraWave`:震动/波浪效果

### D.7 GameApp 关键方法清单 ✅

> 236 方法,95 属性。仅列核心,完整清单见 SYMBOLS.md。

- **生命周期**:`beginRace()` / `startRace()` / `startRaceFromReady()` / `finishRace()` / `restartRace()` / `restartRaceFromPause()` / `returnToReady()` / `resetRace()`
- **准备**:`enterTimeAttackReady()` / `prepareStartupReady()` / `releaseRaceForReady()` / `scheduleStart()`
- **渲染**:`updateAndRender()` / `render()` / `renderGameplayUi()` / `updateMatrixWorld()` / `updateProjectionMatrix()`
- **驾驶**:`updateDriving()` / `drainDrivingInput()` / `handleDrivingCommand()` / `handleTimeAttackDrivingCommand()` / `handleTimeAttackActions()`
- **相机**:`updateActiveRaceCamera()` / `updateRaceCamera()` / `updateSurroundCamera()`
- **赛道**:`updateRoad()` / `updateMovingRoads()` / `updateObstacles()` / `updateTimeAttackRoute()`
- **音频**:`playReady()` / `playResult(isWin)` / `playCollision()` / `playLandingShock()` / `playReset()` / `playLap()` / `playNumber()` / `playGo()` / `playFinalLap()`
- **资源**:`loadP3528Resources()` / `loadCharacterAsset()` / `loadVehicleAsset()` / `loadVehicleRuntime()` / `loadRaceCharacters()` / `preloadContainers()` / `preloadGameplayContainers()`
- **状态**:`setRaceState()` / `setRaceMotionLocked()` / `setPaused()` / `setFullPhysicsBypass()` / `setExceedActive()` / `setDriftActive()` / `setDualBoostAuto()`
- **重置**:`resetFromRouteFrame()` / `completeCheckpointPose()` / `prepareCurrentSectionReset()` / `commitCurrentSectionReset()` / `restoreResetInteraction()`
- **输入**:`setKeyMap()` / `setInputPair()` / `cancelControls()` / `hardCancelControls()` / `cancelAll()` / `setEnabled()`
- **车库/选择**:`openGarage()` / `openTrackSelect()` / `openSettings()` / `selectRace()` / `selectReadyTrack()` / `replaceTrack()`

---

## §E. 输入系统 ✅

> 类:`n$`(键盘,L22627-L22709) / `u$`(触摸,L22960-L23117) / 键盘状态机 `nP`(L17113-L17228) / 自动前进 `s$`(L22714-L22748) / 布局编辑器 `a$`(L22756-L22896) / 物理子步 `k$`(L23465)
> 详见 UNDERSTOOD.md §31。

### E.1 动作枚举 `ft` 与绑定表 `dr`(L17097-L17321)✅

- `ft`(L17097-L17112):`SteerLeft=0, SteerRight=1, Forward=2, Reverse=3, Drift=4, UseItemOrBooster=5, ReorderItems=6, SecondaryItem=7, GaugeState=8, DisplayMode=9, Help=0xa, Reset=0xb, ModeImpulsePositive=0x19, ModeImpulseNegative=0x1a`
- `dr`(L17233-L17321):22 个绑定 `{index, action, defaultKeyCode}`,键码为 **DirectInput 扫描码**(非 KeyboardEvent.code):
  - `0:SteerLeft=0xCB(←)` / `1:SteerRight=0xCD(→)` / `2:Forward=0xC8(↑)` / `3:Reverse=0xD0(↓)`
  - `4:Drift=0x2A(ShiftL)` / `5:UseItemOrBooster=0x1D(CtrlL)` / `6:ReorderItems=0x38(AltL)` / `7:SecondaryItem=0x2C(Z)` / `8:GaugeState=0x39(Space)` / `9:Reset=0x13(R)`
  - 小键盘副键:`0xA:SteerLeft=0x4B(Num4)` / `0xB:SteerRight=0x4D(Num6)` / `0xC:Forward=0x48(Num8)` / `0xD:Reverse=0x50(Num2)` / `0xE:Drift=0x36(ShiftR)` / `0xF:UseItemOrBooster=0x9D(CtrlR)` / `0x10:ReorderItems=0xB8(AltR)`
  - `0x12:ModeImpulsePositive=0x2C(Z)` / `0x13:ModeImpulseNegative=0x2D(X)` / `0x14:GaugeState=0x2D(X,与 0x13 同键)` / `0x15:DisplayMode=0x17(I)` / `0x16:Help=0x3B(F1)`
- `an`(L17322-L17325):`Object.fromEntries(dr.map(({index,defaultKeyCode})=>[index,defaultKeyCode]))` — 默认 keyMap(index→扫描码)
- `cy`(L17326-L17451):扫描码→`[显示名, 是否可绑定]` 表(如 `0x2A:['Shift (Left)',true]`,`0x40:['F6',false]` 不可绑定)
- `sP`(L17452-L17568):`KeyboardEvent.code → 扫描码` 反查表(`'Escape':1, 'KeyW':0x11, 'ArrowUp':0xC8, ...`)
- `hy(code)`(L17570-L17572):`= sP[code]`,KeyboardEvent.code → 扫描码
- `Oh(scancode)`(L17574-L17576):`= cy[scancode]?.[0] ?? ''`,扫描码 → 显示名
- `ly(scancode)`(L17578-L17580):扫描码是否可绑定(`cy[..][1]===true`)
- `oP(record)`(L17582-L17590):校验自定义键位:必须为对象、**恰好 22 个绑定**、每键可绑定;否则抛中文错误
- `X5(map,index,code)`(L22550-L22552):检测某键是否已被其他绑定占用(0x12/0x13 除外)
- `vo(code,keyMap)`(L22618-L22625):`hy(code)` 得扫描码 → 过滤 `dr` 中 `keyMap[index]===扫描码` 的项 → **动作数组**(一键可映射多动作)
- F6/F7/F8 调试开关:`dy`(L17604-L17608):`{F6:'enableRoadSound', F7:'fxEnabled', F8:'bgmEnabled'}`(设置界面 dialogShortcut 亦放行 F9/F10/F11/Ctrl+P,L22542)
- 暂停键:GameApp `onGlobalKeyDown`(L29610):`started && code==='Escape'` → `togglePause()`(**KeyP 不是全局暂停键**,仅在 Ctrl+P 被设置对话框消费)

### E.2 `n$` 类(键盘/触摸统一输入管理,L22627-L22709)✅

- 构造(L22637-L22642):`window.addEventListener('keydown'/'keyup', {passive:false})` + `document.addEventListener('focusin')`
- 状态字段(L22628-L22636):`records[]`(原始事件队列) / `keyboardRecordCount` / `transitions[]`(本轮输出) / `releasedKeys:Set` / `keyboardActions:Set` / `touchActions:Set` / `cancelled` / `enabled` / `keyMap=an`;`r$=0x1f`(L22626)为键盘 record 队列上限 31
- `drain()`(L22643-L22656):逐条消费 records:
  - 键盘 record(`"code" in rec`):`vo(code,keyMap)` 展开为动作,逐动作 `append('keyboard:'+code, action, down)`
  - 触摸 record:`applyTouchAction(action, down)`
  - 清零 `keyboardRecordCount`,splice 返回 `{transitions, cancelled}` 并复位 `cancelled`
- `onKeyDown`(L22679-L22682):`enabled` 且目标非输入框(`Nc`,L22711-L22713:input/textarea/select/contenteditable)才处理;若映射到动作则 `preventDefault()`;**非自动重复**才 `appendKeyboardRecord(code,true)`
- `onKeyUp`(L22683-L22685):先 `releasedKeys.add(code)`,再同上,`appendKeyboardRecord(code,false)`
- `isKeyboardRepeat(e)`(L22689-L22691):`e.repeat && !releasedKeys.delete(code)` — 用 releasedKeys 区分真释放后的重复按下
- `appendKeyboardRecord(code,down)`(L22694-L22698):键盘 record 队列满 31 时删最旧键盘 record,否则计数 +1,入队
- `append(source,action,down)`(L22699-L22708):维护 `keyboardActions`;若该动作正被 touch 按住则**不产生 transition**(touch 优先);否则 push `{source:'keyboard:xxx', sourceKind:'keyboard', action, down}`
- `setTouchAction(action,down)`(L22661-L22665):`enabled` 才把触摸事件入 records;`applyTouchAction`(L22666-L22672):维护 `touchActions`,若 keyboard 未按住同动作则 push `sourceKind:'touch'` transition
- `setEnabled(b)`(L22673-L22674):关闭时 `cancelAll()`;`cancelAll()`(L22675-L22676)= `cancelGameplayInput()` + 清 releasedKeys
- `cancelGameplayInput()`(L22692-L22693):清空 records/transitions/keyboardActions/touchActions,置 `cancelled=true`(下游 drain 后联动 `drivingInput.cancel()` + `physics.cancelControls()`,L29072)
- `dispose()`(L22677-L22678):移除监听 + 禁用
- GameApp 装配(L28433):`this.input = new n$(); input.setKeyMap(gameOptions.keyMap); input.setEnabled(false)`(比赛阶段再开)

### E.3 `u$` 类(触摸控件,L22960-L23117)✅

- 构造(L22961-L22962):注入 DOM:`SIM` 菜单按钮 + `<dialog class="touch-menu">`(显示/隐藏按键、自动前进、暂停、全屏、调整按键、返回)+ `.touch-pad`:
  - 修饰键组(`touch-modifiers`):`Drift`(漂移)/ `ft.UseItemOrBooster`(氮气)/ `ft.GaugeState`(释放超负荷)
  - 方向组(`touch-arrows`):`Forward`(带 AUTO 角标)/ `SteerLeft` / `Reverse` / `SteerRight`
- 字段(L23002-L23010):`touchCapable = navigator.maxTouchPoints>0`;`usingTouch = touchCapable && coarsePointer.matches`;`autoForward = d$()`(localStorage `kartsim.auto-forward`,L22953/L23123);`autoForwardSuspended = document.hidden`;`keyMap = an`
- `bindButton(btn)`(L23032-L23046):按 `data-drive` 建立按钮→ft 动作;`pointerdown`(主键、pad 可见、非编辑态):`preventDefault()` + `useVirtualInput()` + `setPointerCapture`;`pointers.set(pointerId, action)`;仅当该动作尚无指针按住时才 `onAction(action,true)`(多点触控去重)
- `releasePointer(id)`(L23047-L23052):pointerup/cancel/lostpointercapture 统一走此;仅当该动作已无任何指针按住才 `onAction(action,false)`
- `onTouchEnd`(L23053-L23057):`touches.length===0` 时释放全部 touch 指针
- `releaseAll`(L23026-L23029):`suspendAutoForward()` + 释放所有指针
- `onAction` 回调即 `input.setTouchAction(action,down)`(L28433 构造传入);第 3 参回调为 `togglePause`,第 4 参为 `setAutoForwardEnabled`
- `setRaceState(available,paused)`(L23011-L23012) / `refresh()`(L23058-L23061) / `refreshPad`(L23062) / `drivingPadVisible`(L23064-L23065):`touchCapable && available && !paused && 可见 && !menu.open`
- 自动前进:`refreshAutoForward`(L23066-L23068) → `setAutoForwardAllowed = autoForward && usingTouch && !suspended && padVisible`;`setAutoForwardActive`(L23023-L23025)给 Forward 按钮加 `is-auto-forward` 类;`onAutoForwardToggle`(L23075-L23083)写 localStorage,失败提示"仅本次有效"
- 模式切换:`useVirtualInput()`(L23073-L23074)置 usingTouch=true;`onTouch`(L23105-L23107)任意 touch 指针启用;`onKeyDown`(L23108-L23110)映射到动作的键盘输入则 `usingTouch=false + suspendAutoForward()`
- 全屏:`onScreen`(L23084-L23093)requestFullscreen/exitFullscreen,不支持时 `showScreenHelp`(L23094-L23095);`onFullscreenChange`(L23096-L23101)处理 iOS standalone
- 布局编辑器 `a$`(L22756-L22896):拖动/键盘微调按钮位置,`localStorage["kartsim.touch-layout"]`(Fp,L22749),`h$`/`l$`/`zs`(L22931-L22952)校验 `x,y∈[0,1], w,h∈[44,144]`;`Dp`/`Ip`(L22898-L22914)以 fixed + clamp 定位
- 自动前进策略 `s$`(L22714-L22748):`enabled/armed/ready`;`setRaceState(available, armed)`(L22720-L22721,armed 由 GameApp 传入 `Countdown|Racing 且非起步喷窗`,L29074);`isActive(snapshot)` = engaged 且 `reverse===0`;`apply(snapshot)`(L22726-L22730)engage 时强制 `forward=1`;`dispatch`(L22731-L22736):**键盘 forward-down 会取消 armed**;touch forward-down 才 arm(L22741-L22744);reverse-down 时先补发 `forward-up`

### E.4 键盘状态机 `nP`(L17113-L17228)✅

- 字段(L17114-L17127):`leftHeld/rightHeld/rawDriftHeld/derivedDriftHeld`、`forwardSource/reverseSource`(0/1)、`rawSteer`、`swapForwardReverse/invertSteering`、`actionMarkerWord`(位标志字)、`forwardBatchGate/forwardBatchDown`、`driftPressCount`(0xffff 回绕)、`driftReleaseMarker`
- `dispatch(transitions, cb)`(L17128-L17137):遍历 transitions 调 `dispatchOne`;**Forward 批处理门**:`forwardBatchGate` 置位时遇 Forward transition 只更新 `forwardBatchDown` 并 break(暂停恢复等场景丢弃排队的前进沿)
- `dispatchOne(t, cb)`(L17169-L17211)按动作:
  - `SteerLeft`:down→`setRawSteer(1)`,up→rightHeld? -1 : 0;每次都调 `updateDriftChord`
  - `SteerRight`:对称(`setRawSteer(-1)`)
  - `Forward`:`forwardSource=down?1:0`;`actionMarkerWord=Qe(word,0x1,0x2,down)`(L17178);cb 发 `{kind:'forward-down'|'forward-up'}`
  - `Reverse`:同上,位 `0x4/0x8`,kind `reverse-down/up`
  - `Drift`:`rawDriftHeld=down`;**down 时 `driftPressCount=(count+1)&0xffff`、清 release 标记;up 时置 release 标记**(L17188);再 `updateDriftChord`
  - `UseItemOrBooster`:仅 down 时 cb `{kind:'use-item-or-booster'}`
  - `Reset`:down 时 `{kind:'reset'}`;`GaugeState`:down 时 `{kind:'instant-acceleration'}`;其余 `{kind:'unsupported-action'}`
- `updateDriftChord(down, cb, t)`(L17212-L17224):
  - down:需 `rawDriftHeld && rawSteer!==0` 才置 `derivedDriftHeld=true` 并发 `{kind:'drift-start', direction: rawSteer>0?1:-1}`(方向键+漂移组合键)
  - up:`derivedDriftHeld=rawDriftHeld`,发 `{kind:'drift-stop', active: rawDriftHeld}`(松方向键但漂移键仍按住 → active=true 保持漂移)
- `setRawSteer(v)`(L17225-L17227):写 rawSteer 并维护 actionMarkerWord 位:左转位 `0x10/0x20`、右转位 `0x40/0x80`(`Qe(word,setBit,clearBit,set)` L17230-L17232 互斥位对);Forward 用 `0x1/0x2`、Reverse 用 `0x4/0x8`
- `snapshot()`(L17140-L17152):返回 `{forward, reverse(经 swapForwardReverse 交换), steer=rawSteer*(invert?-1:1), rawSteer, steeringInverted, rawDriftHeld, derivedDriftHeld, actionMarkerWord}`
- `cancel()`(L17138-L17139):清全部 held/source/标记,`setRawSteer(0)`
- `getDriftEdgeMetadata()`(L17164-L17168):返回 `{pressCount, released}`(供连喷/双喷窗口判定,`getForwardBatchState` L17159-L17163 同理)

### E.5 输入→物理链路(GameApp 侧)✅

- 每帧 `frame()` → `drainDrivingInput(nowMs, dt)`(L29070-L29075):
  1. `input.drain()` 得 `{transitions, cancelled}`
  2. `cancelled` → `drivingInput.cancel()` + `autoForward.cancel()` + `physics.cancelControls()` + 灯光复位
  3. `autoForward.setRaceState(finishAtMs===0 && (Countdown|Racing), Racing && !isStartBoosterWindow)`
  4. `drivingInput.dispatch(transitions, (kind,t) => autoForward.dispatch(kind,t,drivingInput.snapshot(),cmd => handleDrivingCommand(cmd,nowMs,dt)))`
- `handleDrivingCommand`(L29019-L29020):`handleBaseDrivingCommand` + 非暂停时 `handleTimeAttackDrivingCommand`
- `handleBaseDrivingCommand`(L29028-L29044):`drift-start/stop`、`forward-down/up`、`reverse-down/up` → `physics.handleDrivingCommand(cmd, getDrivingSnapshot())`;forward/reverse 同时驱动 `activeLampFlares.setInputPair('front'/'rear', down)`
- `handleTimeAttackDrivingCommand`(L29045-L29067):
  - `forward-up`:起步喷窗内 → `physics.startRaceBooster()`;重置转速表 1 输入模式
  - `forward-down`:起步喷窗内 → `startRaceBooster()`;再 `physics.startPlayBooster(snapshot)`(漂移+前进起步,见 §G.5)
  - `use-item-or-booster` → `physics.handleDrivingCommand(...)`(普通氮气);`instant-acceleration` 仅 Racing 时转发
  - `reset` → Racing 时 `initiateSpeedReset(true)`(L29053-L29055)
- `getDrivingSnapshot()`(L29026-L29027):`= autoForward.apply(drivingInput.snapshot())`
- GameApp `frame()` 主体(L28679-L28682):`const snap = getDrivingSnapshot()` → `activeCoordinator.run(nowMs, snap)`

### E.6 输入快照→物理子步 ✅

- `mB.run(nowMs, snapshot)`(L27296-L27308):把 snapshot 存 `this.input`,经 fB core 依次执行 `GoTrack → GoCourse → GoPlayKart → GoItemObstacle[] → GoItemEventObject[]`;`GoPlayKart.slot12`(L27272-L27275)内 `this.schedule = kart.update(nowMs, input, track)`;finally 清空 input(缺快照直接 throw,L27274)
- `k$.update(nowMs, input, track)`(L23483-L23491):`clock.advance()` 把帧时长切成 **2ms 定点子步**(`b$.advance` L23340-L23360,单帧上限 500ms,每片 ≤2ms);每片调 `stepSubstep(sliceMs*0.001, input, track)`
- `stepSubstep(dt, input, ctx)`(L23845-L23869):dt 必须 ∈(0, 2ms](fround(0.002),L23846);顺序:`updateStateTimer → updateDriftLifecycleTimers → scanSpecialRoad → rebuildBodyState → probeWheels → applyResetSurfaceRequest → (轨)applyFull3DRail → applySuspension → applyLongitudinal(dt, input, F) → delayedDriftRequest 补触发 → applySteeringAndTires(dt, input, F, T) → applyRoadConsumers → applyBoosterChargeSurface → applyDrag → captureRail/returnToStandard → integrateVelocity → 槽量表 → resolvePrimaryCollision(ctx, input) → ...`
- 快照消费点:
  - `applyLongitudinal(dt, input, F)`(L24125-L24167):`input.forward>0` 且非锁定 → 前进推力(系数随 physicsState 1..0xb / 2 / 0xa / instantAccelerationActive 分档);`input.reverse>0` → 倒车(`reverseAccumulator>0.2s` 才给倒车力,否则刹停/保持);无输入且 |纵向速度|≤0.5 → 滚动阻力刹停
  - `applySteeringAndTires(dt, input, F, T)`(L24168-):`rawSteer*(steeringInverted?-1:1)`,`maxAngle=rad(maxSteerDeg)`(L24177),速度衰减 `exp(-(|v|/steerConstraint)*steeringExponentialScale)`(L24179-L24180);`input.forward!==0` 时用 steeringEnvelope 限制突变;漂移触发相位使用同一 steer 值
  - `resolvePrimaryCollision(ctx, input)`(L24505-):路面/障碍 OBB 碰撞(快照参数在轨模式 3D 中还会传入 applyFull3DRail,L23850)
- 空闲快照常量 `x$`(L23380-L23389):`{forward:0,reverse:0,steer:0,rawSteer:0,steeringInverted:false,rawDriftHeld:false,derivedDriftHeld:false,actionMarkerWord:0}` — 演示/回放路径(L23844)用它步进物理

---

## §F. 音效系统 📌

> 类:`cu`(配置) / `Qm`(AudioContext 管理) / `$u`(引擎音) / `ea`(BGM)
> 详见 UNDERSTOOD.md §32。

### F.1 `cu`(配置,L17591-L17602)

- 属性:`bgmEnabled/bgmVolume/fxEnabled/fxVolume/enableRoadSound/boostBlur/dualBoostAuto/toonLine/shadow/keyMap`
- localStorage key:`kartrider-web:p3528:game-options-v1`

### F.2 `Qm` WeakMap(L17641-L17706)

- `AudioContext → {options, sounds:Set, bgmTransition}`
- `Zt(context, source, group, gain)`:注册声音源(group="bgm"/"parseTrackContainer"(fx))
- `hu(sound)`:根据 group 的 enabled/volume 更新 gain
- `Pe(gainNode, volume, time)`:设置音量(对数尺度, -10000dB→0dB)
- `py(param, value, time)`:setValueAtTime 的对数封装

### F.3 `$u` 类(引擎音,L25541-L25628)

- 资源:`sound_/parseTrackContainer/kart/engine_<type>/motor.ogg`(fallback:engine_common)
- `start()`:createBufferSource + createGain,playbackRate=0.25 初始,loop=true
- `update(ms, state)`:每 64ms 更新
  - `U$(state)` → {pitch, gain} 根据 physicsState/速度计算
- 其他音效:crash.ogg / shock.ogg / drift.ogg / reset.flac
- booster 音效:boosterStart/boosterDrift/booster/boosterZone/boosterJumpZone/boosterDelivery/boosterPlay
- dualBooster / charger / exceed 音效

### F.4 碰撞音效(L25643-L25668)

- `playCollision()`:crash.ogg
- `playSteeringCollision()`:crash.ogg(转向碰撞,音量降低)
- `playLandingShock()`:shock.ogg(落地)
- `playReset()`:reset.flac(重生)

### F.5 `ea` 类(BGM,L28176-L28274)

- 资源:
  - `sound_/bgm/main/single.ogg`:准备阶段
  - `sound_/bgm/main/game_win.ogg`:胜利
  - `sound_/bgm/main/game_lose.ogg`:失败
  - `sound_/bgm/<theme>/`:赛道主题 BGM(多首随机选)
- `selectRace()`:加载赛道 BGM
- `playReady()`:准备音乐
- `playResult(isWin)`:胜负音乐
- 淡入淡出:16 步 × 100ms,transitionStep 0→15,incoming/outgoing 线性交叉
- `restart()`:随机选一首赛道 BGM

### F.6 倒计时音效(L28271-L28274)

- `count_n.flac`:数字音效(3/2/1)
- `count_go.flac`:GO 音效
- `lab_count.flac` / `final_lab.flac`:最终圈音效

### F.7 路面音效

- `road/road.bml`:路面音效配置表(BML XML)
- `road/<name>.flac`:各路面音效文件
- 按 `enableRoadSound` 开关控制

### F.8 音频生命周期(L29509-L29580)

- 比赛开始:创建/复用 AudioContext → 加载赛道 BGM + 车辆音效 + 倒计时音效 + 事件音效 → `activeKartAudio.start()`
- 暂停:`setPaused(true)` → 停止效果源
- 恢复:`context.resume()`

---

## §G. 道具系统 ✅

> H5 版 KartSim **无传统对抗道具**(水弹/水雷/导弹/乌云/磁铁道具本体均无运行时代码),仅保留:①加速器(booster)/能量收集器(charger)体系;②赛道 itemCube/obstacle/event 数据通道;③音效/特效资源位。
> 详见 UNDERSTOOD.md §30。逐函数逆向结论如下。

### G.1 道具相关数据通道(track 侧)✅

- `tx(root, mode)`(L4056-L4085):track 对象 runtime 消费审计。`ToItemCube` / `ToMovableObject` 中:
  - `object type` 属性(L4071-L4075)截断 `\0` 后比对;`itemCube`、`obstacle`、`event` 三类;mode 为 `speed-individual|time-attack`(`za`,L4092-L4094)时跳过 itemCube(L4074)
  - time-attack 下仅 `status==='admit'` 的 obstacle 放行(L4076);其余 `obstacle/event` 未接入 → 报 "尚未接入 M5 runtime"(L4077)
- `C0(obj)`(L4087-L4090):读取 `object` 属性的 `onlyItemGame` 标志;为 true 的对象在非道具模式被 loader 省略(`qi(.., "only-item-game-loader-omission")` L27113)
- `auditTrackObject(...)`(L27053-L27170)逐类判定:
  - `ToItemCube`(L27109):`hg(mode)`(计时类)→ `cube-loader-omission`;`item` 模式 → `cube-grant-unclosed`(未实现);否则 `cube-mode-unclosed`。**即道具箱获取/发放(grant)代码在本版未闭合**
  - `banana/ltejump/mine/mineHidden/waterMine`(L27126):**这些道具类型名存在于类型比对表**,但在 `speed-individual/speed-team/time-attack` 模式一律 `excluded-nonboost-item-runtime`(排除,无 runtime)
  - `obstacle`(L27127-L27149):admit 时 owner="TimeAttack GoItemObstacle snapshot",producer="ToMovableObject obstacle wire + live PRS matrices",pair capacity 8,"commit N -> kart consumption N+1"
  - `event`(L27150-L27163):owner 含 "kart effect presentation + standalone track sound",属性含 effect/scale/gravity/sound/rearm=capacity8
- `mB` 协调器注册 `GoItemObstacle[]`(L27264)与 `GoItemEventObject[]`(L27265):slot12=track.updateObstacles/updateEvents,slot13=registerObstaclePair/registerEventPairs,commit=commitObstacleSnapshot/commitEventSnapshot(L27266-L27271)
- UI 层 `itemBox`(L19227-L19229 `drawItemBox` 等):是**车库/装备物品窗口**(分类 tab + 搜索 + `draftProfile.equipment.itemIds`),与比赛中道具无关

### G.2 赛道 event 道具(缩放/重力/特效/声音)✅

- `resolveTrackEvents(ctx)`(L24614-L24623,子步内调用):对 `ctx.queryEventObb(secondaryCollisionBox())` 命中的每个 event:
  - `scalePercent` → `triggerEventScale()`,非法值 throw(中文:"不在已证 P3528 语料")
  - `gravity` → `triggerEventGravity()`,同上
  - `effect` → `trackEventEffectRequests.push({effect, atMs: currentUpdateMs})`
- `triggerEventScale(pct)`(L23749-L23757):仅接受 `0x64(100%)` 与 `0x140(320%)`;写 `eventScaleTarget={pct/100}`、`eventScaleMode=1`(平滑过渡到目标缩放)
- `triggerEventGravity(g)`(L23757-L23761):仅接受 `[1, 1.5, 2, 3, 3.2, 5, 9]`;触发时速度 ÷4、角速度 ÷5,`gravityDivisor=g`
- `updateEventGravity(nowMs)`(L24498-L24504):记录 anchor,`nowMs-anchor > 1000ms` 且着地后恢复 `gravityDivisor=1`
- GameApp 消费(L28581-L28584):`physics.consumeTrackEventEffectRequests()`(L23620-L23622)→ `activeTrackEventEffects.trigger(effect, atMs)`(缺失 owner 直接 throw)

### G.3 obstacle 道具(压扁/硬停)✅

- `resolveStaticObstacles(ctx)`(子步内,L23865;主体 L24505-L24613):OBB 相撞时按法线高度分:
  - `normal.y > 0.65`(高障碍):速度反射 + `applyHighObstacleAngularResponse`(L24645-L24647)翻滚角速度
  - 低障碍:`applyCollisionDriftGaugePreserve(false)`(L24658-L24663)按 `driftGaguePreservePercent` 保留集气,**charger 激活时保留 100%**;`|响应|>10` 置 `strongLateralCollision`(crash 特效);写入 collisionMotion/AudioStrength
  - `pressMode==="hard-stop"` → `activateHardPress()`(L24643-L24644):压扁缩放(mode1)、`obstacleSuppressionRemainingMs=500ms`、`pressProtected1C0`(压扁保护免前进推力)、清速度
  - `pressMode==="directional"`(L24611)→ `activateDirectionalPress(1|2)`(L24641-L24642):横向/纵向压扁、2000ms 抑制、`automaticResetRequest`
- 自动重生计时:`updatePrimaryAutomaticResetTimers` / `updateObstacleAutomaticResetTimer` / `advanceAutomaticResetTimer`(L24633-L24640):低/高碰撞 1s、障碍 0.4s 累计后 `automaticResetRequest=true` → GameApp `initiateSpeedReset(false)`(L28693)

### G.4 booster(加速器)体系 ✅

- physicsState 状态码(由代码归纳):`0=无` / `1=起步喷(startBooster)` / `2=漂移连喷窗(driftBoost)` / `3=普通氮气` / `0xa=双喷` / `0xd..0x10=区域/跳跃/交付/磁铁区(仅状态保留,驱动音效)` / `0x12=起步道具喷(play)`
- `startRaceBooster()`(L23690-L23693):仅 `physicsState===0`;`stateRemainingMs = max(0, tuning.startBoosterTimeSpeed)`,`physicsState=1`
- `startPlayBooster(snapshot)`(L23696-L23697):需 `raceMotionLocked && snapshot.rawDriftHeld`(倒计时中按住漂移+前进的起步姿态);`physicsState=0x12, stateRemainingMs=1000ms`
- `startNormalBooster(snapshot)`(L24382-L24386,由 `use-item-or-booster` 命令触发 L23584-L23585):条件 `physicsState∈{0,0x12} && snapshot.forward>0 && speedSlots[0]===6`(有氮气槽);消耗一个槽(shift+push -1),`physicsState=3`,`stateRemainingMs = tuning.normalBoosterTime`;统计 `resultBoosterCount++`、`chargerBoosterUses++`、`chargerPendingUses++` → `activateChargerIfReady()`
- 氮气槽/集气互转:`updateModeInventory()`(L23725-L23730):满槽(`committedGauge===driftMaxGauge`)时清空量表并在 `speedSlots` 找 `-1` 空位填 `6`,`state.nitro` = 槽中 6 的个数(值 6 即"满氮气",最多 2 槽,初始槽表见 `speedSlots` 初始化)
- 双喷:`armDualBooster()`(L24412-L24413,普通喷后 arm)/ `refreshDualBoosterReady()`(L24414-L24429,尾窗 = normalBoosterTime 的 `dualBoosterTickMin..Max` 百分比)/ `classifyDualBoosterReady()`(L24430-L24431:过早 0x2 / 过晚(+50ms) 0x3 / 低速 0x4 / 就绪 0x6 / auto 0x7 / 手动待 0x8)/ `updateDualBooster()`(L24405-L24411:autoArm 且就绪 → `physicsState=0xa` 双喷)
- 立即加速(超负荷,GaugeState):`handleDrivingCommand case 'instant-acceleration'`(L23587-L23588):`instAccelGaugeLength>0 && instantGauge>=instAccelGaugeMinUsable` → `instantAccelerationActive=true`;充能 `updateInstantAccelerationGauge`(L24669-):按 `chargeInstAccelGaugeByGrip/ByBoost(+charger 加成 ByBoostAdded)`,激活时每秒消耗 `instantGauge`
- 墙碰充能:`updateInstantWallCharge`(update 内 L23488)/ `beginInstantWallCharge`(L24696 附近,charger 激活加成 `chargeInstAccelGaugeByWall+...Added`)
- 路面充能:`applyBoosterChargeSurface()`(L23870-L23873):路面描述符 `bcharge` 时 `committedGauge` 每子步 +1.6(封顶)

### G.5 charger(能量收集器)✅

- `activateChargerIfReady()`(L24387-L24392):`chargerEnabled && chargerSystemBoosterUseCount>0 && boosterUses>0 && uses/count > activations && 未过期 && 未激活 && pendingUses===count` → `chargerActive=true`、`chargerActivations++`、`chargerExpiryMs = now + max(1, chargerSystemUseTime)`
- `updateChargerExpiry(nowMs)`(L24393-L24394):过期后清 active/expiry/pending
- 加成点:漂移集气 ×`driftGaugeFactor`(L24368)、低速集气 +`chargeBoostBySpeedAdded`(L24373)、碰撞保集气 100%(L24662)、超负荷充能加成(L24678)、追加速比(L24662 附近)
- UI/特效读取:`timeAttackTachometerCharger()`(L23659-L23665)返回 `{count: chargerPendingUses, capacity: chargerSystemBoosterUseCount, active, durationMs}`;GameApp `activeChargerEffect.update(...)`(L28588-L28589)

### G.6 漂移集气(道具槽的来源)✅

- 窗口开启:漂移触发相位结束时(`triggerTimer` 耗尽,L24203)`driftGaugeWindow=true, driftGaugeElapsed=0, pendingGauge=0`
- `accumulateDriftGauge(dt, rail)`(L24358-L24368):需着地/轨且窗口开且 `localForwardSpeed>=0`;`inc = rightSpeed² × dt`(轨模式 ×2);时间加权:`<0.2s ×3`,`0.2-0.5s ×1.5`,之后 `/(2×elapsed)`;charger 激活再 ×`driftGaugeFactor`
- `commitDriftGauge()`(L24379-L24381):`committedGauge = min(driftMaxGauge, committed+pending)`,关窗清零(`stopDrift`/`beginResetInitiation` 等调用)
- `accumulateSpeedGauge`(L24369-L24378):非漂移低速充能(`tachometerIncGauge`,`chargeBoostBySpeed`)

### G.7 道具与音效联动($u 类)✅

- `$u.load()`(L25555-L25564)按 **boosterTypes/physicsState 码** 建 `stateBuffers: Map<码, AudioBuffer>`:
  - `1=boosterStart` / `2=boosterDrift` / `3=booster` / `0xd=boosterZone` / `0xe=boosterJumpZone` / `0xf=boosterDelivery` / **`0x10 = sound_/parseTrackContainer/item/magnet/using.ogg`(磁铁,唯一 item 音效)** / `0x12=boosterPlay`
  - 引擎等级 >6 另载 `dualBoosterReady / dualBooster / charger / exceed`(L25565-L25568)
- `setState(state, dualState)`(L25669-L25670)/ `updateStateSource`(L25696-L25697):physicsState 变化即切换循环音源(0xa 双喷走 enterDualBooster;0xf 无 delivery 资源时静音)
- `setChargerActive(b)`(L25680-L25688):charger.ogg 循环开关;`setExceedActive`(L25671-L25679):exceed.ogg;`setTransformingState`(L25689-L25695):变形车音
- 碰撞音:`playCollision(strength, ms)`(L25643-L25651,节流 + 音量按强度)/ `playSteeringCollision`(L25652-L25660,**中断引擎音**后播 crash)/ `playLandingShock`(L25661-L25668,gain=clamp(0.1..1, strength*0.04))

### G.8 道具与动画/特效联动 ✅

- booster 特效加载 `Rl.load`(L6826-L6916):遍历 `boosterTypes` + `attachments` 节点,加载 `effect/booster|boosterFlare/<type>/booster|boosterTeam|boosterPlay.1s`;引擎 >6 加载 `boosterDual(_S)/boosterDualReady(_S)`;另有 `baseBoosterWave/boosterWave/driftBoostWave/exceedWave`(L6886-L6910)
- `Rl.setState(state, dualMode, exceedActive, ms)`(L6917-L6933):`dualVisual ∈ none|ready|dual`(state=0xa 且 dualMode=1 → ready;state=3/5 且 dualMode=1 → dual),按当前 state 的期望 kind(`JS(state)`/`tA(state)`)切换 visible 并 reset 补间
- GameApp 每帧(L28577-L28589):`kartView.update(state, clock, speed, audioState)` 返回动画槽 → `physics.setAnimationSlot(0..6)`(L23761-L23763);`activeKartMotionBlur.setState(stateCode, speed)`;`consumeCrashEffectRequest`/`consumeShockWaveRequest` 驱动 crash/shockwave 特效;charger 特效见 §G.5
- 压扁:`setVisualScaleMode`(L24438-L24447)+ `updateVisualScale`(L24448-,pn 插值表 L23433-L23441,最长 600ms 恢复)

### G.9 结论:未找到的道具功能(明确列出)✅

- **未找到**(全文检索无运行时代码,仅类型字符串/资源路径出现):水弹(water)、水雷(waterMine,仅类型比对 L27126)、导弹/飞弹(missile)、香蕉皮(banana,仅 L27126)、乌云(cloud)、电磁/磁铁道具本体(magnet 仅有 using.ogg 音效映射 L25562 与 boosterTypes 0x10 状态码,无获取/使用逻辑)、道具箱拾取发放(cube-grant-unclosed L27125/L27109)、道具换位 ReorderItems/副道具 SecondaryItem **有键位绑定(dr index 6/7)但 `dispatchOne` 落入 `unsupported-action`(L17205-L17210),GameApp 亦无处理分支**
- 道具模式的准入由 `onlyItemGame`(L4088)、`za(mode)`(L4092)、`hg(mode)`(cube 判定)等 loader 审计函数预留,H5 仅实现 TimeAttack/速度赛,道具分支均为 block/omit

---

## §H. AI 系统 📌

> 详见 UNDERSTOOD.md §28。H5 版无 AI 对手。

### H.1 关键发现

- **H5 版本无 .kap 文件解析代码**:搜索 deob_named.js 中 "kap" 无命中
- 推测 H5 版 KartSim 仅实现 TimeAttack(计时赛)单人模式
- 无 "opponent"/"rival"/"bot"/"npc" 关键词命中
- **路线跟踪系统存在**但用于玩家跑圈判定,非 AI 导航:
  - `routeStates` WeakMap(L26047):存储每辆车的路线状态
  - `updateRoute`(L26248):更新车辆在路线图中的位置
  - `sampleRoute`(L26203):采样未来路径点(用于迷你地图/进度条)
  - `mB` Coordinator(L29136):路线更新协调器

### H.2 `routeStates` WeakMap(L26047-L26336)

- `routeStates = new WeakMap()` — 以 vehicle 实例为键
- 每个状态:`{section, sectionDistance, lap, ...}`
- `updateRoute(vehicle, body, routeGraph)`:
  - 在当前 section 内投影 body.position 到 frames
  - 超过 section 末尾时推进到 outgoing section
  - 更新 lap 计数(过门时)
- `resetRouteState(vehicle)`:重置到 firstSection

### H.3 `mB` Coordinator(L29136)

- `createCoordinator()` 实例化 `mB` 类
- `run()`:每帧调用,更新所有车辆的路线状态 + 处理路面标签
- 不是 AI 决策器,只是路线跟踪协调

### H.4 结论

- H5 版 KartSim 是**纯 TimeAttack 单人计时赛**,不含 AI 对手
- 若克隆需要 AI 对手,需自行实现:
  - 路径跟踪算法(建议 Pure Pursuit,前瞻距离 ∝ 速度)
  - AI 难度分级(反应延迟/精度/速度上限)
  - 道具使用策略(如实现道具系统)

---

## §I. 渲染与场景图 ⏳

> 待补完整函数级文档。关键类:`Relement`(on/vx) / `ReTriList` / `ReTriStrip` / `ReToonRigid` / `ReToonSkinned` / `OutlinePass` / `KartAnimPlayer` / `YT` / `VehicleImporter`。
> 参考 UNDERSTOOD.md §4-§5,§18,§20。

### I.1 关键函数清单(待补签名)

- `l1(node, basis, position, scale)` @L110559:矩阵设置(basis 行优先,scale 按列乘,平移原样)
- `N0` / `uC`(@291134 / @714822):同 l1 语义
- `ae(v)` @215695:`{x:v[0], y:v[2], z:-v[1]}` D→P 变换
- `ex()` @175051:路线图构建(up 计算)
- `u1` @outline 空间:`Rx(+90°)·matrixWorld`
- `importVehicle1s` @111784:`root.rotation.x = -Math.PI/2`
- `completeCheckpointPose` @1204xxx:P→D `(x, -z, y)`

### I.2 场景节点(Relement)

- 属性:`name/children/transform{basis×3, position, scale}/bounds0/serializedBoundsOverride/cullingTraversalMode/bounds1/rawScalar/nodeEnabled/slot12/slot13/additionalProperty`
- slot:`texture`(TexProperty) / `backface`(kx:`cull: uint32`) / alpha / zbuf
- 材质**父→子继承**

### I.3 strip 展开(§5)

- `even: (a,b,c); odd: (a'=b, b'=a, c)`(indices[i] 与 [i+1] 互换)
- 叠加 backface `cull===3` 时交换后两点

### I.4 渲染相关类清单

- `OutlinePass_class`(33 方法,30 属性)
- `KartAnimPlayer`(10 方法,7 属性)
- `YT`(10 方法,7 属性)— 蒙皮更新,返回 world 数组
- `VehicleImporter`(5 方法,1 属性)
- `ObjGraphReader_class`(10 方法,6 属性)

---

## §J. 资源解析 ⏳

> 待补完整函数级文档。详见 FORMATS.md。

### J.1 资源格式

- `.rho`:块表容器,文件名派生密钥 `adler32(UTF16LE(name)) - 0xa6ee7565`,XOR 密钥流(seed=dataKey^0x8473fbc1,逐个 -0x7b8c043f,16×u32LE=64字节),Adler-32 校验 **初始 a=0**,flags bit2=zlib / bit4=加密 → `rho_unpack.py`
- `.rho5`:region 密钥(KR/CN/TW),AES T-table 变体 PRNG(dk 类),MD5 校验 → `rho5_unpack.py`
- `.1s`:Object47/Typed27 对象图 → `s1_parse.py`
- `.kap`:AI 路径(H5 版无解析代码)
- `track.bml` / `course`:官方路线 XML

### J.2 关键类

- `ou`(60 方法,11 属性):资源/目录管理
  - `loadTimeAttackGarageCatalog()` / `loadTrackConfig()` / `loadVehicleEngineGrades()` / `loadVehicleItemIds()`
  - `timeAttackGarageCatalog()` / `timeAttackCharacterItem()` / `timeAttackKartItem()` / `timeAttackPlateItem()` / `timeAttackTrackCatalog()`
  - `vehicleAssets()` / `vehicleCatalog()` / `vehicleItemId()` / `vehicleLinkCharacterId()` / `vehicleTitles()`
  - `trackMetadata()` / `trackMetadataCatalog()` / `trackTitles()` / `trackWarpConfig()` / `trackWeatherConfig()`
  - `characterResourceDescriptor()` / `itemTableGarageDefinitions()`
  - 属性:`archiveIndexes/archives/byCanonicalPath/byExactCanonicalPath/byPath/canonicalPrefixCache/errors/files/manifestAvailable/region/warnings`

---

## §K. 数学库 / 工具 ⏳

### K.1 几何向量(从代码推断)

- `q(v, s)`:缩放向量(s 标量)
- `Nt(v, s)`:原地缩放
- `Mt(out, v)`:累加(out += v)
- `je(v, v2)`:减法(v -= v2)
- `Ct(a, b)`:点积
- `Hc(a, b)`:叉积
- `qc(v)`:拷贝/克隆
- `de(v)`:清零
- `h(x)`:`Math.fround` 包装

### K.2 三角形相交

- `Fu(triangle, origin, direction)`:三角形-射线(fraction 或 -1)
- `Bu(triangle, obb)`:三角形-OBB SAT(boolean)
- `Q$(triangle, cellAabb)`:三角形-AABB(boolean)

### K.3 坐标变换

- `ae(v)` @215695:`{x:v[0], y:v[2], z:-v[1]}` D→P
- `physicsToPresentation(v)`:`{x, -z, y}` P→D 逆
- `u1`:`Rx(+90°)·matrixWorld` outline 空间

---

## §L. 顶层函数索引 ⏳

> 完整 1673 个符号见 SYMBOLS.md。此处按字母分类列核心函数,待按模块补签名。

### L.1 资源/IO

- `Zs` @176 / `Pv` @188 / `lt` @199 / `sa` @207 / `v` @235 / `ah` @240 / `oa` @300 / `Nv` @325 / `Wg` @336 / `sn` @433

### L.2 解析

- `s1_parse.py` 对应:`parseTrackContainer` @L4533 / `parseToRoad` @L4641 / `buildRouteGraph` @L4101 / `gateTrisFromRecord` @L4272

### L.3 物理

- `stepSubstep` @L23845 / `applyLongitudinal` @L24125 / `applySteeringAndTires` @L24168
- `probeWheels` @L23914 / `resolvePrimaryCollision` @L24505 / `resolveStaticObstacles` @L24536
- `integrateVelocity` / `integrateStandardOrientation` / `rebuildBodyState` @L23881
- `completeCheckpointPose` @L23700

### L.4 碰撞

- `Z$` class @L26491 / `rayQuery` @L26540 / `queryObb` @L26576
- `Fu` / `Bu` / `Q$`(待定位)

### L.5 比赛流程

- `GameApp` @L28428 / `raceLifecycle(lg)` @L27347 / `updateRacing` @L27412 / `updateLapTiming` @L27436
- `im`(driveCameraman) @L12390 / `wB`(surroundCameraman) @L27481
- `ea`(BGM) @L28176 / `$u`(引擎音) @L25541

### L.6 输入

- `n$` @L22630 / `u$` @L23000 / `an`(keyMap) @L17381

---

## 附录:交接下一步建议

1. **补齐 📌 / ⏳ 标记的函数签名**:按行号在 deob_named.js 查找,补充参数/返回值/调用关系。
2. **重点实现**:
   - 物理引擎(`stepSubstep` + `apply*` 系列)— §A 已详述
   - 碰撞(`Z$` + `rayQuery` + `queryObb`)— §B 已详述
   - 赛道(`parseTrackContainer` + `buildRouteGraph`)— §C 已详述
   - 比赛流程(`raceLifecycle` + `GameApp`)— §D 已详述
3. **参考项目结构**:
   - 自研工具:`tools/`(15 个 .py)
   - 前端实现:`web/`(kart.html / character.html)
   - 文档:`docs/`(本文件 + UNDERSTOOD.md + SYMBOLS.md + PROJECT_MEMORY.md + FORMATS.md)
4. **环境**:
   - 本地服务:`python tools/server.py` → http://127.0.0.1:8088/web/
   - 语法检查:`node --input-type=module --check web/kart.html`(或对应文件)
5. **交付检查流程**(硬性):
   - 语法检查 → 浏览器冒烟(__scene/info/canvas) → 真实交互截图
