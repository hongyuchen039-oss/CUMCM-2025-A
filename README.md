# CUMCM 2025 A — 烟幕干扰弹的投放策略

本项目研究无人机投放烟幕干扰弹，对来袭导弹实施有效遮蔽的建模与优化策略。

## 项目入口

- [START_HERE.md](./START_HERE.md) — 当前状态与唯一任务
- [MODEL.md](./MODEL.md) — 模型、假设与算法合同
- [RESULTS.md](./RESULTS.md) — 已验证结果与可信等级
- [NEXT_TASK.md](./NEXT_TASK.md) — 当前执行边界与验收标准
- [problem/FACTS.md](./problem/FACTS.md) — 官方题目事实与模板要求
- [CLAUDE.md](./CLAUDE.md) — 仓库长期工作规则

## 当前状态

TASK_006-P3 Q3 RESULT1.XLSX ARTIFACT GENERATION（PLAN 已冻结）。
本轮对 P2C 冻结的 8 维 candidate 执行一次高精度重建，并从官方空白模板生成、
回读和核验 `outputs/submission/result1.xlsx`。

- **P2 已完成**：Q3 三弹正式 bounded search（512 evaluations / 834.07 s）；
  best `total_union_duration_s = 4.469013137817385 s`，HEAD `70a4dd7`、evidence `dc970a48` 完整保留。
- **P2C 已闭合（CANDIDATE CLOSURE）**：32-evaluation bounded closure（F1=16 / F2=8 / F3=4 / F4=2 / F5=2），
  wall-clock 290.54 s ≤ 600 s。closure canonical candidate 与 P2 共享 7 维，仅
  `speed_mps` 从 116.62799297398149 → 116.12799297398149（差 −0.5 m/s）。
- **P2C closure canonical**:
  `heading_rad=3.127613485137657, speed_mps=116.12799297398149, release_time_1_s=0.993241052387636, delay_1_s=3.720360704323356, release_time_2_s=4.88566490244013, delay_2_s=3.7704749980723404, release_time_3_s=10.157737577136487, delay_3_s=3.7180978311642083`
  `closure_selection_score_s = 4.478218820691105 s` (profile=coarse/0.05)
  `canonical_reconstruction_total_union_duration_s = 4.478204178810118 s` (profile=fine/0.005)
  profile_difference = 1.4641880987653622e-05 s (10^-5 量级, 两个 profile 各自保留, 不混用)
  `source = TASK_006-P2C F5 high-resolution verification`
- **P3 当前阶段（PLAN 冻结，WORKING 待启动）**:
  - 1 次 fine / scan_step=0.005 高精度重建；
  - 期望 `abs(reconstructed - 4.478204178810118) ≤ 1e-12` (fine / 0.005 reconstruction gate);
  - 从官方模板 ZIP `题目及模板/2025高教社杯数学建模A题_结果模板.zip`
    读取 `result1.xlsx` → in-memory edit → 写 `outputs/submission/result1.xlsx`；
  - 模板指纹保留（sheet names / merged cells / freeze panes / header / 附注等）；
  - 程序从磁盘回读，逐格核验 10 列 × 3 行；
  - 7 字段 resume identity（含 `canonical_candidate_sha256` + `official_template_sha256`，新增）；
  - 输出 `outputs/q3/q3_result1_artifact_summary.json`；
  - ≥ 22 个新 result1 模块单元测试（FakeEvaluator + temporary workbook，**不**调用真实 Q3 evaluator）；
  - PR #13 保持 Draft / unmerged。
- **P3 严禁**:
  - 重跑 P2C 32 / P2 512 / Pilot；
  - 调整任何决策变量 / 产生 challenger；
  - 修改 foundation（Q1 / Q2 / q3_three_bombs）；
  - 修改官方模板 ZIP；
  - 生成 result2.xlsx / result3.xlsx；
  - 启动 Final Audit CC / Hermes（MAIN 决定）；
  - 启动 Q4 / Q5（MAIN 决定）；
  - 自动 Ready / merge；
  - 声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum / 官方答案。

