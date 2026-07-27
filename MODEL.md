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
   - 投放瞬间相对无人机共速（**[假设]**，待 Q1 显式声明）；
   - 投放后做抛体运动，重力 g = 9.8 m/s² 沿 −z（**[假设]**）；
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

> 已在 `src/q2_single_bomb.py` 实现, 通过 `tests/test_q2_single_bomb.py` 85 个本地单元测试
> (Section 五 ~ 十七 + 3 个 P1 返工加固类 U2/R2/S2 + G2/J2/K2/N2/P/Q 共 14 组) 验证.
> 本节固定 TASK_004 Search 启动前必须确认的合同.
> 当前层级为 FOUNDATION (基础评估器), 尚未启动正式 Q2 搜索.
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
- 现有 75 个 Q1 cylinder 单元测试 + 42 个 Q1 baseline 测试保持全过
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

程序错误 (空可见集 / 类型错误 / 几何合同错误) 由 batch 统计为 `system_error`,
**不**算入 invalid/pruned/zero/objective; CLI 退出码: 0 = 无 system_error,
1 = ≥1 个 system_error, 2 = 参数错误.

地面边界: `EPS_GROUND = 1e-9 m` (1e-10 量级浮点舍入吸收, 不允许物理地下起爆);
3 区分类: z < -EPS → invalid, -EPS ≤ z < 0 → 归一化为 0, z ≥ 0 → 合法.

性能校准 (3 候选 × 3 profile, warm-up=1, repeat=3, samples 复用):
- Q1 锚点:  coarse 0.196 s / medium 1.85 s / fine 15.05 s
- Q1 邻域:  coarse 0.196 s / medium 1.82 s / fine 14.86 s
- 零目标:  coarse 0.182 s / medium 1.76 s / fine 13.63 s
(以上为 median; Search 预算未冻结, 仅为本轮实测.)

默认 smoke: `candidate_source = prevalidated_nonpruned` (生成阶段已过滤非法,
故 invalid/pruned 计数恒为 0; 想覆盖这些状态需用 `run_smoke_on_candidates`
或 mixed-batch 测试).

仍为 NOT AN OPTIMIZATION RESULT; 仍未启动 Search; 仍未生成 result1.xlsx.

### 8. 本轮唯一入口与建议下一步

- 主程序: `python -m src.q2_single_bomb --smoke-count 100 --seed 2025 --profile coarse`
- 单元测试: `python -m unittest tests.test_q2_single_bomb -v`
- 全部测试: `python -m unittest discover -s tests -p "test_*.py" -v`
- 进入 **TASK_004 Search** 的条件:
  1. Foundation PR 审核并合并
  2. CI 持续 PASS
  3. 本地 Foundation smoke 性能已记入下一阶段预算
  4. 搜索算法 / 收敛标准 / 性能预算重新冻结
