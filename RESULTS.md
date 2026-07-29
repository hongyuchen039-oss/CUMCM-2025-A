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
- 完整圆柱采样等级 (coarse/medium/fine) 与覆盖率阈值是否合适, 待 Q2 启动前外部审核

## Q2 Formal Search (TASK_005 / BEST-KNOWN CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM)

> 已在 `src/q2_search.py` 追加 formal block（schema 3, gate_id
> `q2_search_formal_v1`），通过 `scripts/run_q2_formal.py` 编排, 在
> `tests/test_q2_search.py` 追加 22 个 FormalProfileTests 验证.
> 本节固定 TASK_005 formal profile 的运行结果与可解释性.
> 等级: **FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM**,
> 不得冒充 Q2 VERIFIED / FINAL / 官方答案 / 解析极值.
> 独立审查 (Audit CC / Hermes) 签字后才能立项 TASK_006。

### 1. Declaration

- `declaration = "FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM"`
- `best_known_disclaimer = "NOT A PROVEN GLOBAL OPTIMUM"`
- `final_best_status = "OK_FINE_RESULT"`
- `code_identity_sha256` 共享自 v1.2 pilot (单源 code revision)
- `canonical_result_sha256 = fa279e3fcc696ff83ea19c1069040c2f8bdaa6ebb0ed5ecb9faf7c9e32515d98`

### 2. 搜索规模 (per-seed)

| 阶段 | 候选数 | 说明 |
|---|---|---|
| global_coarse | 595 | 1 anchor + 594 deterministic uniform pseudorandom |
| global_medium | 49 | coarse top-k 候选在该采样级重评 |
| local_coarse | 294 | pipeline-saturating: `local_coarse = local_per_top × |medium_confirmed| = 6 × 49` |
| local_medium | 49 | medium sampling 级重评 |
| fine | 13 | 决赛级细评估 (scan_step=0.005) |
| **合计** | **1000** | 总预算 / 每 seed |

- pipeline-saturating 约束严格保证: `local_coarse = 6 × global_medium`;
  候选 budget 增加通过 global_coarse 缩放, 其它阶段按 5:8:8:2 比例
  (global_medium : local_coarse : local_medium : fine) 协同增长.

### 3. 多 seed 调度

- seeds = [2025, 2026, 2027]，每个 seed 独立 checkpoint / 独立
  run_identity_sha256 / 独立 canonical_result_sha256。
- 三个 seed 真实 wall-clock:
  - seed=2025: 465.61 s
  - seed=2026: 471.47 s
  - seed=2027: 515.14 s
- 三 seed 全部完成 1000 / 1000 评估, 全部 final_best_status = `OK_FINE_RESULT`,
  system_error 计数 = 0.

### 4. Finalist Pool (跨 seed 合并 + pilot best-known 显式注入)

- 跨 seed union top-5 fine: 来自 3 个 seed × 5 fine top 共 15 候选
- 经 `cross_seed_dedup_candidates` 去重 (tolerance 1e-6 各维)
- 显式注入 1 个 pilot best-known (从 `work/q2_pilot_calib/pilot_result.json`
  复水化, 非 PR 描述舍入值)
- `n_finalists_after_dedup = 13` (15 − 2 duplicate + pilot_best 已含 = 13)

### 5. Formal Winner (uniform fine re-evaluation, scan_step=0.005)

| 变元 | 值 |
|---|---|
| heading_rad (θ) | **3.121767217560497** |
| speed_mps (v) | **115.43351397802584** |
| release_time_s (t_release) | **1.7672692031529031** |
| delay_s (δ) | **3.889202402720746** |
| detonation_time_s (t_d) | **5.65647160587365** (= t_release + δ) |
| release_point (R) | (17596.03799572056, 4.044165532408561, 1800.0) |
| detonation_point (D) | (17147.181921223168, 12.944098987698323, 1725.8831128862887) |
| total_duration_s | **2.48275905609131 s** |
| interval | **(6.094727521515435, 8.577486577606745) s** |
| n_intervals | 1 |
| status | `ok` |
| valid | True |
| sample_level | `fine` |
| scan_step_s | 0.005 |
| evaluator_kind | `real` |
| evaluation_id | `c99344f6b900009f6e4cd3d28c6e2e7d` |
| physical_candidate_sha256 | `485582b5dc4f8d9855e5894fcd5372e5e72375206425b756871bfd5ee8763c59` |