P2C 详细结果见 [RESULTS.md](./RESULTS.md) / [MODEL.md §"Q3 Candidate Closure"]；
P3 详细合同见 [MODEL.md §"Q3 result1 artifact generation (TASK_006-P3)"] /
[NEXT_TASK.md](./NEXT_TASK.md)。

TASK_005 Q2 FORMAL SEARCH + BOUNDED REFINEMENT + CLEAN-HEAD VERIFICATION IDENTITY CLOSURE + INDEPENDENT AUDIT 已收口，canonical Q2 result 已晋升：

- **Q2 canonical candidate**:
  `heading_rad=3.126767217560497, speed_mps=116.43351397802584, release_time_s=1.2672692031529031, delay_s=3.789202402720746`
  `total_duration_s = 4.260970878601073`
  `interval (s) = (5.089825368500298, 9.350796247101371)`
- **等级**: `FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM`
- **晋升依据**: 独立 Audit 结论 B (audit passed with doc-only P2, promote after one documentation commit)
- **晋升范围**: 仅 doc-only P2 闭合；不重跑 3×1000；不重跑完整 16 项扰动；不重跑全量测试
- **旧候选** `(3.121767, 115.4335, 1.767269, 3.889202)` dur `2.48275905609131 s` 已降级为 `HISTORICAL FORMAL-SEARCH CANDIDATE`，因旧 16 项扰动 5/16 改善触发 bounded refinement

## Q2 多阶段证据分层

### 1. Q2 formal multi-seed search (TASK_005 P1 closure)
- 3 seeds (2025, 2026, 2027) × 1000 evals/seed × 5-stage pipeline
- 跨 seed finalist pool 13 candidates, pilot best-known 显式注入
- 统一 fine cylinder re-evaluation (scan_step=0.005) → 旧 winner (2.48275905609131 s)
- 时间步长稳定性：0.02 / 0.01 / 0.005 三档 delta=0.000 s
- **16 项 one-var-at-a-time 扰动**：5/16 改善（speed_mps −1 / release_time_s −1 / delay_s +0.1）→ 旧候选不是 16 项邻域局部极值，因此触发 bounded refinement（不是"全部未改善"）
- 物理合法性校验通过
- 22 FormalProfileTests + 20 P1EvidenceGateTests PASS

### 2. Bounded refinement (32 evaluations, ≤2100 s)
- 2 parent rehydration (formal winner + pert_09 best)
- 3-level coordinate search (heading ±0.02/0.01/0.005, speed ±1.0/0.5/0.25, release ±0.2/0.1/0.05, delay ±0.1/0.05/0.025)
- 单 sweep greedy, hard wall-clock gate, atomic checkpoint per eval
- 32/32 budget exhausted (BUDGET EXHAUSTED ≠ CODE FAILED)
- refined candidate dur=4.260970878601073 s（sweep scan_step=0.01）
- 20 RefinementGateTests PASS

### 3. Clean-head verification identity closure (5 evaluator calls)
- identity: worktree-clean + HEAD sha + script sha256 + q2_search code identity + refinement_config_sha256 + parent candidate identity + checkpoint_source_head_sha 全通过
- delay_s ±0.025 (2 evals): 4.258950 / 4.140284 s, neither improves best-known
- stability 0.02 / 0.010 / 0.005 (3 evals): 三档 duration 完全一致, eval_id 同
- physical_validity ok=True
- elapsed = 76.13 s (well under 300 s)
- declaration: BUDGET-LIMITED BEST-KNOWN / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM

### 4. Independent Audit (6 evaluator calls, exact match)
- audit conclusion B: passed with doc-only P2
- identity chain 全通过
- 独立数学复算 6/6 精确一致
- 不需要重跑 3×1000 / 完整 16 项扰动 / 全量测试
- 仅需一个 doc-only commit 闭合 P2

## 测试证据分层

| 阶段 | 测试范围 | 结果 |
|---|---|---|
| formal P1 closure | 473/473 full regression | PASS |
| refinement | 210/210 tests.test_q2_search | PASS |
| clean-head verification | 5 evaluator calls (无测试) | identity / stability / physical validity PASS |
| independent Audit | 6 evaluator calls, exact match | PASS |

