# 当前数学模型

## 题目用人话要求我们做什么
用 1~5 架无人机（FY1~FY5）按受领任务时刻起算的策略飞行并投放烟幕干扰弹，
使得烟幕云团能在来袭导弹（M1/M2/M3，速度 300 m/s 直线飞向假目标）
飞抵真目标（圆柱 r=7 m, h=10 m，**下底面圆心 (0, 200, 0)**，即沿 +y 方向 200 m、
垂直立于 z=0 平面）附近时，对"导弹→真目标"视线形成尽可能长（可累加、不连续）的有效遮蔽。

## 5 个问题之间的关系
- Q1：参数完全给定，求解一个具体遮蔽时长；用作基线对拍与验证。
- Q2：单弹最优化（FY1 → M1，决策量：航向、速度、投放点、起爆点）。
- Q3：单无人机 3 弹串接（FY1 → M1），将最优策略写入 `result1.xlsx`。
- Q4：3 机各 1 弹协同（FY1,FY2,FY3 → M1），写入 `result2.xlsx`。
- Q5：5 机各至多 3 弹，协同 3 枚导弹 M1,M2,M3，写入 `result3.xlsx`。

建模顺序：Q1（基线）→ Q2（单弹最优）→ Q3（单架多弹串接）
→ Q4（多机协同，单目标）→ Q5（多机协同，多目标）。
Q2 决策变量已明确固定为 (heading / speed / release_time / delay)
四个变量；Q3–Q5 尚未进入施工阶段。
每完成一问需在 `RESULTS.md` 记录数值与单位，并按"PLAN/WORKING/VERIFIED/REVIEW/FIX"
流程更新同一任务的 Draft PR。

## 当前可能采用的总体建模路线（方案 A 与方案 B 均已实现, 方案 B 已合并到 main 并在 PR #3 中通过审核）

### 统一坐标系
- 假目标为原点 (0, 0, 0)，水平面 xy，z 向上。
- 真目标下底面圆心 (0, 200, 0)（沿 +y 方向 200 m）。
- 真目标圆柱占据 x² + (y−200)² ≤ 49、0 ≤ z ≤ 10；
  几何中心 (0, 200, 5)。
- 单位：m / s / m/s。

### 几何与运动学

1. 导弹 i 在 t 时刻位置 = 初始位置 + 速度向量 · t；
   速度恒为 300 m/s、方向恒指假目标 (0, 0, 0)。
2. 无人机 j 在 t 时刻位置：
   - 受领任务后立即按选定航向 / 速度直线匀速（z 不变）；
   - 70 ≤ |v| ≤ 140 m/s。
3. 烟幕弹：
   - 投放瞬间相对无人机共速（**[假设] FACTS.md §15**）；
   - 投放后做抛体运动，重力 g = 9.8 m/s² 沿 −z（**[假设] FACTS.md §15**）；
   - 起爆瞬间形成球状云团中心；
   - 起爆后云团中心以 3 m/s 沿 −z 匀速下沉；
   - 视为半径 10 m 的球体；
   - 起爆时刻到起爆时刻 + 20 s 内可遮蔽。
4. 时间零点 t=0：取"警戒雷达发现来袭导弹并立即向无人机指派任务"的时刻（**[约定]**）。

### 遮蔽判定（两层模型）

> 注：原题仅给"云团中心 10 m 范围"未规定严格遮挡几何。`FACTS.md §15 [假设]`
> 明确这是模型近似，不是官方事实。下面两层都要实现并对照差异。

#### 方案 A：点目标基线

- 将真目标近似为代表点，默认候选 = 几何中心 (0, 200, 5)。
- 在 t 时刻取导弹 i 的位置 m(t)，与代表点 p 连成闭线段 seg = [m(t), p]。
- 当云团中心 c(t) 到 seg 的最短距离 d ≤ 10 m **且** 最近点落在 seg 上
  （即参数 t* ∈ [0, 1]，避免延长线误判）。
- 必须在 t ∈ [t_detonate, t_detonate + 20 s] 时间窗内。
- 满足上述条件即判定 t 时刻有效遮蔽。
- **作用**：运动学对拍、几何与时序自洽性验证、Q1 数值基线。

#### 方案 B：完整圆柱正式候选 (FULL-CYLINDER CANDIDATE / EXPERIMENTAL)

- 目标：考虑导弹对真目标圆柱可见表面或可见轮廓的视线集合，
  评估烟幕云团对这些视线的遮挡程度。
- 方案 A 点目标基线与方案 B 完整圆柱正式候选均已实现。
  方案 B 已通过 PR #3 合并到 main, 当前在 Q2/Q3/Q4/Q5 中复用.
  等级: FULL-CYLINDER CANDIDATE / EXPERIMENTAL (合并并不等于升 VERIFIED).
- 候选冻结的方案 B 几何、采样、判据与收敛标准见下文 "完整圆柱遮蔽正式候选" 章节。

#### 项目路线

- Q1：仅使用方案 A 点目标基线，验证运动学、时间轴和程序正确性；
  结果只标记为 BASELINE / EXPERIMENTAL。
- Q2 之前：确定完整圆柱遮蔽判定（阈值、采样、收敛标准）。
- Q2—Q5：根据需要运行点目标与完整圆柱模型并比较差异。
- 不新增第三套模型。

### 多弹时间聚合（**[约定]**，见 FACTS.md §14）

- 单枚烟幕弹独立记录 [t_start, t_end] 与时长 Δt。
- 同一枚导弹被多枚烟幕弹同时干扰：总有效遮蔽时长 = 各弹有效时间区间的**并集长度**。
  - 重叠时间不重复累计；
  - 不连续区间可以相加。
- Q5 跨导弹总目标函数（求和 / 取最小 / 加权）**不在 TASK_001 冻结**。

### 决策变量与目标函数（**[假设]**，各 Q 任务内显式声明）

- Q1：参数全给定，求有效遮蔽时长。
- Q2：FY1 航向、速度、投放点、起爆点 → max 遮蔽时长。
- Q3：FY1 航向、速度、3 枚弹各自投放点 / 起爆点 → max M1 遮蔽时长。
- Q4：FY1,FY2,FY3 各自航向 / 速度 / 投放点 / 起爆点 → max M1 遮蔽时长。
- Q5：5 架各自 (航向, 速度, ≤3 枚弹的投放点/起爆点) → 跨 M1+M2+M3 目标函数
  （具体形式留到 Q5 任务决定）。

## 已确认的参数来源
- 全部 PDF 数值与几何：见 `problem/FACTS.md` §8–§13。
- 全部 [官] / [推] / [约定] / [假设] 标签：见 FACTS.md 同名章节。

## 尚未冻结的假设（[假设]，必须在实现时显式声明）
- 重力加速度 g = 9.8 m/s²（−z）。
- 烟幕弹脱离无人机瞬间的初速度 = 无人机当时速度。
- 起爆后云团沉降瞬时开始（t=0 起即下沉）。
- 遮蔽判定几何：方案 A（点目标）+ 方案 B（完整圆柱），二者对照。
- Q5 跨导弹总目标函数形式（Q5 任务内决定）。
- Q2/Q3/Q4/Q5 中"投放策略"是否包括时序（投放时刻、起爆时刻）（各 Q 任务内决定）。

## 局限
- 方案 A Q1 点目标基线与方案 B 完整圆柱正式候选均已实现。
- 方案 B 已通过 PR #3 合并到 main, 等级仍为 FULL-CYLINDER CANDIDATE / EXPERIMENTAL;
  合并不等于升 VERIFIED.
- Q1 仅验证了一组参数,未与外部标准解对比.

---

## 完整圆柱遮蔽正式候选 (FULL-CYLINDER CANDIDATE / EXPERIMENTAL)

> 已在 `src/q1_cylinder.py` 实现，并通过 `tests/test_q1_cylinder.py` 的 75 个本地单元测试
> (A-L 共 12 组, 含 2 个收敛失败路径测试) 验证。
> 本节固定 Q2/Q3/Q4/Q5 中复用的方案 B 几何、采样、判据与收敛标准.
> 等级仍为 FULL-CYLINDER CANDIDATE / EXPERIMENTAL (合并 ≠ VERIFIED).

### 1. 真目标几何 (复用 FACTS.md §11)

- 圆柱 K = {(x, y, z) | x² + (y−200)² ≤ 49, 0 ≤ z ≤ 10}
- R_T = 7 m, H_T = 10 m, 轴沿 +z, 下底面圆心 = (0, 200, 0), 几何中心 = (0, 200, 5)
- 闭集, 凸集 (后续可见性测试基于此)

### 2. 显式假设 (必须保留为 [假设])

- 真目标为凸圆柱, 可见性采用支持平面判定:
  表面点 X 在 t 时刻可见 ⇔ n(X) · (M(t) − X) >= -EPS_VISIBLE
  (n 为单位外法向, EPS_VISIBLE = 1e-9 用于吸收浮点误差)
- 公共棱边不直接采样, 而由相邻侧面与端面单元中心随网格加密逼近
- 闭线段距离精确化 (point_to_segment_distance), 不使用延长线投影
- 严格遮蔽主判据: 所有当前可见表面采样点的视线均被烟幕球体相交
- 覆盖率仅作辅助诊断, **不**作为正式通过/不通过的判据 (避免人造阈值)

### 3. 采样方法 (单元中心法)

| 等级 | 侧面 (n_θ × n_z) | 端面 (n_r × n_cap_θ) | 总样本数 |
|---|---|---|---|
| coarse | 48 × 8 | 4 × 48 | 768 |
| medium | 96 × 16 | 8 × 96 | 3072 |
| fine | 192 × 32 | 16 × 192 | 12288 |

- **侧面**: θ_j = 2π(j+0.5)/n_θ, z_k = H_T·(k+0.5)/n_z
  - x = R_T·cos(θ), y = 200 + R_T·sin(θ), z ∈ (0, H_T) 严格
  - 法向 n = (cos θ, sin θ, 0) (单位)
  - 单元面积 w_side = 2π·R_T·H_T / (n_θ·n_z)
- **端面** (顶 z=H_T 与底 z=0):
  - 径向 r_i = R_T·√((i+0.5)/n_r), θ_j 同上
  - 顶法向 (0, 0, 1), 底法向 (0, 0, −1)
  - 单元面积 w_cap = π·R_T² / (n_r·n_cap_θ)
- 单元中心严格在 (0, R_T) 与 (0, H_T) 内部, **不**包含侧面/端面公共棱边
- 总权重和 = 2π·R_T·H_T + 2π·R_T² = 真圆柱表面积 (≤ 1e-8 精度)

### 4. 可见性

```
n(X) · (M(t) − X) >= -EPS_VISIBLE   →  X 在 t 时刻可见
```

EPS_VISIBLE = 1e-9 仅用于吸收浮点误差, 不构成轮廓收紧.
切线轮廓邻域 (score ≈ 0) 一律视为可见; 严格遮蔽不应通过
排除轮廓样本而变得更容易.

### 5. 遮挡

```
d_X(t) := min {|C(t) − (1−λ)·M(t) − λ·X| : λ ∈ [0, 1]}  (闭线段距离)
X 在 t 时刻被遮蔽 ⇔ d_X(t) ≤ R_cloud = 10
```

闭线段距离实现见 `src/q1_baseline.point_to_segment_distance`. 参数 λ 必须 ∈ [0, 1],
延长线投影需 clamp 到端点.

### 6. 严格遮蔽主判据

```
strict_margin(t) := R_cloud − max{ d_X(t) : X ∈ 可见表面采样集(t) }
strict_occlusion(t) := strict_margin(t) ≥ 0
```

边界函数: `f_cylinder(t) := max_visible_distance(t) − R_cloud`.
f_cylinder(t) ≤ 0 ⇔ t 时刻严格遮蔽.

### 7. 覆盖率 (辅助诊断)

```
coverage_ratio(t) := Σ{ w_X : X 可见 且 d_X(t) ≤ R_cloud }
                    / Σ{ w_X : X 可见 }
```

- 严格遮蔽 ⇒ coverage_ratio = 1
- 非严格时, coverage_ratio ∈ [0, 1)
- 当前**不**使用 coverage 阈值做判据

### 8. 时间区间算法 (复用)

```
find_strict_intervals(samples, scan_step=0.01)
  ↓
注入 boundary_func = strict_boundary_value 到 q1_baseline.find_effective_intervals
```

复用现有扫描 + 二分求根. 仅替换 boundary_func, 其余时序与扫描参数不变.

### 9. 数值收敛标准 (本轮 FIX 之后真实执行, 通过标准从代码常量读出)

- 空间: medium vs fine 区间数必须一致; 总时长差 ≤ SPATIAL_THR_TOTAL = 0.02 s;
  起点差 ≤ SPATIAL_THR_START = 0.01 s; 终点差 ≤ SPATIAL_THR_END = 0.01 s;
  max_coverage 差 ≤ SPATIAL_THR_COVERAGE = 0.005;
  max_margin 差 ≤ SPATIAL_THR_MARGIN = 0.10 m
- 时间: 0.02 / 0.01 / 0.005 s 三档 n_intervals 一致;
  起点差 ≤ TEMPORAL_THR_START = 0.01 s;
  终点差 ≤ TEMPORAL_THR_END = 0.01 s;
  总时长差 ≤ TEMPORAL_THR_TOTAL = 0.01 s
- 区间端点残差: max |f_cylinder(b)| ≤ SPATIAL_THR_RESIDUAL = TEMPORAL_THR_RESIDUAL = 1e-4
- 真实执行函数: `check_spatial_convergence`, `check_temporal_convergence`,
  返回 `passed=True/False` 与失败原因列表; main() 在任一不通过时返回 2

### 10. 当前结果 (FULL-CYLINDER CANDIDATE / EXPERIMENTAL, 本轮 FIX 后重跑)

| 量 | 值 |
|---|---|
| 方案 A 点目标总时长 | 1.435082 s |
| 方案 B 完整圆柱总时长 (fine) | 1.392384 s |
| 方案 B 遮蔽区间 (fine) | (8.055704, 9.448088) s |
| ΔT (B − A) | −0.042698 s |
| 相对差异 | −2.975% |
| ρ_max (覆盖率峰值) | 1.000 |
| ρ=1 平台 (DIAG_STEP=0.01 s 诊断网格) | 约为 (8.06, 9.44) s, 网格区间跨度 1.380 s |
| SVG_STEP=0.05 s 绘图网格首次采到 ρ=1 | t ≈ 8.100 s (仅用于 SVG 绘图, 不作为平台精确起点) |
| margin_max (严格裕量峰值, 0.001 s 局部网格估计) | 5.282478 m @ t = 9.418317 s (SVG 网格峰值附近 ±0.05 s 局部网格估计, 非解析极值) |
| 空间 coarse/medium/fine 总时长 | 1.394606 / 1.393131 / 1.392384 s |
| 时间 0.02/0.01/0.005 s 总时长 (medium) | 1.393131 / 1.393131 / 1.393131 s |
| 时间收敛 max \|f(b)\| (medium 采样, 三档) | 1.03e-06 (≤ 1e-4 通过) |
| 空间收敛 max \|f(b)\| medium/fine | 1.03e-06 / 1.03e-06 (≤ 1e-4 通过) |
| 时间收敛汇总 | PASS |
| 空间收敛汇总 | PASS |

### 11. 局限

- 单元中心法仍是有限采样近似 (12288 样本 fine), 不解析化
- 不考虑导弹在大入射角下对圆柱的轮廓遮挡几何 (本题远距离下不触发)
- 不引入覆盖率阈值作为正式判据 (避免人造阈值, 由严格遮蔽唯一决定)
- 严格遮蔽仍标记为 FULL-CYLINDER CANDIDATE / EXPERIMENTAL, 不得冒充 VERIFIED / FINAL
- Q2/Q3/Q4/Q5 中必须复用本节的 strict_boundary_value 作为优化目标

### 12. 本轮 FIX 变更 (不改数学结论)

| 变更 | 旧 | 新 | 影响 |
|---|---|---|---|
| 可见性边界 | `score > eps` | `score >= -eps` | 切线轮廓邻域不再被排除, 严格遮蔽区间可能略缩短或不变 (本实测 fine 总时长 = 1.392384 s 不变) |
| 空可见集 | 返回 `max_visible_distance=inf` 等 sentinel | 时间窗内显式 `raise ValueError`, 时间窗外仍返回 sentinel | 异常路径更明确, 防止 "0 可见 + inf 距离 = 偶然通过严格判据" |
| 收敛判定 | 仅为占位 `passed=True` | 真实执行阈值 (SPATIAL_THR_*, TEMPORAL_THR_*), 输出失败原因, main() 返回 2 表示失败 | 保证 main() 退出码反映真实收敛状态 |
| 几何/时序拆分 | 单函数同时读全局轨迹 | 纯几何 `evaluate_occlusion_geometry` + 时序包装 `evaluate_cylinder_state`, Q2 可注入新轨迹 | Q2/Q3/Q4/Q5 可直接复用 |
| 单元测试数量 | 46 测 (A-J) | 75 测 (A-L, 含 K margin/plateau, L 几何 API 输入校验, +2 个收敛失败路径) | 覆盖更全 (含新加的合成几何、注入轨迹、连通性、可视化边界、失败路径) |
| margin 报告精度 | 只在 SVG 0.05 s 网格上 | 0.001 s 局部网格估计, 报告 (max_margin, max_margin_t) | margin_max 从 5.266 m @ 9.420 s (SVG 网格) → 5.282478 m @ 9.418317 s (0.001 s 局部网格估计, 非解析极值) |
| coverage 平台 | 单独声明 ρ=1 | 实测 `coverage_plateau` 函数报告 (8.06, 9.44) 共 1.380 s | 报告 ρ=1 真实持续时长 |

---

## Q1 点目标基线 (BASELINE / EXPERIMENTAL)

> 已在 `src/q1_baseline.py` 实现，并通过 `tests/test_q1_baseline.py` 的 42 个本地单元测试验证。

### 1. 固定输入

| 量 | 值 | 来源 |
|---|---|---|
| FY1 初始位置 U₀ | (17800, 0, 1800) m | FACTS.md §8 [官] |
| M1 初始位置 M₀ | (20000, 0, 2000) m | FACTS.md §8 [官] |
| 假目标 O | (0, 0, 0) m | FACTS.md §7 [官] |
| 点目标代表点 P | (0, 200, 5) m | FACTS.md §15 [假设] (默认候选 = 几何中心) |
| FY1 速度 v_U | (-120, 0, 0) m/s | "120 m/s" 与 "朝假目标方向飞行" 来自 FACTS.md §2 [官]；"等高度直线飞行" 来自 FACTS.md §9 [官]；由 FY1 水平位置 (17800, 0) 指向假目标 (0, 0) 推得 v_U = (-120, 0, 0) m/s |
| 投放时刻 t_release | 1.5 s | FACTS.md §2 [官] |
| 起爆延迟 Δ | 3.6 s | FACTS.md §2 [官] |
| 起爆时刻 t_detonate | t_release + Δ = 5.1 s | 由上述两 [官] 数值相加 |
| M1 速度大小 | 300 m/s | FACTS.md §9 [官] |
| M1 速度方向 | 单位方向 (O − M₀)/|O − M₀| | FACTS.md §9 [官] |
| 云团下沉速度 | 3 m/s (沿 −z) | FACTS.md §10 [官] |
| 云团有效半径 | 10 m | FACTS.md §10 [官] |
| 起爆后有效持续 | 20 s | FACTS.md §10 [官] |

