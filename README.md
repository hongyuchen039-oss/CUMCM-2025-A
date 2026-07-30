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

TASK_006-P2C Q3 THREE-BOMB CANDIDATE CLOSURE 已闭合：F1-F5 sequential propagation /
**32 evals 实测** / **290.54 s 实测 wall-clock**（≤ 600 s hard cap）/ 0 system_error。
P2 5 阶段 / **512 evals 实测** / **834.07 s 实测 wall-clock** 已完成。

- **P2 Q3 candidate generation**: Stage A 360 / B 120 / C 24 / D 6 / E 2 = **512 实测 = 512**
- **P2 Q3 real evaluator calls**: **512**（每条 schedule record 一次 top-level Q3 evaluation）
- **P2 Q3 single-bomb subcalls**: **1536** (= 512 × 3)
- **P2 Q3 wall-clock**: **834.07 s** (≤ 1200 s hard cap)
- **P2 best total_union_duration_s**: **4.469013137817385 s** (相对 Pilot 3.788169 s, **+17.97%**)
- **P2C Q3 closure**: F1=16 / F2=8 / F3=4 / F4=2 / F5=2 = **32 实测 = 32**
- **P2C Q3 single-bomb subcalls**: **96** (= 32 × 3)
- **P2C Q3 wall-clock**: **290.54 s** (≤ 600 s hard cap)
- **P2C closure best total_union_duration_s**: **4.478218820691105 s**
  (vs P2 incumbent 4.469013137817385 s, **+0.21%**)
- **P2C 8-field resume identity**: execution_head_sha + contract_snapshot_sha256 +
  q2/q3 code SHAs + closure_config_sha256 + candidate_schema_version +
  closure_schedule_sha256（新增）
- **P2C sequential stage propagation**: F1+F2 pre-build → execute F1+F2 →
  build F3 from real results → execute F3 → build F4 → execute F4 →
  build F5 → execute F5（不再 pre-construct 全部）
- **P2C cumulative wall-clock**: previous_elapsed + current_process_elapsed =
  elapsed_total，on resume 不 reset to 0
- **P2 evidence preservation**: HEAD=`70a4dd767f057edded65bd2011ac544347f661dc`、
  evidence=`dc970a483ab9e05d76467decf63f61dff70f0862`、512 evals / 834.07 s /
  0 system_error 完整保留；P2 summary 增加 `evidence_closure` 块 +
  `formal_schedule_complete: true` + `pilot_complete_legacy_field: true`
- **foundation frozen**: q3_three_bombs / q2 / q1 全部不允许修改（实测未修改）
- **P0/P1 evidence**: 94-evaluation Pilot (commit `59999f9a`) + closure v2 (FIX `a139988`, VERIFIED `31ddb7b`) 保留
- **等级**: `BUDGET_LIMITED_BEST_KNOWN Q3 CANDIDATE / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM / RESULT1.XLSX NOT GENERATED`
- **禁止**: 重跑 Pilot / 重跑 P2 512 / 修改 foundation / 生成 result1.xlsx /
  启动 P3 / Q4 / Q5 / 自动 Audit / Hermes / Ready / merge

详见 [MODEL.md §"Q3 正式 bounded search (TASK_006-P2 / BUDGET_LIMITED_BEST_KNOWN)"] /
[MODEL.md §"Q3 Candidate Closure (TASK_006-P2C / BUDGET_LIMITED_BEST_KNOWN)"] 与
[START_HERE.md](./START_HERE.md) / [NEXT_TASK.md](./NEXT_TASK.md) / [RESULTS.md](./RESULTS.md)。

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

## TASK_006 当前阶段（Q3 三弹 evaluator + bounded pilot + candidate closure）

- branch: `task/TASK_006-q3-three-bombs`（基于 `main` = `007b93d3…`）
- P2 phase: `TASK_006-P2`（Q3 THREE-BOMB FORMAL BOUNDED SEARCH）— **已完成**
- P2C phase: `TASK_006-P2C`（Q3 CANDIDATE CLOSURE）— **已完成**
- P2 contract_version: 3（P2 v3 snapshot: `work/task_contracts/TASK_006-P2-v3.json`,
  git rm --cached 但本地保留）
- P2C contract_version: 4（P2C v4 snapshot: `work/task_contracts/TASK_006-P2C-v4.json`）
- 本轮 P2C 目标：
  - 修复 P2 sequential stage propagation 缺陷（B/C/D/E schedule 必须按前驱阶段实际产生 candidates 实时构建）；
  - 修复 resume cumulative wall-clock accounting（previous + current_process = elapsed_total, on resume 不 reset to 0）；
  - 新增 8-field resume identity（含 `closure_schedule_sha256`）；
  - 32 evaluation candidate closure：F1=16 / F2=8 / F3=4 / F4=2 / F5=2 = **32** Q3 evaluations；
  - **wall-clock ≤ 600 s**（hard cap）；
  - 单弹 evaluator calls = 32 × 3 = 96；
  - sequential propagation + atomic checkpoint（schema v4）+ 8-field identity fail-closed；
  - 输出 `outputs/q3/q3_candidate_closure_summary.json`（BUDGET_LIMITED_BEST_KNOWN）；
  - 修正 `outputs/q3/q3_formal_search_summary.json`（增加 `evidence_closure` 块 +
    `formal_schedule_complete: true` + `pilot_complete_legacy_field: true`）；
  - 单元测试 ≥ 117 cases（52 P0/P1 + 29 P2 + 36 P2C，FakeEvaluator only，**不**调用真实 Q3 evaluator）。
- 本轮**不**执行：
  - 重跑 Pilot（94 evals evidence commit `59999f9a` 保留）；
  - 重跑 P2 512-evaluation 正式搜索（P2 evidence commit `dc970a48` + HEAD `70a4dd7` 保留）；
  - 修改 Q1 / Q2 / q3_three_bombs 任何实现；
  - 生成 result1.xlsx；
  - 启动 TASK_006-P3 / Q4 / Q5；
  - 启动 Audit CC / Hermes（MAIN 决定）；
  - 自动 Ready / merge；
  - 声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum。
- 最终等级只能是 `BUDGET_LIMITED_BEST_KNOWN`。
- 详细任务边界见 [NEXT_TASK.md](./NEXT_TASK.md)；模型合同见 [MODEL.md](./MODEL.md) §"Q3 正式 bounded search"
  + §"Q3 Candidate Closure (TASK_006-P2C)"；预算见 [bounded_verification/templates/task-contract.md](./.claude/skills/bounded-verification/templates/task-contract.md) Phase contract lifecycle。