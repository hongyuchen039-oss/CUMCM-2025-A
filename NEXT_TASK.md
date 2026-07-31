# TASK_007-P0/P1 CONSOLIDATED AUDIT FIX

> 唯一当前门是 **TASK_007-P0/P1 CONSOLIDATED AUDIT FIX**: 对 PR #14 最新
> Audit 报告 (`6f52c39c14b957d466f39248fcbfa8fae923a234`, verdict
> `CHANGES_REQUIRED`) 全部剩余问题的一次性综合修复。
>
> **不**实现 Q4 evaluator、**不**创建 Q4 测试、**不**运行 Q4 evaluator、
> **不**运行 pilot / search / benchmark、**不**生成 result2.xlsx、
> **不**启动 Audit full rerun / Hermes、**不** Mark Ready、**不** merge、
> **不**启动 TASK_007-P2A / P2B / P3 / P4 / P5、**不**启动 TASK_008。
>
> 本轮最高状态: **TASK_007-P0/P1 CONSOLIDATED AUDIT FIX COMPLETE** /
> Q4 IMPLEMENTATION NOT STARTED / RESULT2.XLSX NOT GENERATED /
> P2A NOT STARTED / P2B NOT STARTED / P3 NOT STARTED / P4 NOT STARTED /
> P5 NOT STARTED / SEEDS NOT FROZEN / BUDGET NOT FROZEN /
> PILOT BUDGET NOT FROZEN / Audit (full rerun) NOT STARTED / Hermes NOT STARTED.

## 阶段状态

