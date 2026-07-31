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

**TASK_006-P3 COMPLETE** — Q3 RESULT1.XLSX GENERATED, ROUND-TRIP VERIFIED.

- PR #13 = Open / Draft / Unmerged / Mergeable.
- FINAL AUDIT / HERMES PENDING.
- TASK_007 NOT STARTED.

**P3 双数值证据（profile provenance, 不混用）**:
- Q3 canonical fine reconstruction: `4.478204178810118 s` (profile=fine, scan_step=0.005)
- P2C closure selection score: `4.478218820691105 s` (profile=coarse, scan_step=0.05, 历史证据)
- profile_difference: `1.4641880987653622e-05 s`

**result1.xlsx**:
- 输出路径: `outputs/submission/result1.xlsx` (5911 bytes)
- 来源模板 ZIP: `题目及模板/2025高教社杯数学建模A题_结果模板.zip` 内 `result1.xlsx` member
- 输出 SHA: `b938a90b96181be14990d5bd3395c2cff72e93035828542617571ddc1d754847`
- round-trip: PASS (abs_tol=1e-10, rel_tol=1e-12, 12-field fingerprint preserved)

**身份链（锁定）**:

| 字段 | SHA |
|---|---|
| main HEAD | `007b93d301db73c9a73904337de34d1b4e13467e` |
| p3_starting_head | `843b4a1e5791e67a09c377c2173f16a1105ab944` |
| p3_execution_head | `cb3dd83c834ec3b5f8c1e85213ddc63301e3d709` |
| p3_evidence_commit | `a04e158b7848d7d5a3d381ed9e5871961267ed37` |
| official_template_zip_sha256 | `f9879c0d36b7bdccb99fb330a8032e62851ab1a1f0a1636c92440a1cdaec658e` |
| official_template_member_sha256 | `d1773205296034c0f02ed7f848f8f1e66af633d1e6562938e059450a554b930e` |
| result1_run_identity_sha256 | `82065aa5fe4d4e6036691a053b38732b9ff1f50497083e3306e262e82a4bfc65` |

**P2 / P2C 证据（锁定，不重跑）**:
- P2: 512 evals / 834.07 s, best = 4.469013137817385 s, HEAD=70a4dd7, evidence=dc970a48
- P2C: 32 evals / 290.54 s, closure_selection_score = 4.478218820691105 s, evidence=843b4a1

**禁止事项**:
- 重跑 P3 / P2 512 / P2C 32 / Pilot
- 修改 foundation (Q1 / Q2 / q3_three_bombs)
- 修改官方模板 ZIP
- 生成 result2.xlsx / result3.xlsx
- 启动 Final Audit CC / Hermes / Q4 / Q5 (MAIN 决定)
- 自动 Ready / merge
- 声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum / 官方答案

**任务编号（固定, 取消 TASK_006-P4 / TASK_006-P5）**:
- `TASK_006` = Q3 + result1.xlsx
- `TASK_007` = Q4 + result2.xlsx
- `TASK_008` = Q5 + result3.xlsx
- `TASK_009` = unified recomputation / sensitivity / robustness / figures
- `TASK_010` = paper / consistency / final package

`TASK_006-P4` / `TASK_006-P5` 编号方案作废 — **HISTORICAL INCORRECT TASK LABEL — DO NOT USE**.

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