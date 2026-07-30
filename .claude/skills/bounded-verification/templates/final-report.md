# Final Report Template

> 每个任务完成后必须按本格式汇报。
> 不得只贴文件名; 不得用日志代替解释。

---

## A. 做了什么

- 列出本任务完成的所有具体步骤。
- 引用 commit SHA 链 (例如: PLAN abc1234 → WORKING def5678 → VERIFIED ghi9012)。
- 引用 artifact 路径 (但不展开内容)。

## B. 为什么这样做

- 解释选用的方法 / 预算 / 验收等级依据。
- 引述对应 Skill 或文档章节 (如
  `.claude/skills/bounded-verification/SKILL.md §6`)。
- 解释为何拒绝其他备选方案。

## C. 当前结果

- 列出关键数值结果。
- 给出可信等级 (例如:
  `EXPERIMENTAL` / `BUDGET_LIMITED_BEST_KNOWN` / `FORMAL_RESULT_VERIFIED`)。
- 引用 artifact 中的关键字段。

## D. Git / HEAD / PR

```
HEAD branch       : task/<TASK_xxx>-<short-name>
HEAD sha          : <commit SHA>
Base branch       : main
Base sha          : <main HEAD SHA when branch was cut>
PR number         : <#> 或 None
PR state          : Open / Draft / Ready / Merged
PR URL            : <github url>
push status       : local = remote = PR head
changed files (vs base) : <list>
force-pushed      : NO
amended           : NO
```

## E. 测试分级

| Layer | 范围 | 结果 | 触发原因 |
|---|---|---|---|
| FAST | <列出命令> | PASS / FAIL | <每个改动后自动> |
| TASK | <列出命令> | PASS / FAIL / N/A | <仅模块修改触发> |
| FULL | <列出命令> | PASS / FAIL / SKIPPED | <仅 milestone 触发> |

## F. 真实运行预算

```
MAX_EXPENSIVE_EVALUATIONS  : <冻结值>
actual_evaluations_used    : <实际>
MAX_RUN_WALL_CLOCK         : <冻结值, 秒>
actual_wall_clock_used     : <实际, 秒>
budget_gate_hit            : <true / false>
wall_clock_gate_hit        : <true / false>
heartbeat_log_path         : <work/log.log 或类似>
```

## G. Checkpoint + identity

```
CHECKPOINT_PATH            : <路径>
head_sha                   : <commit SHA>
config_sha                 : <config SHA 或 refinement_config_sha256>
parent_candidate           : <4-tuple / 8-tuple>
current_best_candidate     : <最新 best>
evaluations_completed      : <整数>
checkpoint_identity_ok     : <true / false>
```

## H. Result level — Result attribution split (重要)

`verified_by` 字段已被废除，原因是它混合了 Builder 测量 / 数学独立
审查 / Git 状态核验 / MAIN 推广授权四个角色。改为五个 **职责互斥**
的字段，**每个字段只能由对应角色填写**：

```
declared_level              : EXPERIMENTAL
                            | BUDGET_LIMITED_BEST_KNOWN
                            | FORMAL_RESULT_VERIFIED

evidence_generated_by       : <Builder 实际执行的 evaluator / 模型 /
                              artifact 复算的来源 commit SHA>
math_reviewed_by            : <独立 Audit CC 复算 PASS；如未运行 → NOT_RUN>
git_verified_by             : <Hermes 核验 HEAD / SHA / PR / push 状态；
                              如未运行 → NOT_RUN>
promotion_authorized_by     : <MAIN / USER 显式签字授权 promote；
                              如未签字 → PENDING>
pending_by                  : <下一步谁审 — 例如 "Audit CC",
                              "Hermes", "MAIN">
```

### 字段归属锁定

- `evidence_generated_by` 只能由 **Builder** 填写。
  Builder 的自我测试与复算不能成为独立 Audit；只能描述
  "本 Builder 工具体生成的 evidence"，绝不写 "Audit"。
- `math_reviewed_by` 只能由 **独立 Audit CC** 填写。
  数学结果是否可信 = `math_reviewed_by = independent Audit PASS`。
  未运行必须写 `NOT_RUN`，**不得**留空或写 `Builder 测量`。
- `git_verified_by` 只能由 **Hermes** 填写。
  Hermes 只核验 Git / PR / SHA / push 状态；Hermes **不验证**
  数学结果。Git 状态正常 ≠ `math_reviewed_by`。
