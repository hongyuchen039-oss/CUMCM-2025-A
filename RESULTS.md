# 当前结果

## 关键结果

### 方案 A — Q1 点目标基线 (BASELINE / EXPERIMENTAL)
- 有效遮蔽总时长: **1.435082 s**
- 遮蔽区间: **(8.013006, 9.448088) s** (均在 [5.1, 25.1] 云团有效窗口内)
- 投放点 R: **(17620.000000, 0, 1800.000000) m** (由 Q1 给定输入推导)
- 起爆点 D: **(17188.000000, 0, 1736.496000) m**
  (在 g=9.8 m/s² 与共速假设下推导, D.z = 1800 − 0.5·9.8·3.6²)
- M1 速度: **(-298.511157, 0, -29.851116) m/s**, **|v| = 300 m/s**
- M1 到达假目标理论时刻: **66.999 s**

### 方案 B — 完整圆柱严格遮蔽 (FULL-CYLINDER CANDIDATE / EXPERIMENTAL, 本轮 FIX 后重跑, 等待审核冻结)
- 有效遮蔽总时长 (fine 采样): **1.392384 s**
- 遮蔽区间 (fine): **(8.055704, 9.448088) s**
- 最大覆盖率 ρ_max = **1.000**
- ρ=1 平台区间 (DIAG_STEP=0.01 s 诊断网格): 约为 **(8.06, 9.44) s**, 网格区间跨度 **1.380 s**
- SVG_STEP=0.05 s 绘图网格首次采到 ρ=1: t ≈ **8.100 s** (仅用于 SVG 绘图, 不作为平台精确起点)
- 最大严格裕量 margin_max (0.001 s 局部网格估计): **5.282478 m** @ t = **9.418317 s**
  (SVG 网格峰值附近 ±0.05 s 局部估计, 非解析极值)

### Q1 点目标近似误差量化
- ΔT (B − A) = **−0.042698 s** (圆柱更短, 因严格约束)
- 相对差异 = **−2.975%** (|ΔT| / 点目标时长)
- 区间上界 9.448088 s 在两方案中一致 (云团下沉后期几何对称)
- 区间下界 8.055704 s (圆柱) > 8.013006 s (点目标), 因几何中心 P=(0,200,5)
  比圆柱表面更容易被遮挡

> 等级: **BASELINE / EXPERIMENTAL** (方案 A), **FULL-CYLINDER CANDIDATE / EXPERIMENTAL** (方案 B).
> 两个方案都不得冒充 VERIFIED / FINAL.

## 模型与一致性

| 检验项 | 期望 | 实际 | 误差 |
|---|---|---|---|
| FY1 投放点 R | (17620, 0, 1800) | (17620.000000, 0, 1800.000000) | ≤ 1e-6 m ✓ |
| 烟幕弹起爆点 D | (17188, 0, 1736.496) | (17188.000000, 0, 1736.496000) | ≤ 1e-6 m ✓ |
| M1 速度大小 | 300 m/s | 300.000000 m/s | ≤ 1e-9 ✓ |
| M1 速度方向 | 沿 (O − M0) 单位方向 | (-298.51, 0, -29.85) | 单位化后一致 ✓ |
| 三档扫描 (整倍数, 点目标) | max \|Δt\| 小 | (8.01300605, 9.44808815) | 区间端点 6.48e-9 s ✓ |
| 三档扫描 (非整倍数, 点目标) | max \|Δt\| 小 | (8.01300605, 9.44808815) | max \|Δt\| = 4.12e-9 s ✓ |
| 区间端点 d-R ≤ 5e-6 | d(t_start) ≈ d(t_end) ≈ 10 | (8.013, 9.448) max \|f(b)\| = 1.03e-6 | ✓ |
| 圆柱采样总权重 | 2πR_T H_T + 2πR_T² | 747.6990515543707 | ≤ 1e-8 ✓ |
| 圆柱法向量 | \|n\| = 1 | 1.0 ± 1e-12 | ✓ |
| 单元中心在内部 | z ∈ (0, H_T) | 所有侧面样本 z 严格在内部 | ✓ |
| NaN/Inf 输入异常 | ValueError | 全部 raise ValueError | ✓ |
| 圆柱时间扫描三档 | max \|Δt\| 小 | 0.02/0.01/0.005 → 区间完全一致 | max \|Δt\| = 0 ✓ |
| 圆柱空间三档收敛 | 总时长单调 | 1.3946 / 1.3931 / 1.3924 | medium vs fine 差 7.5e-4 s ✓ |
| 圆柱区间端点 \|f\| ≤ 1e-4 | 小 | max \|f(b)\| < 1e-4 | ✓ |
| 方案 B ≤ 方案 A (总时长) | ΔT ≤ 0 | ΔT = −0.0427 | ✓ |

## 收敛数据 (实际输出, 非声称值)

### 方案 A 点目标 — 整倍数扫描步长
| scan_step | interval | 总时长 (s) | max \|f(b)\| |
|---|---|---|---|
| 0.0200 | (8.013006052970884, 9.448088154792789) | 1.435082 | 1.03e-6 |
| 0.0100 | (8.013006052970884, 9.448088154792789) | 1.435082 | 1.03e-6 |
| 0.0050 | (8.013006052970884, 9.448088154792789) | 1.435082 | 1.03e-6 |

### 方案 A 点目标 — 非整倍数扫描步长
| scan_step | interval | 总时长 (s) | max \|f(b)\| |
|---|---|---|---|
| 0.0190 | (8.013006056181501, 9.448088157595844) | 1.435082 | 2.92e-7 |
| 0.0110 | (8.013006055872806, 9.448088157511203) | 1.435082 | 3.15e-7 |
| 0.0067 | (8.013006059451143, 9.448088157153016) | 1.435082 | 4.09e-7 |

### 方案 A 6 档配对最大差异
- max \|Δ起点\| = **6.48e-9 s**
- max \|Δ终点\| = **2.80e-9 s**
- max \|Δ总时长\| = **4.12e-9 s**

### 方案 B 完整圆柱 — 空间三档收敛 (时间步长 0.01 s)
| grade | samples | interval | 总时长 (s) | max_ρ | max_margin (m) |
|---|---|---|---|---|---|
| coarse (768) | 768 | (8.053481907844546, 9.448088154792789) | 1.394606 | 1.0000 | 5.2664 |
| medium (3072) | 3072 | (8.054957528114318, 9.448088154792789) | 1.393131 | 1.0000 | 5.2664 |
| fine (12288) | 12288 | (8.055704169273376, 9.448088154792789) | 1.392384 | 1.0000 | 5.2664 |

- coarse vs medium 总时长差 = 1.475e-3 s
- medium vs fine 总时长差 = 7.466e-4 s
- medium vs fine 区间数: 1=1 ✓
- medium vs fine 起终点差: 起点 7.466e-4 s, 终点 0 ✓
- 端点 max \|f_cylinder(b)\| medium = fine = 1.033e-6 (≤ 1e-4 ✓)
- max_coverage 差 (medium vs fine) = 1.574e-13
- max_margin 差 (medium vs fine, 0.01 s 诊断网格) = 0
- **check_spatial_convergence: PASS**

