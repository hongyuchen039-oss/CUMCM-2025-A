# TASK_007-P0/P1 FINAL SEMANTIC AND HASH-SCOPE FIX

> 唯一当前门是 **TASK_007-P0/P1 FINAL SEMANTIC AND HASH-SCOPE FIX**: 对 PR #14
> Delta Audit 报告（object = `2f3a38a5af867569b23cc9bed958cf1a8d4b5b10`, verdict =
> `CHANGES_REQUIRED`, open findings = D1 / D2 / D3 / D4）的最终 P0/P1 文本级定向修复。
>
> **不**实现 Q4 evaluator、**不**创建 Q4 测试、**不**运行 Q4 evaluator、
> **不**运行 pilot / search / benchmark、**不**生成 result2.xlsx、
> **不**启动 Audit full rerun / Hermes、**不** Mark Ready、**不** merge、
> **不**启动 TASK_007-P2A / P2B / P3 / P4 / P5、**不**启动 TASK_008。
>
> 本轮最高状态: **TASK_007-P0/P1 FINAL SEMANTIC AND HASH-SCOPE FIX COMPLETE** /
> Q4 IMPLEMENTATION NOT STARTED / RESULT2.XLSX NOT GENERATED /
> P2A NOT STARTED / P2B NOT STARTED / P3 NOT STARTED / P4 NOT STARTED /
> P5 NOT STARTED / SEEDS NOT FROZEN / BUDGET NOT FROZEN /
> PILOT BUDGET NOT FROZEN / Audit (full rerun) NOT STARTED / Hermes NOT STARTED.

## 阶段状态