不把不同阶段测试数合并成一个虚假的当前测试数。

## 结果等级

TASK_005 canonical Q2 output 是 **FORMAL BUDGET-LIMITED BEST-KNOWN**，
**NOT A PROVEN GLOBAL OPTIMUM**，**LOCAL CONVERGENCE NOT ESTABLISHED**。
PR #12（TASK_GOV_003 bounded verification Skill v0.1）已 merged；TASK_006 启动。

## TASK_006 当前阶段（Q3 三弹 evaluator + bounded pilot + candidate closure + result1.xlsx artifact generation）

- branch: `task/TASK_006-q3-three-bombs`（基于 `main` = `007b93d3…`）
- P0/P1 phase: `TASK_006-P0P1`（PILOT 94 evals evidence commit `59999f9a`）— **完成，保留**
- P2 phase: `TASK_006-P2`（Q3 THREE-BOMB FORMAL BOUNDED SEARCH 512 evals / 834.07 s）— **完成**
- P2C phase: `TASK_006-P2C`（Q3 CANDIDATE CLOSURE 32 evals / 290.54 s）— **完成**
- P3 phase: `TASK_006-P3`（Q3 RESULT1.XLSX ARTIFACT GENERATION，1 fine / 0.005 reconstruction + 官方模板生成 + 回读）— **PLAN 已冻结，WORKING 待启动**
- P0/P1 contract_version: —（P0/P1 evidence commit `59999f9a`）
- P2 contract_version: 3（P2 v3 snapshot: `work/task_contracts/TASK_006-P2-v3.json`, locally preserved NOT committed）
- P2C contract_version: 4（P2C v4 snapshot: `work/task_contracts/TASK_006-P2C-v4.json`, locally preserved NOT committed）
- P3 contract_version: 5（P3 v5 snapshot: `work/task_contracts/TASK_006-P3-v5.json`, locally preserved NOT committed）
- 本轮 P3 目标：
  - 1 次 fine / scan_step=0.005 高精度重建；
  - `abs(reconstructed - 4.478204178810118) ≤ 1e-12` (P3 reconstruction gate);
  - P2C closure selection score = 4.478218820691105 (coarse/0.05) 保留为历史证据；
  - 7 字段 resume identity（含 `canonical_candidate_sha256` + `official_template_sha256`，新增）；
  - 官方模板 ZIP in-memory edit（不修改原 ZIP 字节）→ 写 `outputs/submission/result1.xlsx`；
  - 程序从磁盘回读，逐格核验 10 列 × 3 行（abs_tol=1e-10, rel_tol=1e-12）；
  - 模板指纹保留（sheet names / merged cells / freeze panes / header / 附注等）；
  - 输出 `outputs/q3/q3_result1_artifact_summary.json`；
  - ≥ 22 个新 result1 模块单元测试（FakeEvaluator + temporary workbook，**不**调用真实 Q3 evaluator）；
  - 3 个 commit：PLAN (本文档同步) → WORKING (scripts/build_result1.py + tests) → VERIFIED (artifact + result1.xlsx + 5 docs 同步)。
- 本轮**不**执行：
  - 重跑 Pilot / P2 / P2C（实测保留不变）；
  - 修改 Q1 / Q2 / q3_three_bombs 任何实现；
  - 修改官方模板 ZIP 或其成员字节；
  - 生成 result2.xlsx / result3.xlsx；
  - 启动 Q4 / Q5；
  - 启动 Final Audit CC / Hermes（MAIN 决定）；
  - 自动 Ready / merge；
  - 声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum / 官方答案。
- 最终等级只能是 `BUDGET_LIMITED_BEST_KNOWN`（沿用 P2C 等级，P3 不升 VERIFIED）。
- 详细任务边界见 [NEXT_TASK.md](./NEXT_TASK.md)；模型合同见 [MODEL.md](./MODEL.md) §"Q3 result1 artifact generation (TASK_006-P3)"；预算见 [bounded_verification/templates/task-contract.md](./.claude/skills/bounded-verification/templates/task-contract.md) Phase contract lifecycle。