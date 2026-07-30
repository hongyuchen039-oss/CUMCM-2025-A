# Task Contract Template

> 每个 expensive task 必须在启动前冻结并填写本模板。
> 输出文件必须是 **真实 JSON**（不是 YAML），保存为
> `work/task_context.json`。`scripts/verify_task_context.py` 会
> 校验外层 Harness schema v1 已知字段（FAIL 即 CONTEXT_INVALID）；
> `bounded_verification` 子对象由本 Skill 强制要求，目前靠
> Builder 自检 + Audit CC 复核，Harness v1 不自动校验该子对象。
> 不得先运行后补预算, 不得中途修改已冻结字段。

---

## Harness v1 path semantics（先于模板）

外层 schema v1 中的三个 path 列表字段：

```
allowed_modified_paths
allowed_untracked_paths
forbidden_paths
```

**仅接受**：

- 精确文件路径，例如 `"configs/q3_search_pilot_v1.json"`；
- 真实目录前缀（带末尾 `/`），例如 `"outputs/q3/"`。

**不接受**：

- `*`、`**`、`?`、`[]` 通配符；
- `glob` / `fnmatch` / 正则表达式；
- 任何非字面比较的语义。

判定要点：

- `"outputs/q3/"`（带尾部斜杠）= 授权其子路径；
- `"outputs/q3/**"`（带通配）= **不接受**；
- `"src/q3_*.py"`、`"src/q1_*.py"` 等模板风格路径 = **不接受**。

Pilot/任何 task 在填写 path 列表前必须字面检查
`'*' not in path and '?' not in path and '[' not in path and ']' not in path`。

---

## 完整 JSON 模板（Pilot phase，TASK_006-P0P1）

