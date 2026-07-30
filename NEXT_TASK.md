# TASK_006 — Q3 THREE-BOMB MODEL CONTRACT + REAL EVALUATOR + BOUNDED PILOT — P0/P1 CLOSURE

> 本轮是 TASK_006 的 **P0/P1 CLOSURE** 阶段，**仅**完成：
>
> 1. **不重跑** 94-evaluation Pilot；
> 2. 修复 7 个 closure v2 缺陷（heading_rad 原始范围判定、per_bomb_intervals
>    恰好 3 项、stage_counts 显式 schedule-based、resume identity 加
>    schedule_sha256 + fail-closed、budget_recommendation stage-weighted
>    算术 + MAIN_DECISION_REQUIRED、Q2 degeneration direct vs sequence、
>    repeated determinism 真实 re-eval）；
> 3. 1 次 targeted reconstruction Q3 call（复评 best pilot candidate,
>    coarse profile, scan_step=0.05）；
> 4. 更新 pilot summary + RESULTS.md + NEXT_TASK.md；
> 5. 同步 PR #13 body 6 字段 identity 拆分。
>
> 本轮**不得**：
> - 启动 TASK_006-P2；
> - 重跑完整 94-evaluation Pilot；
> - 生成 result1.xlsx；
> - 扩大正式预算；
> - 修改 Q1 / Q2 核心；
> - amend / force push；
> - 删除或覆盖 v1 contract snapshot；
> - 删除原 Pilot log / checkpoint；
> - 启动 Audit / Hermes；
> - 自动 Ready / merge。
>
> 最终结果等级只能是：`EXPERIMENTAL`。

## 当前任务边界 (closure v2)

- Base: `main` = `007b93d301db73c9a73904337de34d1b4e13467e`
- Branch: `task/TASK_006-q3-three-bombs`
- Phase: `TASK_006-P0P1-CLOSURE`
- Contract version: 2 (v2 snapshot: `work/task_contracts/TASK_006-P0P1-v2.json`)
- 启动 Harness `work/task_context.json`（gitignored, expected_head = `59999f9aba063e90d8428f5f783d8cc4abf10d62`）

### 本轮允许修改（仅 4 个 tracked 路径 + PR body）

| 路径 | 用途 |
|---|---|
| `src/q3_three_bombs.py` | closure v2 修复 (heading / serialize / schedule / fail-closed / budget / Q2-deg / repeat-determinism) + `--targeted-reconstruction` CLI |
| `tests/test_q3.py` | 5 组新测试 (heading strict bounds / Q2-deg direct vs seq / repeat real re-eval / budget arith / resume schedule synthetic) |
| `outputs/q3/q3_pilot_summary.json` | stage_counts 修正 / per_bomb_intervals 3 项 / budget_recommendation stage-weighted / evidence_corrections block |
| `outputs/q3/q3_targeted_reconstruction.json` | 1 次 Q3 call 复评 best pilot candidate |
| `RESULTS.md` | Q3 Pilot 章节 closure v2 同步 |
| `NEXT_TASK.md` | 本文（任务边界） |
| `START_HERE.md` | 最小阶段身份同步 (允许) |
| `README.md` | 最小阶段身份同步 (允许) |

### 禁止修改 (closure v2)

`src/q1_baseline.py`、`src/q1_cylinder.py`、`src/q2_single_bomb.py`、`src/q2_search.py`、
`outputs/q2/`、`outputs/submission/`、`problem/`、`scripts/`、`configs/`、`CLAUDE.md`、
`.claude/`、`.gitignore`、`MODEL.md`、任何 `result*.xlsx`、Q1/Q2 单元测试、tracked `work/` 文件、
search module `src/q3_search.py`（TASK_006-P2 才允许新增）。

### Pilot 证据保留（closure v2 锁定）

| 字段 | 值 |
|---|---|
| original_pilot_execution_head | `4d442a7a16127ca0166d1114656b5fe4d5546b4d` |
| original_evidence_commit | `59999f9aba063e90d8428f5f783d8cc4abf10d62` |
| q3_candidate_evaluations | 94 |
| single_bomb_evaluator_calls | 282 |
| total_wall_clock_seconds | 243.1241612000158 |
| best_pilot_total_union_duration_s | 3.7881687521934495 |
| corrected_stage_counts | {calibration: 6, coarse_exploration: 80, medium_recheck: 6, fine_spotcheck: 2, total: 94} |
| targeted_reconstruction_q3_calls | 1 |