### 2. 显式假设

- g = 9.8 m/s², 方向沿 −z (FACTS.md §15 [假设])
- 烟幕弹脱离无人机瞬间与 FY1 共速 (v_B = v_U) (FACTS.md §15 [假设])
- 忽略空气阻力、风场、烟幕弹旋转等外部扰动 (FACTS.md §12 [假设])
- 起爆后立即以 3 m/s 下沉, 起始时间为 t_detonate (FACTS.md §15 [假设])
- 投放与起爆时间视为理想时序, 无误差 (FACTS.md §15 [假设])
- 遮蔽判定仅用方案 A 点目标代表点 P=(0,200,5);
  完整圆柱几何另在 src/q1_cylinder.py 中实现, 与本基线对照

### 3. 核心公式

- **FY1 位置** (匀速直线):
  U(t) = U₀ + v_U · t

- **烟幕弹抛体** (投放后):
  B(t) = R + v_B · (t − t_release) + (0, 0, −0.5 · g · (t − t_release)²)
  其中 R = U(t_release)

- **M1 位置** (匀速直指假目标):
  M(t) = M₀ + v_M · t
  v_M = 300 · (O − M₀) / |O − M₀|

- **云团中心** (t ≥ t_detonate):
  C(t) = D + (0, 0, −3 · (t − t_detonate))
  其中 D = B(t_detonate)

- **闭线段距离**:
  q = P − M(t)
  λ = clamp( ((C(t) − M(t)) · q) / (q · q), 0, 1 )
  N(t) = M(t) + λ · q
  d(t) = |C(t) − N(t)|

- **遮蔽边界函数**:
  f(t) = d(t) − 10

- **数值求解**:
  在 [t_detonate, t_detonate + 20 s] 内扫描 + 二分求根 (tol = 1e-8 s),
  找出所有 f(t) ≤ 0 的连续区间并精化端点。

### 4. 当前结果 (BASELINE / EXPERIMENTAL)

| 量 | 值 |
|---|---|
| 投放点 R | (17620.000000, 0.000000, 1800.000000) m |
| 起爆点 D | (17188.000000, 0.000000, 1736.496000) m (其中 1736.496 = 1800 − 0.5·9.8·3.6²) |
| M1 速度 | (-298.511157, 0, -29.851116) m/s, |v| = 300 m/s |
| M1 理论到达假目标时刻 | 66.999171 s |
| 遮蔽区间 (方案 A) | (8.013006, 9.448088) s |
| **有效遮蔽总时长** | **1.435082 s** |

### 5. 局限

- 方案 B 完整圆柱正式候选已实现并经 PR #3 合并到 main,
  等级仍为 FULL-CYLINDER CANDIDATE / EXPERIMENTAL; 合并并不等于 VERIFIED.
- 只验证 Q1 一组参数, 未与外部标准解对比
- 等级仅 BASELINE / EXPERIMENTAL, **不能**升级为 VERIFIED 或 FINAL
- 重力 g=9.8 与 9.80665 标准值差异未量化
- 风场、云团水平漂移、起爆时序误差均按 §15 假设忽略

---

## Q2 单弹策略评估合同 (TASK_004 FOUNDATION / NOT AN OPTIMIZATION RESULT)

> 已在 `src/q2_single_bomb.py` 实现, 通过 `tests/test_q2_single_bomb.py` 88 个本地单元测试
> (Section 五 ~ 十七 + 7 个 P1 加固 (G2/J2/K2/N2/P/Q + U2/R2/S2 返工) 共 14 组) 验证.
> 本节固定 TASK_004 Search 启动前必须确认的合同.
> 当前层级: 已通过 PR #5 合并到 main (merge commit 8cfe770).
> 正式 Q2 搜索尚未启动; 远程存在未审核 Search prototype commit
> (`6f728d45b3bb776c19bbe8a857b26570eb79dc68`), 等待 Audit CC 只读审核与 Hermes 仓库事实核验,
> 由 MAIN 作出最终处置决定 (整体采用 / 局部抢救 / 不采用并重写).
> 等级: **TASK_004 FOUNDATION / NOT AN OPTIMIZATION RESULT**, 不得冒充 Q2 VERIFIED / FINAL.

### 1. 决策变量: 4 个独立变量 (Section 五)

- `heading_rad` / θ: 归一化到 [0, 2π)
  - θ=0: +x; θ=π/2: +y; θ=π: -x; 角度逆时针为正
  - 方向向量由 heading 推导: `u(θ) = (cosθ, sinθ, 0)` (不得独立储存)
- `speed_mps` / v: 70 ≤ v ≤ 140 (**[官] FACTS.md §9**, 含端点)
- `release_time_s` / t_release: t_release ≥ 0 (**[约定]**, 项目边界; 允许 t_release = 0)
- `delay_s` / δ: δ ≥ 0 (**[约定]**, 项目边界; 允许 δ = 0)

**不得重复参数化**: 飞行方向向量 / 投放点 / 起爆时刻 / 起爆点 / 云团轨迹均由上述 4 个变量推导.

### 2. 运动学公式 (Section 六, 与 src/q1_baseline 一致)

- FY1 初始位置: F0 = (17800, 0, 1800) (**[官] FACTS.md §8**)
- FY1 速度: v_FY1 = v · u(θ) = (v cosθ, v sinθ, 0) (等高度直线)
- FY1 位置: F(t) = F0 + v_FY1 · t
- 投放点 (推导): R = F(t_release)
- 烟幕弹初速 = FY1 当时速度 (**[假设] FACTS.md §15**: 投放瞬间共速)
- 起爆时刻 (推导): t_d = t_release + δ
- 起爆点 (推导): D = R + v δ u + (0, 0, -0.5 g δ²)
  等价形式: D = F0 + v (t_release + δ) u + (0, 0, -0.5 g δ²)
  (两种形式须由测试证明一致)
- 重力加速度: g = 9.8 m/s² (**[假设] FACTS.md §15**, 方向 -z)
- 云团中心 (t ≥ t_d): C(t) = D + (0, 0, -3(t - t_d))
- 云团半径 R_cloud = 10 m, 有效持续 20 s (**[官] FACTS.md §10**)
- 忽略: 风, 空气阻力, 水平漂移, 地面反弹, 云团形变, 触地后自动失效
  (均按 FACTS.md §15 [假设] 处理)

### 3. 候选合法性 (Section 七)

**A. 物理/合同非法 (status = "invalid", 不评估)**:
- 任意变量非有限数 (NaN / Inf)
- speed_mps ∉ [70, 140]
- release_time_s < 0
- delay_s < 0
- 起爆点 z < 0 (允许 z = 0)

**B. 合法但目标值为 0 的候选**:
- 评估窗口为空 (window_end ≤ window_start)
- 整个窗口内严格遮蔽始终不成立
- t_detonate = t_arrival (search-domain 边界)

**C. 搜索域无损截断 (status = "pruned_zero")**:
- 条件: t_detonate > t_arrival
- 含义: 起爆晚于 M1 到达假目标, 对到达前遮蔽目标没有正收益, 搜索时无损排除
- 文档约束: **不得写成"题目禁止晚于到达时刻起爆"**
- **明确说明**: 这是针对当前"到达前遮蔽目标"的**搜索域无损剪枝**, 不是官
  方物理禁令. valid=True 表示物理/合同合法, 仅在当前目标函数下零收益.

**D. 程序错误 (必须向上传播, 不得吞掉)**:
- 几何函数合同错误 (空可见集 ValueError 等)
- 参数类型编程错误 (非数值 scan_step, sample_level 不在 SAMPLE_GRADES 等)
- 内部断言失败 / 代码 bug / 意外 I/O

策略评估 (`evaluate_single_bomb_strategy`) 仅 try 评估阶段异常 (空可见集等),
这些异常**不**被吞掉, 直接传播. Smoke CLI (`run_smoke`) 在外层捕获以计数.

### 4. 评估窗口与目标函数 (Section 八)

- 窗口起点: t_start = t_detonate
- 窗口终点: t_end = min(t_detonate + 20, t_arrival)
  当 t_end ≤ t_start 时, 目标值为 0 (合法)
- 严格遮蔽判据: 复用 `src/q1_cylinder.strict_boundary_value`
  `f_cylinder(t) ≤ 0 ⇔ t 时刻严格遮蔽`
- 严格遮蔽区间: 复用 `src/q1_cylinder.find_strict_intervals`
- 区间必须按起点升序, 无重叠, 不产生负长度, 限制在评估窗口内
- 正式目标: `J = measure(union(I_1, I_2, ..., I_k))`
  **不得**只保留最长区间; **不得**以 coverage 阈值代替严格遮蔽判据

### 5. 复用 TASK_003 完整圆柱 (Section 十)

- 通过回调注入, **不**复制一份新的圆柱几何实现:
  - `samples`: 复用 `src/q1_cylinder.generate_cylinder_samples`
  - `missile_position_fn`: 默认 `missile_position` (Q1 trajectory)
  - `cloud_center_fn`: 由 `make_cloud_center_fn(strategy, D)` 生成的闭包
  - `window_start`, `window_end`, `scan_step`: 显式传入
- 不修改 `src/q1_cylinder.py` 即可工作 (`evaluate_single_bomb_strategy` 直接
  调 `find_strict_intervals`, 全部参数用关键字传入)
- 现有 75 个 Q1 cylinder 单元测试 + 42 个 Q1 baseline 测试 + 88 个 Q2 Foundation 单元测试保持全过 (205/205)
- Q1 数值结果与冻结候选**不**变化

### 6. 当前局限 (本轮 Foundation, 不得隐去)

- 只实现单候选评估器; **尚未实现搜索算法** (网格 / 局部 / 全局)
- **未启动 Q2 优化**; 本轮 100 个候选 smoke 中的临时最高 objective = 0 (随机策略
  难产生遮蔽区间, 这是预期的, **不**代表最终 Q2 结果)
- 不修改 TASK_003 几何核心; 不修改官方原题; 不修改重参数化
- 不声称全局最优, 不写 `result1.xlsx`, 不进 RESULTS.md 正式数值表
- 等级仅 FOUNDATION, Search 后才可推进到 EXPERIMENTAL, 再到 VERIFIED, 最后到 FINAL

### 7. 本轮加固 (FIX commit, 7 个 P1, 仍为 NOT AN OPTIMIZATION RESULT)

`valid` 仅表示物理/项目合同合法性; `status` 描述评估结果:

| status | valid | 说明 |
|---|---|---|
| `invalid` | False | 物理/合同非法 (含 z < -EPS_GROUND) |
| `pruned_zero` | True | 物理合法, t_detonate > t_arrival (搜索域无损剪枝, 不是官方物理禁令) |
| `zero_window` | True | 物理合法, 评估窗口为空 |
| `ok` | True | 物理合法, 已完成评估, intervals 可空可非空 |

地面边界: `EPS_GROUND = 1e-9 m` (1e-10 量级浮点舍入吸收, 不允许物理地下起爆);
3 区分类: z < -EPS → invalid, -EPS ≤ z < 0 → 归一化为 0, z ≥ 0 → 合法.

### Profile Measurement 程序错误行为

`main --profile-measure` 退出码合同 (保留, 不属于任何债务表):

| 条件 | CLI rc |
|---|---|
| 全部 row `warm_up_error is None` 且 `n_system_error == 0` | 0 |
| 任何 row 存在 `warm_up_error` (warm-up 程序异常) | 1 |
| 任何 row `n_system_error > 0` (formal repeat 程序异常) | 1 |
| 参数错误 (--bogus / 类型错 / 范围外 / 互斥) | 2 |

warm-up 异常与 formal repeat 异常在 CLI 退出码上**严格同权**:
任一发生均返回 rc=1. 字段语义保持分离:
- `warm_up_error` (warm-up 异常) 不计入 `n_system_error`
- `n_system_error` / `system_errors` (repeat 异常) 各自独立保留

默认 smoke CLI 退出码: 0 无 system_error, 1 有 system_error, 2 参数错误
(不因本轮修复而变化).

性能校准 (3 候选 × 3 profile, warm-up=1, repeat=3, samples 复用):
- Q1 锚点:  coarse 0.196 s / medium 1.85 s / fine 15.05 s
- Q1 邻域:  coarse 0.196 s / medium 1.82 s / fine 14.86 s
- 零目标:  coarse 0.182 s / medium 1.76 s / fine 13.63 s
(以上为 median; Search 预算未冻结, 仅为本轮实测.)

默认 smoke: `candidate_source = prevalidated_nonpruned` (生成阶段已过滤非法,
故 invalid/pruned 计数恒为 0; 想覆盖这些状态需用 `run_smoke_on_candidates`
或 mixed-batch 测试).

仍为 NOT AN OPTIMIZATION RESULT; 仍未启动 Search; 仍未生成 result1.xlsx.

### 8. 当前状态与下一阶段入口

- 主程序: `python -m src.q2_single_bomb --smoke-count 100 --seed 2025 --profile coarse`
- 单元测试: `python -m unittest tests.test_q2_single_bomb -v`
- 全部测试: `python -m unittest discover -s tests -p "test_*.py" -v`
- Foundation 状态: **已通过 PR #5 合并到 main** (merge commit 8cfe770); 仍为 NOT AN OPTIMIZATION RESULT
- 下一阶段: **TASK_004 Q2 REAL SEARCH CORE V1** (PARTIAL SALVAGE 已授权)
  - 原 prototype commit (`6f728d45b3bb776c19bbe8a857b26570eb79dc68`) 保留为 ancestor
  - 通过普通 merge (--no-ff) 把 main 同步到 task/TASK_004-search
  - 实评估器接入: `evaluate_with_real_evaluator` 调用
    `src.q2_single_bomb.evaluate_single_bomb_strategy`
  - 串行 pipeline: coarse → medium → local → fine
  - 五类 status 严格分离: invalid / pruned_zero / zero_window / ok / system_error
  - 程序异常 (system_error) 不静默转为 0; CLI rc=1
  - pilot 仍为 NOT A FORMAL Q2 RESULT; best-known 仍为 NOT A PROVEN GLOBAL OPTIMUM
  - 不得在 pilot 基础上声称 Q2 全局最优; 不得写入 RESULTS.md / result*.xlsx

---

## Q2 Real Search Core v1 (TASK_004 / PILOT / NOT A FORMAL Q2 RESULT)

> 已在 `src/q2_search.py` 实现, 通过 `tests/test_q2_search.py` 单元测试 (单测覆盖 + 真实 evaluator 集成) 验证.
> 本节固定 Q2 Real Search Core v1 的算法合同.
> 等级: **PILOT / NOT A FORMAL Q2 RESULT** /
> **BEST-KNOWN CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM**, 不得冒充 Q2 VERIFIED / FINAL.

### 1. 算法角色

- 候选生成: deterministic (seed 锁定); 不依赖真实 evaluator 的随机性
- 真实 evaluator: `evaluate_with_real_evaluator` 调用
  `src.q2_single_bomb.evaluate_single_bomb_strategy`;
  不得伪造 / 复制完整圆柱几何; 不得使用 fake / 合成公式冒充 Q2 结论
- FakeEvaluator: 仅用于测试 / dry-run / 调度开销 benchmark; 任何正式 Search
  都必须 `--evaluator real`
- 串行 pipeline: workers=1 强制; real 模式 workers > 1 拒绝
  (EXPERIMENTAL / DISABLED FOR FORMAL SEARCH)
- Parallel real-evaluator: 暂未启用; 待后续轮次充分验证

### 2. 决策空间 (无魔法上界)

| 变元 | min | max | 来源 |
|---|---|---|---|
| heading_rad | 0.0 | 2π | 周期变量 (FACTS §1) |
| speed_mps | 70.0 | 140.0 | FACTS §9 |
| release_time_s | 0.0 | t_arrival - 1 | 搜索域剪枝 (避免 t_d > t_arrival) |
| delay_s | 0.0 | sqrt(2·u0_z / g) | 从 u0_z / g 推导 (Foundation 物理合同) |

域 = **物理合法 ∩ 搜索域无损剪枝**;
evaluator 仍必须做最终合法性判断.

显式删除: `release_time <= 66` / `delay <= 30` 这类未经说明的硬上界.

### 3. 候选生成 (三段)

A. Anchor: Q1 固定策略 (heading=π, speed=120, release=1.5, delay=3.6)
   用于确认 Search 调用的真实 evaluator 能复现已知非零策略.

B. Global exploration: `random.Random(seed)` 生成的 deterministic uniform
   pseudorandom samples (各维独立确定性均匀伪随机采样); 不依赖
   第三方库; 同一 (seed, domain, count) 必须产生完全一致候选.

C. Local candidates: 围绕 medium 阶段 top-k 候选生成局部扰动;
   扰动幅度 (heading ~0.10 rad, speed ~5 m/s, release ~0.5 s, delay ~0.3 s)
   作为可调参数 (后续轮次可微调).

同一 (seed, domain, algorithm_version, budget) 必须产生完全一致的 manifest.

### 4. Pipeline (coarse → medium → local → fine)

```
[1] coarse global exploration  (96 candidates)
[2] coarse Top-K               (8)
[3] medium re-evaluation       (8)
[4] medium 重新排序后的 Top    (8)
[5] 围绕 medium Top 生成 local candidates (≤ 48)
[6] local coarse 评估
[7] 合并并去重
[8] 从去重后的 medium-confirmed pool 选择 top-2 进入 fine
[9] 输出 best-known candidate 与完整证据
```

禁止:
- coarse 后直接将大量候选送入 fine
- 仅看 coarse 数值就声称最佳
- 将 FakeEvaluator benchmark 当成真实性能
- 将一次 seed 的结果称为全局最优

### 5. SearchEvaluationRow (统一结构)

字段:
- candidate_index, stage, seed
- heading_rad, speed_mps, release_time_s, delay_s
- valid, status (5 类), total_duration_s, intervals
- release_point, detonation_time_s, detonation_point
- sample_level, scan_step_s, evaluator_kind
- wall_clock_s, error_type, error_message

五类状态严格分离:
- invalid: 物理 / 合同非法 (valid=False, 不进入 top-k)
- pruned_zero: 物理合法, t_d > t_arrival (valid=True, 0 目标)
- zero_window: 物理合法, 评估窗口为空 (valid=True, 0 目标)
- ok: 物理合法并完成评估 (valid=True, 排
名)
- system_error: 程序异常 (valid=False, 不进入排名, CLI rc=1)

### 6. Checkpoint v2 (resume identity 校验)

- schema_version = 2
- 字段: algorithm_version, seed, domain_hash, manifest_sha256,
  evaluator_kind, code_revision, stage, sample_level, scan_step_s,
  completed_indexes, rows, best_index, best_total, status_counts,
  system_errors
- 校验: schema / seed / domain_hash / manifest_sha256 / evaluator_kind /
  stage / sample_level / scan_step_s / code_revision 任一 mismatch
  即拒绝 resume
- 原子写入: 临时文件 + rename, 不留残留

### 7. CLI 与退出码

- 默认: `python -m src.q2_search` 仅打印 banner; 不执行 Search
- 正式 Search: 必须 `--run-search --evaluator real`
- `--run-search --evaluator fake` 拒绝 (返回 2)
- real 模式 `--workers > 1` 拒绝 (返回 2)
- 退出码: 0 表示无 system_error; 1 表示有 system_error; 2 表示参数错误

