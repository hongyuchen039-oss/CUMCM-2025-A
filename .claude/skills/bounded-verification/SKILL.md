---
name: bounded-verification
description: 用于数值建模、优化搜索、长时间 evaluator、测试预算、clean-HEAD 正式运行、checkpoint/resume、预算耗尽和结果可信等级管理。
---

# Bounded Verification Skill v0.1

## 1. Purpose

约束高代价数值任务的运行方式，使每个 expensive task 在启动前就冻结
evaluation budget / wall-clock budget / checkpoint path / 验收等级，并在运行
中提供 fail-closed gates + 实时 heartbeat + BUDGET-EXHAUSTED taxonomy，
避免：

- 静默运行 30 分钟以上无法判断状态；
- 预算耗尽后冒充收敛 / 全局最优；
- 局部代码修改触发整段昂贵阶段重跑；
- Reviewer 复制 Builder 整套测试浪费资源。

## 2. When to use

任何满足以下条件之一的任务必须显式引用本 Skill：

- 包含 Python evaluator（fine 圆柱遮蔽 / 单弹策略评估）；
- 需要 3x1000 / NxM 多 seed 搜索；
- 需要 bounded refinement / coordinate search；
- 候选生成器 + 真实评估器 ≥ 100 evaluations；
- wall-clock > 60 秒；
- 涉及 result1/2/3.xlsx 候选冻结。

普通文档 / README / 单元测试 / import smoke 不需要引用。

## 3. Task classification

每个 task 必须属于以下类型之一：

| 类型 | 范围 | 触发 FULL regression |
|---|---|---|
| DOCS | 仅改 docs | 否 |
| FAST | 仅改局部代码 / 单文件 | 否 |
| TASK | 模块级（多文件） | 视修改范围决定 |
| EXPENSIVE | 多 seed 搜索 / refinement / evaluator > 60s | 见 §4（共享数学核心修改 / formal-canonical result freeze / result1/2/3.xlsx freeze / 最终论文一致性 / MAIN 显式授权） |
| GOVERNANCE | Skill / harness / 治理文件 | 否 |

## 4. Test tiers (FAST / TASK / FULL)

| 层级 | 时长 | 范围 | 触发 |
|---|---|---|---|
| FAST | 5-30 秒 | py_compile / import / 小单元测试 / 最小 smoke | 每个改动后 |
| TASK | ≤ 10 分钟 | 真实 integration smoke / checkpoint / resume / task-specific harness | 任务里程碑 |
| FULL | 不限时 | 全量 unittest discover | 仅 milestone 触发 |

FULL 仅在以下 milestone 触发（统一规则，不因 task type 不同而漂移）：

- 共享数学核心修改（`src/q1_*.py` / `src/q2_*.py` / `src/q3_*.py` 等）。
- formal / canonical result freeze（任何 best-known → FORMAL_RESULT_VERIFIED 的晋升）。
- result1.xlsx / result2.xlsx / result3.xlsx 提交物冻结。
- 最终论文一致性审计。
- MAIN 明确授权。

普通文档或局部补丁不得触发 FULL。EXPENSIVE 任务如果只是运行 evaluator 而不涉及上述任何一项，
也不触发 FULL。

## 5. Required task contract

每个 expensive task 必须在启动前冻结并写入 `work/task_context.json`。
文件格式是 **真实 JSON**，不是 YAML。

`work/task_context.json` 由两层组成：

### 5.1 Outer Harness schema v1（必须）

外层字段由 `scripts/verify_task_context.py` 强制校验（v1 已知字段）：

```
schema_version                 : int = 1
task_id                        : str
repository_full_name           : str
worktree_path                  : str
branch                         : str
expected_head                  : 40-char sha
base_branch                    : str
base_sha                       : 40-char sha
pr_number                      : int | null
pr_head_branch                 : str
allowed_modified_paths         : list[str]
allowed_untracked_paths        : list[str]
forbidden_paths                : list[str]
```

以下字段当前由 v1 Harness **忽略**（未知字段保留），

但本 Skill 要求每个 expensive task **必须填**：

```
bounded_verification           : object  (see §5.2)
```

未知附加字段由 Harness v1 默默保留；如果未来 Harness 升级为 v2，
这些字段会按新 schema 校验。**本轮不扩建 Harness。**

### 5.2 bounded_verification nested block（必须）