- `promotion_authorized_by` 只能由 **MAIN / USER** 填写。
  没有显式签字授权，**任何**等级不得 promote。
- `pending_by` 描述下一角色，由 Builder 在汇报末尾填写。

### 角色与字段不允许互填

| 角色 | 可写的字段 | 禁止写的字段 |
|---|---|---|
| Builder | `evidence_generated_by`、`pending_by` | `math_reviewed_by`、`promotion_authorized_by` |
| 独立 Audit CC | `math_reviewed_by` | `evidence_generated_by`、`git_verified_by`、`promotion_authorized_by` |
| Hermes | `git_verified_by` | `evidence_generated_by`、`math_reviewed_by`、`promotion_authorized_by` |
| MAIN / USER | `promotion_authorized_by` | `evidence_generated_by`、`math_reviewed_by`（除非同时是 Audit 签字人）|

### `FORMAL_RESULT_VERIFIED` 的必要条件

`declared_level = FORMAL_RESULT_VERIFIED` 必须同时满足：

- `math_reviewed_by = independent Audit CC PASS`
- `git_verified_by = Hermes PASS`
- `promotion_authorized_by = MAIN / USER`（显式签字）

缺少任一项，**最高只能声明**：

- `BUDGET_LIMITED_BEST_KNOWN`（已通过独立数学复核 + Git 核验，
  但未到 promotion 签字）；或
- `EXPERIMENTAL`（仅 Builder evidence，未到独立数学复核）。

`ANALYTICAL_OPTIMUM` 需额外有解析证明 + MAIN 单独裁决，不在本模板
涵盖。

### 未执行项必须显式标记

任何上述字段若对应动作未执行，必须写：

- `NOT_RUN`（动作尚未触发）；
- `PENDING`（动作已指派但未完成）；
- `NOT_APPLICABLE`（任务类型不适用，例如 DOCS-only 任务无
  `math_reviewed_by` 必要）。

留空 / N/A / TBD 均视为违规。

## I. 已建立的可信维度

- 列出确实 PASS 的维度。
- 引用 audit summary / verifier summary 的字段名作为证据。

## J. 未建立的维度 (不冒充)

- 列出 *明确* 未建立 / 未证明的维度, 包括但不限于:
  - `local_convergence_established` (除本任务显式声明外, 几乎永远 NO)
  - `global_optimum` (除非解析证明)
  - `official_answer` (除非题目材料确认)

## K. 风险与 open question

- 列出在运行中观察到的所有不确定性 / 异常 / 边界。
- 列出用户或 MAIN 必须知道的折中决定。

## L. 不冒充声明 (verbatim)

```
本任务不冒充以下任一陈述:
- VERIFIED GLOBAL OPTIMUM
- FINAL OFFICIAL ANSWER
- ANALYTICAL OPTIMUM
- LOCAL CONVERGENCE ESTABLISHED (除非本任务显式测量并声明 PASS)
- 全项目 / 全 Q 题范围验证
```

## M. 用户决定

- 用户或 MAIN 在本任务范围内必须显式裁决的事项。
- 推荐的下一步 (但不由 MAIN 自动启动)。

## N. 停止状态

```
STOP_AT                  : <task 完成 / checkpoint / 用户暂停 / budget exhausted / failure>
NEXT_TASK_LAUNCHED       : <NO — 必须由 MAIN 显式授权>
PR_AUTO_MERGED           : <NO — 必须由 MAIN / 用户显式决定>
RESULT_AUTO_PROMOTED     : <NO — 必须由独立 Audit / 用户显式裁决>
```

---

## Reporting hygiene

- 数值必须从 artifact 中读出, 不得手抄记忆。
- 禁止无证据的含糊近似（`[redacted]` / `[assume]` / `应该` 等）。
- **允许** 使用 `约` 或 `≈` 表示近似，**但必须同时提供**：
  - 原始精确值；
  - 使用的 rounding / approximation rule（例如："四舍五入到 9 位有效位"、
    "相对差异 = |ΔT| / baseline × 100%, 截断到 3 位小数"）；
  - 该近似所对应的 artifact 字段名、JSON 路径或计算来源行号。
- 不冒充声明不得省略。
- 不在汇报中写"测试都通过"而不分层; 必须 FAST / TASK / FULL 分别报告。
- 不在汇报中写"全局最优"或"verified"而无论证。
- **角色归属**：见 §H 的字段归属锁定。Builder / 独立 Audit CC /
  Hermes / MAIN 必须各填各的字段；不得代签。