### 8. 局限 (本轮 PILOT, 不得隐去)

- 仅实现单 seed / 固定预算的 pilot; **未**实现自适应 / 全局最优证明
- 局部扰动幅度 (heading=0.10 rad, speed=5 m/s, release=0.5 s, delay=0.3 s)
  来自工程经验, **未**做收敛性证明
- parallel real-evaluator 暂未启用; 串行路径为唯一正式路径
- 不声称 Q2 全局最优; 不写入 RESULTS.md; 不生成 result1.xlsx
- 等级仅 PILOT / NOT A FORMAL Q2 RESULT;
  必须通过后续轮次 (冷启动 / 多 seed / 收敛证明) 才能升 VERIFIED / FINAL

### 9. P1 REMEDIATION 增量 (v1.1, 已废弃为历史; 当前为 v1.2)

> 注: v1.1 段保留为历史; 当前生效版本是 v1.2 RP1 closure (§10).
> 旧版的 final_best / run_identity_sha256 / lineage_manifest_sha256 数值
> 已无效, 不得在新文档/PR/代码中继续引用. 待 clean-HEAD v1.2 pilot 完成后
> 重新测量.

v1.1 旧版 (HISTORICAL — DO NOT REPRODUCE):
  - 算法版本号 ALGORITHM_VERSION = "v1.1"
  - P1-A  local domain clamp (wrap_local_candidate)
  - P1-B  5 阶段 pipeline (medium-confirmed → fine-only best)
  - P1-C  evaluation_id + physical_candidate_sha256
  - P1-D  checkpoint v2 + verify_resume_identity
  - P1-E  static_run_identity + lineage_manifest (双 SHA)
  - P1-F  config schema v2
  - P1-G  sampling 真实表述 (deterministic uniform pseudorandom)
  - P2    formal mode disabled

### 10. FINAL REMAINING-P1 CLOSURE (v1.2, 当前生效)

v1.2 在 v1.1 基础上闭合 Remaining-P1 + P2 uniq output schema. 算法版本号
`ALGORITHM_VERSION = "v1.2"`. v1.1 段已废, 不得回退.

RP1-1  evaluation-safe interrupted checkpoint: 每完成一个 evaluation
       即原子写入 checkpoint, `--stop-after-evaluations N` (pilot-only)
       → 输出 CONTROLLED_INTERRUPTION 标记 + rc=3. checkpoint 含
       `status: 'controlled_interruption' | 'running' | 'complete'` +
       `completed_count` + `stage_counts` 5 字段.

RP1-2  resume identity 推导自 current stage_plan: `verify_resume_identity`
       不再以 checkpoint.stage/sample_level/scan_step 自证, 而是从当前
       effective config 的 stage_plan 推导 (P1 resume 阶段期望).
       RP1-2 同时把 config_sha256 / code_identity_sha256 纳入校验链.

RP1-3  effective config 单一入口: `resolve_effective_config(...)` 是
       唯一入口, 覆盖 budget / scan_steps / stage_plan / local_delta /
       sampling_method / workers / formal_enabled / checkpoint_schema.
       pipeline 仅消费 effective config, 不允许 silent fallback.
       production pilot 总评估数固定 == 163
       (97 + 8 + 48 + 8 + 2 = global_coarse + global_medium +
        local_coarse + local_medium + fine); CLI override 仅允许
       测试场景, 不得静默扩缩 production budget.

RP1-4  structured code identity: 至少含 5 字段
       `git_head_sha / worktree_dirty / q2_search_sha256 /
        config_sha256 / algorithm_version`. `run_identity_sha256`
       覆盖这些字段, 不可仅用 `git rev-parse HEAD` 代替.

RP1-5  dirty worktree 拒绝: `require_clean_worktree=True` (CLI 默认)
       → worktree 有未提交/未跟踪变更时 raise ValueError → rc=2.
       `--allow-dirty-worktree` 仅供本地 dry-run.

RP1-6  clean Patch HEAD pilot+checkpoint 必须重新验证: 本轮 commit
       必须先于 pilot 执行; clean HEAD 上 pilot + interrupted + resume
       三轮验证齐全才能升 v1.2.

RP1-7  two fine finalists 完整 lineage: 每个 finalist 含
       `finalist_rank / physical_candidate / fine_evaluation_id /
        fine_total_duration_s / parent_medium_source /
        parent_evaluation_id / parent_total_duration_s`.
       medium_confirmed lineage 与 finalist lineage 必须可追溯.

P2     uniq output constructor (RP1 P2): uninterrupted path 与
       resumed-from-checkpoint path 必须通过同一 `build_pilot_output(...)`
       产出, schema 完全一致; 含 19 个 canonical 字段 + 4 个统一 flag
       (`resumed_from_checkpoint / resumed_n_completed / resumed_status /
        dirty_worktree_at_start`) + `canonical_result_sha256` (sort_keys
       确定性 SHA-256, 仅覆盖 math/lineage 字段, 不含 wall-clock/路径).

CLI 退出码 (v1.2):
  0  = OK (无 system_error 且 fine 有 best)
  1  = system_error
  2  = arg / invalid config / empty fine / formal rejected /
       dirty worktree rejected
  3  = controlled_interruption (RP1-1; pilot-only)

### 11. v1.2 最终证据

最终证据(clean-HEAD uninterrupted/interrupted/resume 三轮实测 ＋ CLI rc codes ＋
所有 v1.2 RP1 + P2 闭合证明)在 PR #9 body 中提供, 本节不再记录具体 measured
values, 避免文档先于实测漂移.

旧 v1.2 文档(HEAD=4a8ee08 / HEAD=f81f436 pilot 数字:
`canonical_result_sha256=8861203e...` /
`run_identity_sha256=9c1f476e...` /
`lineage_manifest_sha256=92fe298a...` /
`global_coarse=98 (97+1 anchor)` /
`completed_count=164`)已被本轮 Verification Correction 主动废弃:

- budget 修语义: `global_coarse_count` 现仅指随机生成候选数, 实际 stage
  global_coarse = global_coarse_count + ANCHOR_COUNT = 96 + 1 = 97;
  总评估数 = 97 + 8 + 48 + 8 + 2 = 163; 试图写入 `global_coarse_count=97`
  现因实际总数 = 164 (≠163) 触发 `resolve_effective_config` 抛 ValueError.
- checkpoint 改语义: 每完成一个 NEW evaluation 即原子写 checkpoint v2
  (RP1 evaluation-safe); stage 末尾再额外存一次 stage-completed 副本.
  旧 v1.2 数字(每 stage-end 才写)不再代表当前实现.
- resume 改语义: 累计 rows 在 ckpt 中保存; 当前 stage 恢复时只 partition
  `source_stage == current_stage` 的 rows; prior-stage rows 由
  `prior_stages_rows` 单独持有, 不得进入当前 stage 排名.
- 旧数字(`98 global_coarse` / `164 completed_count` / `8861203e...`)来自
  不区分 anchor + 在 stage 末尾写 checkpoint + 不做 stage partition 的
  v1.2-OLD 实现; 不得在新文档/PR/代码中重新引用.

等级: PILOT / NOT A FORMAL Q2 RESULT / BEST-KNOWN CANDIDATE /
      NOT A PROVEN GLOBAL OPTIMUM.

---

## Q2 Formal Search Profile (TASK_005 / FORMAL BEST-KNOWN / NOT A PROVEN GLOBAL OPTIMUM)

> 已在 `src/q2_search.py` 追加 formal block (schema 3, gate_id
> `q2_search_formal_v1`), 通过 `scripts/run_q2_formal.py` 编排,
> 22 个 FormalProfileTests + 20 个 P1 证据门测试全部通过.
> 本节固定 Q2 formal profile 的方法、预算、multi-seed 聚合、执行门、
> 稳定性、扰动、物理合法性与局限.
> 等级: **FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM**,
> 不得冒充 Q2 VERIFIED / FINAL / 官方答案 / 解析极值.
> 独立审查 (Audit CC / Hermes) 签字后才能立项 TASK_006.

### 1. 隔离与不变式

- 独立 schema 3 / gate_id `q2_search_formal_v1`; pilot schema 2 不变.
- 独立 declaration: `FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM`.
- 独立 gate error class: `FormalBudgetGateError` (与 pilot
  `FixedProductionBudgetInvariantError` 严格区分).
- pilot fixed-163 (97:8:48:8:2 / 163 evaluations) **不变**:
  pilot production main() 仍 enforce FIXED-163 + production gate.
- formal profile 的预算来自 formal config (`total_budget=1000`),
  通过 pilot pipeline 的 test-only API (`cli_overrides=`)
  注入; pilot 内部 `enforce_fixed_production_result=False` 仅在
  `run_formal_pipeline()` 内部开启, production main() 永不开启.

### 2. Formal execution contract (P1-1)

formal execution path = `src.q2_search.run_formal_pipeline(seed, config, output_dir)`.

| Gate | 来源 | 不通过 → |
|---|---|---|
| `require_clean_worktree=True` | 调用 `run_search_pipeline` | ValueError → BLOCKED |
| pilot budget 由 formal stage_counts 反推 (`formal_pilot_budget_from_stage_counts`) | 函数级保证 | ValueError → BLOCKED |
| pilot pipeline 返回 rc=0 (或 resumed-from-checkpoint) 后, 重新构造 SearchEvaluationRow 列表 | `SearchEvaluationRow.from_dict` | FormalBudgetGateError → BLOCKED |
| **actual** stage_counts 从 `row.source_stage` 重建 (`_reconstruct_actual_stage_counts`) | 重算, 不得从 config 复制 | FormalBudgetGateError → BLOCKED |
| actual_stage_counts 严格等于 formal config stage_counts | `dict == dict` | FormalBudgetGateError → BLOCKED |
| actual_completed_count == formal total_budget (1000) | `int == int` | FormalBudgetGateError → BLOCKED |
| actual_unique_evaluation_ids == formal total_budget (1000) | `set` 大小 | FormalBudgetGateError → BLOCKED |
| seed 一致性 (pipeline 输出 seed == 期望 seed) | `int == int` | FormalBudgetGateError → BLOCKED |
| system_error_count == 0 | `sum(status == "system_error")` | FormalBudgetGateError → BLOCKED |
| final_best_status == "OK_FINE_RESULT" 且 final_best_row 非空 | 出参检查 | FormalBudgetGateError → BLOCKED |
| code_identity_sha256 非空 | 出参检查 | FormalBudgetGateError → BLOCKED |
| `validate_formal_budget(...)` 二次校验 | formal gate | FormalBudgetGateError → BLOCKED |

每 seed 输出 `FormalPipelineResult`:
- `formal_config_sha256` (来自 formal config 文件)
- `pipeline_effective_config_sha256` (来自 pilot pipeline 出参)
- `code_identity_sha256`
- `formal_run_identity_sha256` (绑定 formal config SHA + code identity +
  seed + actual stage counts + total budget + evaluator version)
- `actual_stage_counts` / `actual_completed_count` /
  `actual_unique_evaluation_ids` (全部从 pipeline 实际数据重建)

### 3. Multi-seed 调度

- seeds = `[2025, 2026, 2027]`, formal config 强制断言.
- 每 seed 独立 run; 任一 seed 不通过 → 全部 BLOCKED, 不写 summary.
- per-seed wall-clock (实测): 465.61s / 471.47s / 515.14s (平均 ~484s).
- 三 seed 共 ~25 分钟 wall-clock, 在 3600s ceiling 内 (~7%).

### 4. Cross-seed 聚合

- 每 seed 取 fine top-5 (status=ok, valid=True, 按 total_duration_s desc).
- 3 seed × 5 = 15 raw 候选.
- `cross_seed_dedup_candidates` 按 tolerance (1e-6 各维) 去重:
  - "first wins" 稳定策略, 输出 (canonical_tuple, original_index).
- pilot best-known 显式注入 (P1-4):
  - 优先级 1: `work/q2_pilot_calib/pilot_result.json` (prior calibration)
  - 优先级 2: 确定性 seed=2025 fixed-163 clean pilot 重跑,
    保存到 `work/q2_pilot_calib/pilot_result.json`
  - 优先级 3: 失败 → `FormalBudgetGateError("BLOCKED")`, 不静默继续.
- 注入前后 pool 大小记录在 `per_seed_summary.json`.

### 5. 统一 fine 复评 + 稳定性

- 对跨 seed finalist pool 全部 4-tuple, 重新以 fine / scan_step=0.005
  评估, 排序 desc, 取最长的合法 candidate 作为 winner.
- 三档稳定性: scan_step ∈ {0.02, 0.01, 0.005}, 同一 winner:
  - 任一档 duration 与其它档差 > 0.02s → 视为不收敛, BLOCKED.
  - 本次实测 delta=0.000s (function 光滑 + 区间算法稳定).

### 6. 16 项 one-variable-at-a-time 扰动 (P1-3)

| 变量 | 大尺度 | 小尺度 |
|---|---|---|
| heading_rad | ±0.05 | ±0.02 |
| speed_mps | ±2.0 | ±1.0 |
| release_time_s | ±0.5 | ±0.2 |
| delay_s | ±0.3 | ±0.1 |

- 4 变量 × 2 方向 × 2 尺度 = 16 evaluations.
- 每次仅扰动一个变量; 其余三个保持 winner 精确值.
- heading 按 2π 周期 wrap; 其他变量必须经 `formal_physical_validity`
  合法检查, 非法扰动记录 reason, 不静默 clamp.
- 每个合法扰动以 fine / scan_step=0.005 评估.
- 任一扰动改善 winner (Δ > 1e-9) → `local_not_yet_converged=True`
  → 阻止 winner 冻结, 触发有界局部 refinement.
- 全部 16 个合法扰动均未改善（[HISTORICAL RULE 仅说明定义；当前旧 formal-search candidate 实测 5/16 改善，因此触发 bounded refinement 并降级为 HISTORICAL FORMAL-SEARCH CANDIDATE]）。

### 7. 物理合法性 (P1-2 + P1-4)

`formal_physical_validity(winner)`:
- 任一变量 NaN/Inf → False
- speed_mps ∉ [70, 140] → False
- release_time_s < 0 → False
- delay_s < 0 → False
- delay_s > sqrt(2·u0_z / g) ≈ 19.18 → False
- heading_rad (wrap 后) ∉ [0, 2π) → False

物理不合法 → 阻止 winner 冻结, BLOCKED.

### 8. Finalist 失败保护 (P1-2)

任一条件触发即 raise `FormalBudgetGateError`, **不**写入 summary:
- finalist pool 为空
- finalist re-eval 无合法 fine row
- winner.status != "ok"
- winner.valid != True
- physical_validity 不通过
- stability_ok != True
- finalist pool 中 system_error > 0

### 9. 局限

- formal search 是 deterministic uniform pseudorandom + 5-stage pipeline,
  **不是**全局最优证明, **不是**解析极值, **不是**官方答案.
- 未做约束优化 / Pareto frontier / 多弹搜索 / LHS / 贝叶斯优化.
- 旧 formal-search candidate 的 16 项 one-variable perturbation 中
  有 5 项改善（旧候选不是 16 项邻域局部极值），因此触发
  bounded refinement；综合搜索空间未穷尽。
- pilot best-known 注入依赖一次确定性 fixed-163 clean pilot (worktree
  必须 clean; 否则 fallback 链失败 → BLOCKED).
- 等级: **FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM**
  → 现已被审计 + doc-only P2 闭合后的更优候选替代为
  `FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE /
   LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM`。
  旧 2.48275905609131 s 候选降级为 `HISTORICAL FORMAL-SEARCH CANDIDATE`。
  不得在 canonical 候选基础上声称 Q2 全局最优 / VERIFIED / FINAL /
  官方答案, 除非独立审查签字并立项 TASK_006。

## TASK_005 LOCAL REFINEMENT — BOUNDED RUNTIME AMENDMENT (本轮生效)

> MAIN 补充修订: 不重跑 3 seeds, 不重跑 17 候选完整复评, 不重跑 473 全量.
> 只在 clean HEAD 上对 2 个 parent 做确定性 coordinate search, 最多 32 次
> refinement evaluation, 硬时间上限 2100s.

### 1. 复评起点

A. 原 formal candidate (POST-FIX winner):
```
h=3.121767217560497, s=115.43351397802584,
r=1.7672692031529031, d=3.889202402720746
```

B. 上一轮 16 项扰动中表现最好的候选 (pert_09):
```
h=3.121767217560497, s=115.43351397802584,
r=1.2672692031529031, d=3.889202402720746
```
两者均使用 real evaluator + scan_step=0.005 复评, 真实 duration
较大者作为 refinement 起点. 不信任文档中 pert_09 的 3.312s 舍入结果.

### 2. 坐标搜索 3 levels (deterministic coordinate search)

| Level | 4 vars 尺度 | sweeps | evals/sweep | 总预算 |
|---|---|---|---|---|
| Level 1 | heading ±0.02, speed ±1.0, release ±0.2, delay ±0.1 | 2 | 8 | 16 |
| Level 2 | heading ±0.01, speed ±0.5, release ±0.1, delay ±0.05 | 1 | 8 | 8 |
| Level 3 | heading ±0.005, speed ±0.25, release ±0.05, delay ±0.025 | 1 | 8 | 8 |
| **总计** | | **4** | | **32** |

- 每次 sweep = 4 vars × 2 signs = 8 evaluations
- 每轮仅扰动一个变量, 其它三个保持当前 best 精确值
- heading 按 2π 周期 wrap
- sweep scan_step = 0.01 (与 formal pipeline 一致)
- 改善容差 1e-6 s (strict improvement)
- 单 sweep greedy: 严格改善最大者作为 sweep 新 best
- 任一 sweep 无改善 → 提前 break level

### 3. 有界预算 + 硬时间上限

- REFINE_MAX_TOTAL_EVALUATIONS = 32 (跨所有 levels 累计)
- REFINE_HARD_DEADLINE_S = 2100 (从第一次 parent 复评 wall-clock)
- 每次 evaluation 前检查 deadline; 不足则:
  - 不启动下一次 evaluation
  - 原子写入 checkpoint
  - 抛 `FormalRefinementGateError`
  - 返回非零退出码
  - 不生成成功 summary

### 4. 可恢复 checkpoint

每 evaluation 后原子写入 `work/q2_formal_refinement/checkpoint.json`,
含:
- HEAD SHA
- parent candidate
- current best candidate + duration
- level / sweep
- evaluations completed
- evaluated candidate identities
- elapsed seconds
- refinement config SHA
- status

resume 验证: HEAD 一致 + refinement config SHA 一致 + parent identity 合法.
任一不一致 → BLOCKED, 不静默 fallback.

### 5. 实时进度 + 静默禁止

每 evaluation 必须打印一行 `[REFINE]` (flush=True), 包含
eval / level / sweep / variable / direction / duration / best_duration /
elapsed_s / remaining_budget / eta_s.

启动命令必须 `set -o pipefail; ... | tee log; rc=${PIPESTATUS[0]}; exit "$rc"`,
禁止 `| tail -10`, 禁止仅依据管道末命令 rc 判断成功.

### 6. 失败保护 (fail-closed)