```
bounded_verification:
  goal                          : str
  task_type                     : DOCS | FAST | TASK | EXPENSIVE | GOVERNANCE
  acceptance_level              : EXPERIMENTAL | BUDGET_LIMITED_BEST_KNOWN
                                   | FORMAL_RESULT_VERIFIED
  fast_tests                    : list[str]
  task_tests                    : list[str]
  full_regression_trigger       : bool
  max_test_wall_clock_seconds   : int
  max_expensive_evaluations     : int
  max_run_wall_clock_seconds    : int
  checkpoint_path               : str
  resume_identity_fields        : list[str]
  output_artifacts              : list[str]
  result_claim                  : str
  stop_condition                : str
```

### 5.3 Validation split（重要）

- 外层 Harness schema v1 由 `verify_task_context.py` 强制校验（FAIL = CONTEXT_INVALID）。
- `bounded_verification` 子对象由本 Skill 强制要求；Harness v1 当前
  不校验 `bounded_verification` 字段；其正确性靠 **Builder 自检 +
  独立 Audit 复核**。
- **不得声称** `verify_task_context.py` 已自动校验预算字段。
- 模板见 `templates/task-contract.md`。**不得先运行后补预算。**

### 5.4 Harness v1 path semantics

外层 schema v1 中的三个 path 列表字段

```
allowed_modified_paths
allowed_untracked_paths
forbidden_paths
```

**仅接受精确路径或真实目录前缀**：

- 精确文件路径，例如 `"configs/q3_search_pilot_v1.json"`；
- 真实目录前缀（带末尾 `/`），例如 `"outputs/q3/"`。

**不接受任何通配符**：

- `*`、`**`、`?`、`[]` 通配符；
- glob / fnmatch / 正则语义。

判定要点：

- `"outputs/q3/"`（带尾部斜杠）= 授权其子路径；
- `"outputs/q3/**"`（带通配）= **不接受**；
- `"src/q3_*.py"`、`"src/q1_*.py"` 模板风格路径 = **不接受**。

Builder 在写入 `work/task_context.json` 前必须字面检查所有 path：
`'*' / '?' / '[' / ']'` 任一出现即拒绝。

### 5.5 Phase contract lifecycle

每个 task 由若干 phase 组成（例如 P0/P1 pilot → P2 formal_search
→ P3 refinement → P4 verification → P5 audit → P6 freeze）。每个
phase 必须在 `bounded_verification` 下重新冻结下列字段：

```
phase_id                    : str, e.g. "TASK_006-P0P1"
contract_version            : int, 从 1 单调递增
target_acceptance_level     : EXPERIMENTAL / BUDGET_LIMITED_BEST_KNOWN / FORMAL_RESULT_VERIFIED
contract_snapshot_path      : 归档上一 phase 合同的副本路径
```

Phase 内 frozen fields（**不得在 phase 运行中修改**）：

- `phase_id`
- `contract_version`
- `target_acceptance_level`
- `max_expensive_evaluations`
- `max_run_wall_clock_seconds`
- `checkpoint_path`
- `resume_identity_fields`

进入下一 phase 的强制顺序（**phase-boundary re-freeze**）：

1. 当前 phase 必须先达到 `stop_condition`。
2. MAIN 审查当前 phase 的 evidence（result level + checkpoint
   identity + 不冒充声明 + 测试层级）。
3. MAIN 显式授权下一 phase。
4. 形成新的 committed HEAD（包含新 phase 的预算调整 / schema 微调）。
5. `phase_id` 更新。
6. `contract_version` +1。
7. 新预算数字重新冻结（基于上一 phase 实测）。
8. 新 `checkpoint_path`（不得与历史 phase 共享）。
9. 保存旧合同 snapshot 到 `contract_snapshot_path`。
10. 更新 `work/task_context.json`。
11. Harness 通过（`CONTEXT_VALID_*`）后才可启动下一 phase。

**明确**：phase-boundary re-freeze 不是 mid-run budget mutation。

**禁止**：在 P0/P1 pilot 阶段期间自动跳入 P2 formal_search /
refinement / result*.xlsx 冻结。

详细字段定义见 `templates/task-contract.md` §"Phase contract lifecycle"。

## 6. Evaluation budget

正式运行前必须冻结 `bounded_verification.max_expensive_evaluations`：

| 阶段类别 | TASK_005 历史参考（reference example，并非全项目固定上限） |
|---|---|
| pilot multi-seed | seed 数量 × 单 seed 上限（TASK_005 = 3 × 1000）|
| cross-seed finalist re-eval | ≤ 30 candidates（TASK_005 historical） |
| bounded refinement | ≤ 32 evaluations（TASK_005 historical） |
| clean-head verification | ≤ 5 evaluator calls（TASK_005 historical） |
| independent Audit | ≤ 6 evaluator calls（TASK_005 historical） |

**重要说明**：