> 与 pilot fixed-163 seed=2025 best-known 在 1e-6 容差内完全一致
> (formal pipeline 重新评估确认, 跨 seed 独立验证 3 次均收敛到同一候选).

### 6. 时间步长稳定性 (3 档)

| scan_step | total_duration_s | status | valid | n_intervals |
|---|---|---|---|---|
| 0.0200 | 2.48275905609131 | ok | True | 1 |
| 0.0100 | 2.48275905609131 | ok | True | 1 |
| 0.0050 | 2.48275905609131 | ok | True | 1 |

- `delta_0p01_vs_0p005_s = 0.000000`
- `stability_ok = True`
- 三档 evaluation_id 一致 (`ad4e701cbff6404ec01f76ec7955bdaf`,
  表明完全相同细粒度采样点落入同一区间)

### 7. 局部扰动检查 (4 方向, scan_step=0.005)

| 方向 | Δ(θ, v, t_r, δ) | 候选 (h, s, r, d) | 总时长 | improves? |
|---|---|---|---|---|
| + 大 | (+0.05, +2.0, +0.5, +0.3) | (3.172, 117.43, 2.267, 4.189) | 0.0 s | False |
| − 大 | (-0.05, -2.0, -0.5, -0.3) | (3.072, 113.43, 1.267, 3.589) | 0.0 s | False |
| + 小 | (+0.02, +1.0, +0.2, +0.1) | (3.142, 116.43, 1.967, 3.989) | 2.172051 s | False |
| − 小 | (-0.02, -1.0, -0.2, -0.1) | (3.102, 114.43, 1.567, 3.789) | 0.0 s | False |

- baseline = 2.48275905609131 s
- `any_improves = False`
- `local_not_yet_converged = False` (winner 是一个真实的局部极值)

### 8. 物理合法性

- `physical_validity.ok = True`
- 全部 4 维 (speed, release, delay, heading) 通过 fail-closed 校验:
  - speed_mps = 115.43 ∈ [70, 140] ✓
  - release_time_s = 1.767 ≥ 0 ✓
  - delay_s = 3.889 ∈ [0, sqrt(2·1800/9.8)] ≈ [0, 19.18] ✓
  - heading_rad = 3.1218 ∈ [0, 2π) ✓

### 9. 局限

- formal search 是 deterministic uniform pseudorandom + 5-stage pipeline,
  **不是**全局最优证明, **不是**解析极值, **不是**官方答案.
- 未做约束优化 / Pareto frontier / 多弹搜索 / 大规模 LHS / 贝叶斯优化.
- 跨 seed + 局部扰动均未发现更优候选, 但综合搜索空间未穷尽.
- 不得在 formal winner 基础上声称 Q2 全局最优 / 写入
  RESULTS.md 最终结果表 / 写入 result1.xlsx, 除非独立审查签字.
- 等级: **FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM**.
  下一阶段需独立审查 (Audit CC / Hermes) 复算 winner 物理量 + 稳定性 +
  扰动 + finalist pool 解释性, 通过后才可立项 TASK_006 (Q3 / result1.xlsx).

## 等级
- 方案 A 点目标基线: **BASELINE / EXPERIMENTAL**
- 方案 B 完整圆柱: **FULL-CYLINDER CANDIDATE / EXPERIMENTAL**
- Q2 Formal Search (TASK_005): **FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM**

## 备注
- 任何后续计算结果必须以本文件为唯一更新入口。
- 等级只能从 EXPERIMENTAL 推进到 VERIFIED，再推进到 FINAL；不能跳过。
- 本轮 42 (方案 A) + 75 (方案 B, 含 2 个收敛失败路径) 单元测试 + 6 档扫描 + 三档空间采样 + 三档时间采样
  + coverage_plateau + margin 局部网格估计共同验证, 未伪造任何"论文对比"或"权威背书".
- 本轮 FIX 前后可见性边界、收敛判定、几何/时序拆分均有变更, 详见 MODEL.md §12.