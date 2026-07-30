# Task Contract Template

> 每个 expensive task 必须在启动前冻结并填写本模板。
> 输出文件必须是 **真实 JSON**（不是 YAML），保存为
> `work/task_context.json`。`scripts/verify_task_context.py` 会
> 校验外层 Harness schema v1 字段（FAIL 即 CONTEXT_INVALID）；
> `bounded_verification` 子对象由本 Skill 强制要求，目前靠
> Builder 自检 + Audit CC 复核，Harness v1 不自动校验该子对象。
> 不得先运行后补预算, 不得中途修改已冻结字段。

---

## 完整 JSON 模板

```json
{
  "schema_version": 1,
  "task_id": "TASK_006",
  "repository_full_name": "hongyuchen039-oss/CUMCM-2025-A",
  "worktree_path": "C:\\Users\\33560\\Desktop\\CUMCM_2025_A",
  "branch": "task/TASK_006-q3-three-bombs",
  "expected_head": "<40-char commit SHA, 紧跟 latest commit>",
  "base_branch": "main",
  "base_sha": "<40-char commit SHA of main>",
  "pr_number": null,
  "pr_head_branch": "task/TASK_006-q3-three-bombs",

  "allowed_modified_paths": [
    "src/q3_*.py",
    "scripts/run_q3_*.py",
    "tests/test_q3_*.py",
    "outputs/q3/**"
  ],

  "allowed_untracked_paths": [
    "work/"
  ],

  "forbidden_paths": [
    "src/q1_*.py",
    "src/q2_*.py",
    "outputs/submission/result*.xlsx"
  ],

  "bounded_verification": {
    "goal": "在 TASK_005 canonical Q2 result 基础上, 用 Q2→Q3 接口复用, 寻找 Q3 三弹串接的最优策略, 并产出 outputs/submission/result1.xlsx.",
    "task_type": "EXPENSIVE",
    "acceptance_level": "FORMAL_RESULT_VERIFIED",

    "fast_tests": [
      "tests.test_q3_three_bombs.smoke"
    ],
    "task_tests": [
      "tests.test_q3_three_bombs.integration"
    ],
    "full_regression_trigger": false,
    "max_test_wall_clock_seconds": 600,

    "max_expensive_evaluations": 96,
    "max_run_wall_clock_seconds": 900,

    "checkpoint_path": "work/q3_three_bombs/checkpoint.json",
    "resume_identity_fields": [
      "head_sha",
      "config_sha256",
      "parent_candidate"
    ],

    "output_artifacts": [
      "outputs/q3/q3_summary.json",
      "outputs/submission/result1.xlsx"
    ],

    "result_claim": "BUDGET_LIMITED_BEST_KNOWN / NOT_A_PROVEN_GLOBAL_OPTIMUM — task-specific",
    "stop_condition": "budget_exhausted OR wall_clock_hit OR manual_stop OR independent_audit_signoff"
  }
}
```

---

## 字段含义

### Outer Harness schema v1（强制）

| 字段 | 含义 |
|---|---|
| `schema_version` | 当前 = 1，固定值 |
| `task_id` | 与分支名一致，例如 `TASK_006` |
| `repository_full_name` | GitHub `<owner>/<repo>` |
| `worktree_path` | 本地绝对路径 |
| `branch` | 当前任务分支 |
| `expected_head` | 该分支当前 commit SHA（40 字符，冻结当下） |
| `base_branch` | 通常 `"main"` |
| `base_sha` | base 分支当时的 commit SHA |
| `pr_number` | 该 task 的 PR 编号，整数或 null |
| `pr_head_branch` | PR 头分支（同 `branch`） |
| `allowed_modified_paths` | 允许修改的路径白名单 |
| `allowed_untracked_paths` | 允许 untracked 的路径（如 `work/`） |
| `forbidden_paths` | 绝对禁止路径 |

### bounded_verification nested（Skill 强制, Harness v1 当前不校验）

| 字段 | 含义 |
|---|---|
| `goal` | 一句话任务产出 |
| `task_type` | DOCS / FAST / TASK / EXPENSIVE / GOVERNANCE |
| `acceptance_level` | EXPERIMENTAL / BUDGET_LIMITED_BEST_KNOWN / FORMAL_RESULT_VERIFIED |
| `fast_tests` | FAST 层级运行的 pytest/unittest 模块列表 |
| `task_tests` | TASK 层级运行的测试模块列表 |
| `full_regression_trigger` | true 仅当 milestone 触发（见 SKILL.md §4） |
| `max_test_wall_clock_seconds` | FAST/TASK/FULL 测试墙钟上限 |
| `max_expensive_evaluations` | 该 task 预算内允许的 evaluator 调用数 |
| `max_run_wall_clock_seconds` | 该 task 整段运行墙钟上限 |
| `checkpoint_path` | atomic checkpoint 文件路径 |
| `resume_identity_fields` | resume 时强制校验的字段名列表 |
| `output_artifacts` | 写出文件路径列表 |
| `result_claim` | 任务结果声明 + 不冒充字句 |
| `stop_condition` | 何时停止（必须显式） |

---

## Validation gate

外层 Harness schema v1：

```bash
python scripts/verify_task_context.py --context work/task_context.json
```

要求: `CONTEXT_VALID_CLEAN` 或 `CONTEXT_VALID_AUTHORIZED_DIRTY`。
`CONTEXT_INVALID` 立即停止, 不得绕过 / 不得 reset / stash / clean /
rebase / 改写 context。

`bounded_verification` 子对象的正确性由 Builder 自检 + 独立 Audit CC
复核保证；**当前 Harness v1 不自动校验**，**不得声称**已自动校验。

---

## 任务特定预算（task-specific budget）

> 任务特定的 evaluator 预算数字 **必须** 在 `bounded_verification` 内重新
> 冻结，**不得**自动沿用历史数字。SKILL.md §6/§7 列出的 30 / 32 / 5 / 6 /
> 2100 / 300 等仅作为 **TASK_005 historical reference example**，不是
> 全项目固定上限。每个新任务必须在 pilot 阶段或 evidence 基础上重新决定：

- `max_expensive_evaluations`
- `max_run_wall_clock_seconds`
- `checkpoint_path`（不得与历史 task 共享）
- `resume_identity_fields`（按需扩展）

---

## Forbidden patterns

- 把 YAML 风格文本保存为 `work/task_context.json`（必须是 JSON）。
- 启动时未填写 `bounded_verification.max_expensive_evaluations` 或
  `bounded_verification.max_run_wall_clock_seconds`。
- 用 `cli_overrides=` 在运行中临时改预算。
- 同一 `checkpoint_path` 被多个任务共享。
- 任意时刻 `bounded_verification.resume_identity_fields` 与历史
  checkpoint 不一致仍强行 resume。
- 在 dirty worktree 上产生 canonical 结果。
- `bounded_verification.acceptance_level` 缺省未填。
- `bounded_verification.stop_condition` 未写明。
- 自动沿用 TASK_005 的预算数字而不重新冻结。