- 预算耗尽 → `TASK_005 LOCAL REFINEMENT BUDGET EXHAUSTED — RESULT REVIEW BLOCKED`
- 时间上限命中 → `TASK_005 LOCAL REFINEMENT WALL-CLOCK GATE HIT — RESULT REVIEW BLOCKED`
- 最终 16 项 one-var 仍有改善 → `TASK_005 LOCAL REFINEMENT P1 REMAINS — MATH/RESULT REVIEW BLOCKED`
- 全部 16 项 one-var 合法扰动均无改善 → `local_perturbation_passed = true`,
  可以 `TASK_005 LOCAL REFINEMENT FROZEN — WAITING FOR INDEPENDENT MATH/RESULT REVIEW`.

### 7. 最终验证 (refine 完成后, scan_step=0.005)

1. refined candidate stability 复评 (0.02 / 0.01 / 0.005 三档)
2. 最终 16 项 one-variable perturbations (4 vars × 2 signs × 2 scales)
3. 仅当 16 项中任一合法候选改善 > 1e-6 → 阻断冻结, 不得再自动启动第二轮

---

## 当前 Q2 result status (TASK_005 DOC-ONLY P2 CLOSED)

> 独立 Audit 结论 B 已生效: passed with doc-only P2；canonical Q2
> result 由 bounded refinement 4.260970878601073 s 候选晋升；旧
> formal-search 2.48275905609131 s 候选降级。

### Historical formal-search candidate (SUPERSEDED)

| 字段 | 值 |
|---|---|
| heading_rad | 3.121767217560497 |
| speed_mps | 115.43351397802584 |
| release_time_s | 1.7672692031529031 |
| delay_s | 3.889202402720746 |
| total_duration_s | 2.48275905609131 |
| status | HISTORICAL FORMAL-SEARCH CANDIDATE |

### Canonical budget-limited best-known (CURRENT)

| 字段 | 值 |
|---|---|
| heading_rad | 3.126767217560497 |
| speed_mps | 116.43351397802584 |
| release_time_s | 1.2672692031529031 |
| delay_s | 3.789202402720746 |
| total_duration_s | 4.260970878601073 |
| interval (s) | (5.089825368500298, 9.350796247101371) |
| status | FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE |
| qualifiers | LOCAL CONVERGENCE NOT ESTABLISHED |
|           | NOT A PROVEN GLOBAL OPTIMUM |

改善幅度（相对 historical）：
- duration 改善 = 4.260970878601073 − 2.48275905609131 ≈ 1.778211822509763 s
- 相对改善 ≈ 71.6%

### Verified（独立 Audit 通过维度）

- execution identity (worktree-clean + HEAD sha + script sha256 + q2_search code identity + refinement_config_sha256 + parent candidate identity + checkpoint_source_head_sha 全通过)
- scan stability (0.02 / 0.010 / 0.005 三档 duration 完全一致)
- physical validity (speed ∈ [70, 140], release ≥ 0, delay 在落地约束内, heading ∈ [0, 2π))
- independent audit evaluator recomputation 6/6 exact match

### Not established（明确不冒充）

- local convergence: 未建立（新候选未在 clean HEAD 上重跑完整 16 项扰动，按 Audit 结论 B 不需要重跑）
- global optimum: 未证明（bounded refinement 预算 32/32 耗尽；budget exhausted ≠ code failed）
- official answer: 不冒充

### Evidence lineage（保留分层，不混淆）

```
formal multi-seed exploration (3 seeds × 1000, 16 项扰动)
    ↓ old candidate 5/16 改善, 不构成局部极值
bounded refinement (32 evaluations, 3 levels, ≤2100 s)
    ↓ refined candidate dur=4.260970878601073 s
clean-head verification identity closure (5 evaluator calls)
    ↓ identity / stability / physical validity 全过
independent Audit (6 evaluator calls, exact match)
    ↓ conclusion B (passed with doc-only P2)
DOC-ONLY P2 CLOSED → canonical promotion
```

不得把 Audit PASS 解释为 local optimum 或 global optimum。

---

## Q3 三弹串接评估合同 (TASK_006-P0P1 / PILOT / NOT A FORMAL Q3 RESULT)

> 已在 `src/q3_three_bombs.py` 实现，通过 `tests/test_q3.py` 单元测试验证。
> 本节固定 Q3 Three-Bomb Model Contract：8 维决策变量、共享 heading/speed、
> 投放间隔 ≥ 1 s、union 目标、search-domain pruning 约定与 result1.xlsx J 列约定。
> 等级: **EXPERIMENTAL Q3 PILOT / NOT A FORMAL Q3 RESULT / RESULT1.XLSX NOT GENERATED**。
> 独立审查签字 + MAIN 显式立项 TASK_006-P2 后才能升 `BUDGET_LIMITED_BEST_KNOWN` 或
> 进一步生成 result1.xlsx。

### 1. 官方事实（FACTS.md §4 + §10 + §12 + §13.1）

- **[官]** FY1 投放 3 枚烟幕干扰弹对 M1 实施干扰（FACTS.md §4）。
- **[官]** 同架相邻两枚投放间隔 ≥ 1 s（FACTS.md §10 / §12）。
- **[官]** FY1 任务期间只使用一个 heading、一个 speed（FACTS.md §9：本任务指令"一旦确定就不再调整"；
  本节对 Q3 的工程化解释见 §3 [约定]）。
- **[官]** FY1 速度 70~140 m/s，等高度匀速直线飞行（FACTS.md §9 / §12）。
- **[官]** 烟幕干扰弹脱离无人机后受重力作用；起爆后形成半径 R = 10 m 的下沉云团；
  起爆后有效持续 20 s（FACTS.md §10）。
- **[官]** 结果保存到 result1.xlsx；模板 10 列 × 3 行（FACTS.md §13.1）。

### 2. 8 维决策变量

```python
@dataclass(frozen=True)
class ThreeBombCandidate:
    heading_rad: float              # θ ∈ [0, 2π), 三枚弹共享
    speed_mps: float                # v ∈ [70, 140], 三枚弹共享
    release_time_1_s: float         # ≥ 0
    delay_1_s: float                # ≥ 0
    release_time_2_s: float         # ≥ release_time_1_s + 1
    delay_2_s: float                # ≥ 0
    release_time_3_s: float         # ≥ release_time_2_s + 1
    delay_3_s: float                # ≥ 0
```

候选合同：

- `0 ≤ heading_rad < 2π`
- `70 ≤ speed_mps ≤ 140`
- `release_time_i_s ≥ 0`
- `delay_i_s ≥ 0`
- `release_time_2_s − release_time_1_s ≥ 1`
- `release_time_3_s − release_time_2_s ≥ 1`

### 3. 共享 heading / speed（[约定]）

**[约定]** 三枚烟幕干扰弹在任务期间共用同一架 FY1 的 heading 与 speed；
因此 `ThreeBombCandidate` 中 `heading_rad` 与 `speed_mps` 各只出现一次，三枚弹各自的
4 元子策略 `SingleBombStrategy(heading_rad, speed_mps, release_time_i_s, delay_i_s)`
由该候选直接推导。该约定继承自 FACTS.md §9 中"无人机一旦确定航向与速度就不再调整"
的 [官] 表述；若未来需要按 Q4 / Q5 的多机结构拆分 heading / speed，本合同不再适用。

### 4. 运动学与几何（全部复用 Q2）

每枚弹直接映射为 `SingleBombStrategy`：

```python
strat_i = SingleBombStrategy(
    heading_rad=candidate.heading_rad,
    speed_mps=candidate.speed_mps,
    release_time_s=candidate.release_time_i_s,
    delay_s=candidate.delay_i_s,
)
```

`evaluate_three_bomb_strategy(...)` 强制调用三次
`src.q2_single_bomb.evaluate_single_bomb_strategy`（不得复制、不得绕过）。
返回的 `SingleBombEvaluation` 在 §5 / §6 / §7 中被合并到三弹 union。

### 5. 单弹合法性继承 Q2（保留其语义）

| 状态 | valid | 含义 |
|---|---|---|
| `invalid` | False | 物理 / 合同非法（非有限 / 越界 / 起爆 z < -EPS_GROUND） |
| `pruned_zero` | True | t_detonate > t_arrival（搜索域无损剪枝, 不是官方物理禁令） |
| `zero_window` | True | 合法但评估窗口为空 |
| `ok` | True | 物理合法并完成评估 |

继承语义（来自 `src/q2_single_bomb.EPS_GROUND` + `validate_strategy` + `evaluate_single_bomb_strategy`）：
- 非有限值 → invalid；
- speed 越界 / release < 0 / delay < 0 / 起爆点明显低于地面 → invalid；
- t_detonate > t_arrival → pruned_zero（不是物理非法，是合法候选的 0 收益）；
- zero_window（合法但窗口为空）→ 合法；
- 程序异常（空可见集、类型错误、内部断言失败）→ 由 evaluator 抛出，不吞掉，
  外层 Pilot 记录 `system_error` 并停止，不得冒充 zero。

### 6. Q3 整体合法性

- 三枚弹均物理合法 → Q3 candidate valid；
- 某枚弹 pruned_zero / zero_window → 整组仍 valid，该弹贡献空区间；
- 某枚弹 invalid → 整组 Q3 candidate invalid；
- 任一单弹 evaluator 抛出程序异常 → Q3 evaluator 必须抛出，外层 Pilot 记录
  `system_error` 并停止，不得继续冒充结果。

### 7. Search-domain pruning（[约定] / 搜索域剪枝）

Pilot 候选生成器可以优先生成 `t_detonate < t_arrival` 的候选，作为无损搜索域剪枝。
这不是官方物理约束，是项目级搜索约定。必须在 MODEL.md 中标记为 **[约定]**：
> t_detonate > t_arrival 的候选被搜索域剪枝为 `pruned_zero`（valid=True, total=0），
> 不是物理非法；Q3 candidate 的搜索域为单弹释放时刻 + 延迟满足
> `(release + delay) < t_arrival`。

### 8. 三弹区间并集目标

每枚弹得到严格有效区间 `I_1, I_2, I_3`（来自 Q2 evaluator）。

Q3 目标：

```
total_union_duration = measure(union(I_1 ∪ I_2 ∪ I_3))
```

必须：
- 重叠部分只计算一次；
- 不连续区间分别累加；
- nested interval 正确；
- touching interval 使用确定性规范化（epsilon = 1e-12 s，固定、极小）；
- 空区间合法（贡献 0）；
- 区间排序稳定（按 start 升序，相同 start 按 end 升序）；
- 不得把三枚单弹 duration 直接相加冒充 union；
- 不得使用会改变可观测时长的大容差。

实现：

```python
normalize_intervals(intervals) -> tuple  # 排序 + touching 合并 + epsilon 规范化
union_intervals(*interval_lists) -> tuple  # 多组区间并集
total_union_duration(intervals) -> float   # sum(end - start)
```

### 9. Q3 Evaluator 输出结构

```python
@dataclass(frozen=True)
class ThreeBombEvaluation:
    candidate: ThreeBombCandidate
    valid: bool
    status: str           # "invalid" | "zero_union" | "ok"
    reason: str
    bomb_evaluations: tuple  # 3 × SingleBombEvaluation
    union_intervals: tuple
    total_union_duration_s: float
    q3_evaluation_id: str
    sample_level: str
    scan_step_s: float
    elapsed_s: float
    single_bomb_evaluator_calls: int
```

- `status ∈ {"invalid", "zero_union", "ok"}`；
- 程序异常不放进普通 status，由 evaluator 抛出并由 Pilot 外层记录 system_error；
- `q3_evaluation_id` 基于 canonical JSON + SHA-256，至少绑定：
  - candidate 8 个变量；
  - `sample_level`；
  - `scan_step`；
  - candidate schema version；
  - Q2 evaluator code SHA；
  - Pilot config SHA；
- 同一候选、同一配置必须产生同一 ID。

### 10. result1.xlsx 合同（[约定]，不生成）

- A 列 / B 列：无人机运动方向（度）、速度（m/s）三行相同；
- C 列：烟幕干扰弹编号 1、2、3；
- D–F 列：每枚弹的投放点 xyz；
- G–I 列：每枚弹的起爆点 xyz；
- J 列：每枚弹自身有效遮蔽时长（单弹 duration，不写 union）；
- 三弹 union 总时长写入 `outputs/q3/q3_pilot_summary.json` 与 `RESULTS.md`；
- 方向角规则：+x = 0°，逆时针为正，范围 0~360°（继承 FACTS.md §13.4 [官]）；
- 本合同标注 **[约定]**，**不得**冒充官方逐字规定。

本轮**禁止**：
- 创建 `outputs/submission/result1.xlsx`；
- 复制或修改官方模板；
- 引入 openpyxl；
- 写 Excel writer。

### 11. 候选来源（必须标注 `candidate_source`）

Pilot 候选必须标注来源：

1. `q2_canonical_seed_family`：从 canonical Q2 candidate 派生三弹合法 seed family；
2. `deterministic_random_seed_2025`：seed=2025；
3. `deterministic_random_seed_2026`：seed=2026；
4. `profile_calibration`：粗 / 中 / 细各 1 候选（每种 sample grade 的成本校准）；
5. `finalist_medium_recheck`：从 medium recheck top-K 重评；
6. `finalist_fine_spotcheck`：从 fine finalist top-2 重评。

Q2 canonical anchor（仅作 seed 来源）：
```
heading_rad = 3.126767217560497
speed_mps   = 116.43351397802584
release_time_s = 1.2672692031529031
delay_s    = 3.789202402720746
```

不得宣称"复制三次就是 Q3 最优"。`candidate_source` 必须出现在每个 Q3 evaluation
的行日志与 `outputs/q3/q3_pilot_summary.json` 的 per-row 统计中。

### 12. Pilot 固定预算（不冒充）

| 维度 | 上限 |
|---|---|
| Pilot 顶层 Q3 candidate evaluation | 96 |
| Pilot wall-clock | 900 s |
| 单弹 evaluator 调用上限 | 96 × 3 = 288 |
| 真实 TASK 测试 Q3 evaluation | 3 |

阶段分配建议：

- Stage A — profile calibration：`2 candidates × coarse/medium/fine` = 6 Q3 evals
- Stage B — deterministic coarse exploration：≤ 80 Q3 evals
- Stage C — medium finalist recheck：≤ top 8 Q3 evals
- Stage D — fine spot-check：≤ top 2 Q3 evals

总计 ≤ 96。执行前检查剩余 budget。

| 触发 | 状态 | 后续 |
|---|---|---|
| wall-clock 命中 | `WALL_CLOCK_GATE_HIT` | 原子写 checkpoint；保存 best pilot candidate；不自动延长 |
| evaluation 预算耗尽 | `EVALUATION_BUDGET_EXHAUSTED` | 原子写 checkpoint；不写 `CODE_TEST_FAILED`；保留 best pilot candidate |
| TASK 测试失败 | `CODE_TEST_FAILED` | 不进入 Pilot；只修真实失败；`FIX:` 前缀；`contract_version` +1 |
| 任意单弹 evaluator 异常 | `RUN_SYSTEM_ERROR` | Pilot 立即停止；记录；不冒充结果 |

本轮结果仍只能是 `EXPERIMENTAL`。**不得**因为出现较好候选就升级
`BUDGET_LIMITED_BEST_KNOWN`（该等级留给 TASK_006-P2 正式预算运行）。

### 13. 当前状态（本轮 P0/P1）

- `src/q3_three_bombs.py` 已实现 `ThreeBombCandidate` / `validate_candidate` /
  `evaluate_bomb_sequence` / `evaluate_three_bomb_strategy` /
  `normalize_intervals` / `union_intervals` / `total_union_duration` /
  `ThreeBombEvaluation` / Pilot CLI `--pilot-only`。
- `tests/test_q3.py` 已覆盖：interval union（overlapping/disjoint/touching/nested/empty）、
  非有限输入、speed bounds、release spacing（exactly 1 s accepted / below 1 s rejected）、
  deterministic evaluation ID、candidate serialization、Q2 one-bomb degeneration exact
  comparison、三弹共享 heading / speed、three-bomb union consistency、invalid candidate
  fail-closed、pruned_zero 仍是 legal、system_error 不得变成 zero、checkpoint atomic
  write、resume success、resume identity mismatch blocked、actual evaluation count、
  unique evaluation IDs、repeated run determinism。
- Pilot 已执行；budget / wall-clock / counts / timing / best candidate 全部记录在
  `outputs/q3/q3_pilot_summary.json`。
- 等级：`EXPERIMENTAL Q3 PILOT / NOT A FORMAL Q3 RESULT / RESULT1.XLSX NOT GENERATED`。
- **不**进入 TASK_006-P2（Q3 Formal Search + result1.xlsx）。

### 14. 局限

- Q3 Pilot 是 deterministic uniform pseudorandom + 5 candidate source；
  **不是**全局最优证明，**不是**解析极值，**不是**官方答案。
- 本轮不启动完整 16 项 one-var 扰动；不启动 coordinate refinement；
  不启动 multi-seed 调度；不写 result1.xlsx。
- 候选生成与 budget 都按 Pilot 固定上限；不冒充正式 Q3 结果。
- 共享 heading / speed 是项目约定，不是官方物理常量；Q4 / Q5 不复用本合同的共享规则。

---

## Q3 正式 bounded search (TASK_006-P2 / BUDGET_LIMITED_BEST_KNOWN / NOT A PROVEN GLOBAL OPTIMUM)

> 已在 `src/q3_search.py` 实现，通过 `tests/test_q3.py` 新增 ≥ 20 个搜索单元测试
> （FakeEvaluator only, 不调用真实 Q3 evaluator）验证。
> 本节固定 Q3 Formal Bounded Search v3 的方法、预算、5 阶段、multi-seed 聚合、
> checkpoint / resume、stage 优先级、合法性与局限。
> 等级: **BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE / LOCAL CONVERGENCE NOT ESTABLISHED
> / NOT A PROVEN GLOBAL OPTIMUM / RESULT1.XLSX NOT GENERATED**。
> 不得冒充 Q3 VERIFIED / FINAL / 官方答案 / 解析极值 / 全局最优。
> 独立审查 (Audit CC / Hermes) 签字后才能立项 TASK_006-P3 (result1.xlsx)。

### 1. 基础约束

- 严格基于冻结的 `src/q3_three_bombs.py` (ThreeBombCandidate /
  validate_candidate / evaluate_three_bomb_strategy / normalize_intervals /
  union_intervals / total_union_duration / ThreeBombEvaluation)。
- 严格复用 Q2 single-bomb evaluator（不复制、不绕过）。
- 候选 generation **仅**是 deterministic uniform pseudorandom + scheduled
  perturbation；不依赖第三方优化库（不引入 scipy.optimize / 贝叶斯 / NSGA）。
- Foundation 文件（P0/P1）冻结：不得修改 q3_three_bombs.py / q1 / q2 任何
  实现文件；不得 modify pilot log / checkpoint。

### 2. 预算分配（hard cap, 5 阶段严格总和 = 512）

| 阶段 | 预算 | Profile | 说明 |
|---|---|---|---|
| Stage A — structured coarse exploration | **360** | coarse (0.05) | 3 seeds × 120 = 360 |
| Stage B — bounded coarse refinement | **120** | coarse (0.05) | 12 parents × 10 perturbations = 120 |
| Stage C — medium finalist recheck | **24** | medium (0.02) | 12 parents × 2 perturbation sets |
| Stage D — fine finalist recheck | **6** | fine (0.01) | top-6 finalists |
| Stage E — high-resolution verification | **2** | fine (0.005) | final top-2 验证 / tie-break |
| **总计** | **512** | | |