```json
{
  "schema_version": 1,
  "task_id": "TASK_006",
  "repository_full_name": "hongyuchen039-oss/CUMCM-2025-A",
  "worktree_path": "C:\\Users\\33560\\Desktop\\CUMCM_2025_A",
  "branch": "task/TASK_006-q3-pilot",
  "expected_head": "<40-char commit SHA, 紧跟 latest commit>",
  "base_branch": "main",
  "base_sha": "<40-char commit SHA of main>",
  "pr_number": null,
  "pr_head_branch": "task/TASK_006-q3-pilot",

  "allowed_modified_paths": [
    "src/q3_three_bombs.py",
    "src/q3_search.py",
    "scripts/run_q3.py",
    "tests/test_q3.py",
    "configs/q3_search_pilot_v1.json",
    "outputs/q3/",
    "START_HERE.md",
    "NEXT_TASK.md",
    "MODEL.md",
    "RESULTS.md",
    "README.md"
  ],

  "allowed_untracked_paths": [
    "work/"
  ],

  "forbidden_paths": [
    "src/q1_baseline.py",
    "src/q1_cylinder.py",
    "src/q2_single_bomb.py",
    "src/q2_search.py",
    "outputs/q2/",
    "outputs/submission/",
    "problem/",
    "CLAUDE.md",
    ".claude/"
  ],

  "bounded_verification": {
    "phase_id": "TASK_006-P0P1",
    "contract_version": 1,
    "target_acceptance_level": "EXPERIMENTAL",
    "contract_snapshot_path": "work/task_contracts/TASK_006-P0P1-v1.json",

    "goal": "实现 Q3 三弹 evaluator 和 bounded pilot；测量 evaluator 成本；提交正式预算建议。",
    "task_type": "EXPENSIVE",

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

    "checkpoint_path": "work/q3_pilot/checkpoint.json",
    "resume_identity_fields": [
      "head_sha",
      "config_sha256",
      "parent_candidate"
    ],

    "output_artifacts": [
      "outputs/q3/q3_pilot_summary.json"
    ],

    "result_claim": "EXPERIMENTAL Q3 PILOT / NOT A FORMAL Q3 RESULT / RESULT1.XLSX NOT GENERATED / NOT A PROVEN GLOBAL OPTIMUM",
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
| `task_id` | 与分支名一致 |
| `repository_full_name` | GitHub `<owner>/<repo>` |
| `worktree_path` | 本地绝对路径 |
| `branch` | 当前任务分支 |
| `expected_head` | 该分支当前 commit SHA（40 字符，冻结当下） |
| `base_branch` | 通常 `"main"` |
| `base_sha` | base 分支当时的 commit SHA |
| `pr_number` | 该 task 的 PR 编号，整数或 null |
| `pr_head_branch` | PR 头分支 |
| `allowed_modified_paths` | 精确路径或目录前缀（**无 wildcard**） |
| `allowed_untracked_paths` | 精确路径或目录前缀（**无 wildcard**） |
| `forbidden_paths` | 精确路径或目录前缀（**无 wildcard**） |

### bounded_verification nested（Skill 强制, Harness v1 当前不校验）

| 字段 | 含义 |
|---|---|
| `phase_id` | 当前阶段 ID，例如 `TASK_006-P0P1` |
| `contract_version` | 当前 phase 合同内的版本号，必须从 1 开始单调递增 |
| `target_acceptance_level` | 本阶段目标达到的可信等级（`EXPERIMENTAL` / `BUDGET_LIMITED_BEST_KNOWN` / `FORMAL_RESULT_VERIFIED`） |
| `contract_snapshot_path` | 当前合同 snapshot 副本路径，phase 切换时保留历史版本 |
| `goal` | 一句话任务产出 |
| `task_type` | DOCS / FAST / TASK / EXPENSIVE / GOVERNANCE |
| `fast_tests` | FAST 层级运行的 pytest/unittest 模块列表 |
| `task_tests` | TASK 层级运行的测试模块列表 |
| `full_regression_trigger` | true 仅当 milestone 触发（见 SKILL.md §4） |
| `max_test_wall_clock_seconds` | FAST/TASK/FULL 测试墙钟上限 |
| `max_expensive_evaluations` | 该 phase 预算内允许的 evaluator 调用数 |
| `max_run_wall_clock_seconds` | 该 phase 整段运行墙钟上限 |
| `checkpoint_path` | atomic checkpoint 文件路径 |
| `resume_identity_fields` | resume 时强制校验的字段名列表 |
| `output_artifacts` | 写出文件路径列表 |
| `result_claim` | 任务结果声明 + 不冒充字句 |
| `stop_condition` | 何时停止（必须显式） |

---

## Phase contract lifecycle（必须）

### 每 phase 都启动前必须

1. 复制上一 phase 完成的 `contract_snapshot_path`，归档到
   `work/task_contracts/<phase_id>-v<contract_version_prev>.json`。
2. `phase_id`、`contract_version`、`target_acceptance_level`、
   `max_expensive_evaluations`、`max_run_wall_clock_seconds`、
   `checkpoint_path` 都重新评估或重新冻结。
3. 写入新的 `work/task_context.json`，并跑：
   `python scripts/verify_task_context.py --context work/task_context.json`
   → 至少 `CONTEXT_VALID_AUTHORIZED_DIRTY`。

### Phase 内 frozen fields

- 同一 phase 内，下列字段**不得**在运行中修改：
  - `phase_id`
  - `contract_version`
  - `target_acceptance_level`
  - `max_expensive_evaluations`
  - `max_run_wall_clock_seconds`
  - `checkpoint_path`
  - `resume_identity_fields`

### 进入下一 phase 的强制顺序

1. 当前 phase 必须先达到 `stop_condition`。
2. MAIN 审查当前 phase 的 evidence（result level + checkpoint identity
   + 不冒充声明 + 测试层级）。
3. MAIN 显式授权下一 phase。
4. 形成新的 committed HEAD（包含新 phase 的预算调整 / schema 微调）。
5. `phase_id` 更新。
6. `contract_version` +1。
7. 新预算数字重新冻结（基于上一 phase 实测）。
8. 新 `checkpoint_path`（不得与历史 phase 共享）。
9. 保存旧合同 snapshot 到 `contract_snapshot_path`。
10. 更新 `work/task_context.json`。
11. Harness 通过（`CONTEXT_VALID_*`）后才可启动下一 phase。

**明确**：这叫 phase-boundary re-freeze，不是 mid-run budget mutation。

**禁止**：在 P0/P1 pilot 阶段期间自动跳入 P2 formal_search / refinement /
result*.xlsx 冻结。

---

## Pilot 阶段明确禁止（防止越级）

Pilot (`target_acceptance_level = EXPERIMENTAL`) 阶段明确禁止：

- 写 `target_acceptance_level = FORMAL_RESULT_VERIFIED`。
- 写 `output_artifacts` 含 `outputs/submission/result1.xlsx`。
- 声称 `result1.xlsx` 已生成 / 已提交。
- 写入正式 `Q3 production budget`（仅允许 pilot 实测预算）。
- 声称 `formal search` 已授权 / 已运行。

Pilot 阶段只能产出 EXPERIMENTAL 级别 evidence + 真实预算建议。

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

Path lists 在写入 `work/task_context.json` 前必须字面检查无 wildcard
（`scan path for '*' / '?' / '[' / ']'`），否则 Harness 不会拦截但
未来 v2 版本会 FAIL。

---

## 任务特定预算（task-specific budget）

任务特定的 evaluator 预算数字 **必须** 在 `bounded_verification` 内重新
冻结，**不得**自动沿用历史数字。SKILL.md §6/§7 列出的 30 / 32 / 5 / 6 /
2100 / 300 等仅作为 **TASK_005 historical reference example**，不是
全项目固定上限，也不是全 phase 通用上限。每个 phase 必须重新冻结。

---

## Forbidden patterns

- 把 YAML 风格文本保存为 `work/task_context.json`（必须是 JSON）。
- 启动时未填写 `bounded_verification.max_expensive_evaluations` 或
  `bounded_verification.max_run_wall_clock_seconds`。
- 启动时未填写 `bounded_verification.phase_id` /
  `bounded_verification.contract_version` /
  `bounded_verification.target_acceptance_level` /
  `bounded_verification.contract_snapshot_path`。
- 用 `cli_overrides=` 在运行中临时改预算。
- 同一 `checkpoint_path` 被多个 phase 共享。
- 任意时刻 `bounded_verification.resume_identity_fields` 与历史
  checkpoint 不一致仍强行 resume。
- 在 dirty worktree 上产生 canonical 结果。
- `bounded_verification.acceptance_level` 缺省未填。
- `bounded_verification.stop_condition` 未写明。
- `allowed_*_paths` / `forbidden_paths` 中出现 `*` / `**` / `?` /
  `[]` 等通配符。
- 自动从 P0/P1 pilot 阶段进入 P2 formal / freeze。
- 自动沿用 TASK_005 的预算数字而不重新冻结。
