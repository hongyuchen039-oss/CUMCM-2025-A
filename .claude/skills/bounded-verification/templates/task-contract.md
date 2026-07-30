# Task Contract Template

> 每个 expensive task 必须在启动前冻结并填写本模板,
> 然后保存为 `work/task_context.json`。
> 不得先运行后补预算, 不得中途修改已冻结字段。

---

## Required fields

```yaml
task_id                    : <TASK_xxx — 与分支名一致>
base_sha                   : <commit SHA, 必须是干净 HEAD>
branch                     : <task/<TASK_xxx>-<short-name>>
worktree                   : <绝对路径>

goal                       : <一句话, 明确任务产出>
task_type                  : <DOCS / FAST / TASK / EXPENSIVE / GOVERNANCE>
acceptance_level           : <EXPERIMENTAL / BUDGET_LIMITED_BEST_KNOWN / FORMAL_RESULT_VERIFIED>

## Test tier
FAST_TESTS                 : <pytest 文件或 unittest 模块, 或 None>
TASK_TESTS                 : <同上, 或 None>
FULL_REGRESSION_TRIGGER    : <true 仅当里程碑触发; 默认 false>
MAX_TEST_WALL_CLOCK        : <FAST < 30s, TASK < 600s, FULL 不限>

## Runtime budget
MAX_EXPENSIVE_EVALUATIONS  : <整数, 例如 32 或 5>
MAX_RUN_WALL_CLOCK         : <秒, 例如 2100 或 300>

## Identity
CHECKPOINT_PATH            : <work/<sub>/checkpoint.json, 路径>
RESUME_IDENTITY_FIELDS     :
  - head_sha
  - config_sha
  - parent_candidate
  - evaluations_completed

## Path policy
ALLOWED_PATHS              : <允许修改的路径白名单>
FORBIDDEN_PATHS            : <绝对禁止的路径黑名单>

## Artifacts
OUTPUT_ARTIFACTS           :
  - <写出的总结文件路径>
  - <result*.xlsx 路径 (若适用)>

## Result statement
RESULT_CLAIM               : <目标可信等级 + 不冒充声明>
STOP_CONDITION             : <何时停止 — 不自动进入下一阶段>
```

## Validation gate

```bash
python scripts/verify_task_context.py --context work/task_context.json
```

要求: `CONTEXT_VALID_CLEAN` 或 `CONTEXT_VALID_AUTHORIZED_DIRTY`。
`CONTEXT_INVALID` 立即停止, 不得绕过。

---

## Example (filled)

```yaml
task_id                    : TASK_006
base_sha                   : 5604bb086668ac6a857fc2c5ad86b0b8eb2713ae
branch                     : task/TASK_006-q3-three-bombs
worktree                   : C:\Users\33560\Desktop\CUMCM_2025_A

goal                       : 找到 Q3 三弹串接的最优策略, 生成 result1.xlsx
task_type                  : EXPENSIVE
acceptance_level           : FORMAL_RESULT_VERIFIED

FAST_TESTS                 : tests.test_q3_three_bombs.smoke
TASK_TESTS                 : tests.test_q3_three_bombs.integration
FULL_REGRESSION_TRIGGER    : false
MAX_TEST_WALL_CLOCK        : 600

MAX_EXPENSIVE_EVALUATIONS  : 500
MAX_RUN_WALL_CLOCK         : 3600

CHECKPOINT_PATH            : work/q3_three_bombs/checkpoint.json
RESUME_IDENTITY_FIELDS     : [head_sha, config_sha, parent_candidate]

ALLOWED_PATHS              : [src/q3_*.py, scripts/run_q3*.py, tests/test_q3_*.py]
FORBIDDEN_PATHS            : [src/q1_*.py, src/q2_*.py, result*.xlsx]

OUTPUT_ARTIFACTS           :
  - outputs/q3/q3_summary.json
  - outputs/submission/result1.xlsx

RESULT_CLAIM               : BUDGET_LIMITED_BEST_KNOWN / NOT_A_PROVEN_GLOBAL_OPTIMUM
STOP_CONDITION             : budget_exhausted OR wall_clock_hit OR manual_stop
```

---

## Forbidden patterns

- 启动时未填写 `MAX_EXPENSIVE_EVALUATIONS` 或 `MAX_RUN_WALL_CLOCK`
- 用 `cli_overrides=` 在运行中临时改预算
- 同一 checkpoint 路径被多个任务共享
- 任意时刻 `RESUME_IDENTITY_FIELDS` 与历史 checkpoint 不一致仍强行 resume
- 在 dirty worktree 上产生 canonical 结果
- `acceptance_level` 缺省未填
- `STOP_CONDITION` 未写明