### 方案 B 完整圆柱 — 时间三档收敛 (medium 空间采样)
| scan_step | interval | 总时长 (s) | max \|f(b)\| |
|---|---|---|---|
| 0.0200 | (8.054957528114318, 9.448088154792789) | 1.393131 | 1.03e-6 |
| 0.0100 | (8.054957528114318, 9.448088154792789) | 1.393131 | 1.03e-6 |
| 0.0050 | (8.054957528114318, 9.448088154792789) | 1.393131 | 1.03e-6 |

- max \|Δt\| = 0 (三档完全一致, 因函数光滑 + 区间算法找到同一根)
- 区间端点 max \|f_cylinder(b)\| ≤ 1e-4 ✓
- **check_temporal_convergence: PASS**

## 单元测试

### 方案 A (tests/test_q1_baseline.py)
- **42 个测试全过** (10 组 A-J)

| 组 | 测试数 | 内容 |
|---|---|---|
| A | 3 | Q1 输入推算 R, D, D.z 解析式 |
| B | 3 | M1 速度方向与大小, 防 (-300,0,0) 错值 |
| C | 3 | 二分求根 (含 cos, 端点同号异常) |
| D | 5 | 闭线段距离 5 个退化/正常情形 |
| E | 3 | 区间端点 \|f\| ≤ 5e-6 + 进入/离开状态 |
| F | 5 | NaN/Inf 输入 ValueError, 早投放异常 |
| G | 5 | 时间窗外判定 |
| H | 5 | 整倍数步长 / 非整倍数步长 / 六档两两比较 / 每档端点残差 / compute_q1 返回字段检查 |
| I | 8 | 边界函数注入 (全窗口/全无效/两段/非格点/截断/云团60m/P点/非法扫描步长) |
| J | 2 | 云团按 3 m/s 下沉 / P 点几何一致性 |

### 方案 B (tests/test_q1_cylinder.py)
- **75 个测试全过** (12 组 A-L, 含 2 个收敛失败路径测试)

| 组 | 测试数 | 内容 |
|---|---|---|
| A | 10 | 圆柱采样几何 (单元数/权重/法向量/单元中心/参数校验) |
| B | 10 | 可见性 (远距离顶面/底面/半侧/反向观测 + eps 边界 ±) |
| C | 5 | 遮挡 (云内/云外/radius=0/边界/无效 radius) |
| D | 6 | 覆盖率 (单位区间/strict =1/无权无可见/权 1+9 加权/两都遮挡/两都不遮挡) |
| E | 6 | 严格裕量 (margin = R − max_d, strict ⇔ margin ≥ 0, worst 位置一致/窗内空可见异常/窗外无异常) |
| F | 8 | 区间算法注入 (全窗口/零窗口/非格点/两段/立即开始/截断到结束/t_arrival/非法步长) |
| G | 5 | Q1 回归 (基线不变/上界一致/ΔT ≤ 0/ΔT 公式/真实输出) |
| H | 9 | 空间收敛 (check_passed_true/区间数一致/起点差/终点差/总时长差/coverage 差/margin 差/残差/人为破坏可失败) |
| I | 6 | 时间收敛 (check_passed_true/区间数一致/起终点总时长/残差/多区间合成/人为破坏可失败) |
| J | 4 | SVG 解析 (合法 XML/有标题/有等级标签/有时间面板块) |
| K | 3 | margin 局部网格估计 + coverage 平台 + 时间序列有限性 |
| L | 4 | 几何 API 输入校验 (非有限 m/c/radius 抛异常 + 轨迹回调注入) |

`python -m unittest tests.test_q1_baseline -v` → 42 / 42 ok.
`python -m unittest tests.test_q1_cylinder -v` → 75 / 75 ok.

## 图像产物

### 方案 A
- `outputs/q1/q1_baseline_plot.svg` (8208 字节, 标准 SVG, 4 轨迹 + 关键点 + 椭圆云团 + 遮蔽 + 图例)
- x-z 投影: 包含 M1 / FY1 / 烟幕弹 / 云团下沉 / 真目标 P (0,200,5) / 假目标 O (0,0,0)

### 方案 B
- `outputs/q1/q1_cylinder_comparison.svg` (`os.path.getsize` 报告 78857 字节 ≈ 77 KB, 标准 SVG)
- 上半: x-z 投影 + 圆柱严格遮蔽段 (红色虚线)
- 下半: 时间对照面板 (点目标 vs 圆柱严格 + 覆盖率曲线 + 裕量曲线)
- 图例完整 (8 项)
- SVG 标题: "Q1 Point vs Full-Cylinder Comparison"
- SVG 红色副标题: "[FULL-CYLINDER CANDIDATE / EXPERIMENTAL] not a final answer"

## 官方题目提取
- PDF 读取：成功（1 页题面）
- PDF 事实逐项核对：完成
- 三个结果模板字段逐项核验：完成（result1/2/3.xlsx 表头、方向角附注、数据行数）
- 模板未修改、未提交
- 模板 ZIP 在 `题目及模板/` 本机保留（gitignore）

## 未明确事项
- 数量已重计（见 `problem/FACTS.md §15`），不再沿用失效的 9 项。
- 完整圆柱仍是单元中心法 (12288 样本 fine), 不解析化 (MODEL.md §11 局限)
- 重力 g = 9.8 与 9.80665 标准值差异未量化
- 风场、云团水平漂移、起爆时序误差均按 §15 假设忽略
- 完整圆柱采样等级 (coarse/medium/fine) 与覆盖率阈值已通过 473/473 full regression 验证

## Q2 Formal Search (TASK_005 / HISTORICAL FORMAL-SEARCH CANDIDATE / PRE-AUDIT)

> **SUPERSEDED — CURRENT CANONICAL 见 PROMOTION SUMMARY §B**
> 本节记录 TASK_005 formal profile 在独立 Audit 前的运行结果。
> 当前 canonical Q2 result 已由 bounded refinement + Audit 结论 B
> 晋升为 4.260970878601073 s；本节记录的 2.48275905609131 s 候选
> 已降级为 HISTORICAL FORMAL-SEARCH CANDIDATE。
> 等级（本节历史阶段）: FORMAL BEST-KNOWN Q2 CANDIDATE /
> NOT A PROVEN GLOBAL OPTIMUM。
> 独立审查（Audit CC / Hermes）签字后已晋升为 canonical；当前阶段
> TASK_005 DOC-ONLY P2 CLOSED — WAITING FOR HERMES / USER MERGE
> DECISION。

> **PRE-FIX EVIDENCE INVALIDATED (TASK_005 P1 closure)**
>
> 本节初版（`canonical_result_sha256 = fa279e3fcc6…`、4 方向扰动、
> raw per-seed artifacts 留在 tracked tree 等）由 P1 前的 WORKING
> 提交固化。其执行路径混用了 `require_clean_worktree=False` /
> `enforce_fixed_production_result=False` / `cli_overrides=`，未把
> actual stage counts / unique eval ids / formal run identity 绑定
> formal config SHA；扰动只覆盖 4 条多变量对角线而非 16 项 one-var；
> pilot best-known 注入不 fail-closed；finalist 不 fail-closed。
> 本节数字仅作历史背景，不构成正式冻结结论。
> 正式冻结结果见 §5 P1 RERUN 列（canonical_result_sha256 =
> 2efcc91486d4ce9d22bfdedc0a4d57c36857d506126bca40c1a31695a96d1b3a,
> clean-HEAD 467314d, 16 项扰动完成, fail-closed 全部启用）。