run wall-clock ≤ 1200 s；任一上限达到不自动延长。

### 3. Stage A 子分配（每 seed 120 = 60 + 40 + 20）

| 子块 | 每 seed | 总 | 合同 |
|---|---|---|---|
| A1 staggered canonical family | 20 | 60 | release_time_i ∈ {best_pilot_r1 + δ_2, best_pilot_r1 + δ_3}, δ_2 ∈ [3, 5], δ_3 ∈ [δ_2 + 1, 9]; delay_i = best_pilot_delay_i + η_i, η_i ∈ [-0.1, 0.1] |
| A2 compensated release chain | 13 | 40 | release_time_1 = best_pilot_r1; release_time_2 = release_time_1 + delay_1/2; release_time_3 = release_time_2 + delay_2/2 + 1; delay_i = best_pilot_delay_i + η_i, η_i ∈ [-0.05, 0.05] |
| A3 bounded directional diversity | 7 | 20 | heading ∈ {best_pilot_h - 0.05, best_pilot_h, best_pilot_h + 0.05}; speed ∈ {best_pilot_s - 2, best_pilot_s, best_pilot_s + 2}; release/delay 沿用 A1 |

每个 seed 独立 random.Random(seed) 实例；同一 (seed, subblock, candidate_source)
必须产生完全一致的候选顺序。

### 4. Stage B bounded coarse refinement

- parents = Stage A top-12 candidates（按 total_union_duration_s desc 去重）。
- 每 parent 派生 10 perturbations（heading ±0.02 / speed ±1.0 / release ±0.2 /
  delay ±0.1 中任选 1-2 个变量）。
- 同一 parent 多次扰动；同一 candidate 多次被命中时按 schedule 顺序
  evaluation_id 重复但 status 计为 completed；不重复占用预算。
- 仅在 coarse (0.05) profile 下评估。

### 5. Stage C / D / E finalist 复评

- Stage C：从 Stage A + B 合并后去重的 top-12 中，每 parent 选 2 组（release
  微调 + delay 微调）共 24 候选，medium (0.02) 复评。
- Stage D：从 Stage C 完成后 top-6，fine (0.01) 复评。
- Stage E：从 Stage D 完成后 top-2，fine (0.005) 复评，最终 tie-break
  on total_union_duration_s。

### 6. Multi-seed 聚合

- seeds = `[2025, 2026, 2027]`（formal config 强制断言）。
- 每 seed 独立 dispatch；任一 seed 触发 RUN_SYSTEM_ERROR 或 fail-closed
  → 整体 BLOCKED，不写 summary。
- final winner = Stage E top-1 candidate。

### 7. Checkpoint v3 / Resume identity

- 路径：`work/q3_formal/checkpoint.json`。
- schema_version = 3。
- 7 字段 resume identity（任一 mismatch → BLOCKED, exit 2）：
  1. `execution_head_sha`
  2. `contract_snapshot_sha256`
  3. `q2_single_bomb_code_sha256`
  4. `q3_three_bombs_code_sha256`
  5. `q3_search_code_sha256`
  6. `formal_config_sha256`
  7. `candidate_schema_version`
- atomic write：temp + flush + fsync + os.replace。
- corrupt / load error → `status = CHECKPOINT_LOAD_ERROR`, exit 2。

### 8. CLI 与退出码

- 默认 `python -m src.q3_search` 仅打印 banner。
- 正式搜索：`python -u -m src.q3_search --formal-search --budget 512
  --wall-clock-cap 1200 --seeds 2025 2026 2027`。
- `--dry-run` / `--fake-evaluator` 用于本地调度 / 测试（不消耗 real eval）。
- 退出码：0 无 system_error + Stage E 完成；1 system_error；2 arg / config 错误
  / dirty worktree / fail-closed / 预算耗尽 / wall-clock hit；3 controlled
  interruption。

### 9. 输出 summary JSON schema (canonical)

`outputs/q3/q3_formal_search_summary.json` 至少含以下字段：

- `phase_id = "TASK_006-P2"`
- `contract_version = 3`
- `result_level.declared_level = "BUDGET_LIMITED_BEST_KNOWN"`
- `result_level.not_a_proven_global_optimum = true`
- `result_level.local_convergence_established = false`
- `result_level.result1_xlsx_generated = false`
- `stage_counts`: {A, B, C, D, E, total} 必须总和 = 512
- `best_candidate`: 8 维 + `total_union_duration_s` + `union_intervals` +
  `per_bomb_intervals` (3 items) + `per_bomb_duration_s` (3 items)
- `identity`: 7-field resume identity SHAs + `formal_run_identity_sha256`
- `timing`: per-stage wall-clock / median / p90
- `counts`: completed / system_error / unique_evaluation_ids / single_bomb_calls
- `status`: pilot_complete / wall_clock_gate_hit / evaluation_budget_exhausted
  / run_system_error / checkpoint_load_error / resume_identity_mismatch

### 10. 局限

- 候选 generation 是 deterministic uniform pseudorandom + scheduled perturbation；
  **不是**全局最优证明，**不是**解析极值，**不是**官方答案。
- Stage B/C/D/E 的 refinement scope 受 5 阶段预算硬约束，未穷尽搜索空间；
  16 项 one-var perturbation + coordinate descent 未启动（留给 TASK_006-P2C）。
- multi-seed 仅 3 seeds；统计意义有限。
- 不声称 Q3 全局最优 / VERIFIED / FINAL / 官方答案 / 解析极值；
  **不**声称 local convergence。
- 等级仅 BUDGET_LIMITED_BEST_KNOWN；独立审查签字后才能升 VERIFIED 或进一步
  生成 result1.xlsx（TASK_006-P3）。

---

## Q3 Candidate Closure (TASK_006-P2C / BUDGET_LIMITED_BEST_KNOWN / NOT A PROVEN GLOBAL OPTIMUM)

> 已在 `src/q3_search.py` 追加 `run_candidate_closure(...)` 函数，通过
> `tests/test_q3.py` 新增 36 个 P2C 单元测试（FakeEvaluator only）验证。
> 本节固定 Q3 candidate closure 的方法、预算、F1-F5 顺序传播、累计 resume 语义、
> schedule SHA、checkpoint v4、selection rule 与局限。
> 等级: **BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE / LOCAL CONVERGENCE NOT ESTABLISHED
> / NOT A PROVEN GLOBAL OPTIMUM / RESULT1.XLSX NOT GENERATED**。
> 不得冒充 Q3 VERIFIED / FINAL / 官方答案 / 解析极值 / 全局最优 / local convergence。
> 独立审查 (Audit CC / Hermes) 签字后才能立项 TASK_006-P3 (result1.xlsx)。

### 1. 前驱与基础约束

- 严格基于 P2 冻结结果：`outputs/q3/q3_formal_search_summary.json` 的
  `best_candidate` (8 维) + `best_total_union_duration_s = 4.469013137817385 s`。
- 严格复用 Q2 single-bomb evaluator + Q3 three-bomb evaluator
  (via `src/q3_three_bombs.evaluate_three_bomb_strategy`)。
- Foundation 文件（P0/P1/P2）冻结：不得修改 q3_three_bombs.py / q1 / q2 / q3_search core。
- **不**重跑 P2 512-evaluation 正式搜索。

### 2. Pre-closure limitation（合同级声明）

P2 阶段的 B/C/D/E schedule 是从 Stage A result pool 一次性 pre-constructed 的；
该实现正确性已由 P2 实证（512/834.07 s/0 system_error）保证，但其 schedule 不能
反映"前驱阶段实际产生哪些 candidates"的真实约束。P2C 阶段必须改为 sequential
propagation：

> B/C/D/E schedules are preconstructed from the Stage A result pool rather than
> propagated sequentially after each preceding stage completed.
> (TASK_006-P2C-v4 contract, `pre_closure_stage_selection_limitation` 字段)

P2C closure 必须：

- sequential_propagation: true
- build_per_stage_only_after_predecessor_complete: true
- schedule_immutable_after_construction: true
- closure_schedule_sha256_in_resume_identity: true

### 3. 预算分配（hard cap, F1-F5 严格总和 = 32）

| 阶段 | 预算 | Profile | 说明 |
|---|---|---|---|
| F1 — one-variable perturbation | **16** | coarse (0.05) | 8 vars × 2 directions（+/-） |
| F2 — coordinate combinations | **8** | coarse (0.05) | 8 fixed combinations |
| F3 — medium recheck | **4** | medium (0.02) | parents = incumbent + top-3 challengers |
| F4 — fine recheck | **2** | fine (0.01) | parents = F3 top-k |
| F5 — high-resolution verification | **2** | fine (0.005) | final canonical selection |
| **总计** | **32** | | |
| **single_bomb_evaluator_calls** | 96 | | 32 × 3 = 96 |

Run wall-clock ≤ **600 s**；任一上限达到不自动延长。

### 4. F1 one-variable perturbation 步长

| 变量 | 步长（rad/m/s） |
|---|---|
| heading_rad | 0.002 |
| speed_mps | 0.5 |
| release_time_1_s | 0.10 |
| delay_1_s | 0.05 |
| release_time_2_s | 0.10 |
| delay_2_s | 0.05 |
| release_time_3_s | 0.10 |
| delay_3_s | 0.05 |

- 8 变量 × 2 方向 = **16 records**
- 每 record 复制 incumbent，扰动单变量单方向，其余 7 变量保持 incumbent 值。
- Fallback scales: `[0.5, 0.25]`；当扰动后 candidate 不满足 `validate_candidate`
  （release spacing ≥ 1 s 等）时，按 [0.5, 0.25] 缩放步长重试；仍失败则丢弃该 record。
- Records 在 closure 启动前 pre-built（确定性、seed-locked）。

### 5. F2 coordinate combinations

8 fixed combinations（每个 combination 用 ±1 方向 × main step × combination size）：

| # | combo | 说明 |
|---|---|---|
| 1 | heading+speed | 2 变量 |
| 2 | release_time_1+delay_1 | 2 变量 |
| 3 | release_time_2+delay_2 | 2 变量 |
| 4 | release_time_3+delay_3 | 2 变量 |
| 5 | heading+speed+release_time_1+delay_1 | 4 变量 |
| 6 | release_time_2+delay_2+release_time_3+delay_3 | 4 变量 |
| 7 | all_release_delay | 6 变量（release_1/2/3 + delay_1/2/3） |
| 8 | all_eight | 8 变量 |

- F2 records 与 F1 records 同时 pre-build（不依赖 F1 执行结果；只依赖 incumbent）。
- Records 在 closure 启动前 pre-built（确定性、seed-locked）。

### 6. F3 / F4 / F5 sequential propagation

| 阶段 | parents | records | profile |
|---|---|---|---|
| F3 | incumbent ∪ best-of-(F1+F2) up to top_k=3 | 4 | medium (0.02) |
| F4 | F3 完成后 top-k | 2 | fine (0.01) |
| F5 | F4 完成后 top-k | 2 | fine (0.005) |

- F3/F4/F5 records **不能**pre-build；必须在前驱阶段执行完成后才构建。
- 每阶段记录其 predecessor 结果，按 `total_union_duration_s desc` 排序，
  取 top-3（含 incumbent）+ pre-defined perturbation patterns 生成下一阶段 records。
- top_k 默认 = 3；F4/F5 top_k 由合同固定 = 2。
- per-stage schedule immutable after construction。

### 7. Selection rule

```
canonical_closure_candidate = argmax total_union_duration_s over all 32 records
if abs(duration_a - duration_b) <= 1e-12:
    tie-break on evaluation_id lexicographic
```

- ε = 1e-12 s（固定、极小）。
- 仅在 ε 内才有 tie-break；超过 ε 的差异视为 strict improvement。

### 8. Cumulative Wall-Clock

```
current_process_elapsed = time.perf_counter() - start_time
cumulative_elapsed = previous_elapsed_seconds_total + current_process_elapsed
if cumulative_elapsed >= wall_clock_cap_seconds:
    stop, write checkpoint, status = WALL_CLOCK_GATE_HIT, no auto extension
```

- On resume: previous_elapsed_seconds_total 从 checkpoint 加载，**不**reset to 0。
- heartbeat 输出 cumulative elapsed + remaining budget。

### 9. Schedule SHA256

```
closure_schedule_sha256 = sha256(canonical_json({
  "F1_records": [...16 deterministic candidate dicts...],
  "F2_records": [...8 deterministic candidate dicts...]
}))
```

- F3/F4/F5 records 不进入 schedule SHA（运行时动态生成）。
- 同一 incumbent + 同一 f1_steps + 同一 f2_combinations 必须产生同一 schedule SHA。
- schedule SHA 作为 8-field resume identity 第 8 字段。

### 10. Checkpoint v4 / Resume identity (8 fields)

- 路径：`work/q3_candidate_closure/checkpoint.json`
- **checkpoint_schema_version = 4**
- resume 强制校验 **8 字段**（任一 mismatch → BLOCKED, exit 2）：
  1. `execution_head_sha`
  2. `contract_snapshot_sha256`
  3. `q2_single_bomb_code_sha256`
  4. `q3_three_bombs_code_sha256`
  5. `q3_search_code_sha256`
  6. `closure_config_sha256`
  7. `candidate_schema_version`
  8. `closure_schedule_sha256`
- atomic write：temp + flush + fsync + os.replace。
- corrupt / load error → `status = CHECKPOINT_LOAD_ERROR`, exit 2。
- identity mismatch → `status = RESUME_IDENTITY_MISMATCH`, exit 2。
- cumulative wall-clock fields persisted：`previous_elapsed_seconds_total`,
  `current_process_elapsed_seconds`, `elapsed_seconds_total`。

### 11. CLI 与退出码

- 默认 `python -m src.q3_search` 仅打印 banner。
- P2 正式搜索：`python -u -m src.q3_search --formal-search --budget 512
  --wall-clock-cap 1200 --seeds 2025 2026 2027`。
- P2C candidate closure：`python -u -m src.q3_search --candidate-closure
  --budget 32 --wall-clock-cap 600 --snapshot-path work/task_contracts/TASK_006-P2C-v4.json`。
- `--dry-run` / `--fake-evaluator` 用于本地调度 / 测试（不消耗 real eval）。
- 退出码：0 无 system_error + F5 完成；1 system_error；2 arg / config 错误
  / dirty worktree / fail-closed / 预算耗尽 / wall-clock hit；3 controlled
  interruption。

### 12. P2C 输出 summary JSON schema (canonical)

`outputs/q3/q3_candidate_closure_summary.json` 至少含以下字段：

- `phase_id = "TASK_006-P2C"`
- `contract_version = 4`
- `result_level.declared_level = "BUDGET_LIMITED_BEST_KNOWN"`
- `result_level.not_a_proven_global_optimum = true`
- `result_level.local_convergence_established = false`
- `result_level.not_a_formal_q3_result = true`
- `result_level.result1_xlsx_generated = false`
- `stage_counts`: {A=0, B=0, C=0, D=0, E=0, F1=16, F2=8, F3=4, F4=2, F5=2, total=32}
- `counts`: {completed_q3_evaluations=32, single_bomb_evaluator_calls=96,
   system_error_count=0, unique_q3_evaluation_ids=32}
- `canonical_q3_candidate`: 8 维 canonical candidate
- `canonical_q3_evidence`: {rehydrated_from_completed_records: true, total_union_duration_s}
- `canonical_total_union_duration_s`: 4.478218820691105
- `comparison`: {incumbent_reference_total_union_duration_s=4.469013137817385,
   absolute_improvement_s=0.009205682873719923, relative_improvement=0.0020598916561287784}
- `incumbent_high_resolution`: {candidate (8 维), p2_evidence_commit,
   p2_execution_head, reference_total_union_duration_s, source}
- `original_p2_evidence_preservation`: {original_p2_execution_head,
   original_p2_evidence_commit, original_512_evaluations_preserved=true,
   original_834_07s_wall_clock_preserved=true, p2_search_rerun_performed=false}
- `identity`: 8-field resume identity SHAs + closure_run_identity_sha256
- `timing`: per-stage wall-clock / median / p90
- `status`: pilot_complete / wall_clock_gate_hit / evaluation_budget_exhausted
  / run_system_error / checkpoint_load_error / resume_identity_mismatch
- `p2c_contract_snapshot_path`: `work/task_contracts/TASK_006-P2C-v4.json`

P2 summary 同步修正：
`outputs/q3/q3_formal_search_summary.json` 增加 `evidence_closure` 块 +
`formal_schedule_complete: true` + `pilot_complete_legacy_field: true`。
原始 P2 512/834.07 s/HEAD=70a4dd7 事实保留不变。

### 13. 局限

- F1-F5 closure 是 bounded refinement over P2 stage E top-1 incumbent；
  **不是**全局最优证明，**不是**解析极值，**不是**官方答案。
- F1/F2 步长固定（heading ±0.002 rad / speed ±0.5 m/s / release ±0.10 s / delay ±0.05 s），
  F1 fallback scales [0.5, 0.25]；未做 Pareto frontier / 多起点 / 自适应步长。
- F3/F4/F5 top-k 选择固定（top_k=3 / 2 / 2）；未做 cross-stage 双向传播。
- selection rule 仅在 ε=1e-12 s 内有 tie-break；超过 ε 视为 strict improvement。
- F5 high-resolution 复评后 canonical 总时长相对 P2 incumbent 仅 +0.21%，
  表明 P2 stage E 局部收敛近似完成；不构成"局部极值证明"。
- 不声称 Q3 全局最优 / VERIFIED / FINAL / 官方答案 / 解析极值；
  **不**声称 local convergence。
- 等级仅 BUDGET_LIMITED_BEST_KNOWN；独立审查签字后才能升 VERIFIED 或进一步
  生成 result1.xlsx（TASK_006-P3）。

---

## Q3 result1 artifact generation (TASK_006-P3 / BUDGET_LIMITED_BEST_KNOWN / NOT A PROVEN GLOBAL OPTIMUM)

> 已在 `scripts/build_result1.py` 实现；通过 `tests/test_q3.py` 新增 ≥ 22 个
> result1 模块单元测试（FakeEvaluator + temporary workbook，**不**调用真实
> Q3 evaluator）验证。本节固定 Q3 result1.xlsx 生成的官方模板处理、列写入合同、
> heading conversion、J 列约定、reconstruction gate、template preservation contract、
> workbook round-trip 与局限。
> 等级: **BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE WITH GENERATED AND ROUND-TRIP-VERIFIED
> RESULT1.XLSX / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM**。
> 不得冒充 Q3 VERIFIED / FINAL / 官方答案 / 解析极值 / 全局最优 / local convergence。

### 0. Closeout 状态（DOCS/METADATA ONLY, 不重跑）

- **TASK_006-P3 COMPLETE**
- result1.xlsx **GENERATED** + **ROUND-TRIP VERIFIED**
- 冻结的 8-dimensional candidate 未改变；P3 是 artifact generation, **不是** 新 optimization
- 当前 Gate: **FINAL AUDIT / HERMES PENDING**
- TASK_007 NOT STARTED
- p3_starting_head = `843b4a1e5791e67a09c377c2173f16a1105ab944`
- p3_execution_head = `cb3dd83c834ec3b5f8c1e85213ddc63301e3d709`
- p3_evidence_commit = `a04e158b7848d7d5a3d381ed9e5871961267ed37`
- result1.xlsx SHA = `b938a90b96181be14990d5bd3395c2cff72e93035828542617571ddc1d754847`
- P2C closure selection score (coarse/0.05) = `4.478218820691105 s` (历史证据)
- P3 canonical reconstruction (fine/0.005) = `4.478204178810118 s` (result1.xlsx 几何来源)
- absolute profile difference = `1.4641880987653622e-05 s`
- official_template_zip_sha256 = `f9879c0d36b7bdccb99fb330a8032e62851ab1a1f0a1636c92440a1cdaec658e`
- official_template_member_sha256 = `d1773205296034c0f02ed7f848f8f1e66af633d1e6562938e059450a554b930e`