## Closure v2 预算 (与 P0P1 不同的预算上限)

| 维度 | 上限 |
|---|---|
| 顶层 Q3 candidate evaluation（本轮总开销） | **4** |
| Run wall-clock | **600 s** |
| Test wall-clock | 600 s |
| 真实 TASK 测试 Q3 evaluation 数 | **3** |
| Targeted reconstruction Q3 calls | **1** |

## Checkpoint / Resume (closure v2)

- 路径：`work/q3_pilot/checkpoint.json`
- **checkpoint_schema_version = 2**
- 每个 Q3 candidate evaluation 后原子写入（temp + flush + fsync + os.replace）
- resume 强制校验 6 字段（任一不匹配立即停止，exit 2，**不静默 fallback**）：
  - `execution_head_sha`
  - `contract_snapshot_sha256`
  - `q2_single_bomb_code_sha256`
  - `candidate_schema_version`
  - `pilot_config_sha256`
  - **`schedule_sha256`**（新增, SHA-256 of schedule record list）
- corrupt / load error → `status = CHECKPOINT_LOAD_ERROR`, exit 2
- identity mismatch → `status = RESUME_IDENTITY_MISMATCH`, exit 2

## 测试分级 (closure v2)

### FAST（≤30 s）
- py_compile
- interval union (overlapping / disjoint / touching / nested / empty)
- non-finite inputs
- speed bounds
- release spacing (exactly 1 s accepted / below 1 s rejected)
- deterministic evaluation ID
- candidate serialization
- checkpoint atomic write
- pilot config caps
- **heading_rad strict raw bounds (新增 5 cases: 0 accepted / nextafter(2π,0) accepted / -1e-12 rejected / 2π rejected / 4π rejected)**
- **budget_recommendation arithmetic (新增: efficient / conservative scenarios / MAIN_DECISION_REQUIRED / null refinement/verification fields)**
- **resume schedule synthetic (新增: schedule_sha / stage_counts / fail-closed paths)**

### TASK（≤600 s, 真实 Q3 evaluation ≤ 3）
- setUpClass 共享 1 次 Q3 eval (anchor coarse)
- 已有 6 个 setUpClass 复用 + invalid fail-closed + system_error raises
- test_evaluation_id_uniqueness (ID-only, 0 extra real eval)
- **TestQ2DegenerationDirectVsSequence (新增: direct vs sequence, 0 Q3 eval)**
- **TestRepeatedDeterminismRealReeval (新增: 2 Q3 eval, full payload exact match)**

Q3 evaluator real-call budget = 1 (setUpClass) + 2 (repeated determinism) = **3**, 严格 ≤ cap.

### FULL

**SKIPPED**. MAIN 未授权 FULL; Q3 Pilot is bounded only; closure v2 禁止 full rerun.

## 提交序列 (closure v2)

1. **FIX**: `src/q3_three_bombs.py` (closure v2 实现) + `tests/test_q3.py` (5 组新测试). 不 amend, 不 force push.
2. **VERIFIED**: `outputs/q3/q3_pilot_summary.json` (corrected stage_counts / per_bomb_intervals / budget_recommendation / evidence_corrections) + `outputs/q3/q3_targeted_reconstruction.json` (1 Q3 call) + `RESULTS.md` (Q3 Pilot 章节 closure v2 同步) + `NEXT_TASK.md` (本文) + 必要时 `START_HERE.md` / `README.md` 最小身份同步.
3. **Push + PR body**: `task/TASK_006-q3-three-bombs`, push 后更新 PR #13 body 6 字段 identity.

## Draft PR (closure v2)

- Title: `TASK_006: build Q3 three-bomb evaluator and pilot (P0/P1 closure v2)`
- base: `main`
- PR body 必须包含 6 字段 identity 拆分：
  - **base_sha** = `007b93d301db73c9a73904337de34d1b4e13467e`
  - **original_pilot_execution_head** = `4d442a7a16127ca0166d1114656b5fe4d5546b4d`
  - **original_pilot_evidence_commit** = `59999f9aba063e90d8428f5f783d8cc4abf10d62`
  - **closure_code_head** = FIX commit SHA
  - **closure_evidence_head** = VERIFIED commit SHA
  - **current_pr_head** = current PR head SHA (after push)