### 1. Declaration

- `declaration = "FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM"`
- `best_known_disclaimer = "NOT A PROVEN GLOBAL OPTIMUM"`
- `final_best_status = "OK_FINE_RESULT"`（P1 rerun 后确认, 3 seeds × 1000 evals 全部产出 valid OK_FINE_RESULT）

### 2. 搜索规模 (per-seed, formal config 强制)

| 阶段 | 候选数 | 说明 |
|---|---|---|
| global_coarse | 595 | 1 anchor + 594 deterministic uniform pseudorandom |
| global_medium | 49 | coarse top-k 候选在该采样级重评 |
| local_coarse | 294 | pipeline-saturating: `local_coarse = local_per_top × |medium_confirmed| = 6 × 49` |
| local_medium | 49 | medium sampling 级重评 |
| fine | 13 | 决赛级细评估 (scan_step=0.005) |
| **合计** | **1000** | 总预算 / 每 seed |

- pipeline-saturating 约束严格保证: `local_coarse = 6 × global_medium`.
- **actual_stage_counts** 在 P1 证据门下从 `row.source_stage` 重建,
  严格等于上述值, 不从 config 复制.

### 3. 多 seed 调度

- seeds = `[2025, 2026, 2027]`, formal config 强制断言.
- 每 seed 独立 run_identity_sha256 / 独立 canonical_result_sha256.
- 任一 seed gate 不通过 → 全部 BLOCKED.

### 4. Finalist Pool (跨 seed 合并 + pilot best-known 显式注入)

- 每 seed fine top-5 → 共 15 候选
- `cross_seed_dedup_candidates` 去重 (tolerance 1e-6 各维)
- pilot best-known 显式注入 (P1-4):
  - 优先级 1: `work/q2_pilot_calib/pilot_result.json`
  - 优先级 2: 确定性 seed=2025 fixed-163 clean pilot 重跑
  - 优先级 3: 失败 → BLOCKED

### 5. Formal Winner (P1 RERUN 后, clean-HEAD, canonical_result_sha256 = 2efcc91486d4ce9d22bfdedc0a4d57c36857d506126bca40c1a31695a96d1b3a)

| 变元 | PRE-FIX (INVALIDATED) | P1 RERUN (本轮冻结) |
|---|---|---|
| heading_rad (θ) | 3.121767217560497 | **3.121767217560497** |
| speed_mps (v) | 115.43351397802584 | **115.43351397802584** |
| release_time_s | 1.7672692031529031 | **1.7672692031529031** |
| delay_s | 3.889202402720746 | **3.889202402720746** |
| total_duration_s | 2.48275905609131 s | **2.48275905609131 s** |
| interval | (6.0947…, 8.5774…) | **(6.094727521515435, 8.577486577606745) s** |
| source_stage | formal_finalist_v2 | **formal_finalist_v2** |
| evaluation_id | — | **3e1fa381e092dfdf3c72e10da7edeede** |
| physical_candidate_sha256 | — | **485582b5dc4f8d9855e5894fcd5372e5e72375206425b756871bfd5ee8763c59** |
| scan_step_s (winner 评测) | 0.005 | **0.005** |
| wall_clock_s (winner 评测) | — | **29.33535759994993** |
| pilot_best_source | — | **pilot_artifact_local** |
| pilot_best_canonical_result_sha256 | — | **230fa220d65161f2979f16ac197a5347d2f7f5ea18b5d69cc484a9750971646a** |
| pilot_best_run_identity_sha256 | — | **89593a2318419d663ab6e47cfca9e88ec8b600d675c3d118ca8a8b956ddb61ca** |

> PRE-FIX 列仅作历史背景, 不得作为正式冻结结论.
> P1 RERUN 列为本轮 clean-HEAD rerun 后的正式冻结 (canonical_result_sha256
> 与 PRE-FIX 不同: `fa279e3fcc6…` → `2efcc91486d4…`), 16 项扰动显示
> `local_perturbation_passed=False` (5/16 改善), 故本候选为
> best-known 但需进一步局部搜索; 不冒充全局最优 / VERIFIED / FINAL.
> 跨 seed 一致性: seed=2026 与 seed=2027 都各自跑出 fine winner
> `total_duration_s = 1.3923839855194124` 对应 (θ=π, v=120, r=1.5,
> d=3.6), 但 pilot 注入的 θ=3.121767217560497 候选在 seed=2025 fine
> 阶段重评后 total_duration_s=2.48275905609131, 经过 13 个 fine 候选
> 比较胜出 (finalist pool 共 13 distinct candidates after dedup).

### 6. 时间步长稳定性 (3 档, P1 RERUN 后, clean-HEAD)

| scan_step | total_duration_s | status | valid | n_intervals | evaluation_id |
|---|---|---|---|---|---|
| 0.0200 | 2.48275905609131 | ok | True | 1 | ad4e701cbff6404ec01f76ec7955bdaf |
| 0.0100 | 2.48275905609131 | ok | True | 1 | ad4e701cbff6404ec01f76ec7955bdaf |
| 0.0050 | 2.48275905609131 | ok | True | 1 | ad4e701cbff6404ec01f76ec7955bdaf |

- `delta_0p01_vs_0p005_s = 0.000000`
- `stability_ok = True`（P1 rerun 后重新测量, 仍完全一致, 三档 evaluation_id 同一）

### 7. 16 项 one-variable-at-a-time 扰动 (P1 RERUN 后, 全部执行)

| Pert | 变量 | sign | scale | perturbed candidate (4-tuple) | total_duration_s | improves_winner |
|---|---|---|---|---|---|---|
| 00 | heading_rad | +1 | large (0.05) | (3.1717672175604967, 115.43…, 1.767…, 3.889…) | 0.0 | False |
| 01 | heading_rad | -1 | large (0.05) | (3.071767217560497, …) | 0.0 | False |
| 02 | heading_rad | +1 | small (0.02) | (3.141767217560497, …) | 2.273793992996219 | False |
| 03 | heading_rad | -1 | small (0.02) | (3.101767217560497, …) | 0.0 | False |
| 04 | speed_mps | +1 | large (2.0) | (3.121…, 117.43351397802584, …) | 1.7018811130523686 | False |
| 05 | speed_mps | -1 | large (2.0) | (3.121…, 113.43351397802584, …) | 3.02023230552673 | **True** |
| 06 | speed_mps | +1 | small (1.0) | (3.121…, 116.43351397802584, …) | 2.136833305358884 | False |
| 07 | speed_mps | -1 | small (1.0) | (3.121…, 114.43351397802584, …) | 2.7724792957305917 | **True** |
| 08 | release_time_s | +1 | large (0.5) | (3.121…, 115.43…, 2.267269203152903, …) | 0.0 | False |
| 09 | release_time_s | -1 | large (0.5) | (3.121…, 115.43…, 1.2672692031529031, …) | 3.3120429182052593 | **True** |
| 10 | release_time_s | +1 | small (0.2) | (3.121…, 115.43…, 1.967269203152903, …) | 0.0 | False |
| 11 | release_time_s | -1 | small (0.2) | (3.121…, 115.43…, 1.5672692031529032, …) | 3.256385827064512 | **True** |
| 12 | delay_s | +1 | large (0.3) | (3.121…, 115.43…, 1.767…, 4.189202402720746) | 2.3056549978256244 | False |
| 13 | delay_s | -1 | large (0.3) | (3.121…, 115.43…, 1.767…, 3.5892024027207463) | 0.0 | False |
| 14 | delay_s | +1 | small (0.1) | (3.121…, 115.43…, 1.767…, 3.989202402720746) | 2.878093400001525 | **True** |
| 15 | delay_s | -1 | small (0.1) | (3.121…, 115.43…, 1.767…, 3.789202402720746) | 0.2748999881744396 | False |