历史过程 commit (`03ddda3` PLAN, `0597028` WORKING, `108d21b` headers-fix) 是 P3
身份链内的施工过程；真实 `p3_execution_head` = `cb3dd83c`, 真实 `p3_evidence_commit`
= `a04e158b`. 若任何叙述把 `108d21b` 当作 execution-head, 属
**HISTORICAL COMMIT ROLE REQUIRES FINAL AUDIT ANCESTRY CHECK**, 不由本 closeout
自行重定义, 不重跑 P3.

独立 Final Audit (Audit CC) + Hermes 签字后才能正式合并 PR #13.

### 1. 官方模板处理

- 源：`题目及模板/2025高教社杯数学建模A题_结果模板.zip`。
- 仅以 read-only ZIP 打开（`zipfile.ZipFile(..., mode="r")`，**不得**写入或覆盖）。
- 成员 basename 必须正好为 `result1.xlsx`（唯一）。
- 通过 `io.BytesIO` 加载到内存；openpyxl 打开 in-memory bytes。
- **不得**修改原 ZIP、原成员字节；模板 SHA-256 记录在 resume identity 中。
- `outputs/submission/result1.xlsx` 必须由官方模板 in-memory edit 后另存得到。

### 2. 模板结构识别（10 列 × 3 数据行）

- 头 10 列必须严格 contiguous 且按下列顺序出现：
  1. `无人机运动方向`
  2. `无人机运动速度 (m/s)`
  3. `烟幕干扰弹编号`
  4. `烟幕干扰弹投放点的x坐标 (m)`
  5. `烟幕干扰弹投放点的y坐标 (m)`
  6. `烟幕干扰弹投放点的z坐标 (m)`
  7. `烟幕干扰弹起爆点的x坐标 (m)`
  8. `烟幕干扰弹起爆点的y坐标 (m)`
  9. `烟幕干扰弹起爆点的z坐标 (m)`
  10. `有效干扰时长 (s)`

注：实际官方模板表头含单位后缀（`(m/s)`、`(m)`、`(s)`），与 FACTS.md §13.1
的纯字段名描述略有差异；本合同的 canonical 表头以官方模板实际字符为准。
- 缺失 / 重复 / 顺序错 / 任意列多 / 任意列少 → BLOCKED, exit 2。
- 数据行必须严格 3 行（与官方模板一致）。

### 3. 行写入映射

| 列 | 内容 | 行重复规则 |
|---|---|---|
| A | heading_deg | 三行相同（继承共享 heading） |
| B | speed_mps | 三行相同（继承共享 speed） |
| C | 1, 2, 3 | 顺序炸弹编号 |
| D-F | release_point i xyz | 逐弹独立 |
| G-I | detonation_point i xyz | 逐弹独立 |
| J | bomb i own total_duration_s | 逐弹自身 duration，**不是 union** |

### 4. Heading conversion（[约定]）

- `heading_rad ∈ [0, 2π)` → `heading_deg = degrees(heading_rad) % 360`,
  保证 `0 ≤ heading_deg < 360`。
- 继承 FACTS.md §13.4 [官]：+x = 0°，逆时针为正，范围 0~360°。
- 三行 A 列写入相同 heading_deg 值；不做四舍五入（保留浮点精度，仅做模 360）。
- 测试覆盖：heading_rad = 0, π/2, π, 3π/2, 2π, 2π+0.001,
  -0.001, 6.2831853 都应输出合法 [0, 360) 度数。

### 5. J 列逐弹 duration 约定（[约定]）

- J 列 = bomb i own `total_duration_s`（来自 `SingleBombEvaluation.total_duration_s`）。
- 三弹 union 总时长 4.478218820691105 **不**写入 J 列。
- 仅写入 `q3_result1_artifact_summary.json` 的 `union_total_union_duration_s` 字段、
  `RESULTS.md` 与 PR body。
- 写入顺序：C=1 对应 bomb 1 的 total_duration_s；C=2 对应 bomb 2 的；
  C=3 对应 bomb 3 的。

### 6. Canonical reconstruction gate（1 次真实 Q3 调用）

- 输入：冻结的 8 维 candidate。
- 调用：`src/q3_three_bombs.evaluate_three_bomb_strategy(candidate,
  sample_level="fine", scan_step=0.005)`（exactly 1 次）。
- 期望 `total_union_duration_s ≈ 4.478204178810118` (P3 canonical reconstruction reference).
- 验收：`abs(reconstructed - 4.478204178810118) <= 1e-12`.
- 不通过 → BLOCKED, exit 2；不写入 `outputs/submission/result1.xlsx`；不冒充
  RESULT1.XLSX GENERATED。
- 预算：max_expensive_evaluations = 1；max_run_wall_clock_seconds = 300；
  max_test_wall_clock_seconds = 300。任一上限达到 → BLOCKED。

#### Profile provenance（重要区分）

- P3 canonical reconstruction (fine / 0.005) → **4.478204178810118 s**
  (the P3 reconstruction reference / result1.xlsx 填写用的几何)
- P2C closure selection score (coarse / 0.05) → **4.478218820691105 s**
  (P2C 历史证据, 不是 P3 高精度重建参考)
- 绝对差 (fine vs coarse): **1.4641880987653622e-05 s** (10^-5 量级)
- 不混用: 不得把 fine / 0.005 结果与 coarse / 0.05 reference 做 1e-12 比较,
  也不得放宽 tolerance 到 2e-5. 两个数值各自保留, profile 来源明确.

### 7. Template preservation contract

下列任一改变 → FAIL：

- workbook sheet names（含 case）
- active sheet
- sheet dimensions
- merged-cell ranges
- freeze panes
- header row values（10 个 canonical header）
- annotation / footer text
- row heights
- column widths
- non-data cell values / formulas / style_id
- number formats
- print settings（当可读时）

模板 fingerprint 必须在 in-memory edit 前后 / save → reopen 后均一致。

### 8. 所有单元格类型合同

- 全部 A:J 数据 cell 必须为数值类型（`int` / `float`）。
- **不得**写带单位字符串（如 `"120 m/s"`），不得写公式（`=...`），不得写
  JSON 字符串，不得写 `NaN` / `Inf` / `None`。
- 非数值 cell 写入 → BLOCKED, exit 2。
- 数据 cell 类型检查：`isinstance(cell.value, (int, float)) and
  math.isfinite(cell.value)`。

### 9. Round-trip 核验

- save → 关闭 workbook → 从磁盘重新打开（`load_workbook(output_path)`）→
  逐格读取三行 A:J。
- 数值比较：abs_tol = 1e-10；rel_tol = 1e-12。
- 模板 fingerprint 二次核验（同 §7）。
- 任意不通过 → FAIL, exit 2；不得伪造 PASS。

### 10. Resume identity (7 字段, checkpoint_schema_version=5)

- 路径：`work/q3_result1/checkpoint.json`。
- 7 字段（任一 mismatch → BLOCKED, exit 2）：
  1. `execution_head_sha` — 当前 commit HEAD
  2. `contract_snapshot_sha256` — `work/task_contracts/TASK_006-P3-v5.json` 的 SHA-256
  3. `q2_single_bomb_code_sha256` — `src/q2_single_bomb.py` 的 SHA-256
  4. `q3_three_bombs_code_sha256` — `src/q3_three_bombs.py` 的 SHA-256
  5. `result1_builder_code_sha256` — `scripts/build_result1.py` 的 SHA-256
  6. `canonical_candidate_sha256` — 冻结 8 维 candidate 的 SHA-256
  7. `official_template_sha256` — `题目及模板/..._结果模板.zip` 整文件字节的 SHA-256
     （legacy 字段；P3 closeout 新增 `official_template_member_sha256` 给出
     `result1.xlsx` member 字节的 SHA-256；新增 `official_template_zip_sha256` 给出
     ZIP 整文件字节的 SHA-256。两个新字段的语义在
     `outputs/q3/q3_result1_artifact_summary.json` `identity_provenance_closeout`
     块中明确说明, 不替换 legacy 字段。）
- atomic write：temp + flush + fsync + os.replace。
- corrupt / load error → `status = CHECKPOINT_LOAD_ERROR`, exit 2。
- identity mismatch → `status = RESUME_IDENTITY_MISMATCH`, exit 2。

### 11. Artifact summary JSON schema

`outputs/q3/q3_result1_artifact_summary.json` 至少含：

- `phase_id = "TASK_006-P3"`
- `contract_version = 5`
- `result_level.declared_level = "BUDGET_LIMITED_BEST_KNOWN"` + `result1_xlsx_generated`
- `identity`: 7 字段 SHA + `result1_run_identity_sha256`
- `canonical_candidate`: 8 维 frozen candidate
- `canonical_reconstruction`: 1 call 的真实输出（含 bomb_evaluations, union_intervals,
  total_union_duration_s, sample_level=fine, scan_step=0.005, q3_evaluation_id,
  elapsed_s, single_bomb_evaluator_calls=3）
- `reconstruction_gate`: abs(reconstructed - reference) ≤ 1e-12 ✓
- `workbook`: official_template_sha256, output_path, output_sha256,
  template_member_basename, sheet_names, active_sheet, header_names,
  column_mapping, three_rows_written, all_cells_numeric, union_duration_written_to_j
  (必须为 false), round_trip_status
- `template_fingerprint`: 保存前后 + save→reopen 后均一致的所有非数据 cell 元数据
- `status`: result1_xlsx_generated / template_mismatch / round_trip_fail /
  checkpoint_load_error / resume_identity_mismatch
- `output_path`: `outputs/submission/result1.xlsx`

### 12. 测试（≥ 22 新增，0 real Q3 evaluation in tests）

`tests/test_q3.py` 新增至少 22 个 result1 模块测试（全部用 FakeEvaluator 或
temporary workbook，**不**调用真实 Q3 evaluator）：

1. heading rad → degree（含 wrap-around / 负值 / 2π+ 等）
2. header detection（10 列 contiguous + canonical 顺序）
3. 缺失 header blocked
4. 重复 header blocked
5. workbook creation（from ZIP, read-only）
6. 三行严格 3 行（C=1, 2, 3）
7. C 列 bomb index 顺序 [1, 2, 3]
8. A / B 列三行相同
9. D-F 与 release_points 对应
10. G-I 与 detonation_points 对应
11. J 列 per-bomb duration（非 union）
12. union NOT written into J cells（写入 4.47821… 必须 BLOCKED）
13. NaN / Inf 写入 BLOCKED
14. 字符串 / 公式 / JSON 写入 BLOCKED
15. structural fingerprint preserved（headers, freeze panes, merged cells, etc.）
16. non-data formula preserved
17. styles preserved
18. round-trip read（save → reopen → verify 全部 10×3 cell）
19. official template unchanged（SHA-256 不变）
20. output SHA-256 recorded
21. summary JSON round-trip（artifact summary 可读回 / 字段完整）
22. reconstruction mismatch fail-closed（mock evaluator 输出 4.4782189 → fail）

### 13. CLI 与退出码

- 默认 `python -m scripts.build_result1` 执行 P3 流程：
  1. 验证 7 字段 resume identity（start from clean HEAD）；
  2. 从官方 ZIP 加载 result1.xlsx 到内存；
  3. 验证 10 列 contiguous + 3 行；
  4. 调用 `evaluate_three_bomb_strategy(candidate, sample_level="fine",
     scan_step=0.005)` 一次；
  5. 验证 reconstruction gate（abs diff ≤ 1e-12）；
  6. 写入 A:J 三行；
  7. 保存到 `outputs/submission/result1.xlsx`；
  8. 关闭并重新打开，round-trip 核验；
  9. 写 `q3_result1_artifact_summary.json`。
- `--dry-run`：跳过步骤 4-7，仅做结构识别与 resume identity 校验。
- 退出码：0 PASS；1 system_error；2 arg / identity mismatch / reconstruction
  gate fail / round-trip fail / template fingerprint mismatch。

### 14. 局限

- 不重跑 Pilot / P2 / P2C；冻结的 8 维 candidate 是 P3 唯一输入。
- 一次 fine / 0.005 重建是 deterministic re-evaluation，**不是**新的搜索、
  **不是** challenger、**不是** refinement。
- shared heading / speed / interval union 来自 P2C 合同，不在本阶段改写。
- 不声称 Q3 全局最优 / VERIFIED / FINAL / 官方答案 / 解析极值；
  **不**声称 local convergence。
- 等级仅 BUDGET_LIMITED_BEST_KNOWN；Final Audit + Hermes 签字后才能升
  VERIFIED 或进一步生成 result2.xlsx / result3.xlsx / 启动 Q4 / Q5。
- 模板 fingerprint 校验保证官方模板未被破坏，但**不**验证模板本身的数学正确性。
- 不引入 openpyxl 之外的新依赖；仅 openpyxl + zipfile + stdlib。

---

## TASK_007 Q4 THREE-DRONE FOUNDATION CONTRACT (TASK_007-P0P1 / CONTRACT_ONLY / NOT IMPLEMENTED)

> 本节为 TASK_007-P0/P1 冻结的 12 维 Q4 candidate 评估合同，**仅合同**，不实现。
> 本轮 (TASK_007-P0/P1) 输出上限 = CONTRACT_ONLY / IMPLEMENTATION NOT STARTED /
> RESULT2.XLSX NOT GENERATED。后续 TASK_007-P2A / P2B / P3 / P4 / P5 才进入 Q4
> evaluator + search + 写盘。
>
> **本节为 v2 canonical contract** (审计综合修复后); 历史 v1 snapshot 已被
> 第一次 FIX commit (`6f52c39c14b957d466f39248fcbfa8fae923a234`) 覆盖，详见 §15。
> 后续 P2A / P2B / P3 / P4 / P5 context 全部引用 v2，不再引用 v1。
>
> 等级: **TASK_007 Q4 FOUNDATION CONTRACT — CONTRACT_ONLY**。
> 不得冒充 Q4 IMPLEMENTED / Q4 SEARCHED / RESULT2.XLSX GENERATED / VERIFIED / FINAL /
> local convergence / global optimum / 官方答案。

### 0. TASK_007 阶段映射 (phase map, TASK_007-P0P1 冻结)

| 阶段 | 范围 | 输出物 / artifact root | 触发条件 |
|---|---|---|---|
| **TASK_007-P0/P1** (本轮) | preflight + 12-dim candidate 合同 + work/ ignore 治理 + result2.xlsx 模板 read-only 验证 + Q2 u0 复用审计 | MODEL.md / NEXT_TASK.md / FACTS.md / work/task_contracts/TASK_007-P0P1-v1.json (历史) / work/task_contracts/TASK_007-P0P1-v2.json (canonical) / work/q4_foundation/ | MAIN 立项 |
| **TASK_007-P2A** | Q4 evaluator 实现 + 单元测试 (静态 / 受控 / stub / fixture); 真实 Q4 evaluator 调用 = 0 | src/q4_three_drones.py / tests/test_q4.py | MAIN 显式授权 + AUDIT DELTA RECHECK 通过 + P0/P1 v2 冻结 |
| **TASK_007-P2B** | tiny bounded pilot + runtime calibration (在 MAIN 显式冻结的 pilot self-budget 内运行有限真实 Q4 评估) | work/q4_pilot/ (P2 唯一目录) | MAIN 显式授权 + P2A MAIN REVIEW 通过 + pilot self-budget 显式冻结 |
| **TASK_007-P3** | Q4 正式 bounded search (使用 P2B 推荐的 task-specific 预算) | work/q4_search/ (P3 唯一目录; 含 formal_search_config.json, checkpoint.json, finalists.json, formal_search_summary.json 等) | MAIN 显式授权 + P2B runtime calibration 完成 + P3 budget 冻结 |
| **TASK_007-P4** | candidate closure + 局部 refined re-evaluation + 跨 seed 鲁棒性 (基于 P3 冻结的 finalists) | work/q4_candidate_closure/ (P4 唯一目录; 含 closure_context.json, checkpoint.json, input_manifest.json, final_candidate.json, candidate_closure_summary.json) | MAIN 显式授权 + P3 主搜索完成 + finalists 冻结 |
| **TASK_007-P5** | fine reconstruction (反算 per-drone release / detonation / duration) + 写盘 `outputs/submission/result2.xlsx` + round-trip 验证 (rows 2-4 写入 / row 5 保留 / B6 附注保留 / A1:J6 footprint) | `outputs/submission/result2.xlsx` + work/q4_result2/ evidence | MAIN 显式授权 + P4 candidate closure 完成 |

约束：
- **P0/P1** 本轮**不**实现 evaluator / **不**运行 search / **不**写盘；
- **P2A** 真实 Q4 evaluator calls = 0；**P2B** 在 MAIN 显式冻结的 self-budget 内；
- **P3** 启动前 P2B 必须已经 runtime calibration 完成 + P2B recommended budget frozen；
- **P4** 启动前 P3 必须已经产出 best-so-far candidate + formal_search_summary frozen；
- **P5** 启动前 P4 必须已经 candidate closure 完成 + final_candidate frozen；
- P5 写盘前必须完成 §7 写盘合同全部 round-trip 验证 (rows 2-4 写入 / row 5 保留 /
  B6 附注保留 / A1:J6 footprint / sheet name / header A1:J1);
- 任一阶段不通过 MAIN REVIEW 不得跳级进入下一阶段；
- **单 PR 规则** (见 §13): PR #14 整个 TASK_007 期间保持 Draft, 不合并。

### 1. 官方事实 (FACTS.md §5 + §8 + §9 + §13.2 + §13.4)

- **[官]** FY1、FY2、FY3 各投放**恰好 1 枚**烟幕干扰弹对 M1 实施干扰（FACTS.md §5）；
  Q4 文本为"利用 FY1、FY2、FY3 共 3 架无人机**各投放 1 枚**烟幕干扰弹"。
- **[官]** 三架无人机初始位置（FACTS.md §8）：

  | 编号 | 坐标 (x, y, z) |
  |---|---|
  | FY1 | (17800, 0, 1800) |
  | FY2 | (12000, 1400, 1400) |
  | FY3 | (6000, −3000, 700) |

- **[官]** Q4 每架 1 枚，FACTS.md §10 / §12 "同架两枚之间投放间隔 ≥ 1 s" 在 Q4 **不触发**
  （每架仅 1 枚，不存在"同架次两枚之间"的间隔场景）。FACTS.md §10 / §12 文本仍为 [官]
  规则，但 Q4 不调用该约束。
- **[官]** 每架无人机 70~140 m/s 等高度匀速直线，**且各架 heading / speed 独立**：
  FACTS.md §9 "每架无人机的航向、速度可不相同，但一旦确定就不再调整"。
  Q4 没有"三架共享航向 / 速度"约束，与 Q3 §3 [约定] 严格区分。