- 上述数字仅作为 TASK_005 项目阶段的 reference example；
- Q3 / Q4 / Q5 等后续 task **必须**根据 pilot 实测 + checkpoint
  evidence 重新冻结 task-specific 数值；
- task contract 中实际填写的 `max_expensive_evaluations` 优先于
  上表；
- 不得自动沿用 TASK_005 数字；
- 不得声称这些数字是"全项目上限"。

每次新 evaluation 启动前调用 `_check_budget()`：

- 已完成数 ≥ MAX → raise `EvaluationBudgetExhausted`
- 原子写 checkpoint
- 抛异常并保留 `BUDGET_LIMITED_BEST_KNOWN` 状态
- 不静默继续

## 7. Wall-clock budget

正式运行前必须冻结 `bounded_verification.max_run_wall_clock_seconds`：

| 阶段类别 | TASK_005 历史参考（reference example，并非全项目固定上限） |
|---|---|
| pilot multi-seed | ≤ 3600 s（TASK_005 historical） |
| bounded refinement | ≤ 2100 s（TASK_005 historical） |
| clean-head verification | ≤ 300 s（TASK_005 historical） |

**重要说明**：

- 上述数字仅作为 TASK_005 项目阶段的 reference example；
- Q3 / Q4 / Q5 等后续 task **必须**根据 pilot 实测重新冻结
  task-specific 数值；
- task contract 中实际填写的 `max_run_wall_clock_seconds` 优先于
  上表；
- 不得自动沿用 TASK_005 数字；
- 不得声称这些数字是"全项目上限"。

每次新 evaluation 启动前调用 `_check_deadline()`：

- elapsed ≥ MAX → raise `WallClockGateHit`
- 原子写 checkpoint
- 抛异常并保留 best-known 状态

## 8. Clean committed HEAD requirement

正式结果必须在干净 committed HEAD 上产生。Clean 的判定标准：

- 无 tracked modifications（`git diff --name-only` / `git diff --cached --name-only` 为空）；
- 无 staged files（`git diff --cached --name-only` 为空）；
- 无 conflicts（`git status --porcelain` 不包含 `UU` / `AA` 之类）；
- 无未授权的 deleted / renamed files（必须在
  `allowed_modified_paths` / `forbidden_paths` 授权范围内变更）；
- 仅允许 Harness `allowed_untracked_paths` 授权的 untracked 路径
  （典型 = `work/`）；
- Harness 状态必须有效：
  `python scripts/verify_task_context.py --context work/task_context.json`
  返回 `CONTEXT_VALID_CLEAN` 或 `CONTEXT_VALID_AUTHORIZED_DIRTY`。

若任何 untracked 路径不在 `allowed_untracked_paths` 列表中，Harness
返回 `CONTEXT_INVALID`，必须立即停止，不得 reset / stash / clean /
rebase / 改写 context 绕过。

正式结果（canonical Q candidate / final P1 evidence / freeze-ready
state）不得在 dirty / non-clean HEAD 上产生。

## 9. Harness integration

所有 expensive task 必须依赖：

`python scripts/verify_task_context.py --context work/task_context.json`

任一不符立即停止。不得 reset / stash / clean / rebase / 改写 context 绕过。

## 10. Long-run visibility

长任务必须使用：

```
set -o pipefail
python -u script.py 2>&1 | tee work/log.log
rc=${PIPESTATUS[0]}
exit "$rc"
```

`print(..., flush=True)` 每 evaluation 一行。

禁止：

- 使用 `tail` 隐藏实时输出
- 静默运行数十分钟
- 吞掉 pipeline 前端退出码
- 仅凭文件暂时没有更新判断"卡死"

Heartbeat 至少包含：

```
stage
completed / budget
best_observed
elapsed
remaining
ETA
checkpoint
```

## 11. Checkpoint / resume identity

每个 evaluation 后原子写入 checkpoint：

- tmpfile + fsync + os.replace
- 含 fields：
  - head_sha
  - config_sha256
  - parent_candidate
  - current_best_candidate
  - current_best_duration
  - level / sweep
  - evaluations_completed
  - evaluated_candidate_identities
  - elapsed_seconds
  - status

resume 校验：head_sha / config_sha256 / parent_candidate 任一 mismatch →
raise `ResumeIdentityMismatch` → BLOCKED，不静默 fallback。

## 12. Failure and stop taxonomy

固定以下状态：