- `n_total_perturbations = 16`
- `n_legal_perturbations = 16`
- `n_illegal_perturbations = 0`
- `n_legal_improving = 5` (perts 05, 07, 09, 11, 14)
- `any_improves = True`
- `any_physical_rejected = False`
- `local_not_yet_converged = True`
- **`local_perturbation_passed = False`**（即 winner 不是 16 项 one-var
  邻域内的局部极值；speed、release_time_s、delay_s 三个方向均存在
  改善扰动，旧候选不是局部最优，因此触发 bounded refinement；
  旧候选 2.48275905609131 s 已降级为 HISTORICAL FORMAL-SEARCH
  CANDIDATE，不再作为 canonical Q2 result）

### 7. 16 项 one-variable-at-a-time 扰动 (P1-3)

> PRE-FIX 仅覆盖 4 条多变量对角线 (大+ / 大− / 小+ / 小−), 不构成 16 项覆盖.
> P1 闭环后改为 4 变量 × 2 方向 × 2 尺度 = 16 evaluations.

| 变量 | 大尺度 | 小尺度 |
|---|---|---|
| heading_rad | ±0.05 | ±0.02 |
| speed_mps | ±2.0 | ±1.0 |
| release_time_s | ±0.5 | ±0.2 |
| delay_s | ±0.3 | ±0.1 |

- 每次仅扰动一个变量; 其余三个保持 winner 精确值.
- heading 按 2π 周期 wrap; 其他变量必须经 `formal_physical_validity`
  合法检查, 非法扰动记录 reason, 不静默 clamp.
- 任一扰动改善 winner (Δ > 1e-9) → `local_not_yet_converged=True`.
- 全部 16 个合法扰动均未改善（[HISTORICAL RULE 仅说明定义；当前旧 formal-search candidate 实测 5/16 改善，因此触发 bounded refinement 并降级为 HISTORICAL FORMAL-SEARCH CANDIDATE]）。

### 8. 物理合法性

`formal_physical_validity(winner)` fail-closed 校验:
- NaN/Inf → False
- speed_mps ∉ [70, 140] → False
- release_time_s < 0 → False
- delay_s < 0 → False
- delay_s > sqrt(2·1800/9.8) ≈ 19.18 → False
- heading_rad (wrap 后) ∉ [0, 2π) → False

### 9. 局限

- formal search 是 deterministic uniform pseudorandom + 5-stage pipeline,
  **不是**全局最优证明, **不是**解析极值, **不是**官方答案.
- 未做约束优化 / Pareto frontier / 多弹搜索 / LHS / 贝叶斯优化.
- 旧 formal-search candidate 跨 seed + 16 项扰动实测 5/16 改善（旧候选
  不是 16 项邻域局部极值），因此触发 bounded refinement 并发现更优
  候选 4.260970878601073 s；综合搜索空间仍未穷尽。
- pilot best-known 注入依赖一次确定性 fixed-163 clean pilot (worktree
  必须 clean; 否则 fallback 链失败 → BLOCKED).
- 等级: **FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM**.
  不得在 formal winner 基础上声称 Q2 全局最优 / VERIFIED / FINAL /
  官方答案, 除非独立审查签字并立项 TASK_006.

### 10. Per-seed formal run identity (P1 RERUN, clean-HEAD)

| seed | wall_clock_s | formal_run_identity_sha256 | actual_completed_count | actual_unique_evaluation_ids | final_best_status | fine_top1_total_duration_s |
|---|---|---|---|---|---|---|
| 2025 | 454.1617 | abaf88cb7c7e7665165a7a6ab4a279ee37afec5cfabc81533100f5d464ec6871 | 1000 | 1000 | OK_FINE_RESULT | 2.48275905609131 |
| 2026 | 442.4309 | 0dae4822e8607ea00e835bc1d4a5821d19404036b3cd67831a92116d713e24b2 | 1000 | 1000 | OK_FINE_RESULT | 1.3923839855194124 |
| 2027 | 461.1655 | 0c8480c896518415508ee84bef66b38f6ce70a9cc055d4fbd77cfb40de57abe3 | 1000 | 1000 | OK_FINE_RESULT | 1.3923839855194124 |

- 三个 seed 共用 `formal_config_sha256 = 988932acf0c1ca58140e1563ccdbe45303b412466ce59287c57ec5020dd75c0f`
- 三个 seed 共用 `code_identity_sha256 = a1e425821afefb9910afca15f3cbd96adebd4fb85b90c57ba9bc3c414aec8a63`
- 三个 seed 共用 `pipeline_effective_config_sha256 = 14675a3f7b263c89eb73e3061f8a5e642709c6e754ef6278176334d8b16ac09c`
- `actual_stage_counts` (每个 seed, 从 `row.source_stage` 重建):
  `{"global_coarse": 595, "global_medium": 49, "local_coarse": 294,
  "local_medium": 49, "fine": 13}`, 严格 = config 总预算 1000.
- `system_error_count` 每个 seed 都为 0.
- `n_finalists_after_dedup = 13` (15 个 fine-top-5 → 13 distinct after
  cross-seed dedup tolerance 1e-6).
- pilot best-known candidate (priority 1 命中
  `work/q2_pilot_calib/pilot_result.json`) 被注入 finalist pool:
  `(3.121767217560497, 115.43351397802584, 1.7672692031529031,
  3.889202402720746)`.

## TASK_005 LOCAL REFINEMENT (BOUNDED RUNTIME AMENDMENT, MAIN 补充修订)

> 不重跑 3 seeds / 不重跑 17 候选完整复评 / 不重跑 473 全量.
> 复评起点: 2 个 parent (formal winner + pert_09 best), 真实 duration
> 较大者作为 refinement 起点.
> 最多 32 次 refinement evaluation, 硬时间上限 2100s.

### STATUS

**`TASK_005 LOCAL REFINEMENT BUDGET EXHAUSTED — RESULT REVIEW BLOCKED`**

- 32/32 evaluation 用完, level_3 sweep=1 进行到 release_time_s -1 (eval 32)
  后 budget gate 触发, 未运行最终 stability (3 档) + 最终 16 项 one-var 扰动.