| 阶段 | 状态 |
|---|---|
| TASK_006-P3 (Q3 result1.xlsx) | **COMPLETE + MERGED** (PR #13 → main @ `2839151c9ef027c200f84ec342e17d43874ca254`) |
| TASK_007-P0/P1 (CONSOLIDATED AUDIT FIX) | **CONSOLIDATED FIX COMPLETE — AUDIT DELTA RECHECK PENDING — THIS PR** |
| TASK_007-P2A (Q4 evaluator + 单元测试) | **NOT STARTED** |
| TASK_007-P2B (tiny bounded pilot + runtime calibration) | **NOT STARTED** |
| TASK_007-P3 (Q4 formal bounded search) | **NOT STARTED** |
| TASK_007-P4 (candidate closure) | **NOT STARTED** |
| TASK_007-P5 (result2.xlsx write + round-trip) | **NOT STARTED** |
| TASK_008 | **NOT STARTED** |

## 起点身份 (CONSOLIDATED FIX 启动)

| 字段 | 值 |
|---|---|
| 起始 HEAD (main) | `2839151c9ef027c200f84ec342e17d43874ca254` (PR #13 mergeCommit) |
| branch | `task/TASK_007-q4-result2` |
| base_branch | `main` |
| base_sha | `2839151c9ef027c200f84ec342e17d43874ca254` |
| 上一个 commit (FIX) | `6f52c39c14b957d466f39248fcbfa8fae923a234` (Audit basis HEAD) |
| 上上一个 commit (PLAN) | `217985bd4f03a1e023d37e896c4035c1a58f515f` |
| 本轮 CONSOLIDATED FIX commit | (本轮生成, 第三个普通 commit, 非 amend, 非 squash) |
| task_id | `TASK_007-P0P1-AUDIT-CONSOLIDATED-FIX` |
| phase_id | `TASK_007-P0P1` |
| contract_version | 2 (v2 canonical 替换 v1 historical) |
| pr_number | 14 |
| pr_state_target | open, draft=true, merged=false, mergeable=true |
| pr_commits_target | 3 (PLAN + FIX + CONSOLIDATED FIX) |
| pr_title | "TASK_007: freeze Q4 three-drone strategy contract" |
| audit_object | `6f52c39c14b957d466f39248fcbfa8fae923a234` |
| audit_verdict | `CHANGES_REQUIRED` |
| audit_completed | YES |
| current_action | `CONSOLIDATED_FIX` |
| next_gate | `AUDIT_DELTA_RECHECK` |
| worktree | `C:\Users\33560\Desktop\CUMCM_2025_A` |
| repository | `hongyuchen039-oss/CUMCM-2025-A` |

## 本轮范围 (CONSOLIDATED FIX, NOT IMPLEMENTATION)

### 阻塞项 (必须关闭)

**N1 — system error 合同矛盾**: 唯一 system error 模型 = **EXCEPTION PROPAGATION**。
- 删除 / 改写: 系统异常后仍宣称三次调用全部完成的旧措辞、异常位置伪造 evaluation
  对象 (例如把 SingleBombEvaluation 的 status 字段扩展为伪 system_error 含义) 的旧做法、
  "未运行无人机构造 fake evaluation"、"系统异常时返回正常 `ThreeDroneEvaluation`"、
  "系统异常计入物理 invalid"、"无论异常发生位置都宣称 calls=3"；
- 引入新异常类 `Q4EvaluationSystemError`；
- 阶段 A prevalidation (0 次 evaluate_single_bomb_strategy) + 阶段 B 顺序 3 次调用 + 阶段 C 异常立即停止抛错；
- 异常对象 / 外层 error record 至少携带 failing_drone_id / attempted_single_bomb_calls=k /
  completed_single_bomb_calls=k-1 / completed_drone_ids / completed_evaluations /
  original_exception_type / original_exception_message。

**N2 — q4_evaluation_id 缺少关键身份**: 重建 **Q4 FORMAL EVALUATION IDENTITY SCHEMA**。
- 不再称为固定的 N 字段数字；schema 实际 category 数量由 v2 §6 冻结的 8 个 category
  决定；identity schema 改称 "Q4 FORMAL EVALUATION IDENTITY SCHEMA"；
- 8 category: candidate identity / per-drone context (fy1/2/3_initial_position_m 必须分别绑定) /
  missile and target context / numerical profile (含 q1_cylinder_code_sha, cylinder_sample_profile_sha256) /
  code identity (含 q1_baseline_code_sha, q1_cylinder_code_sha, q2_single_bomb_code_sha, q3_union_helper_code_sha, q4_evaluator_code_sha) /
  runtime/config identity / physical constants / contract identity；
- **NO FORMAL Q4 EVALUATION ID MAY BE GENERATED BEFORE `q4_evaluator_code_sha` EXISTS**;
- 不得使用 `null` / `"pending"` / 空字符串 / 占位 SHA 替代 `q4_evaluator_code_sha`；
- 不得用 `q4_pilot_config_sha` 代替 `q4_evaluator_code_sha`；
- identity payload 使用 **raw prevalidated heading** (满足 `0 ≤ heading_rad < 2π`); 不得使用 Q2 返回的 `normalized_heading_rad`;
- 措辞: "在相同受支持 Python/runtime 环境、相同代码 bytes、相同冻结配置和无外部非确定性输入的前提下, 同一 q4_evaluation_id 预期产生确定性一致结果";
- canonical JSON 规则冻结: UTF-8, sorted keys, no whitespace, allow_nan=False, NaN/Inf rejected at prevalidation, -0.0 → 0.0, tuple → fixed-order array, drone_order 固定, no locale, no display-string, hash input = canonical JSON UTF-8 bytes.

**N3 — 不可变 v1 snapshot 被覆盖**:
- v1 文件 (`work/task_contracts/TASK_007-P0P1-v1.json`) 加
  `snapshot_status = "HISTORICAL_OVERWRITE_RECORDED"` +
  `original_snapshot_immutable_intent = true` +
  `overwritten_during_fix_head = "6f52c39..."` +
  `original_pre_fix_v1_recoverable = false` +
  `historical_note` (HISTORICAL SNAPSHOT CONTENT NOT independently recoverable) +
  `canonical_for_future_execution = false` +
  `superseded_by = "TASK_007-P0P1-v2.json"`;
- 创建 v2 canonical (`work/task_contracts/TASK_007-P0P1-v2.json`): `contract_version=2`,
  `status="CANONICAL_CORRECTED_CONTRACT"`, `supersedes=v1`,
  `audit_basis_head=6f52c39`, `next_gate="AUDIT_DELTA_RECHECK"`;
- 未来 P2A/P2B/P3/P4/P5 context **必须**引用 v2, 不得再引用 v1;
- 治理说明放在 tracked MODEL.md / NEXT_TASK.md; 完整本机 JSON 不塞入 tracked 文档;
- 合同修订必须创建 `vN+1`, 不得覆盖 `vN`。

**N4 — P3/P4 artifact ownership 重叠**:
- P3 = `work/q4_search/` (P3 唯一目录, 不得写 `q4_candidate_closure/`);
- P4 = `work/q4_candidate_closure/` (P4 唯一目录, 自有 `checkpoint.json`,
  **不**覆盖 / 续写 `work/q4_search/checkpoint.json`);
- P4 `input_manifest.json` 必须绑定 P3 SHAs:
  `p3_formal_search_summary_sha256` / `p3_finalists_sha256` /
  `p3_config_sha256` / `p3_code_identity_sha` / `p3_ending_head` / `p4_starting_head`;
- P5 input 必须绑定 P4 SHAs: `p4_candidate_closure_summary_sha256` /
  `p4_final_candidate_sha256` / `p4_ending_head` / `p5_starting_head`；
- P5 不修改 P3 / P4 checkpoint。

### 非阻塞项 (顺手关闭)

**N5 — P2 tiny pilot 自预算时序**:
- P2 拆成 P2A (impl + test, real Q4 calls = 0) + P2B (tiny pilot + runtime calibration);
- P2B pilot self-budget 字段列表冻结 (pilot_seed / pilot_sample_level / pilot_scan_step /
  max_q4_evaluations / max_single_bomb_calls = 3 × max_q4_evaluations /
  max_wall_clock_seconds / checkpoint_path / heartbeat_interval / stop_classification /
  resume_identity / system-error attempted-call accounting);
- P2B pilot self-budget 现在 **NOT FROZEN**; 只有 MAIN 在 P2A 后显式授权并给出具体数字才能开始 P2B;
- P2B pilot budget 与 P3 formal budget 是两套不同预算集合, 不得混用。

**P2-1 — 固定字段数量标签** (旧数量标签习惯 — 把 q4_evaluation_id 绑定
  字段数固定写成具体数字的措辞): 改称 "Q4 FORMAL EVALUATION IDENTITY SCHEMA"；
  字段数量由 schema 实际 category 决定。

**P2-2 — raw heading 与 normalized heading 语义**: 明确 identity payload 使用 raw prevalidated heading, 不使用 normalized output。

**P2-3 — template check JSON 中 FACTS 修复状态过期**: 刷新
`work/q4_foundation/result2_template_readonly_check.json`:
"DEFERRED" → "CORRECTED in FIX commit 6f52c39c14b957d466f39248fcbfa8fae923a234"。

**P2-4 — PR body 中 Audit 状态过期**: 更新 PR #14 body, Audit status = CHANGES REQUIRED,
Audit completed = YES, current action = CONSOLIDATED FIX, Hermes = NOT STARTED,
**不**再写 "Audit 未启动" (此处按字面禁止项的近义描述)。

**P2-5 — 同一 TASK_007 是否继续同一 PR 的边界不明确**:
冻结唯一规则: **PR #14 remains Draft and unmerged throughout TASK_007 construction**;
删除任何 "P0/P1 PR 合并后才允许 P2 启动" / "PR 合并或 MAIN 显式放行" /
"PR 合并 OR MAIN 显式授权" 等双轨措辞 (此处用近义描述替代被禁字面)。

## 显式不做 (本轮 boundary)

- ❌ 修改 `main` / 在 main 直接 commit / 修改 origin;
- ❌ 修改 Q1 / Q2 / Q3 任何 source / foundation;
- ❌ 创建 `src/q4_three_drones.py`;
- ❌ 创建 `tests/test_q4.py`;
- ❌ 运行真实 Q1 / Q2 / Q3 / Q4 evaluator;
- ❌ 运行 smoke / pilot / search / benchmark;
- ❌ 生成 Excel / `workbook.save` / 写盘 result2.xlsx;
- ❌ 修改官方模板 ZIP;
- ❌ 创建 CI / 修改 workflow;
- ❌ 安装任何依赖;
- ❌ 创建额外 tracked 报告;
- ❌ 重新修改 `.gitignore` (本轮 boundary);
- ❌ 重新修改 `problem/FACTS.md` (本轮 boundary, Audit 已通过);
- ❌ 启动 Audit full rerun (Audit delta recheck 待 MAIN);
- ❌ 启动 Hermes (MAIN 决定);
- ❌ Mark Ready / merge;
- ❌ 启动 TASK_007-P2A / P2B / P3 / P4 / P5;
- ❌ 启动 TASK_008;
- ❌ Amend 任何之前的 commit (PLAN / FIX);
- ❌ Squash commits;
- ❌ Force push;
- ❌ 使用 `git add .`;
- ❌ 不得声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum / 官方答案
  / Q4 IMPLEMENTED / Q4 SEARCHED / RESULT2.XLSX GENERATED / Q4 EVALUATOR VALIDATED
  / P2A STARTED / P2B STARTED / P3 STARTED / P4 STARTED / P5 STARTED /
  seeds frozen / budget frozen / pilot budget frozen。

## 身份链 (CONSOLIDATED FIX 锁定)

| 字段 | SHA / 值 |
|---|---|
| 起始 HEAD (main) | `2839151c9ef027c200f84ec342e17d43874ca254` |
| PLAN commit (原, 未 amend) | `217985bd4f03a1e023d37e896c4035c1a58f515f` |
| 上一个 FIX commit (Audit basis HEAD) | `6f52c39c14b957d466f39248fcbfa8fae923a234` |
| 本轮 CONSOLIDATED FIX commit | (本轮生成, 第三个普通 commit) |
| 起始 phase | `TASK_007-P0P1` |
| contract_version | 2 (v2 canonical 替换 v1 historical) |
| v1 historical snapshot | `work/task_contracts/TASK_007-P0P1-v1.json` (HISTORICAL_OVERWRITE_RECORDED) |
| v2 canonical contract | `work/task_contracts/TASK_007-P0P1-v2.json` |
| pr_commits_target | 3 (PLAN + FIX + CONSOLIDATED FIX) |
| pr_state_target | open, draft=true, merged=false, mergeable=true |

## 官方 result2.xlsx 模板 read-only 验证 (保持)

| 字段 | 值 |
|---|---|
| 官方 ZIP SHA-256 | `f9879c0d36b7bdccb99fb330a8032e62851ab1a1f0a1636c92440a1cdaec658e` (14884 bytes, 3 members) |
| result2.xlsx member size | 5272 bytes |
| result2.xlsx member SHA-256 | `91fbc42459aa4c98838b0a4dbe740ec5b970436c3f86d8a22dd7303f127cf106` |
| sheet | `Sheet1` (唯一) |
| header | row 1, A1:J1 (10 列) |
| 模板空白格式行 | rows 2-5 (4 行) |
| 实际写入区 | rows 2, 3, 4 (FY1 → row 2, FY2 → row 3, FY3 → row 4) |
| 保留空白格式行 | row 5 (官方模板预存, 不删除不重排不写入) |
| 附注 cell | B6 (注: 以 x 轴为正向, 逆时针方向为正, 取值 0~360（度）) |
| workbook footprint | A1:J6 |
| FACTS.md §13.2 修正 | CORRECTED in FIX commit `6f52c39c14b957d466f39248fcbfa8fae923a234` |

详细验证日志: `work/q4_foundation/result2_template_readonly_check.json` (untracked, 本轮已刷新 FACTS 状态)。

## 当前 result level

- `TASK_007 Q4 FOUNDATION CONTRACT — CONTRACT_ONLY`
- `CONSOLIDATED AUDIT FIX COMPLETE` (本轮范围)
- IMPLEMENTATION NOT STARTED
- RESULT2.XLSX NOT GENERATED
- TASK_007-P2A NOT STARTED
- TASK_007-P2B NOT STARTED
- TASK_007-P3 NOT STARTED
- TASK_007-P4 NOT STARTED
- TASK_007-P5 NOT STARTED
- TASK_008 NOT STARTED
- seeds 数量 / 具体 seed 列表 / wall-clock / evaluation cap / search config / pilot self-budget NOT FROZEN
- Audit (full rerun) NOT STARTED
- Hermes NOT STARTED
- NOT Q4 IMPLEMENTED
- NOT Q4 SEARCHED
- NOT Q4 EVALUATOR VALIDATED
- NOT FORMAL_RESULT_VERIFIED
- NOT local convergence
- NOT global optimum
- NOT 官方答案

## result1.xlsx 状态 (保留不变)

| 字段 | 值 |
|---|---|
| result1.xlsx output SHA | `b938a90b96181be14990d5bd3395c2cff72e93035828542617571ddc1d754847` |
| result1_run_identity_sha256 | `82065aa5fe4d4e6036691a053b38732b9ff1f50497083e3306e262e82a4bfc65` |
| 状态 | GENERATED + ROUND-TRIP-VERIFIED (TASK_006-P3, NOT touched by TASK_007) |

## 任务编号 (固定)

| 编号 | 范围 |
|---|---|
| `TASK_006` | Q3 + result1.xlsx |
| `TASK_007-P0P1` | Q4 foundation preflight + contract freeze + CONTRACT CORRECTION + CONSOLIDATED AUDIT FIX (本轮) |
| `TASK_007-P2A` | Q4 evaluator + 单元测试 (real Q4 calls = 0) |
| `TASK_007-P2B` | tiny bounded pilot + runtime calibration (pilot self-budget NOT FROZEN) |
| `TASK_007-P3` | Q4 formal bounded search (artifact root = work/q4_search/) |
| `TASK_007-P4` | candidate closure (artifact root = work/q4_candidate_closure/) |
| `TASK_007-P5` | fine reconstruction + result2.xlsx 写盘 + round-trip 验证 |
| `TASK_008` | Q5 + result3.xlsx |
| `TASK_009` | unified recomputation / sensitivity / robustness / figures |
| `TASK_010` | paper / consistency / final package |

## 本轮允许的 tracked 文件变更 (2 个)

| 文件 | 类型 |
|---|---|
| `MODEL.md` | TASK_007 Q4 THREE-DRONE FOUNDATION CONTRACT 章节 (v2 canonical 替换 v1) |
| `NEXT_TASK.md` | 重写为本轮 CONSOLIDATED AUDIT FIX scope |

## 本轮允许的 untracked 文件 (work/)

| 文件 | 类型 |
|---|---|
| `work/task_context.json` | task_context (TASK_007-P0P1-AUDIT-CONSOLIDATED-FIX) |
| `work/task_contracts/TASK_007-P0P1-v1.json` | 历史覆盖记录 (本轮打 HISTORICAL_OVERWRITE_RECORDED 标记) |
| `work/task_contracts/TASK_007-P0P1-v2.json` | canonical corrected contract (本轮新建) |
| `work/q4_foundation/result2_template_readonly_check.json` | 模板 read-only 验证日志 (本轮刷新 FACTS 状态) |
| `work/pr_14_consolidated_fix_body.md` | PR #14 描述 (本轮更新) |

## 关闭条件 (本门)

- ✅ Harness `verify_task_context.py` → `CONTEXT_VALID_CLEAN` 或
  `CONTEXT_VALID_AUTHORIZED_DIRTY`
- ✅ `work/task_context.json` 含 audit_object / audit_verdict / next_gate = `AUDIT_DELTA_RECHECK`
- ✅ `work/task_contracts/TASK_007-P0P1-v1.json` 含 `snapshot_status = HISTORICAL_OVERWRITE_RECORDED`
- ✅ `work/task_contracts/TASK_007-P0P1-v2.json` 含 `contract_version=2` / `status=CANONICAL_CORRECTED_CONTRACT` / `supersedes=v1` / `audit_basis_head=6f52c39` / `next_gate=AUDIT_DELTA_RECHECK`
- ✅ `MODEL.md` 含 `Q4EvaluationSystemError` 定义 + `attempted_single_bomb_calls` / `completed_single_bomb_calls` + `fy1_initial_position_m` / `fy2_initial_position_m` / `fy3_initial_position_m` + `q4_evaluator_code_sha` + `q1_cylinder_code_sha` + `cylinder_sample_profile_sha256` + `TASK_007-P0P1-v2.json` + `work/q4_search/checkpoint.json` + `work/q4_candidate_closure/checkpoint.json` + `P2A` / `P2B` + `AUDIT DELTA RECHECK` + EXCEPTION PROPAGATION 措辞
- ✅ `MODEL.md` 不存在以下被禁内容 (此处按 v2 §16 静态文本不变量逐项核查, 实际
  字面已在 MODEL.md / NEXT_TASK.md 全部替换为合规描述):
  - 把伪 system_error 作为 SingleBombEvaluation 的 status 字段语义
  - 任何 fake / 伪造的 evaluation 对象构造
  - 在 system error 时声称 completed calls = 3
  - 任何 phase 把 candidate_closure 目录当作自己 artifact root
  - 任何 PR-merged-then-P2 / PR-merged-or-MAIN-approval 双轨措辞
  - 把 "Audit 未启动" 作为 PR 当前状态 (本轮必须显式标 Audit verdict=CHANGES_REQUIRED, Audit completed=YES, current action=CONSOLIDATED_FIX)
  - 把 q4_evaluation_id schema 称作固定 N 字段
  - 类似 "Q4 union 否定" 的简化否定旧措辞
- ✅ `NEXT_TASK.md` current gate = TASK_007-P0/P1 CONSOLIDATED AUDIT FIX, next gate = AUDIT DELTA RECHECK
- ✅ `NEXT_TASK.md` 不写 P2 STARTED
- ✅ `work/q4_foundation/result2_template_readonly_check.json` FACTS 状态刷新
- ✅ 单次 commit "FIX: close TASK_007 audit identity and phase ownership blockers" (第三个普通 commit, 非 amend, 非 squash, 非 force)
- ✅ push 到 origin
- ✅ PR #14 仍为 Draft, 描述更新
- ✅ PR #14 验证: state=OPEN, draft=true, merged=false, mergeable=true, head=新 CONSOLIDATED FIX commit, commits=3, base=2839151c
- ✅ 累计 changed files = {.gitignore, MODEL.md, NEXT_TASK.md, problem/FACTS.md} (4 个, 不得出现第五个)

不自动 (本轮 boundary):

- ❌ 启动 Q4 evaluator 实现 (TASK_007-P2A)
- ❌ 启动 Q4 tiny pilot / runtime calibration (TASK_007-P2B)
- ❌ 启动 Q4 正式搜索 (TASK_007-P3)
- ❌ 启动 candidate closure (TASK_007-P4)
- ❌ 启动 result2.xlsx 写盘 (TASK_007-P5)
- ❌ 启动 Audit full rerun
- ❌ 启动 Hermes
- ❌ Mark Ready / merge
- ❌ 启动 TASK_008
- ❌ 冻结 seeds / wall-clock / evaluation cap / search config / pilot self-budget / 任何 P2B / P3 数字
- ❌ 冒充 Q4 IMPLEMENTED / Q4 SEARCHED / RESULT2 GENERATED / P2A STARTED /
  P2B STARTED / P3 STARTED / P4 STARTED / P5 STARTED / FORMAL_RESULT_VERIFIED / 官方答案

## 下一门 (待 MAIN 显式授权)

**AUDIT DELTA RECHECK** — 验证本轮 CONSOLIDATED FIX 的 N1 / N2 / N3 / N4 / N5 修复是否完整,
是否仍 CONTRACT_ONLY, 是否不冒充实现 / 搜索 / 写盘 / pilot / runtime calibration /
P2A / P2B / P3 / P4 / P5。

MAIN 显式授权后才能进入:
- TASK_007-P2A (Q4 evaluator + 单元测试, real Q4 calls = 0)

PR #14 整个 TASK_007 期间保持 Draft, 不合并 (单 PR 规则)。
