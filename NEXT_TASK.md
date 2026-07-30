# TASK_006 — Q3 THREE-BOMB MODEL CONTRACT + REAL EVALUATOR + BOUNDED PILOT — P0/P1

> 本轮是 TASK_006 的 **P0/P1** 阶段，**仅**完成：
>
> 1. Q3 三弹数学与工程合同；
> 2. 三弹真实 evaluator；
> 3. 区间并集逻辑与测试；
> 4. checkpoint / resume；
> 5. bounded pilot；
> 6. 实测 evaluator 成本；
> 7. 向 MAIN 提交正式搜索预算建议。
>
> 本轮**不得**：
> - 执行 Q3 Formal Search；
> - 声称获得 Q3 正式结果；
> - 生成 result1.xlsx；
> - 修改官方空白模板；
> - 自动进入 TASK_006-P2；
> - 启动 Q4 / Q5；
> - 自动启动 Audit CC 或 Hermes；
> - 自动 Ready 或 merge。
>
> 最终结果等级只能是：`EXPERIMENTAL`。

## 当前任务边界

- Base: `main` = `007b93d301db73c9a73904337de34d1b4e13467e`
- Branch: `task/TASK_006-q3-three-bombs`
- Phase: `TASK_006-P0P1`
- 启动 Harness `work/task_context.json`（gitignored）

### 本轮允许修改（仅 8 个 tracked 路径 + PR body）

| 路径 | 用途 |
|---|---|
| `src/q3_three_bombs.py` | 三弹 evaluator + bounded pilot CLI |
| `tests/test_q3.py` | Q3 单元测试 |
| `outputs/q3/` | Pilot summary 输出 |
| `START_HERE.md` | 当前阶段页 |
| `NEXT_TASK.md` | 本文（任务边界） |
| `MODEL.md` | Q3 数学与工程合同 |
| `RESULTS.md` | Pilot 实测结果（EXPERIMENTAL only） |
| `README.md` | 工程阶段同步 |

### 禁止修改

`src/q1_baseline.py`、`src/q1_cylinder.py`、`src/q2_single_bomb.py`、`src/q2_search.py`、
`outputs/q2/`、`outputs/submission/`、`problem/`、`scripts/`、`configs/`、`CLAUDE.md`、
`.claude/`、`.gitignore`、任何 `result*.xlsx`、Q1/Q2 单元测试、tracked `work/` 文件、
search module `src/q3_search.py`（TASK_006-P2 才允许新增）。

## Pilot 预算

| 维度 | 上限 | 来源 |
|---|---|---|
| 顶层 Q3 candidate evaluation（pilot cap） | 96 | `bounded_verification.pilot_q3_evaluation_cap` |
| Pilot wall-clock | 900 s | `bounded_verification.pilot_wall_clock_seconds` |
| 真实 TASK 测试 Q3 evaluation 数 | 3 | `bounded_verification.real_task_test_q3_evaluation_cap` |
| 总 expensive evaluation 上限 | 99 | `bounded_verification.max_expensive_evaluations` |
| 测试 wall-clock | 600 s | `bounded_verification.max_test_wall_clock_seconds` |
| Run wall-clock | 1500 s | `bounded_verification.max_run_wall_clock_seconds` |

每次 Q3 candidate evaluation 内部预计调用 3 次单弹 evaluator；
summary 必须同时记录：
- `q3_candidate_evaluations`
- `single_bomb_evaluator_calls`

不得用"96"掩盖实际 3 倍单弹调用量。

## Checkpoint / Resume

- 路径：`work/q3_pilot/checkpoint.json`
- 每个 Q3 candidate evaluation 后原子写入（temp + flush + fsync + os.replace）
- resume 强制校验（任一不匹配立即停止，不静默忽略）：
  - `execution_head_sha`
  - `contract_snapshot_sha256`
  - `q2_single_bomb_code_sha256`
  - `candidate_schema_version`
  - `pilot_config_sha256`

## execution clean-HEAD Gate

Pilot evidence 必须绑定执行时的 clean committed HEAD：
- `execution_head_sha` = Pilot 启动前的 clean committed HEAD
- Pilot 完成后写 summary
- 后续 VERIFIED commit 不得冒充为 execution HEAD