- wall-clock gate 未命中 (444.27s < 2100s 硬上限).
- 改善趋势在 level_3 中持续 (eval 28 heading-0.005 → dur=4.260971),
  但受 bounded budget 限制, 不能继续.
- 最终 refined candidate (at sweep scan_step=0.01):
  `(3.126767217560497, 116.43351397802584, 1.2672692031529031,
  3.789202402720746)`, dur=4.260971 s.
- 完整 summary: `outputs/q2/q2_refine_summary.json`
  (`status="TASK_005 LOCAL REFINEMENT BUDGET EXHAUSTED —
  RESULT REVIEW BLOCKED"`,
  `budget_gate_hit=true`, `final_verification_run=false`).

### 0. 复评结果

| 起点 | h | s | r | d | real duration @ scan_step=0.005 |
|---|---|---|---|---|---|
| A. formal winner | 3.121767217560497 | 115.43351397802584 | 1.7672692031529031 | 3.889202402720746 | 2.482759 s |
| B. pert_09 best | 3.121767217560497 | 115.43351397802584 | 1.2672692031529031 | 3.889202402720746 | **3.312043 s** |

- 实测 scan_step=0.005 (per-eval at sweep scan_step=0.01 yields same
  durations as 0.005 within tolerance): pert_09 真实 duration = 3.312043 s,
  大于 formal winner 的 2.482759 s → 起点选 B.
- 不信任文档中 pert_09 的 3.312s 舍入: 实测 confirms the rounded value
  (3.312043 ≈ 3.312).

### 1. Coordinate search 进展 (32/32 evals)

| Level | sweep | evals | best candidate (after sweep) | best duration |
|---|---|---|---|---|
| 1 | 1 | 3..10 | (3.121767, 115.4335, 1.267269, 3.789202) | 3.651923 |
| 1 | 2 | 11..18 | (3.121767, 116.4335, 1.267269, 3.789202) | 3.676963 |
| 2 | 1 | 19..26 | (3.131767, 116.4335, 1.267269, 3.789202) | 3.843550 |
| 3 | 1 | 27..32 (6/8) | (3.126767, 116.4335, 1.267269, 3.789202) | **4.260971** |

- evaluations_completed = 32 (≤ 32)
- elapsed_seconds = 444.27 (<< 2100s 硬上限)
- wall_clock_gate_hit = false
- budget_gate_hit = true (level_3 sweep=1 中 release_time_s -1 之后,
  剩 delay_s ±0.025 两项未跑)

**重要说明 (single-sweep greedy semantics)**:

每个 sweep 的 8 个候选在 sweep 开始时一次性生成, 中心是 sweep 开始时的
current_best. 当一个 later-position 候选 (e.g. delay_s -1) 改善时,
current_best 被更新为该候选 — 该候选保留了 sweep 中心在其他 3 个变量上的
值, 而非后续改进的值. 因此速度变量在 level_1 sweep 2 (eval 13 speed+1
改善) 后变为 116.4335, 而非累加为 117.4335.

这是 deterministic coordinate search 的标准行为, 不是 bug. 每个 level
都在 "sweep-start center" 的邻域内做 single-sweep greedy 改善.

### 2. 最终稳定性 (未运行)

| scan_step | total_duration_s | n_intervals |
|---|---|---|
| 0.0200 | NOT RUN | — |
| 0.0100 | NOT RUN | — |
| 0.0050 | NOT RUN | — |

- `final_verification_run = false` (budget exhausted before final block)

### 3. 最终 16 项 one-var 扰动 (未运行)

- `n_total_perturbations`: 16 (planned, not executed)
- `n_legal_perturbations`: NOT RUN
- `n_legal_improving`: NOT RUN
- `any_improves`: NOT RUN
- `local_perturbation_passed`: null
- 由于 budget exhausted 在 final verification 之前触发, P1 REMAINS
  路径未启用; 状态由 budget gate 主导.

### 4. 失败模式 (触发)

- **`TASK_005 LOCAL REFINEMENT BUDGET EXHAUSTED — RESULT REVIEW BLOCKED`**
  (32 次 evaluation 用完, level_3 sweep=1 未跑完, 仍有改善趋势
  [eval 28 heading-0.005 → 4.260971])
- 不得自动增加预算, 不得再启动第二轮 refinement.
- 不得冒充: local_perturbation_passed, stability_ok, refined_candidate
  是局部最优.

### 5. 等级 (本轮)

- 等级: **FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM**
  (formal 冻结在 REVIEW 335a1f4d; local refinement budget exhausted,
  refined candidate 不构成冻结结论, 只作为 best-known 候选记录)
- 不得在 refined candidate 基础上声称 Q2 全局最优 / VERIFIED / FINAL /
  官方答案, 除非独立审查签字并扩大 refinement 预算 (本任务禁止).

### 6. 实测 vs 文档舍入

- pert_09 在上一轮 16 项扰动文档中报告 `total_duration_s = 3.3120429182052593`,
  本轮 refinement 重新复评得 `3.312043 s` (差异 < 1e-5 s, 在 evaluator
  数值容差内). MAIN 明确要求 "不得信任文档中的 3.312 秒舍入结果而跳过复评",
  本轮实际执行了复评, 实测 confirms 文档值.

## TASK_005 CLEAN-HEAD VERIFICATION IDENTITY CLOSURE (per MAIN 修订)

> 不启动新一轮局部搜索, 不扩大到新的 coordinate sweep, 不重跑
> 3×1000 formal search, 不重跑全项目测试, 不启动 Q3, 不生成
> result*.xlsx. 仅在干净 committed HEAD 上重跑 5 次 evaluation
> (2 delay_s ±0.025 + 3 档 stability), 硬墙钟 300s. 删除 4ca43eb
> 上 "deliberately do NOT raise on HEAD mismatch" 的 fail-open
> 行为, 改为显式 identity binding.

### 0. Identity Binding (verification runner 显式验证)

| Field | Value |
|---|---|
| `verification_run_head_sha` | 4a1cbd9520d1a62eeeb4cb91180e989c91dcf036 (FIX commit, scripts/run_q2_formal_verify.py) |
| `verification_script_sha256` | 53e37211c50bdd5395c3fa22dcf9c77a71df5be975fa0803e478a2dfaea28b66 |
| `q2_search_code_identity` | 3b90accd0ca7695fe8a56e9044fac5fefe8119cfb8ba72d857327ac1e5877ac7 |
| `checkpoint_source_head_sha` | ac97a38c7564c9d7f2c0793c935eeb27bbd1fa90 (original 32-eval run authored at FIX commit) |
| `refinement_config_sha256` | 6f9cb503397996b788d0edfc6491b5a4425dd6e4a784f7ad82f8616acfd65a3d |
| `parent_candidate` | (3.121767217560497, 115.43351397802584, 1.7672692031529031, 3.889202402720746) |
| `current_best_candidate` (validated) | (3.126767217560497, 116.43351397802584, 1.2672692031529031, 3.789202402720746) |
| `evaluations_completed` (validated) | 32 |
| `evaluator_call_count` | 5/5 (strict) |
| `checkpoint_identity_validation` | True |
| tracked worktree clean at start | True |
| `evidence_refresh_head_sha` | 3948b70df0df86d4142b0c725a398ab751b35708 |

