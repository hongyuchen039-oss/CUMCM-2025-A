# 当前唯一任务

## 任务标题
TASK_005 FINAL GIT / PR VERIFICATION — HERMES HANDOFF

## 已完成
- independent Audit passed
- no P0 / no P1
- doc-only P2 closed by current commit
- canonical Q2 result promoted: 4.260970878601073 s

## 状态声明（不变）

```
FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE /
LOCAL CONVERGENCE NOT ESTABLISHED /
NOT A PROVEN GLOBAL OPTIMUM
```

## Canonical Q2 result

```
heading_rad     = 3.126767217560497
speed_mps       = 116.43351397802584
release_time_s  = 1.2672692031529031
delay_s         = 3.789202402720746
total_duration_s = 4.260970878601073
interval (s)    = (5.089825368500298, 9.350796247101371)
```

旧候选 `(3.121767217560497, 115.43351397802584, 1.7672692031529031, 3.889202402720746)` dur `2.48275905609131 s` 已降级为 `HISTORICAL FORMAL-SEARCH CANDIDATE`。

## 当前唯一任务（read-only）

Hermes 只读核验最终仓库和 PR 事实，不修改任何文件。

### Hermes 应核验

- current PR head after DOCS promotion commit（占位标记：`FINAL_DOC_HEAD_TO_BE_FILLED_AFTER_COMMIT`；实际 SHA 在 PR body / final report 中给出，避免自引用循环）
- branch = `task/TASK_005-q2-formal-search`
- base = `9ea31890c22b11089f9d224c0e90f1a0cab8fde8`
- commit count、push status
- PR Open / Draft / unmerged
- changed files 仅落在允许范围：START_HERE.md / NEXT_TASK.md / README.md / MODEL.md / RESULTS.md
- no Q3 启动
- no result*.xlsx
- no src / tests / scripts / configs / outputs JSON / problem / CLAUDE / .claude / Harness / .gitignore 改动
- 任务上下文 verify_task_context 状态有效

### Hermes 禁止

- 修改任何文件
- commit / push
- 转 Ready / merge
- 启动 TASK_006

### Hermes 输出（四选一）

- `PASS`
- `PASS WITH P2`
- `P1 BLOCK`
- `INCOMPLETE`

### Hermes 完成后

MAIN / 用户授权 Ready 或 merge。

## 绝对禁止（已在本轮执行过的不重复）

- 重跑 evaluator
- 重跑 formal / refinement / verification runner
- 重跑 3×1000
- 重跑完整 16 项扰动
- 运行 tests.test_q2_search
- 运行 unittest discover
- 自动 merge
- 自动 Ready
- 启动 Audit CC / Hermes（仅 MAIN 可启动）
- 修改 src / tests / scripts / configs / outputs JSON / problem / CLAUDE / .claude / Harness / .gitignore
- 修改原始 checkpoint / work/q2_formal_refinement/checkpoint.json

## 验证内容（已在本轮执行）

- `git diff --check`
- 文本一致性 grep
- harness: `python scripts/verify_task_context.py --context work/task_context.json`
  → `CONTEXT_VALID_AUTHORIZED_DIRTY` 或 `CONTEXT_VALID_CLEAN`

## 跟踪证据

- `outputs/q2/q2_verify_summary.json` (tracked)
  - `verification_run_head_sha = 4a1cbd9520d1a62eeeb4cb91180e989c91dcf036`
  - `verification_script_sha256 = 53e37211c50bdd5395c3fa22dcf9c77a71df5be975fa0803e478a2dfaea28b66`
  - `q2_search_code_identity    = 3b90accd0ca7695fe8a56e9044fac5fefe8119cfb8ba72d857327ac1e5877ac7`
  - `checkpoint_source_head_sha = ac97a38c7564c9d7f2c0793c935eeb27bbd1fa90`
  - `refinement_config_sha256   = 6f9cb503397996b788d0edfc6491b5a4425dd6e4a784f7ad82f8616acfd65a3d`
  - `evaluator_call_count       = 5`
  - `stability_evaluation_id    = c19c1eaddffdb8567f4053c118c4a1ed`
  - `checkpoint_identity_validation = True`
  - `stability_ok = True`
  - `physical_validity.ok = True`
  - `local_convergence_established = False`

## 提交后停止条件

DOCS commit + push + PR #11 body 更新后立即停止；不自动 merge；不进入 Q3 / TASK_006；不启动 Audit CC / Hermes（仅 MAIN 决定）。