| 阶段 | 状态 |
|---|---|
| TASK_006-P3 (Q3 result1.xlsx) | **COMPLETE + MERGED** (PR #13 → main @ `2839151c9ef027c200f84ec342e17d43874ca254`) |
| TASK_007-P0/P1 (FINAL SEMANTIC AND HASH-SCOPE FIX) | **FINAL FIX COMPLETE — FINAL MICRO DELTA RECHECK PENDING — THIS PR** |
| TASK_007-P2A (Q4 evaluator + 单元测试) | **NOT STARTED** |
| TASK_007-P2B (tiny bounded pilot + runtime calibration) | **NOT STARTED** |
| TASK_007-P3 (Q4 formal bounded search) | **NOT STARTED** |
| TASK_007-P4 (candidate closure) | **NOT STARTED** |
| TASK_007-P5 (result2.xlsx write + round-trip) | **NOT STARTED** |
| TASK_008 | **NOT STARTED** |

## 起点身份 (FINAL FIX 启动)

| 字段 | 值 |
|---|---|
| 起始 HEAD (main) | `2839151c9ef027c200f84ec342e17d43874ca254` (PR #13 mergeCommit) |
| branch | `task/TASK_007-q4-result2` |
| base_branch | `main` |
| base_sha | `2839151c9ef027c200f84ec342e17d43874ca254` |
| 上一轮 CONSOLIDATED FIX commit (Delta Audit basis HEAD) | `2f3a38a5af867569b23cc9bed958cf1a8d4b5b10` |
| 上一个 FIX commit (Audit basis HEAD) | `6f52c39c14b957d466f39248fcbfa8fae923a234` |
| 上上一个 commit (PLAN) | `217985bd4f03a1e023d37e896c4035c1a58f515f` |
| 本轮 FINAL SEMANTIC FIX commit | (本轮生成, 第四个普通 commit, 非 amend, 非 squash) |
| task_id | `TASK_007-P0P1-FINAL-SEMANTIC-HASH-FIX` |
| phase_id | `TASK_007-P0P1` |
| contract_version | 3 (v3 canonical 替换 v2 superseded；v1 immutable) |
| pr_number | 14 |
| pr_state_target | open, draft=true, merged=false, mergeable=true |
| pr_commits_target | 4 (PLAN + FIX + CONSOLIDATED FIX + FINAL SEMANTIC FIX) |
| pr_title | "TASK_007: freeze Q4 three-drone strategy contract" |
| First full Audit verdict | `CHANGES REQUIRED` (object `6f52c39...`) |
| Delta Audit verdict | `CHANGES REQUIRED` (object `2f3a38a...`) |
| Delta Audit open findings | D1, D2, D3, D4 |
| current_action | `FINAL_SEMANTIC_AND_HASH_SCOPE_FIX` |
| next_gate | `FINAL_MICRO_DELTA_RECHECK` |
| worktree | `C:\Users\33560\Desktop\CUMCM_2025_A` |
| repository | `hongyuchen039-oss/CUMCM-2025-A` |

## 本轮范围 (FINAL SEMANTIC FIX, NOT IMPLEMENTATION)

### Delta Audit 阻塞项 (本轮关闭)

**D1 — Q2 valid/status 映射错误**: 冻结完整 status → valid → Q4 聚合语义映射表。

| Q2 status | Q2 valid | Q4 聚合语义 |
|---|---:|---|
| `invalid` | `false` | Q4 candidate 返回 `valid=false, status="invalid"` |
| `pruned_zero` | `true` | 合法零贡献，intervals 为空；Q4 仍可 `valid=true` |
| `zero_window` | `true` | 合法零贡献，intervals 为空；Q4 仍可 `valid=true` |
| `ok` | `true` | 使用真实 intervals 参加三机 union |

明确：
- `pruned_zero` **不得**导致 Q4 invalid；
- `zero_window` **不得**导致 Q4 invalid；
- 二者都是 Q2 evaluator 的正常、合法、零收益结果；
- system error 与以上四个 status **完全分离**，不属于 Q2 status；
- 三个 Q2 调用正常结束后, **仅当**至少一个真实返回是
  `(valid=false, status="invalid")` 时, Q4 才返回 invalid；
- `pruned_zero`、`zero_window` 与其他合法 evaluation 可以共同计算 union。

**D2 — identity hash scope 不明确及 contract hash 自引用**: 冻结所有 hash 字段的精确
计算范围。

- 统一字段后缀 `_sha256`，所有正式 identity hash 均为 lowercase 64-character
  SHA-256 hex digest；
- **不得**把 Git blob OID 当作 SHA-256 结果；
- 正式 code identity 算法: **SHA-256 over exact Git blob content bytes at
  `execution_head_sha`**；
  - 冻结 `execution_head_sha`；通过 `git rev-parse <sha>:<path>` 解析 blob；
    通过 `git cat-file blob <blob_oid>` 读取 blob 原始 bytes；
    **不**做换行转换 / **不**做 UTF-8 解码再编码 / **不**删除 trailing whitespace；
    直接 SHA-256；
  - 保存: repository path / `execution_head_sha` / `git_blob_oid` / `blob_size` /
    SHA-256；
  - **不得**使用工作树文件 bytes（Windows autocrlf / 编码设置可能改变 bytes）；
  - **不得**通过 PowerShell 文本管道读取后再 hash；
- 正式 code identity 字段（范围为整个 Git blob，**不**做函数文本抽取）：
  - `q1_baseline_code_sha256` = SHA-256 of exact Git blob content bytes of
    `src/q1_baseline.py` at `execution_head_sha`；
  - `q1_cylinder_code_sha256` = SHA-256 of exact Git blob content bytes of
    `src/q1_cylinder.py` at `execution_head_sha`；
  - `q2_single_bomb_code_sha256` = SHA-256 of exact Git blob content bytes of
    `src/q2_single_bomb.py` at `execution_head_sha`；
  - `q3_three_bombs_code_sha256` = SHA-256 of exact Git blob content bytes of
    `src/q3_three_bombs.py` at `execution_head_sha`（整个 Git blob,
    **不**做函数文本抽取 — 函数抽取会引入 AST / 注释 / 缩进 / 边界定义差异）；
  - `q4_evaluator_code_sha256` = SHA-256 of exact Git blob content bytes of
    `src/q4_three_drones.py` at `execution_head_sha`；该文件尚不存在前
    **不得**生成正式 q4_evaluation_id；
- `q4_config_sha256` 必须基于 `q4_config_identity_payload`，payload 仅含影响
  evaluator 结果或调用语义的**有效**配置字段；不含日志路径 / 生成时间 / 主机名等
  **非结果**字段；拥有 `q4_config_schema_version`；使用 MODEL.md canonical JSON 规则；
  **不**包含 `q4_config_sha256` 自身；
- `cylinder_sample_profile_sha256` 必须基于 `cylinder_sample_profile_identity_payload`，
  payload 固定 schema: `cylinder_sample_profile_schema_version` /
  `sample_level` / `sampling_algorithm_id` / `effective_profile_parameters`；
  `effective_profile_parameters` 必须包含 Q1 cylinder sampler 实际读取、并会影响
  采样点或权重的全部最终有效参数；不得只保存 `sample_level = "medium"` 而省略
  medium 实际展开后的参数；任一影响结果的 sampler 参数未进入 payload: **fail closed**,
  不得生成正式 ID；payload **不**包含 `cylinder_sample_profile_sha256` 自身；
- `q4_model_contract_sha256` 解决自引用：算法 =
  `SHA256_CANONICAL_JSON_EXCLUDING_SELF_FIELD_V1`；
  - 读取 v3 JSON object；从 top level 删除字段 `q4_model_contract_sha256`；
  - 递归 canonical normalization（`-0.0` → `0.0`；tuple → stable JSON array；
    NaN / Inf 禁止）；serialize canonical JSON
    (UTF-8 / `ensure_ascii=False` / `sort_keys=True` /
    `separators=(",", ":")` / `allow_nan=False`)；
  - 对 canonical JSON bytes 计算 SHA-256；写入 v3 顶层
    `q4_model_contract_sha256`；
  - 验证：再次删除该字段并重算，**必须**等于存储值；
  - **不**对包含自身 hash 值的完整文件 bytes 直接求 hash；
  - `contract_hash_excluded_fields = ["q4_model_contract_sha256"]`；
- 旧字段名（无 `_sha256` 后缀的旧 code identity 字段名）已废止，不得进入正式
  evaluation identity。

**D3 — heading radians 约束来源标签错误**: 把 `[官]` 改为 `[约定]`。

- 旧（错误）：`[官]` Q4 heading 原始字段约束: `0 ≤ heading_rad_fyi < 2π`；
- 新（正确）：`[约定]` Q4 heading 的内部弧度表示合同: `0 ≤ heading_rad_fyi < 2π`；
- 该内部 radians 表示等价映射自 `FACTS.md §13.4 [官]` 方向角规则
  (0° ≤ heading_deg < 360°)；
- 官方模板规定方向角单位和范围；内部使用 radians 是工程表示；`[0, 2π)` 用于
  消除周期重复；该内部表示**不是**官方原文；
- identity 使用 prevalidation 后的 raw radians 字段；
- Q2 normalized heading **不**替换 identity candidate field。

**D4 — P2A 零真实调用与 P2B 预算依据矛盾**: 删除所有"基于 P2A 实际 evaluator 性能" /
"基于 P2A 实测" / "P2A runtime calibration" 措辞。P2A real Q4 evaluator calls = 0，
**不**存在真实 Q4 runtime；P2A 的 stub / mock / fixture wall-clock **不得**用作 P2B
或 P3 预算依据。

冻结正确流程：

```
P2A:
  - 实现 evaluator；
  - 实现 tests；
  - stub / injected evaluator / fixture；
  - 静态和受控测试；
  - real Q4 evaluation = 0；
  - 不产生可用于预算估计的真实 Q4 wall-clock。
  - stub/mock wall-clock: 不得用作 P2B / P3 预算依据。

P2B self-budget (首次真实 Q4 call 前冻结):
  MAIN 根据以下依据冻结一个保守的小型安全预算：
    (a) Q3 历史实测 wall-clock；
    (b) 单次 Q4 正常路径包含 3 次 Q2 evaluator；
    (c) 12 维 candidate 的静态复杂度；
    (d) 当前机器和 Python 环境；
    (e) 保守安全上界；
    (f) 用户明确授权。
  P2B self-budget 不得依赖不存在的 P2A 真实 runtime。

P2B runtime calibration (self-budget 内):
  真实 Q4 candidate wall-clock / 真实 single-bomb call wall-clock /
  valid / invalid / zero / system-error 比例 / checkpoint 开销 / resume 开销。

P3 formal budget (P2B 结束后):
  MAIN 根据 P2B 真实 runtime 冻结 P3 formal budget；
  可以且必须依赖 P2B 真实 runtime；
  不得混用 P2B pilot budget 与 P3 formal budget。
```

调用预算措辞修正：
- `max_attempted_single_bomb_calls = 3 × max_q4_evaluations` 是**硬上限**,
  **不是**实际调用数恒等式；
- 实际 attempted calls 可能更少（prevalidation invalid: 0 / 第 1 或 2 次 system
  error 提前停止 / wall-clock stop / 用户中止 / checkpoint stop）；
- 正常且全部完成的单个 Q4 evaluation: `attempted = 3`, `completed = 3`；
- 不得把预算上限与实际调用会计混为一谈。

### 已关闭 (N3 / N4, 不重开)

- **N3 — v1 historical overwrite + v2 canonical 治理**: v1 immutable (SHA / size
  本轮前后完全一致); v2 superseded (immutable, 本轮不修改); v3 canonical
  (absorbs v2 + D1-D4);
- **N4 — P3/P4 artifact 所有权**: P3 = `work/q4_search/` (P3 own checkpoint);
  P4 = `work/q4_candidate_closure/` (P4 own checkpoint); P4 input_manifest 绑定
  P3 SHAs; P5 不修改 P3 / P4 checkpoint。

## 显式不做 (本轮 boundary)

- ❌ 修改 `main` / 在 main 直接 commit / 修改 origin；
- ❌ 修改 Q1 / Q2 / Q3 任何 source / foundation；
- ❌ 创建 `src/q4_three_drones.py`；
- ❌ 创建 `tests/test_q4.py`；
- ❌ 运行真实 Q1 / Q2 / Q3 / Q4 evaluator；
- ❌ 运行 smoke / pilot / search / benchmark；
- ❌ 生成 Excel / `workbook.save` / 写盘 result2.xlsx；
- ❌ 修改官方模板 ZIP；
- ❌ 创建 CI / 修改 workflow；
- ❌ 安装任何依赖；
- ❌ 创建额外 tracked 报告；
- ❌ 重新修改 `.gitignore` (本轮 boundary)；
- ❌ 重新修改 `problem/FACTS.md` (本轮 boundary, Audit 已通过)；
- ❌ 重新修改 `work/task_contracts/TASK_007-P0P1-v1.json` (本轮 boundary,
  immutable historical record)；
- ❌ 重新修改 `work/task_contracts/TASK_007-P0P1-v2.json` (本轮 boundary,
  immutable superseded record)；
- ❌ 启动 Audit full rerun (Audit delta recheck 待 MAIN)；
- ❌ 启动 Hermes (MAIN 决定)；
- ❌ Mark Ready / merge；
- ❌ 启动 TASK_007-P2A / P2B / P3 / P4 / P5；
- ❌ 启动 TASK_008；
- ❌ Amend 任何之前的 commit (PLAN / FIX / CONSOLIDATED FIX)；
- ❌ Squash commits；
- ❌ Force push；
- ❌ 使用 `git add .`；
- ❌ 不得声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum / 官方答案
  / Q4 IMPLEMENTED / Q4 SEARCHED / RESULT2.XLSX GENERATED / Q4 EVALUATOR VALIDATED
  / P2A 启动 / P2B 启动 / P3 启动 / P4 启动 / P5 启动 /
  seeds frozen / budget frozen / pilot budget frozen。

## 身份链 (FINAL SEMANTIC FIX 锁定)

| 字段 | SHA / 值 |
|---|---|
| 起始 HEAD (main) | `2839151c9ef027c200f84ec342e17d43874ca254` |
| PLAN commit (原, 未 amend) | `217985bd4f03a1e023d37e896c4035c1a58f515f` |
| 第一个 FIX commit (Audit basis HEAD) | `6f52c39c14b957d466f39248fcbfa8fae923a234` |
| 第二个 CONSOLIDATED FIX commit (Delta Audit basis HEAD) | `2f3a38a5af867569b23cc9bed958cf1a8d4b5b10` |
| 本轮 FINAL SEMANTIC FIX commit | (本轮生成, 第四个普通 commit) |
| 起始 phase | `TASK_007-P0P1` |
| contract_version | 3 (v3 canonical; v2 superseded immutable; v1 historical immutable) |
| v1 historical snapshot | `work/task_contracts/TASK_007-P0P1-v1.json` (HISTORICAL_OVERWRITE_RECORDED, immutable) |
| v2 superseded contract | `work/task_contracts/TASK_007-P0P1-v2.json` (SUPERSEDED_CORRECTED_CONTRACT, immutable) |
| v3 canonical contract | `work/task_contracts/TASK_007-P0P1-v3.json` (CANONICAL_FINAL_P0P1_CONTRACT) |
| v3 contract_hash_algorithm | `SHA256_CANONICAL_JSON_EXCLUDING_SELF_FIELD_V1` |
| v3 contract_hash_excluded_fields | `["q4_model_contract_sha256"]` |
| pr_commits_target | 4 (PLAN + FIX + CONSOLIDATED FIX + FINAL SEMANTIC FIX) |
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

详细验证日志: `work/q4_foundation/result2_template_readonly_check.json` (untracked, 已刷新 FACTS 状态)。

## 当前 result level

- `TASK_007 Q4 FOUNDATION CONTRACT — CONTRACT_ONLY`
- `FINAL SEMANTIC AND HASH-SCOPE FIX COMPLETE` (本轮范围)
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
| `TASK_007-P0P1` | Q4 foundation preflight + contract freeze + CONTRACT CORRECTION + CONSOLIDATED AUDIT FIX + FINAL SEMANTIC AND HASH-SCOPE FIX (本轮) |
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
| `MODEL.md` | TASK_007 Q4 THREE-DRONE FOUNDATION CONTRACT 章节 (D1 status 映射 / D2 hash scope + algorithm / D3 heading 标签 / D4 budget flow + v3 canonical 治理) |
| `NEXT_TASK.md` | 重写为本轮 FINAL SEMANTIC AND HASH-SCOPE FIX scope |

## 本轮允许的 untracked 文件 (work/)

| 文件 | 类型 |
|---|---|
| `work/task_context.json` | task_context (TASK_007-P0P1-FINAL-SEMANTIC-HASH-FIX) |
| `work/task_contracts/TASK_007-P0P1-v1.json` | 历史覆盖记录 (本轮 immutable, 不修改) |
| `work/task_contracts/TASK_007-P0P1-v2.json` | superseded corrected contract (本轮 immutable, 不修改) |
| `work/task_contracts/TASK_007-P0P1-v3.json` | canonical final P0/P1 contract (absorbs v2 + D1-D4, NEW) |
| `work/q4_foundation/result2_template_readonly_check.json` | 模板 read-only 验证日志 |
| `work/pr_14_contract_correction_body.md` | PR #14 描述 (本轮更新) |

## 关闭条件 (本门)

- ✅ Harness `verify_task_context.py` → `CONTEXT_VALID_CLEAN` 或
  `CONTEXT_VALID_AUTHORIZED_DIRTY`
- ✅ `work/task_context.json` 含 `task_id = TASK_007-P0P1-FINAL-SEMANTIC-HASH-FIX` /
  `starting_head = 2f3a38a` / `audit_delta_object = 2f3a38a` /
  `audit_delta_verdict = CHANGES_REQUIRED` / `open_findings = [D1, D2, D3, D4]` /
  `canonical_contract = TASK_007-P0P1-v3.json` /
  `max_expensive_evaluations = 0` / `result2_generated = false` /
  `next_gate = FINAL_MICRO_DELTA_RECHECK`
- ✅ `work/task_contracts/TASK_007-P0P1-v1.json` SHA / size 本轮前后**完全一致**
  (HISTORICAL_OVERWRITE_RECORDED, immutable)
- ✅ `work/task_contracts/TASK_007-P0P1-v2.json` SHA / size 本轮前后**完全一致**
  (SUPERSEDED_CORRECTED_CONTRACT, immutable)
- ✅ `work/task_contracts/TASK_007-P0P1-v3.json` 含
  `contract_version = 3` / `status = CANONICAL_FINAL_P0P1_CONTRACT` /
  `supersedes = TASK_007-P0P1-v2.json` /
  `audit_basis_head = 2f3a38a` / `next_gate = FINAL_MICRO_DELTA_RECHECK` /
  `contract_hash_algorithm = SHA256_CANONICAL_JSON_EXCLUDING_SELF_FIELD_V1` /
  `contract_hash_excluded_fields = ["q4_model_contract_sha256"]` /
  `q4_model_contract_sha256` (算法 = exclude self field, NOT hashing complete
  v3 bytes including own hash)
- ✅ `MODEL.md` 包含 D1 status mapping (invalid→valid=false; pruned_zero/zero_window/ok
  → valid=true) + D2 hash scope (`_sha256` 后缀; exact Git blob content bytes;
  `execution_head_sha` / `git_blob_oid` / `blob_size`) + D2
  `SHA256_CANONICAL_JSON_EXCLUDING_SELF_FIELD_V1` + `cylinder_sample_profile_identity_payload`
  含 `effective_profile_parameters` + `q4_config_identity_payload` 排除非结果字段 +
  D3 `[约定]` Q4 heading 内部弧度表示 + D4 P2A real Q4 calls = 0 → 不作预算依据 /
  P2B self-budget 基于 Q3 历史 + 12 维静态 + 保守上界 + 用户授权 / P3 budget 基于
  P2B 真实 runtime
- ✅ `MODEL.md` 不存在 `q3_union_helper_code_sha` / `[官] Q4 heading 原始字段约束` /
  `基于 P2A 实际` / `基于 P2A 实测` / `P2A runtime calibration` / `Q4 union = NO`
- ✅ `NEXT_TASK.md` current gate = TASK_007-P0/P1 FINAL SEMANTIC AND HASH-SCOPE FIX,
  next gate = FINAL MICRO DELTA RECHECK
- ✅ `NEXT_TASK.md` 不写 P2A / P2B / P3 / P4 / P5 / Hermes / Audit full rerun
  STARTED
- ✅ 单次 commit "FIX: close TASK_007 final semantic and hash scope gaps"
  (第四个普通 commit, 非 amend, 非 squash, 非 force)
- ✅ push 到 origin
- ✅ PR #14 仍为 Draft, 描述更新为 FINAL SEMANTIC AND HASH-SCOPE FIX 状态
- ✅ PR #14 验证: state=OPEN, draft=true, merged=false, mergeable=true,
  head=新 FINAL SEMANTIC FIX commit, commits=4, base=2839151c
- ✅ 累计 changed files = {.gitignore, MODEL.md, NEXT_TASK.md, problem/FACTS.md}
  (4 个, 不得出现第五个)

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
- ❌ 冻结 seeds / wall-clock / evaluation cap / search config / pilot self-budget /
  任何 P2B / P3 数字
- ❌ 冒充 Q4 IMPLEMENTED / Q4 SEARCHED / RESULT2 GENERATED / P2A 启动 /
  P2B 启动 / P3 启动 / P4 启动 / P5 启动 / FORMAL_RESULT_VERIFIED /
  官方答案

## 下一门 (待 MAIN 显式授权)

**FINAL MICRO DELTA RECHECK** — 验证本轮 FINAL SEMANTIC AND HASH-SCOPE FIX 的
D1 / D2 / D3 / D4 修复是否完整, 是否仍 CONTRACT_ONLY, 是否不冒充实现 / 搜索 /
写盘 / pilot / runtime calibration / P2A / P2B / P3 / P4 / P5 / Audit full rerun
/ Hermes / Ready / merge / TASK_008。

MAIN 显式授权后才能进入:
- TASK_007-P2A (Q4 evaluator + 单元测试, real Q4 calls = 0)

PR #14 整个 TASK_007 期间保持 Draft, 不合并 (单 PR 规则)。