### 1. 5 Evaluator Calls (clean HEAD)

| # | Stage | Var | Sign | Candidate | Physical OK | Duration (s) | Improves |
|---|---|---|---|---|---|---|---|
| 1 | delay | delay_s | +1 | (3.126767, 116.4335, 1.267269, 3.814202) | True | 4.258950 | False |
| 2 | delay | delay_s | -1 | (3.126767, 116.4335, 1.267269, 3.764202) | True | 4.140284 | False |
| 3 | stability | (all) | n/a | best-known @ 0.0200 | True | 4.260970 | n/a |
| 4 | stability | (all) | n/a | best-known @ 0.0100 | True | 4.260970 | n/a |
| 5 | stability | (all) | n/a | best-known @ 0.0050 | True | 4.260970 | n/a |

- 两项 verification evals 均未改善 best-known (4.260971 s).
- 完整 tracked summary: `outputs/q2/q2_verify_summary.json`.

### 2. 3 档 stability (scan_step=0.02/0.01/0.005, eval=3~5 of verify)

| scan_step | total_duration_s | valid | status | n_intervals | evaluation_id |
|---|---|---|---|---|---|
| 0.0200 | 4.260970878601073 | True | ok | 1 | c19c1eaddffdb8567f4053c118c4a1ed |
| 0.0100 | 4.260970878601073 | True | ok | 1 | c19c1eaddffdb8567f4053c118c4a1ed |
| 0.0050 | 4.260970878601073 | True | ok | 1 | c19c1eaddffdb8567f4053c118c4a1ed |

- `delta_0p01_vs_0p005_s = 0.000000`
- `stability_ok = True`
- 三档 evaluation_id 同, 严格验证 best-known 在 3 档扫描下完全收敛.

### 3. 物理合法性

- `formal_physical_validity(best_known)` → ok=True, reason=""
- speed_mps=116.4335 ∈ [70, 140] ✓
- release_time_s=1.267269 ≥ 0 ✓
- delay_s=3.789202 ∈ [0, sqrt(2·1800/9.8)≈19.18] ✓
- heading_rad=3.126767 ∈ [0, 2π) ✓
- 全部 NaN/Inf 检查通过 ✓

### 4. 等级 (本轮)

**`FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE /
LOCAL CONVERGENCE NOT ESTABLISHED /
NOT A PROVEN GLOBAL OPTIMUM`**

- 335a1f4d 上 FORMAL BEST-KNOWN Q2 CANDIDATE (h=3.121767, s=115.4335,
  r=1.767269, d=3.889202, dur=2.482759) 仍是 FORMAL 冻结结论.
- 本轮 clean-head verification identity closure 仅在干净 committed
  HEAD 上重跑 5 次 evaluation (2 delay_s ±0.025 + 3 档 stability) +
  物理合法性. 未启动新 coordinate sweep, 未跑完整 16 项 one-var 扰动.
- 严格不冒充: VERIFIED / FINAL / 全局最优 / 官方答案 /
  local_perturbation_passed / local convergence established.
- best-known candidate: (3.126767, 116.4335, 1.267269, 3.789202),
  dur=4.260971 s (sweep scan_step=0.01), stability 三档完全一致.
- 独立审查 (Audit CC / Hermes) 签字后才能替换 335a1f4d 上的 FORMAL
  冻结或立项 TASK_006 (Q3 三弹串接 / result1.xlsx).

## 等级
- 方案 A 点目标基线: **BASELINE / EXPERIMENTAL**
- 方案 B 完整圆柱: **FULL-CYLINDER CANDIDATE / EXPERIMENTAL**
- Q2 canonical (TASK_005 / DOC-ONLY P2 CLOSED, audit conclusion B): **FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM**
- Q2 historical (TASK_005 / PRE-AUDIT, 467314d): **HISTORICAL FORMAL-SEARCH CANDIDATE**

---

## PROMOTION SUMMARY (DOC-ONLY P2 CLOSED)

独立 Audit 结论 B：`AUDIT PASSED WITH DOC-ONLY P2 — PROMOTE AFTER ONE SMALL DOCUMENTATION COMMIT`。
本节为本轮 DOC-ONLY commit 的核心 promotion 摘要。

### A. Historical formal-search candidate (SUPERSEDED)

| 字段 | 值 |
|---|---|
| heading_rad | 3.121767217560497 |
| speed_mps | 115.43351397802584 |
| release_time_s | 1.7672692031529031 |
| delay_s | 3.889202402720746 |
| total_duration_s | 2.48275905609131 |
| status | HISTORICAL FORMAL-SEARCH CANDIDATE |

### B. Canonical Q2 result after bounded refinement and independent audit (PROMOTED)

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

### Improvement over historical

```
duration_improvement = 4.260970878601073 - 2.48275905609131
                     ≈ 1.778211822509763 s
relative_improvement ≈ 71.6%
```

### Identity chain (audit-tracked, complete)

```
verification_run_head_sha   = 4a1cbd9520d1a62eeeb4cb91180e989c91dcf036
verification_script_sha256  = 53e37211c50bdd5395c3fa22dcf9c77a71df5be975fa0803e478a2dfaea28b66
q2_search_code_identity     = 3b90accd0ca7695fe8a56e9044fac5fefe8119cfb8ba72d857327ac1e5877ac7
checkpoint_source_head_sha  = ac97a38c7564c9d7f2c0793c935eeb27bbd1fa90
refinement_config_sha256    = 6f9cb503397996b788d0edfc6491b5a4425dd6e4a784f7ad82f8616acfd65a3d
evidence_refresh_head_sha   = 3948b70df0df86d4142b0c725a398ab751b35708
current_doc_promotion_head_sha = current PR head after DOCS promotion commit
stability_evaluation_id     = c19c1eaddffdb8567f4053c118c4a1ed
evaluator_call_count        = 5
checkpoint_identity_validation = True
stability_ok                = True
physical_validity.ok        = True
local_convergence_established = False
```

### Audit conclusion

```
AUDIT PASSED WITH DOC-ONLY P2
DOC-ONLY P2 CLOSED BY CURRENT COMMIT
```

### Strict non-claims

- 不冒充 VERIFIED GLOBAL OPTIMUM
- 不冒充 FINAL OFFICIAL ANSWER
- 不冒充 ANALYTICAL OPTIMUM
- 不冒充 LOCAL CONVERGENCE ESTABLISHED
- 不冒充 2.482759 与 4.260971 并列为两个 current winner（仅 4.260971 为 current canonical, 2.482759 仅保留为 historical formal-search 证据）

---

### TASK_005 P1 closure 测试汇总 (clean-HEAD, P1 RERUN 阶段)

- `tests.test_q2_search` 全集 190/190 PASS
  - 148 pilot-related (`Q2SearchProfileTests` 等)
  - 22 `FormalProfileTests` (formal config 隔离、run_identity 绑定、budget gate 等)
  - 20 `P1EvidenceGateTests` (clean worktree、fail-closed finalist、16 one-var 扰动、
    pilot 三级注入等)