| 状态 | 含义 | 后续动作 |
|---|---|---|
| `CONTEXT_INVALID` | task_context 校验失败 | 立即停止，不绕过 |
| `FAST_TESTS_PASS` | FAST 层级测试通过 | 继续 TASK |
| `TASK_TESTS_PASS` | TASK 层级测试通过 | 继续 EXPENSIVE |
| `FULL_REGRESSION_PASS` | 全量回归通过 | 可晋升 canonical |
| `CODE_TEST_FAILED` | 代码或测试失败 | 必须修复，不可晋升 |
| `EXECUTION_EVIDENCE_INVALID` | 执行证据与声明不符 | BLOCKED |
| `RUN_SYSTEM_ERROR` | 运行时异常 | 必须修复 |
| `WALL_CLOCK_GATE_HIT` | 时间上限命中 | 保留已完成部分 |
| `EVALUATION_BUDGET_EXHAUSTED` | 评估预算耗尽 | best-known 记录 |
| `BUDGET_LIMITED_BEST_KNOWN` | 预算受限 best-known | 不冒充 converged |
| `LOCAL_CONVERGENCE_NOT_ESTABLISHED` | 局部收敛未建立 | 不冒充 optimum |
| `FORMAL_RESULT_VERIFIED` | 正式结果验证通过 | 可晋升 |
| `NOT_A_PROVEN_GLOBAL_OPTIMUM` | 全局最优未证明 | 必须显式声明 |

必须明确：**`BUDGET_EXHAUSTED != CODE_FAILED`**。

BUDGET_EXHAUSTED 是资源限制，不阻塞晋升到 BUDGET_LIMITED_BEST_KNOWN。
CODE_FAILED 阻塞一切晋升，必须修复后重跑。

## 13. Candidate-pool rule

所有已经实际评估且合法的候选必须进入 candidate pool。

若新候选优于当前 best：

- 更新 best-observed；
- 不得因为它来自"扰动"而继续保留旧 baseline；
- 是否继续搜索由预算决定；
- 不得自动扩大预算；
- 预算结束可冻结为 `BUDGET_LIMITED_BEST_KNOWN`；
- 不得自动声明 local / global optimum。

## 14. Result credibility levels

强制使用以下等级（不得跳跃）：

```
EXPERIMENTAL       (单次尝试，未交叉验证)
  → BUDGET_LIMITED_BEST_KNOWN   (预算受限 best-known)
    → FORMAL_RESULT_VERIFIED     (正式结果已验证，独立 Audit 通过)
      → ANALYTICAL_OPTIMUM       (解析证明全局最优)
```

每级必须显式记录 promoted-by / verified-by / pending-by，禁止伪造跳跃。

## 15. Builder / Audit / Hermes boundaries

| 角色 | 写入 | 验证 |
|---|---|---|
| Builder | 写代码 / 写 docs / 写 summary | 不自我审计 |
| Audit CC | 只读 | 复算 + 身份链校验 |
| Hermes | 只读 | Git / PR / SHA / push 核验 |
| MAIN | 合并决策 | 转 Ready / merge |

Builder 不得自我晋升。
Audit 不得修改代码。
Hermes 不得 commit / push / merge。
MAIN 不直接参与代码施工。

## 16. Anti-patterns

禁止：

- 自动扩大预算
- 每次运行全量测试
- 自动 merge / 自动 Ready
- 自动启动下一阶段
- 静默运行数十分钟
- 跨任务共享 checkpoint 路径
- 静默 fallback（resume mismatch 时静默忽略）
- 把 BUDGET_EXHAUSTED 写成 CODE_FAILED
- 用 coverage 阈值代替严格遮蔽判据
- 16 项 one-var 改善后仍宣称"局部最优"
- 把 best-known 直接晋升为 VERIFIED 而无独立 Audit

## 17. Final reporting

每个 task 完成后必须按 `templates/final-report.md` 格式汇报，含：

- 做了什么
- 为什么这样做
- 当前结果
- Git / HEAD / PR
- 测试分级（FAST / TASK / FULL）
- 真实运行预算
- checkpoint 路径 + identity
- result level（含 verified / not-established 维度）
- 风险
- 不冒充声明
- 用户决定
- 停止状态

## 18. Mandatory stop condition

完成后立即停止。不自动合并；不自动进入下一阶段；不擅自扩大任务。
由 MAIN 显式发出下一任务授权才能继续。

---

## Three stress scenarios (manual演练, no new test framework)

### Scenario A: 一行代码修改

期望：FAST only，不运行 FULL。

### Scenario B: 长时间数值搜索

期望：evaluation budget + wall-clock budget + checkpoint + 实时输出 +
pipefail 全部启用。

### Scenario C: 预算耗尽但出现更优候选

期望：更新 best-observed；状态为 `BUDGET_LIMITED_BEST_KNOWN`；不自动扩大预算；
不声明局部或全局最优。

记录三项均 PASS。