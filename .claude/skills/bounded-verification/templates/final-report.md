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

## H. Result level

```
declared_level             : <EXPERIMENTAL / BUDGET_LIMITED_BEST_KNOWN / FORMAL_RESULT_VERIFIED>
verified_by                : <Audit CC / Hermes / 自身测量>
pending_by                 : <下一步谁审>
```

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