- **[官]** 烟幕干扰弹投放后受重力；起爆后 10 m 半径球状云团；3 m/s 下沉；
  起爆后 20 s 有效；同 FACTS.md §10 / §9（Q2 / Q3 复用）。
- **[官]** 真目标几何同 FACTS.md §11：圆柱 r=7 m, h=10 m，下底面圆心 (0, 200, 0)。
- **[官]** M1 飞行同 FACTS.md §8 / §9：起点 (20000, 0, 2000)，300 m/s 直指假目标。
- **[官]** 结果保存到 result2.xlsx（FACTS.md §5 / §13.2，§13.2 已由 FIX commit `6f52c39`
  修正为"官方要求 vs 模板格式行"两个不同事实分离）。
- **[官]** 模板附注：方向角 +x=0°，逆时针为正，0~360°（FACTS.md §13.4）。
- **[官]** Q4 heading 原始字段约束 (来自 FACTS.md §9 + §10 + 几何约定): 任何合法
  candidate 的原始 `heading_rad_fyi` 必须满足 `0 ≤ heading_rad_fyi < 2π`。
  原始 heading 在 prevalidation 阶段强制，Q2 返回的 `normalized_heading_rad` **不**替换
  identity payload 中的 candidate raw heading。

### 2. 12 维决策变量 (ThreeDroneCandidate)

每架无人机独立 4 变量（heading_rad, speed_mps, release_time_s, delay_s），
共 3 架 × 4 = **12 维**：

```python
@dataclass(frozen=True)
class ThreeDroneCandidate:
    # FY1 (drone_order index 0)
    heading_rad_fy1: float        # θ_1 ∈ [0, 2π) — 原始字段, prevalidation 阶段强制
    speed_mps_fy1: float          # v_1 ∈ [70, 140]
    release_time_s_fy1: float     # ≥ 0
    delay_s_fy1: float            # ≥ 0
    # FY2 (drone_order index 1)
    heading_rad_fy2: float        # θ_2 ∈ [0, 2π) — 原始字段, prevalidation 阶段强制
    speed_mps_fy2: float          # v_2 ∈ [70, 140]
    release_time_s_fy2: float     # ≥ 0
    delay_s_fy2: float            # ≥ 0
    # FY3 (drone_order index 2)
    heading_rad_fy3: float        # θ_3 ∈ [0, 2π) — 原始字段, prevalidation 阶段强制
    speed_mps_fy3: float          # v_3 ∈ [70, 140]
    release_time_s_fy3: float     # ≥ 0
    delay_s_fy3: float            # ≥ 0
```

候选合同：

- 全部 12 个变量必须有限数；NaN / +Inf / -Inf 在 prevalidation 阶段拒绝；
- 原始字段判定（不先 normalize）：
  `heading_rad_fyi ∈ [0, 2π)`, `speed_mps_fyi ∈ [70, 140]`，
  `release_time_s_fyi ≥ 0`, `delay_s_fyi ≥ 0`；
- 由于原始 heading 已限制在 `[0, 2π)`，**不存在** `0` 与 `2π` 重复策略；
- **三架各自 heading / speed 独立**（与 Q3 共享 heading / speed 的 §3 [约定] 严格相反）；
- 三架无人机两两之间**不**引入"投放间隔 ≥ 1 s"或"共享 release_time / delay"等约束
  （FACTS.md §10 / §12 是"**同架**两枚"间隔；Q4 每架 1 枚，跨架无约束）；
- 不引入跨架视线协同 / 时序协同 / 通信延迟等第三套变量；保持 Q2 风格的单弹独立决策。

### 3. 与 Q3 的差异 (避免继承错误)

| 维度 | Q3 (TASK_006) | Q4 (TASK_007) |
|---|---|---|
| 候选维度 | 8 = 2 共享 + 3 × 2 | **12 = 3 × 4** (每架独立 4 变量) |
| 共享 heading / speed | YES (Q3 §3 [约定]) | **NO** (FACTS.md §9 明确"每架可不相同") |
| 共享 release / delay | NO (本来就是各弹独立) | NO |
| 同架投放间隔约束 | YES (≥ 1 s, FACTS §10) | **不触发** (FY1/FY2/FY3 各恰好 1 枚) |
| 跨架耦合约束 | 不存在 | **不引入** (避免人为耦合) |
| union 范围 | Q3 union = 同一 FY1 的三枚烟幕弹区间并集 | **Q4 union = FY1/FY2/FY3 三架各一枚烟幕弹区间并集** (= I_FY1 ∪ I_FY2 ∪ I_FY3) |
| evaluator 单弹调用数 (正常路径) | 3 × 1 = 3 (同架多弹) | 3 × 1 = 3 (跨架各 1) |
| evaluator 调用 u0 | U0 (FY1 初始位置) | U0_FY1 / U0_FY2 / U0_FY3 (**每架独立**, 本节 §4) |
| union 输入来源 | 3 × SingleBombEvaluation (同 FY1) | 3 × SingleBombEvaluation (FY1 / FY2 / FY3) |

注: 旧措辞 (任何类似"Q4 union 否定 → 三机 union" 的简化否定) 已废, 替换为
"Q4 union = FY1/FY2/FY3 三架各一枚烟幕弹区间并集 (= I_FY1 ∪ I_FY2 ∪ I_FY3)"。

### 4. Q2 evaluator u0 复用 (本轮 §10 P0-1)

Q2 single-bomb evaluator (`src.q2_single_bomb`) 的 public API 已经原生支持 per-drone
初始位置参数 `u0: Vec`：

| 函数 | 是否接受 u0 | 是否使用 u0 | 用途 |
|---|---|---|---|
| `release_point(strategy, u0=U0)` | YES | YES (via `fy1_position(t, u0, v)`) | 投放点计算 |
| `detonation_point(strategy, u0=U0)` | YES | YES (via `release_point(strategy, u0)`) | 起爆点计算 |
| `detonation_point_eq2(strategy, u0=U0)` | YES | YES (via `vector_add(u0, ...)`) | 等价形式（测试用） |
| `validate_strategy(strategy, u0=U0)` | YES | YES (调用 `detonation_point(s, u0)` 做 z 分类) | 物理 / 合同合法性 |
| `evaluate_single_bomb_strategy(strategy, ..., u0=U0, ...)` | YES | YES (向下传递到 validate/release/detonation) | 单弹完整评估 |

Q4 评估 = 严格两阶段 + EXCEPTION PROPAGATION MODEL（N1 冻结）：

#### 阶段 A — Candidate prevalidation (0 次 evaluate_single_bomb_strategy)

对 FY1 / FY2 / FY3 三个策略做纯轻量预检：

- finite (NaN / +Inf / -Inf 拒绝);
- 原始 heading 字段范围 `0 ≤ heading_rad_fyi < 2π`;
- `speed_mps_fyi ∈ [70, 140]`;
- `release_time_s_fyi ≥ 0`；
- `delay_s_fyi ≥ 0`；
- 使用对应 `u0 = U0_FYi` 计算 `detonation_z_fyi`，要求 `detonation_z_fyi ≥ -EPS_GROUND`。

阶段 A **不调用** `evaluate_single_bomb_strategy`。本阶段计数：

```
attempted_single_bomb_calls = 0
completed_single_bomb_calls = 0
```

如果任一策略预检失败 → 直接返回正常 `ThreeDroneEvaluation`：

```
valid = False
status = "invalid"
reason = "prevalidation_failed: <具体策略 + 失败字段>"
drone_evaluations = ()
union_intervals = ()
total_union_duration_s = 0
attempted_single_bomb_calls = 0
completed_single_bomb_calls = 0
```

**不得**调用 Q2 evaluator；**不得**伪造任何 SingleBombEvaluation。

#### 阶段 B — Normal evaluator execution (3 次 evaluate_single_bomb_strategy)

仅当阶段 A 三个策略全部通过 → 进入阶段 B。固定顺序：

```
FY1 → FY2 → FY3
```

每次调用：

```python
evaluate_single_bomb_strategy(
    SingleBombStrategy(
        heading_rad=c.heading_rad_fyi,
        speed_mps=c.speed_mps_fyi,
        release_time_s=c.release_time_s_fyi,
        delay_s=c.delay_s_fyi,
    ),
    sample_level=..., scan_step=..., u0=U0_FYi,
)
```

阶段 B 全部正常返回：

```
attempted_single_bomb_calls = 3
completed_single_bomb_calls = 3
len(drone_evaluations) = 3
```

随后根据 Q2 returns 计算 Q4 valid / status / union_intervals / total_union_duration_s。

#### 阶段 C — System error (EXCEPTION PROPAGATION MODEL)

如果阶段 B 中第 k 次调用抛出**程序异常**（系统异常；非 Q2 合法 `valid=False` 返回）：

1. **立即停止**后续 (k+1, k+2) 调用；
2. **抛出** `Q4EvaluationSystemError`（v2 冻结的新异常类，见 §5）；
3. **不返回**正常 `ThreeDroneEvaluation`；
4. **不构造**任何 fake `SingleBombEvaluation`；
5. **不**将 system error 解释为 invalid / zero_union / pruned_zero / zero_window / ok；
6. **不**向 Q2 status 集合 (invalid / pruned_zero / zero_window / ok) 加入 `system_error`；
7. `ThreeDroneEvaluation` 字段不承载 system error。

异常对象 / 外层 error record 至少携带：

- `failing_drone_id`（如 "FY2"）
- `attempted_single_bomb_calls = k`（已发起调用总数, 包括失败那次）
- `completed_single_bomb_calls = k - 1`（已成功完成调用数, 失败那次不计）
- `completed_drone_ids`（如 ["FY1"]）
- `completed_evaluations`（已成功完成的 SingleBombEvaluation 列表）
- `original_exception_type`
- `original_exception_message`

外层 Pilot / Search runner 负责：
- 捕获 `Q4EvaluationSystemError`；
- 增加 system_error 计数；
- 记录上述 attempted / completed call accounting；
- 将该候选从正常 objective 排名中排除；
- 以非零执行状态或 fail-closed 规则停止 / 报告。

#### Q2 合法 status 集合 (冻结, 不扩展)

Q2 合法 status 仍然只有：

- `invalid`
- `pruned_zero`
- `zero_window`
- `ok`

若 Q2 正常返回 `valid=False`（`status="invalid"` 或 `pruned_zero` 或 `zero_window`），
它仍是**正常返回**的 Q2 evaluation，**不是** system error。

三次 Q2 调用正常结束后，如果任一 Q2 result `valid=False`：

```
ThreeDroneEvaluation.valid = False
ThreeDroneEvaluation.status = "invalid"
ThreeDroneEvaluation.drone_evaluations 保留 3 个真实 Q2 返回 (长度=3)
```

`pruned_zero` / `zero_window`: Q4 仍可 `valid=True`，但该单弹贡献空区间，参与 union 仍合法。

### 5. ThreeDroneEvaluation 输出结构 (v2 冻结, NOT implemented)

```python
@dataclass(frozen=True)
class ThreeDroneEvaluation:
    candidate: ThreeDroneCandidate
    valid: bool
    status: str           # 正常: "invalid" | "zero_union" | "ok"
    reason: str
    drone_evaluations: tuple  # 长度 0 (prevalidation invalid) 或 3 (normal path)
    union_intervals: tuple
    total_union_duration_s: float
    sample_level: str
    scan_step_s: float
    elapsed_s: float
    q4_evaluation_id: str      # 见 §6 (Q4 FORMAL EVALUATION IDENTITY SCHEMA)
    attempted_single_bomb_calls: int   # 0 (prevalidation invalid) 或 3 (normal path)
    completed_single_bomb_calls: int   # 0 (prevalidation invalid) 或 3 (normal path)
```

不变量：

- prevalidation invalid path: `drone_evaluations = ()`, `attempted = 0`, `completed = 0`,
  `valid = False`, `status = "invalid"`；
- normal evaluator path: `len(drone_evaluations) = 3`, `attempted = 3`, `completed = 3`；
- system error path: **不生成** `ThreeDroneEvaluation`；抛 `Q4EvaluationSystemError`。

normal status set: `{invalid, zero_union, ok}`。`system_error` 不是 Q4 status。

异常类：

```python
class Q4EvaluationSystemError(RuntimeError):
    failing_drone_id: str
    attempted_single_bomb_calls: int
    completed_single_bomb_calls: int
    completed_drone_ids: list
    completed_evaluations: list
    original_exception_type: str
    original_exception_message: str
```

Q4 目标 (继承 FACTS.md §14; [约定]):

```
total_union_duration = measure(I_FY1 ∪ I_FY2 ∪ I_FY3)
```

union 行为（与 Q3 §8 一致）：

- 重叠部分只计算一次；
- 不连续区间分别累加；
- nested interval 正确；
- touching interval 使用确定性规范化（epsilon = 1e-12 s）；
- 空区间合法（贡献 0）；
- 区间排序稳定（按 start 升序，相同 start 按 end 升序）；
- 不得把三架单弹 duration 直接相加冒充 union；
- 不得使用会改变可观测时长的大容差。

实现复用 Q3 已经冻结的 helper：
- `src.q3_three_bombs.normalize_intervals`
- `src.q3_three_bombs.union_intervals`
- `src.q3_three_bombs.total_union_duration`

Q3 union vs Q4 union 措辞统一：

- Q3 union = 同一 FY1 的三枚烟幕弹区间并集 (intervals of 3 bombs from one drone, FY1)。
- Q4 union = FY1/FY2/FY3 三架各一枚烟幕弹区间并集 (= I_FY1 ∪ I_FY2 ∪ I_FY3)。

旧措辞 (任何类似简化否定的旧 union 描述) 已删除。

### 6. Q4 FORMAL EVALUATION IDENTITY SCHEMA (v2 冻结, NOT implemented)

> **关键合同**: 不得在 `q4_evaluator_code_sha` 存在之前生成任何正式 Q4 evaluation ID。
> 不得使用 `null` / `"pending"` / 空字符串 / 占位 SHA 代替 `q4_evaluator_code_sha`。

`q4_evaluation_id` = SHA-256 over canonical JSON identity payload (§7 冻结序列化规则)。

字段数量由 schema 实际内容决定；不把字段数量写成合同重点。
schema 由以下 8 个 category 构成：

#### 1. Candidate identity

- `candidate_schema_version`
- candidate 12 个原始字段：
  - `candidate.heading_rad_fy1` / `speed_mps_fy1` / `release_time_s_fy1` / `delay_s_fy1`
  - `candidate.heading_rad_fy2` / `speed_mps_fy2` / `release_time_s_fy2` / `delay_s_fy2`
  - `candidate.heading_rad_fy3` / `speed_mps_fy3` / `release_time_s_fy3` / `delay_s_fy3`
- `drone_order = ["FY1", "FY2", "FY3"]` (固定, 不允许重排)
- **raw heading 规则**: identity payload 使用 prevalidation 后的原始
  `candidate.heading_rad_fyi` (满足 `0 ≤ heading_rad_fyi < 2π`)；Q2 返回的
  `normalized_heading_rad` **不得**替换 identity payload 中的 candidate raw heading。

#### 2. Per-drone context

- `fy1_initial_position_m = [17800, 0, 1800]`
- `fy2_initial_position_m = [12000, 1400, 1400]`
- `fy3_initial_position_m = [6000, -3000, 700]`

> **不得**只绑定 `drone_order` 而不绑定各 `u0` 字段。

#### 3. Missile and target context

- `missile_id = "M1"`
- `missile_initial_position_m = [20000, 0, 2000]`
- `missile_speed_mps = 300`
- `missile_trajectory_identity` (含航向 / 指向 fake_target_origin 等不可变指纹)
- `fake_target_origin_m = [0, 0, 0]`
- `true_target_geometry_parameters`:
  - `radius = 7`
  - `height = 10`
  - `lower_center = [0, 200, 0]`
- `true_target_geometry_id` (上述参数的不可变指纹)

#### 4. Numerical profile

- `sample_level`
- `scan_step_s`
- `cylinder_sample_profile_parameters`
- `cylinder_sample_profile_sha256`
- `interval_touching_epsilon_s`
- `candidate_raw_heading_policy` (固定: 0 ≤ heading_rad < 2π, identity 用 raw)

#### 5. Code identity (本类所有项必须存在)

- `q1_baseline_code_sha`
- `q1_cylinder_code_sha`
- `q2_single_bomb_code_sha`
- `q3_union_helper_code_sha`
- `q4_evaluator_code_sha` ← **REQUIRED**

> **NO FORMAL Q4 EVALUATION ID MAY BE GENERATED BEFORE
> `q4_evaluator_code_sha` EXISTS**。
>
> 在 P0/P1 阶段, `q4_evaluator_code_sha` 尚不存在；P0/P1 阶段**不得**生成任何
> 正式 `q4_evaluation_id`。任何 `null` / `"pending"` / `""` / 占位 SHA 替代
> `q4_evaluator_code_sha` 都是**禁止**的。
>
> **不得**用 `q4_pilot_config_sha` 代替 `q4_evaluator_code_sha`。

#### 6. Runtime / config identity

- `q4_config_schema_version`
- `q4_config_sha256`
- `objective_identity` (= `"measure(I_FY1 ∪ I_FY2 ∪ I_FY3)"`)
- `evaluation_call_contract_version` (= v2 冻结的两阶段 + EXCEPTION PROPAGATION)

#### 7. Physical constants

- `gravity_mps2` (= 9.8, -z 方向, MODEL 假设)
- `cloud_radius_m` (= 10)
- `cloud_sink_mps` (= 3)
- `cloud_duration_s` (= 20)
- `EPS_GROUND`
- 其他 evaluator 实际读取且可能改变结果的常量

#### 8. Contract identity

- `q4_model_contract_version`
- `q4_model_contract_sha256`

> 用于证明正式 evaluator 依照哪个冻结合同执行。P0/P1 阶段正式 `q4_evaluator_code_sha`
> 不存在 → 不得生成正式 `q4_evaluation_id`。

#### 措辞 (避免过强)

```
在相同受支持 Python/runtime 环境、相同代码 bytes、相同冻结配置和无外部非确定性输入的
前提下，同一 q4_evaluation_id 预期产生确定性一致结果。
```

正式验证仍必须通过：
- repeated-run deterministic test；
- checkpoint / resume test；
- identity mutation tests。

**不得**用 ID 本身代替确定性测试。

### 7. canonical JSON 规则 (v2 冻结)

`q4_evaluation_id` 的 SHA-256 输入 = canonical JSON UTF-8 bytes，必须满足：

- **UTF-8** 编码；
- JSON object keys 按**字典序排序**（不依赖 Python dict 插入顺序）；
- `separators` 使用无空白稳定形式 (e.g. `(",", ":")`)；
- `allow_nan = false`；
- **NaN / +Inf / -Inf** 在 prevalidation 阶段拒绝，不进入 canonical JSON；
- 所有 **`-0.0`** 在 identity payload 中规范化为 `0.0`；
- **tuple** 在 payload 中转为固定顺序 JSON array；
- `drone_order` 固定 `["FY1", "FY2", "FY3"]`；
- **不**依赖 Python dict 插入顺序；
- **不**依赖 locale；
- **不**依赖格式化后的显示字符串；
- **hash 输入** = canonical JSON UTF-8 bytes。

### 8. result2.xlsx 写盘合同 (TASK_007-P5 冻结, NOT yet generated)

**模板结构 (TASK_007-P0/P1 实测)**：