- `tests.test_q1_baseline` 42/42 PASS
- `tests.test_q1_cylinder` 75/75 PASS
- 总计 **307/307 PASS** (本轮 P1 RERUN 阶段唯一一次全量回归)

### TASK_005 Refinement 阶段测试汇总 (clean-HEAD, ac97a38)

- `tests.test_q2_search` 全集 210/210 PASS（148 + 22 + 20 + 20 RefinementGateTests）
- 472/472 PASS（含 tests.test_q1_baseline 42 + tests.test_q1_cylinder 75）

### TASK_005 Clean-head verification 阶段

- 不重跑测试
- 5 evaluator calls
- identity / stability / physical validity PASS

### TASK_005 Independent Audit 阶段

- 不重跑测试
- 6 evaluator calls, exact match
- Audit 结论 B

## 备注
- 任何后续计算结果必须以本文件为唯一更新入口。
- 等级只能从 EXPERIMENTAL 推进到 VERIFIED，再推进到 FINAL；不能跳过。
- TASK_005 P1 RERUN 阶段 42 (方案 A) + 75 (方案 B, 含 2 个收敛失败路径) 单元测试 + 6 档扫描 + 三档空间采样 + 三档时间采样
  + coverage_plateau + margin 局部网格估计共同验证, 未伪造任何"论文对比"或"权威背书".
- TASK_005 Refinement 阶段增加 20 个 RefinementGateTests，全部 PASS。
- TASK_005 Clean-head verification 阶段不重跑测试，仅 5 evaluator calls
  (identity / stability / physical validity PASS)。
- TASK_005 Independent Audit 阶段不重跑测试，仅 6 evaluator calls exact match
  (Audit 结论 B：passed with doc-only P2)。
- 不冒充 VERIFIED GLOBAL OPTIMUM / FINAL OFFICIAL ANSWER / ANALYTICAL OPTIMUM /
  LOCAL CONVERGENCE ESTABLISHED。
- 本轮 P1 RERUN 阶段 FIX 前后可见性边界、收敛判定、几何/时序拆分均有变更, 详见 MODEL.md §12.

---

## Q3 Pilot (TASK_006-P0P1-CLOSURE / EXPERIMENTAL Q3 PILOT / RESULT1.XLSX NOT GENERATED)

> 本节为 Q3 三弹 evaluator + bounded pilot 的实测记录。
> 等级: **EXPERIMENTAL Q3 PILOT / NOT A FORMAL Q3 RESULT / RESULT1.XLSX NOT GENERATED**。
> Pilot 在 clean-HEAD `4d442a7a16127ca0166d1114656b5fe4d5546b4d` 上完成（commit `59999f9aba063e90d8428f5f783d8cc4abf10d62`）。
> **closure v2 (TASK_006-P0P1-CLOSURE)**: 不重跑 94-evaluation Pilot,
> 仅修复 (a) stage_counts 机器证据, (b) per_bomb_intervals 序列化,
> (c) budget_recommendation 算术, (d) resume identity + fail-closed,
> (e) heading_rad 原始范围。1 次 targeted reconstruction Q3 call
> 复评 best pilot candidate (coarse profile, scan_step=0.05),
> 严格 = 原始 3.788169 s。
> 独立审查签字 + MAIN 显式立项 TASK_006-P2 后才能升 `BUDGET_LIMITED_BEST_KNOWN`
> 或进一步生成 result1.xlsx。

### 0. 等级与不冒充

- 等级: `EXPERIMENTAL Q3 PILOT`
- `LOCAL CONVERGENCE NOT ESTABLISHED`
- `NOT A PROVEN GLOBAL OPTIMUM`
- `RESULT1.XLSX NOT GENERATED`
- 实际 Q3 evaluation count: **94** / cap 96
- 实际 single-bomb evaluator calls: **282** (= 94 × 3)
- 实际 wall-clock: **243.124 s** / cap 900 s
- system_error_count: **0**
- unique_q3_evaluation_ids: **86** (Stage C/D 决赛阶段重评引入 8 个重复 ID)
- 执行 HEAD: `4d442a7a16127ca0166d1114656b5fe4d5546b4d` (WORKING commit)
- base SHA: `007b93d301db73c9a73904337de34d1b4e13467e`
- closure v2 evidence HEAD: `59999f9aba063e90d8428f5f783d8cc4abf10d62` (VERIFIED commit, 保留原 94-evaluation 证据)
- closure v2 code HEAD: 待 VERIFIED commit 后填入 (本节 FIX commit)
- 1 次 targeted reconstruction Q3 call: `outputs/q3/q3_targeted_reconstruction.json`
  (q3_evaluation_id = f98d28e99c3901be135a9d2a25b93849ad19e7391a10846431ca6138f51478ff,
  total_union_duration_s = 3.788169 s, 与原始 3.7881687521934495 s 严格一致)

### 1. Pilot 阶段分配（实测, closure v2 显式 stage_counts）

| 阶段 | 候选来源 | 评估数 | profile |
|---|---|---|---|
| Stage A profile calibration (calibration) | profile_calibration (q2_canonical_seed_family) | 6 | 2 cands × coarse/medium/fine |
| Stage B deterministic coarse exploration (coarse_exploration) | deterministic_random_seed_2025 + _2026 | 80 | coarse |
| Stage C medium finalist recheck (medium_recheck) | finalist_medium_recheck | 6 | medium |
| Stage D fine spot-check (fine_spotcheck) | finalist_fine_spotcheck | 2 | fine |
| **合计 (total)** | | **94** | |

closure v2 §三: `stage_counts = {calibration: 6, coarse_exploration: 80, medium_recheck: 6, fine_spotcheck: 2, total: 94}` 由 schedule record 精确 +1, 不得从 profile count 反推。

- Stage D 的 `top-2 fine finalists` 来自 finalist_medium_recheck 排序后 top-2 (medium 评估过后的候选)
- 仅 best candidate 在 Stage A 由 profile_calibration 进入 (coarse profile dur=3.788 s, medium dur=3.784 s, fine dur=3.782 s)

### 2. Pilot 维度实测

| profile | count | median Q3 (s) | p90 Q3 (s) | median single-bomb (s) | p90 single-bomb (s) |
|---|---|---|---|---|---|
| coarse | 82 | 0.5227 | 0.5750 | 0.1742 | 0.1917 |
| medium | 8 | 5.3604 | 5.5935 | 1.7868 | 1.8645 |
| fine | 4 | 41.2872 | 41.5400 | 13.7624 | 13.8467 |

- 观察: fine 单次 Q3 evaluation 约 41 s（≈ 3 × 13.8 s），与 medium/coarse 拉开数量级差；stage B coarse 阶段 80 个候选只用 ~30 s
- 总 wall-clock 243 s (cap 900 s 充足预算), 主要消耗在 Stage A fine profile calibration (~150 s) 与 Stage D 决赛 fine spot-check (~80 s)
- 全程 0 system_error, 全部 evaluation 走完单弹 evaluator 三次调用

### 3. Best Pilot candidate