- PR body 还需包含：
  - 8 维合同 / 三弹 union 目标 / Q2 reuse
  - tests 分级 (52 / 52 PASS)
  - 真实 evaluator counts: pilot 94 + reconstruction 1 + 测试 3 = 98 (≤ 99 max_expensive_evaluations)
  - single-bomb subcall counts: pilot 282 + reconstruction 3 + 测试 9 (3 real × 3 bombs) = 294
  - actual wall-clock: pilot 243.124 s + reconstruction 0.536 s + 测试 ~2 s
  - corrected stage_counts: {calibration: 6, coarse_exploration: 80, medium_recheck: 6, fine_spotcheck: 2, total: 94}
  - corrected per_bomb_intervals: `[[[5.551...]], [], []]`
  - budget_recommendation: stage-weighted + MAIN_DECISION_REQUIRED + efficient 730 s + conservative 1114 s
  - 1 targeted reconstruction Q3 call = 3.788169 s (复评 = 原 3.788169 s)
  - declared_level = EXPERIMENTAL
  - NOT A FORMAL Q3 RESULT
  - RESULT1.XLSX NOT GENERATED
  - LOCAL CONVERGENCE NOT ESTABLISHED
  - NOT A PROVEN GLOBAL OPTIMUM
  - TASK_006-P2 NOT STARTED
  - Q1 / Q2 files NOT modified
  - v1 contract snapshot preserved (NOT overwritten)
  - original Pilot log / checkpoint preserved (NOT deleted)
  - audit / hermes / p2 NOT STARTED

PR 保持 Draft. 不 Ready. 不 merge.

## 验收 Gate (closure v2 必须全部满足)

- [x] validate_candidate 原始 heading_rad 严格 [0, 2π) 判定（5 个新测试 PASS）
- [x] per_bomb_intervals 序列化恰好 3 项（test_serialize_best_candidate_exactly_three_bomb_intervals PASS）
- [x] PilotStats.stage_counts 显式 schedule-based, {calibration: 6, coarse_exploration: 80, medium_recheck: 6, fine_spotcheck: 2, total: 94}（test_stage_counts_increment_via_schedule_records PASS）
- [x] resume identity 6 字段（含 schedule_sha256）+ fail-closed（test_fail_closed_on_checkpoint_load_error / test_fail_closed_on_identity_mismatch PASS）
- [x] budget_recommendation stage-weighted + MAIN_DECISION_REQUIRED + efficient / conservative + null refinement / verification（test_efficient_conservative_scenarios_with_timing / test_no_timing_returns_decision_required PASS）
- [x] Q2 degeneration direct vs sequence exact comparison (test_direct_vs_sequence_anchor_first_bomb PASS)
- [x] repeated determinism 真实 re-eval full payload match (test_same_anchor_evaluated_twice_full_payload_match PASS)
- [x] 1 次 targeted reconstruction Q3 call = 3.788169 s (复评 matches 原始 3.788169 s)
- [x] 52 / 52 tests pass
- [x] outputs/q3/q3_pilot_summary.json 含 evidence_corrections block + 6 字段 identity 拆分
- [x] RESULT1.XLSX NOT GENERATED
- [x] Q1/Q2 files NOT modified
- [x] v1 contract snapshot preserved
- [x] original Pilot log / checkpoint preserved
- [x] TASK_006-P2 NOT STARTED
- [x] result1.xlsx 不存在
- [x] outputs/submission/ 未改

## 停止条件

本轮（`TASK_006-P0P1-CLOSURE`）完成后立即停止。

不自动：
- 启动 Audit CC；
- 启动 Hermes；
- 开始 TASK_006-P2 / Formal Search；
- 生成 result1.xlsx；
- 进入 Q4；
- Ready；
- merge。

由 MAIN / 用户显式决定 TASK_006-P2 立项、result1.xlsx 启动、budget 选定 (efficient 730 s vs conservative 1114 s).