若 Pilot 前代码发生任何新 commit：
- 旧 contract snapshot 不得复用
- `contract_version` +1
- 新 snapshot path（`work/task_contracts/TASK_006-P0P1-v{N}.json`）
- 重新绑定 execution HEAD

## 测试分级

### FAST（≤30 s）
- py_compile；
- interval union（overlapping / disjoint / touching / nested / empty）；
- 非有限输入；
- speed bounds；
- release spacing（exactly 1 s accepted / below 1 s rejected）；
- deterministic evaluation ID；
- candidate serialization；
- budget gate 注入式 cheap test。

### TASK（≤600 s）
- 完整 `tests.test_q3`；
- 最多 3 个真实 Q3 evaluator smoke（`real_task_test_q3_evaluation_cap`）；
- Q2 one-bomb degeneration exact comparison；
- 三弹共享 heading / speed；
- three-bomb union consistency；
- invalid candidate fail-closed；
- pruned_zero 仍是 legal；
- system error 不得变成 zero；
- checkpoint atomic write；
- resume success；
- resume identity mismatch blocked；
- actual evaluation count；
- unique evaluation IDs；
- repeated run determinism。

TASK 测试使用 `coarse profile`，除非某项测试明确需要一次 medium 边界核验。
不得在测试中消耗 fine Pilot 预算。

### FULL

**SKIPPED**。原因：
- 不修改共享 Q1/Q2 数学核心；
- 不冻结正式 Q3 结果；
- 不生成 result1.xlsx；
- MAIN 未授权 FULL。

不得运行：
- `python -m unittest discover`（重跑 Q1/Q2）；
- 重新跑 Q2 3×1000、Q2 16 项扰动、Q2 refinement、Q2 verification、Q2 Audit evaluator。

## Pilot 实时输出

Pilot 必须通过类似命令启动：

```bash
set -o pipefail
python -u -m src.q3_three_bombs --pilot-only 2>&1 |
  tee work/q3_pilot/pilot.log
rc=${PIPESTATUS[0]}
exit "$rc"
```

每个 Q3 evaluation 后输出并 flush（python `-u` + `flush=True`）：

```
[PILOT] stage=<A|B|C|D>
        completed=<n>/<pilot_cap>
        single_bomb_calls=<n>
        candidate_source=<...>
        current_duration=<s>
        best_observed=<s>
        elapsed=<s>
        remaining_budget=<evals>
        remaining_wall_clock=<s>
        ETA=<s>
        checkpoint_path=work/q3_pilot/checkpoint.json
```

禁止：
- 使用 `tail` 隐藏输出；
- 静默运行；
- 吞掉 Python 退出码；
- 仅凭短时间没有输出判断卡死；
- 在 system_error 后继续搜索。

## result1.xlsx 合同（不生成，只冻结语义）

本轮**仅**在 `MODEL.md` 冻结语义，不生成文件。

官方模板（`problem/FACTS.md §13.1`）：
- 10 列（A-J）、3 行；
- A：无人机运动方向，度；
- B：无人机运动速度，m/s；
- C：烟幕干扰弹编号，1~3；
- D–F：投放点 xyz；
- G–I：起爆点 xyz；
- J：有效干扰时长，s；
- +x 为 0°；逆时针为正；范围 0~360°。

冻结 [约定]：
- A / B 三行相同（三枚弹共享 heading_rad 与 speed_mps）；
- C 列为 1、2、3；
- D–I 为每枚弹自己的投放点和起爆点；
- J 列写每枚弹自身有效遮蔽时长；
- 三弹 union 总时长写入 `outputs/q3/q3_pilot_summary.json` 与 `RESULTS.md`；
- union 总时长**不**重复填进三行 J。

必须在 `MODEL.md` 标记 `[约定]`，**不得**冒充官方逐字规定。

本轮禁止：
- 创建 `outputs/submission/result1.xlsx`；
- 复制官方模板；
- 修改官方模板；
- 引入 openpyxl；
- 写 Excel writer。

## 提交序列（本轮目标）

