# 项目驾驶舱

## 最终目标
完成 2025 CUMCM A 题 Q1–Q5 的可信建模、数值策略、result1/2/3.xlsx 与论文。

## 当前问题
Q2 单架 FY1 投放一枚烟幕弹的最优策略。

## 当前阶段
TASK_005 Q2 FORMAL EVIDENCE PATCH BUILT AND RERUN (P1 closure)
— WAITING FOR INDEPENDENT MATH/RESULT REVIEW.

## 最后可信成果
- Q1 点目标基线、完整圆柱严格遮蔽候选已冻结（不在本任务修改）；
- Q2 单候选真实评估器已接入（src/q2_single_bomb.py, 不在本任务修改）；
- Q2 Search Core v1.2 RP1 已合入 main，包含 fixed-163 pilot 不变量、
  evaluation-safe checkpoint / resume / structured code identity / canonical result；
- TASK_GOV_002 Harness task-context preflight 已部署；
- **TASK_005 Q2 formal search 已在本分支 P1 闭环 (clean-HEAD 467314d)：**
  - 3 seeds × 1000 evals/seed × full 5-stage pipeline；
  - cross-seed finalist pool 13 candidates, pilot best-known 已显式注入 (priority 1)；
  - 统一 fine cylinder re-evaluation (scan_step = 0.005) → winner；
  - canonical_result_sha256 = `2efcc91486d4ce9d22bfdedc0a4d57c36857d506126bca40c1a31695a96d1b3a`；
  - 时间步长稳定性：0.02 / 0.01 / 0.005 三档 duration 完全一致 (delta = 0.000s)；
  - **16 项 one-var-at-a-time 扰动 (4 vars × 2 signs × 2 scales) 全部执行**，
    5/16 改善 (speed_mps -1 / release_time_s -1 / delay_s +0.1) → winner 不是 16 项
    one-var 邻域局部极值，**local_perturbation_passed=False**；
  - 物理合法性校验通过 (speed ∈ [70, 140], release ≥ 0, delay 在落地约束内,
    heading ∈ [0, 2π) 包裹)；
  - formal profile 严格隔离自 pilot fixed-163 (独立 schema 3、独立
    declaration、独立 gate error class、独立 config 文件)；
  - **22 个 FormalProfileTests + 20 个 P1EvidenceGateTests 全部 PASS**，
    148 个 pilot 测试未删除或放宽；
  - raw per-seed artifacts 已 gitignored (work/q2_formal/seed_*)；tracked
    tree 仅留 outputs/q2/q2_formal_summary.json + per_seed_summary.json。

## 当前最大不确定性
- formal search 是 deterministic uniform pseudorandom + 5-stage pipeline,
  不是全局最优证明，仅为 best-known candidate。
- 多 seed fine winner 中 seed=2026/2027 各自找到 (θ=π, v=120, r=1.5,
  d=3.6) dur=1.392384s, 但 pilot 注入的 θ=3.121767217560497 候选在
  seed=2025 fine 阶段重评后 dur=2.48275905609131s, 经 finalist 池
  13-candidate 比较胜出（formal winner 与 pilot fixed-163 best-known
  完全一致：h=3.121767217560497, s=115.43351397802584,
  r=1.7672692031529031, d=3.889202402720746, dur=2.48275905609131 s,
  interval=(6.094727521515435, 8.577486577606745)）。
- 16 项 one-var 扰动有 5 项改善 → 存在 speed / release / delay 三方向
  可继续局部搜索的邻居，但本轮 budget gate (1000 evals/seed) 已耗尽,
  不在本任务扩张。
- 未做约束优化 / Pareto frontier / 多弹搜索。

## 当前唯一任务
独立数学/结果审查 (Audit CC / Hermes)：复算 winner 物理量 + 稳定性 +
16 项 one-var 扰动 + finalist pool 解释性；不修改本任务分支；不在本轮
出 result*.xlsx。

## 当前阻断
无。等待独立审查完成。

## 下一里程碑
独立审查通过后立项 TASK_006（Q3 三弹串接 / result1.xlsx 提交物）。

## 尚未进入
- Q3 三弹串接；
- result1.xlsx 生成；
- Q4 / Q5；
- 论文；
- 进一步 formal search（预算 ≥ 2000 已超过 wall-clock gate，禁止本任务自行扩张）。