| 区域 | 范围 | 说明 |
|---|---|---|
| sheet name | `Sheet1` | 唯一 sheet (TASK_007-P0/P1 实测) |
| header 范围 | A1:J1 | row 1, 10 列 (TASK_007-P0/P1 实测) |
| output_rows (写入区) | rows 2, 3, 4 | FY1 → row 2, FY2 → row 3, FY3 → row 4 (drone_order 锁定) |
| preserved_blank_row (保留) | row 5 | 官方模板预存的空白格式行, **不删除、不重排、不写入** 任何数据 |
| note_cell (附注) | B6 | 「注：以 x 轴为正向，逆时针方向为正，取值 0~360（度）」保留原样 |
| workbook 整体 footprint | A1:J6 | 6 行 × 10 列, 含 header + 3 数据行 + 1 保留行 + 1 附注行 |

**列写入合同 (rows 2, 3, 4 三行, drone_order 锁定)**:

| 列 | 写入值 |
|---|---|
| A | 文本 "FY1" / "FY2" / "FY3" (drone_order) |
| B | drone_i heading **度** (degrees(raw heading_rad_fyi) % 360; raw heading 来自 prevalidation 字段) |
| C | drone_i speed_mps_fyi |
| D-F | drone_i release_point xyz (由 Q2 evaluator 推导) |
| G-I | drone_i detonation_point xyz (由 Q2 evaluator 推导) |
| J | drone_i own `total_duration_s` (**每架自身**, 不是 union) |

约束：

- **rows 2, 3, 4** 写入三条数据（FY1 / FY2 / FY3 顺序，drone_order 锁定）；
- **row 5 保持官方模板原状和空白**，**不删除、不重排、不写入** 第四条记录；
  row 5 是官方模板预存的空白格式行, 不是 Q4 第四条结果;
- **不**写入三机 union 总时长到 J 列；J 列是 per-drone own duration；
- 方向角规则：+x=0°，逆时针为正，0~360°（FACTS.md §13.4 [官]）；
- header A1:J1 保留原样 (官方模板 10 列表头, **不得覆盖、不得改字段名、不得改列宽**);
- B6 附注 (「注：以 x 轴为正向, 逆时针方向为正, 取值 0~360（度）」) 保留原样,
  不得修改、不得删除、不得改写到其他单元格;
- sheet name `Sheet1` 保留, 不得新增、删除、重命名 sheet;
- merged cells / freeze panes / row heights / column widths 全部保留原样;
- 模板 fingerprint (sheet names / A1:J1 header / B6 note / row 5 空白 / 整体 A1:J6
  footprint / merged cells / freeze panes / row heights / column widths)
  round-trip 校验必须 PASS, 包括 row 5 必须保持空白和 B6 附注必须保持原文;
- 写入流程必须使用 `BytesIO` 打开官方模板副本, **不**直接修改磁盘上官方模板文件;
  写入完成后 BytesIO 内容 save 到 `outputs/submission/result2.xlsx`;
- 写盘后必须由程序**重新读回** `outputs/submission/result2.xlsx`, 验证:
  sheet name / A1:J1 header / rows 2-4 内容 (3 行 FY1/FY2/FY3) / row 5 保持空白 /
  B6 附注原文 / A1:J6 footprint;
- 本合同**冻结**于 TASK_007-P5 启动前；本轮 (P0/P1) 不生成 result2.xlsx。

### 9. Q4 候选来源 (TASK_007-P2A/P2B 冻结, NOT yet implemented)

候选 `candidate_source` 字段（占位，待 P2A/P2B frozen）：

1. `q2_canonical_seed_family_fy1` — 从 Q2 canonical anchor 派生 FY1 子段，FY2/FY3 用
   Q3 candidate closure P2C winner 的部分时序种子；
2. `q2_canonical_seed_family_fy2` — 同上，对 FY2 角色；
3. `q2_canonical_seed_family_fy3` — 同上，对 FY3 角色；
4. `deterministic_random_seed_<n>` — 12 维独立均匀采样，`<n>` 为占位 seed 整数
   （具体 seed 列表 NOT frozen 在 P0/P1；P2B 启动前由 MAIN 在新 contract_version
   中冻结 seeds 列表，本 P0/P1 不预先固定具体数字）；
5. `finalist_medium_recheck` — 从 medium recheck top-K；
6. `finalist_fine_spotcheck` — 从 fine finalist top-K。

注：占位候选源列表，不在 P0/P1 实施；最终 candidate_source 集合 + 数字 seed
列表在 TASK_007-P2B 启动前由 MAIN 在新的 contract_version 中冻结。本 P0/P1
**不**预先固定任何具体 seed 数字，不声称 seeds 列表已 frozen，不声称
"multi-seed 必须 ≥ 3"。

### 10. 未来预算与运行边界 (placeholder, NOT frozen)

Q4 未来预算冻结规则 (TASK_007-P2A / P2B / P3 contract 必须遵守)：

- 真实 Q4 evaluation 调用上限 `max_expensive_evaluations` 必须在 P2B 启动前由 MAIN
  基于 P2A 实际 evaluator 性能 **重新冻结 task-specific 数值**；
- 不得沿用 Q3 数字；
- wall-clock `max_run_wall_clock_seconds` 同上；
- seeds 数量与具体 seed 列表必须在 P2B 启动前由 MAIN 重新冻结；本 P0/P1 不得声称
  seeds 数量、具体 seed 列表、wall-clock 上限、evaluation 上限已 frozen；
- 单次 Q4 evaluation = 阶段 A (prevalidation, 0 次 evaluate_single_bomb_strategy)
  + 阶段 B (3 次 evaluate_single_bomb_strategy, FY1 → FY2 → FY3 顺序)；
- P2B pilot self-budget 与 P3 formal budget 是**两套不同**预算集合, 不得混用;
- 严禁在 P0/P1 阶段**冻结**任何未来 P2B / P3 budget / wall-clock / seed 数；
  本节只声明预算冻结的**规则**，不声明预算数字。

### 11. 本轮 TASK_007-P0/P1 边界 (contract only)

- ✅ 冻结 12-dim `ThreeDroneCandidate` 合同 (§2)；
- ✅ 明确"三架 heading / speed 独立" (§1 / §2 / §3)；
- ✅ 确认 Q2 evaluator u0 复用路径 (§4)；
- ✅ 冻结 EXCEPTION PROPAGATION MODEL + 两阶段调用会计 (§4, N1)；
- ✅ 冻结 interval-union 目标 + Q3/Q4 union 措辞统一 (§5)；
- ✅ 冻结 `ThreeDroneEvaluation` 输出结构 (含 attempted/completed) + Q4 FORMAL
  EVALUATION IDENTITY SCHEMA 8 category + `q4_evaluator_code_sha` required (§5, §6, N2)；
- ✅ 冻结 canonical JSON 规则 (§7)；
- ✅ 冻结 result2.xlsx 写盘合同 (rows 2-4 / row 5 保留 / B6 / A1:J6) (§8)；
- ✅ 占位候选来源 (具体 seed 数字 NOT frozen) (§9)；
- ✅ 占位未来预算规则 (P2B / P3 数值 NOT frozen) (§10)；
- ✅ 冻结 TASK_007 阶段映射 P0P1 / P2A / P2B / P3 / P4 / P5 (§0)；
- ✅ 冻结 P2A / P2B subgates (§16, N5)；
- ✅ 冻结 P3 = work/q4_search/ + P4 = work/q4_candidate_closure/ 目录所有权
  + 各自 checkpoint + P4 input_manifest 绑定 P3 SHAs (§15, N4)；
- ✅ 冻结单 PR 规则 PR #14 整个 TASK_007 期间 Draft 不合并 (§13)；
- ✅ 冻结 v1 historical overwrite record + v2 canonical 治理 (§14, N3)；
- ✅ 修改 `.gitignore` 覆盖 `work/task_contracts/`, `work/q3_*/`, `work/q4_*/`,
  `work/p3_closeout/` (governance fix, P0/P1 阶段完成);
- ✅ read-only 验证官方 result2.xlsx 模板 SHA + 结构，存到
  `work/q4_foundation/result2_template_readonly_check.json` (FACTS.md §13.2 状态
  已在本文件中刷新为 "CORRECTED in FIX commit 6f52c39");
- ✅ 写入 `work/task_contracts/TASK_007-P0P1-v1.json` 不可变 snapshot (历史覆盖记录);
- ✅ 写入 `work/task_contracts/TASK_007-P0P1-v2.json` canonical corrected contract;
- ✅ 修正 `problem/FACTS.md §13.2` (官方要求 vs 模板格式行分离, 写入策略明确)。

不得在本轮：

- ❌ 创建 `src/q4_three_drones.py` 或任何 Q4 实现文件；
- ❌ 创建 `tests/test_q4.py`；
- ❌ 写 Q4 evaluator / search / pilot CLI；
- ❌ 运行 Q4 任何 evaluator / 任何搜索 / 任何 pilot / 任何 runtime calibration；
- ❌ 创建 `outputs/submission/result2.xlsx`；
- ❌ 修改 Q1 / Q2 / q3_three_bombs / q3_search 任何 foundation 文件；
- ❌ 修改 result1.xlsx 或其 evidence；
- ❌ 修改官方模板 ZIP 或解压模板到仓库；
- ❌ 创建 CI / 修改 workflow；
- ❌ 安装任何依赖 (scipy / numpy / pandas 等)；
- ❌ 启动 Audit CC full rerun / Hermes (MAIN 决定)；
- ❌ Mark Ready / merge；
- ❌ 启动 TASK_008；
- ❌ 启动 TASK_007-P2A / P2B / P3 / P4 / P5；
- ❌ 重新修改 `.gitignore` (本轮 boundary);
- ❌ 重新修改 `problem/FACTS.md` (本轮 boundary, Audit 已通过);
- ❌ Amend 任何之前的 commit (PLAN / FIX);
- ❌ Squash commits;
- ❌ Force push;
- ❌ 声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum / 官方答案
  / Q4 IMPLEMENTED / Q4 SEARCHED / RESULT2.XLSX GENERATED / Q4 EVALUATOR VALIDATED
  / P2A STARTED / P2B STARTED / P3 STARTED / P4 STARTED / P5 STARTED /
  seeds frozen / budget frozen / pilot budget frozen。

### 12. 当前状态 (本轮 P0/P1)

- 本轮输出上限：`CONTRACT_ONLY`。
- `src/q4_three_drones.py` **不存在**；
- `tests/test_q4.py` **不存在**；
- `outputs/submission/result2.xlsx` **不存在**；
- `work/q4_pilot/` **不存在**；
- `work/q4_search/` **不存在**；
- `work/q4_candidate_closure/` **不存在**；
- `work/q4_result2/` **不存在**；
- `work/q4_foundation/` 仅含 `result2_template_readonly_check.json` (read-only inspection)；
- 等级: **TASK_007 Q4 FOUNDATION CONTRACT — CONTRACT_ONLY**。
- 不进入 TASK_007-P2A (Q4 evaluator + 单元测试) /
  P2B (tiny pilot + runtime calibration) / P3 (Q4 formal bounded search) /
  P4 (candidate closure) / P5 (result2.xlsx 写盘)，
  必须 MAIN 显式立项后才能进入。
- seeds 数量 / 具体 seed 列表 / wall-clock / evaluation 上限 / pilot self-budget
  **均 NOT frozen**。

### 13. 单 PR 规则 (TASK_007 整个构建期, v2 冻结)

> **冻结唯一规则**: PR #14 remains Draft and unmerged throughout TASK_007 construction.

- 整个 TASK_007 (P0/P1 → P2A → P2B → P3 → P4 → P5) 使用同一 branch:
  `task/TASK_007-q4-result2`；
- 整个 TASK_007 使用同一 Draft PR: **#14**；
- 原因: CLAUDE.md 规定同一任务只维护一个 Draft PR；
- P0/P1 / P2A / P2B / P3 / P4 / P5 通过普通 commit 累积到 PR #14;
- 只有 TASK_007-P5 完成、result2.xlsx 验证、Final Audit、Hermes 和 MAIN final gate
  **全部**通过后, 才申请用户 Ready / merge 授权;
- **不**采用任何双轨措辞, 不得写 (此处按字面禁止项的近义描述):
  - "P0/P1 PR 合并后才允许 P2 启动"
  - "PR 合并或 MAIN 显式放行"
  - "PR 合并 OR MAIN 显式授权"
- 任何此类旧措辞已删除; 仅保留本节唯一规则。

### 14. v1 historical + v2 canonical 治理 (N3, 治理说明)

历史事件（不可变事实）：

- 原 TASK_007-P0/P1 v1 contract snapshot 在第一次 FIX commit
  (`6f52c39c14b957d466f39248fcbfa8fae923a234`) 中被覆盖；
- v1 文件 (`work/task_contracts/TASK_007-P0P1-v1.json`) 从未被 Git tracked；
- v1 原 bytes 不可独立恢复；不得猜测、不得从当前 v1 反推、不得用 reflog 声称恢复、
  不得删除当前 v1 隐瞒覆盖事件；
- v1 当前内容已带 `snapshot_status = "HISTORICAL_OVERWRITE_RECORDED"` 标记。

v2 canonical (后续 P2A / P2B / P3 / P4 / P5 唯一引用)：

- `work/task_contracts/TASK_007-P0P1-v2.json`
- `contract_version = 2`
- `status = "CANONICAL_CORRECTED_CONTRACT"`
- `supersedes = "TASK_007-P0P1-v1.json"`
- `audit_basis_head = "6f52c39c14b957d466f39248fcbfa8fae923a234"`
- `created_by_fix_round = "CONSOLIDATED_AUDIT_FIX"`
- `next_gate = "AUDIT_DELTA_RECHECK"`

合同修订规则 (v2 之后)：

- 每次合同修订**必须**创建 `vN+1` 新文件，**不得**覆盖 `vN`；
- 未来 P2A / P2B / P3 / P4 / P5 context 全部引用最新 `vN`；
- 完整本机 JSON 内容**不**塞入 tracked 文档；tracked 文档只做治理说明。

### 15. P3 / P4 artifact 所有权 (N4, v2 冻结)

互不重叠的目录：

#### P2 (含 P2A + P2B)

`work/q4_pilot/` 仅存：

- P2 pilot context；
- pilot checkpoint；
- runtime calibration；
- benchmark summary；
- P3 budget recommendation。

#### P3 (formal bounded search)

`work/q4_search/` 仅存：

- `formal_search_config.json`
- `checkpoint.json`
- heartbeat / stop evidence；
- seed summaries；
- `candidates_evaluated.jsonl` 或同等结构；
- `finalists.json`
- `formal_search_summary.json`

P3 **不得**写 `work/q4_candidate_closure/`。

P3 完成条件：
- 所有受批准 seed 在预算内结束；
- formal checkpoint 完整；
- finalists 列表冻结；
- `formal_search_summary` 绑定 P3 identity;
- 不执行 closure refinement。

#### P4 (candidate closure)

`work/q4_candidate_closure/` 仅存：

- `closure_context.json`
- `checkpoint.json` ← P4 own; P4 **不**覆盖 / 续写 `work/q4_search/checkpoint.json`
- `input_manifest.json` ← 必须绑定 P3 SHAs
- refined candidate evaluations；
- cross-seed comparison；
- `final_candidate.json`
- `candidate_closure_summary.json`

P4 `input_manifest.json` 必须绑定：

- `p3_formal_search_summary_sha256`
- `p3_finalists_sha256`
- `p3_config_sha256`
- `p3_code_identity_sha`
- `p3_ending_head`
- `p4_starting_head`

P4 完成条件：
- final candidate 唯一；
- closure budget 结束；
- required profiles 完成；
- final_candidate identity 冻结；
- 可供 P5 reconstruction 使用。

#### P5 (result2.xlsx 写盘)

`work/q4_result2/` + `outputs/submission/result2.xlsx`。

P5 input 必须绑定：
- `p4_candidate_closure_summary_sha256`
- `p4_final_candidate_sha256`
- `p4_ending_head`
- `p5_starting_head`

P5 **不**修改 P3 / P4 checkpoint。

### 16. P2A / P2B subgates (N5, v2 冻结)

P2 仍是一个 phase, 但拆成两个内部 gate。

#### P2A — implementation and test

- 实现 Q4 evaluator (`src/q4_three_drones.py`)；
- 创建 Q4 单元测试 (`tests/test_q4.py`)；
- 静态和受控单元测试；
- 可使用注入 evaluator / stub / fixture；
- **不**运行真实昂贵 Q4 candidate；
- **P2A 真实 Q4 evaluator calls = 0**；
- P2A 完成后由 MAIN 审查代码和测试。

#### P2B — tiny bounded pilot and runtime calibration

在任何真实 Q4 evaluator 调用前, **必须**先冻结 P2B pilot self-budget：

- `pilot_seed`
- `pilot_sample_level`
- `pilot_scan_step`
- `max_q4_evaluations`
- `max_single_bomb_calls` = `3 × max_q4_evaluations` (合同约束, 不得更改比例)
- `max_wall_clock_seconds`
- `checkpoint_path`
- `heartbeat_interval`
- `stop_classification`
- `resume_identity`
- 预先明确的 system-error attempted-call accounting 规则

**P2B pilot self-budget 现在 NOT FROZEN**; 只有 MAIN 在 P2A 后显式授权并给出具体数字,
才能开始 P2B。

P2B 输出 (`work/q4_pilot/`)：

- task-specific runtime measurement；
- valid / zero / system_error counts；
- per-Q4 evaluation timing；
- per-single-call timing；
- recommended P3 formal budget。

P2B 结束后, MAIN 再冻结 P3 formal search budget。

**P2B pilot budget 与 P3 formal budget 是两套不同预算集合, 不得混用**。

### 17. 局限

- 12 维决策变量比 Q3 8 维大 50%, 候选空间更大；本轮未做任何 pilot / 单 seed /
  multi-seed 实测, 因此 TASK_007-P2B 预算 / wall-clock / seed 数均**未冻结**,
  留到 P2B 启动前由 MAIN 基于 P2A 实测 + 12 维搜索工程经验重新冻结。
- 候选源 (§9) 是占位；具体 seed 数字 NOT frozen 在 P0/P1；正式 P2B 启动前 MAIN 必须
  重新冻结：
  - seeds 数量；
  - 具体 seed 列表；
  - 每 seed evaluation cap；
  - 每 seed wall-clock cap；
  - finalist / refinement 子阶段预算分配 (P3 → P4 → P5 各阶段预算分配)。
- 本合同不包含 result2.xlsx 之外的额外 Excel 副作用 (如不在 result2 写入 union
  total 时长, 不在 result1 跨写, 不修改 result1.xlsx 任何 evidence)。
- 不引入 Q4-specific 的新第三套遮蔽几何；Q4 复用 Q1 完整圆柱 §3-§6 几何。
- 不引入跨架协同 / 通信延迟 / 视线接力等第三套模型；
  本合同仅按 FACTS.md §5 文本冻结 3 架独立单弹协同 (interval union)。
- 等级仅 CONTRACT_ONLY；不冒充 Q4 IMPLEMENTED / Q4 SEARCHED / RESULT2 GENERATED /
  P2A / P2B / P3 / P4 / P5 STARTED。
- v1 historical content 不可独立恢复 (见 §14)；后续 P2A / P2B / P3 / P4 / P5 必须
  引用 v2 canonical contract。