1. **PLAN**: freeze Q3 three-bomb pilot contract（仅文档：`START_HERE.md` /
   `NEXT_TASK.md` / `MODEL.md` / `README.md`）。初始 Harness context 为本地
   文件，不提交。
2. **WORKING**: add Q3 evaluator and bounded pilot（`src/q3_three_bombs.py`
   + `tests/test_q3.py` + 必要文档增量）。在该 commit 后：更新 expected_head、
   Harness、保存 immutable contract snapshot、跑 TASK tests、跑 Pilot。
3. **VERIFIED**: record Q3 pilot runtime evidence（`outputs/q3/q3_pilot_summary.json`
   + `RESULTS.md` + 文档同步）。

若代码或测试失败：
- 停止 Pilot；
- 只修真实失败；
- 使用 `FIX:` 前缀；
- 新 commit 后不得复用旧 snapshot；
- `contract_version` +1；
- 新 snapshot path；
- 重跑受影响检查；
- 不自动扩大预算。

## Draft PR

完成后 push：`task/TASK_006-q3-three-bombs`。

创建唯一 Draft PR：
- Title: `TASK_006: build Q3 three-bomb evaluator and pilot`
- base: `main`
- PR body 必须包含：
  - base SHA；
  - execution HEAD；
  - evidence commit；
  - 8 维合同；
  - 三弹 union 目标；
  - Q2 reuse；
  - tests 分级；
  - 真实 evaluator counts；
  - single-bomb subcall counts；
  - actual wall-clock；
  - checkpoint identity；
  - best Pilot candidate；
  - formal budget recommendation；
  - declared_level = EXPERIMENTAL；
  - NOT A FORMAL Q3 RESULT；
  - RESULT1.XLSX NOT GENERATED；
  - LOCAL CONVERGENCE NOT ESTABLISHED；
  - NOT A PROVEN GLOBAL OPTIMUM；
  - TASK_006-P2 NOT STARTED。

创建 PR 后：
- 将实际 `pr_number` 写入本地 task_context；
- 更新 `expected_head`；
- Harness；
- PR 保持 Draft；
- 不 Ready；
- 不 merge。

## 验收 Gate（本轮必须全部满足）

- P0 模型合同完整（MODEL.md 已冻结 8 维候选 + 共享 heading/speed + 投放间隔 + 单弹合法性 + union 目标 + search-domain pruning [约定] + result1.xlsx J 列 [约定] + Pilot != Formal）；
- 三枚弹共享 heading / speed；
- 投放间隔约束正确（≥ 1 s）；
- Q2 evaluator 被复用而非复制（`evaluate_three_bomb_strategy` 必须调用 `evaluate_single_bomb_strategy`）；
- union 不重复累计；
- one-bomb degeneration exact（Q2 单弹测试通过）；
- FAST PASS；
- TASK PASS；
- FULL SKIPPED；
- `system_error_count = 0`；
- checkpoint / resume PASS；
- identity mismatch fail-closed；
- actual Q3 evaluation count ≤ 99；
- Pilot count ≤ 96；
- real TASK test count ≤ 3；
- Pilot wall-clock ≤ 900 s；
- summary JSON 可重新读取；
- result1.xlsx 不存在；
- `outputs/submission/` 未改；
- Q1/Q2 files 未改；
- PR Draft / unmerged；
- TASK_006-P2 未启动。

Pilot 未跑满 96 但因 wall-clock gate 正常停止：**不是代码失败**。
只要完成：
- profile timing；
- 至少 12 个 Q3 candidate evaluations；
- system_error = 0；
- checkpoint identity valid；
- 有足够数据提出预算建议；
可报告：`PILOT WALL-CLOCK-LIMITED COMPLETE`，但仍只能是 `EXPERIMENTAL`。

少于 12 个 Q3 evaluations：报告 `PILOT INCOMPLETE`，**不得**自动延长。

## 停止条件

本轮（`TASK_006-P0/P1`）完成后立即停止。

不自动：
- 启动 Audit CC；
- 启动 Hermes；
- 开始 Formal Search；
- 生成 result1.xlsx；
- 进入 Q4；
- Ready；
- merge。

由 MAIN / 用户显式决定 Pilot 预算冻结、TASK_006-P2 立项与 result1.xlsx 启动时机。