| 字段 | 值 |
|---|---|
| heading_rad | 3.129077304371891 |
| speed_mps | 116.7252038036431 |
| release_time_1_s | 1.2583116888277712 |
| delay_1_s | 3.7238593454001645 |
| release_time_2_s | 2.2592064941885104 |
| delay_2_s | 3.7378011061070766 |
| release_time_3_s | 5.205790545673161 |
| delay_3_s | 3.637016476748259 |
| per_bomb_duration_s | [3.788169, 0, 0] |
| **per_bomb_intervals** (closure v2: 恰好 3 项) | `[[[5.551472308646765, 9.339641060840215]], [], []]` |
| total_union_duration_s | 3.7881687521934495 |
| union_intervals | [(5.551472308646765, 9.339641060840215)] |
| evaluation_id | f98d28e99c3901be135a9d2a25b93849ad19e7391a10846431ca6138f51478ff |
| sample_level | coarse |
| scan_step | 0.05 |

- **重要观察**: Pilot best candidate 仅 bomb 1 贡献非零 duration (3.788 s); bomb 2 与 bomb 3 各自总时长 0
- 原因: pilot 候选生成采用 `q2_canonical_seed_family` 锚点 + 随机扰动, 三枚弹的 release_time 间隔较大 (≥1 s), 后两枚弹的 detonate 时刻常落入 t_arrival 之后或严格遮蔽时间窗外, 贡献空 union
- 该观察仅为 Pilot 阶段粗扫结果, 不构成 Q3 真实最优; 真实 Q3 形式搜索可能产生非平凡 union (三枚弹均贡献), 需要 bounded formal search 评估
- closure v2 §二: `per_bomb_intervals` 必须为恰好 3 项 list (即便部分 bomb 空 union 也输出 `[]`)

### 4. Budget recommendation (closure v2: stage-weighted 公式 + efficient / conservative 双方案)

**`recommendation_status: MAIN_DECISION_REQUIRED`** — closure v2 不得硬编码
单一推荐值, 改用 stage-weighted 公式 + efficient / conservative 两 scenario,
由 MAIN 在 TASK_006-P2 立项前决定。

公式: `sum(profile_count × profile_p90) × safety_factor (1.5)`

#### efficient scenario

| 字段 | 值 |
|---|---|
| coarse_evaluations | 480 |
| medium_evaluations | 8 |
| fine_evaluations | 4 |
| total_q3_evaluations | 492 |
| p90_raw_seconds | 486.912 (= 480×0.5750 + 8×5.5935 + 4×41.5400) |
| safety_factor | 1.5 |
| recommended_wall_clock_seconds | **730** |

#### conservative scenario

| 字段 | 值 |
|---|---|
| coarse_evaluations | 480 |
| medium_evaluations | 24 |
| fine_evaluations | 8 |
| total_q3_evaluations | 512 |
| p90_raw_seconds | 742.568 (= 480×0.5750 + 24×5.5935 + 8×41.5400) |
| safety_factor | 1.5 |
| recommended_wall_clock_seconds | **1114** |

#### explicit null fields (closure v2 §十二禁止硬编码 legacy constants)

| 字段 | 值 |
|---|---|
| recommended_refinement_evaluations | **null** |
| recommended_verification_q3_calls | **null** |

calculation_basis:
- coarse_p90 = 0.5750 s (count=82)
- medium_p90 = 5.5935 s (count=8)
- fine_p90 = 41.5400 s (count=4)
- safety_factor = 1.5
- pilot completed 94 evals

### 5. MAIN 决策建议（不冒充）

预算推荐来自实测 p90 per profile，未照抄 TASK_005 的 3×1000 / 32 / 5 / 6。

考虑到 fine profile 单次 ~41 s 远高于 coarse (~0.5 s)，MAIN 在 TASK_006-P2 立项前可考虑：
1. **优先 coarse 阶段大量采样**: fine 只用于 finalist 重评;
2. **降低 fine 阶段比例**: 若非必要可只对 top-2 而非 top-8 做 fine 复评 (对应 conservative 比 efficient 多 4 fine evals ≈ 166 s);
3. **取消 Stage A 中 fine profile calibration**: Stage A 已有 coarse+medium，fine 耗时占 60% 但对 Stage B/C/D 决策不直接参与;
4. **efficient / conservative 之差 ~384 s**: 主要来自 medium 8 vs 24 (96 s p90 差) 与 fine 4 vs 8 (166 s p90 差).

closure v2 推荐 efficient 起步 (730 s wall) + 决赛阶段按需升级到 conservative (1114 s wall); 保守上限不应超过 1500 s (与 TASK_005 Q2 历史最严上限对齐)。

本轮仅交付实测与建议，不冒充 Q3 Formal Search 的最优预算。

### 6. 不冒充

- 不冒充 VERIFIED GLOBAL OPTIMUM
- 不冒充 FINAL OFFICIAL ANSWER
- 不冒充 LOCAL CONVERGENCE ESTABLISHED
- 不冒充 730 / 1114 s 必须是真实 wall-clock 上限（仅基于 Pilot 实测 + safety_factor 推导）
- 不冒充 Pilot best candidate (3.788 s) 是 Q3 全局最优
- 不冒充 Pilot 中发现的"单弹贡献"模式是 Q3 真实最优结构
- closure v2 budget recommendation 显式 `MAIN_DECISION_REQUIRED`, 由 MAIN 在 efficient / conservative 之间决策

### 7. closure v2 修复清单（evidence_corrections, 见 q3_pilot_summary.json）

| corrected_field | 原状态 (commit 59999f9a) | closure v2 状态 | 来源 |
|---|---|---|---|
| stage_counts | {calibration: 12, coarse_exploration: 78, fine_spotcheck: 4, medium_recheck: 8} | {calibration: 6, coarse_exploration: 80, medium_recheck: 6, fine_spotcheck: 2, total: 94} | schedule record 显式 +1 |
| best_pilot_candidate.per_bomb_intervals | 1 项 list (缺 2 枚) | 3 项 list (bomb 1 非空, bomb 2/3 空) | _serialize_best_candidate 重写 |
| budget_recommendation | 硬编码 528 / 32 / 5 / 16557 | stage-weighted + MAIN_DECISION_REQUIRED + efficient / conservative | _recommend_budget 重写 |
| resume_identity.schedule_sha256 | 缺失 | 新增 (6 项 identity 之一) | run_pilot 重写为 schedule-based |
| resume_identity.fail_closed | 静默 fallback | CHECKPOINT_LOAD_ERROR / RESUME_IDENTITY_MISMATCH (exit 2) | run_pilot 重写 |
| validate_candidate.heading_rad_strict_range | normalize 后判定 (隐式 wrap) | 原始字段 0 ≤ heading_rad < 2π 严格判定 | closure v2 §四 |

- closure v2 evidence commit HEAD (FIX commit) 与 original_pilot_evidence_commit (`59999f9a`) 不同; PR body 用 base_sha / original_pilot_execution_head (`4d442a7a`) / original_evidence_commit (`59999f9a`) / closure_code_head / closure_evidence_head / current_pr_head 6 个独立字段区分.
- 1 次 targeted reconstruction Q3 call = `python -m src.q3_three_bombs --targeted-reconstruction --profile coarse --scan-step 0.05`, 输出 `outputs/q3/q3_targeted_reconstruction.json`.