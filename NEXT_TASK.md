# TASK_GOV_003 — BOUNDED VERIFICATION SKILL v0.1 — P1B CONTRACT CLOSURE

> 本轮是 TASK_GOV_003 的 **P1B second contract fix**。在 P1 fix
> （`34d8e8f`）已并入 PR #12 的基础上，再修三处 P1：
>
> 1. Harness v1 不支持 glob/path-wildcard — `allowed_*_paths` /
>    `forbidden_paths` 必须为精确路径或真实目录前缀；
> 2. Skill 缺 Pilot → Formal 的 phase-boundary 重新冻结合同；
> 3. final-report 的 `verified_by` 会混淆 Builder / Audit /
>    Hermes / MAIN，必须拆分为四个职责互斥的字段。
>
> 不修改 `CLAUDE.md` / `START_HERE.md`；不修改 Harness；不启动
> TASK_006；不重跑测试 / evaluator / Q2 / Q3。

## 当前任务边界

- Base: `main` = `5604bb086668ac6a857fc2c5ad86b0b8eb2713ae`
- Pre-fix head (audit base): `34d8e8f3e994a317463e2130cf6f57043e428f74`
  （PR #12 上的 P1 FIX commit；本轮 P1B FIX 的起点）
- Branch: `task/TASK_GOV_003-bounded-verification`
- PR: `#12`

### 本轮允许修改（仅 4 个文件 + PR body）

| 路径 | 用途 |
|---|---|
| `.claude/skills/bounded-verification/SKILL.md` | 加 §5.4 Harness path semantics（no glob）+ §5.5 phase contract lifecycle；改 §8 clean HEAD 措辞 |
| `.claude/skills/bounded-verification/templates/task-contract.md` | 删 wildcard 示例；加 phase_id / contract_version / target_acceptance_level / contract_snapshot_path；以 TASK_006-P0P1 pilot 模板为准 |
| `.claude/skills/bounded-verification/templates/final-report.md` | 拆 verified_by 为 evidence_generated_by / math_reviewed_by / git_verified_by / promotion_authorized_by / pending_by |
| `NEXT_TASK.md` | 回填 pre-fix head = `34d8e8f…`；"五项 milestone" + 新增 Hermes 校验项 |
| `PR #12 body` | 加 **Second Fix Closure** 小节 |

### 禁止修改

`CLAUDE.md`、`START_HERE.md`、`scripts/verify_task_context.py`、
`configs/`、`src/`、`tests/`、`outputs/`、`problem/`、`MODEL.md`、
`RESULTS.md`、`README.md`、`.gitignore`、任何 `result*.xlsx`、
任何 tracked `work/` 文件。

## 本轮修复要点（pre-fix `34d8e8f` vs post-fix）

| 维度 | pre-fix | post-fix |
|---|---|---|
| `task-contract.md` pilot 示例 path lists | 含 `src/q3_*.py` / `outputs/q3/**` / `src/q2_*.py` 等 wildcard | 改为精确路径（`src/q3_three_bombs.py` / `outputs/q3/` 等），与 Harness v1 字面校验能力匹配 |
| Skill §5 / `task-contract.md` phase 字段 | 缺 `phase_id` / `contract_version` / `target_acceptance_level` / `contract_snapshot_path` | 4 个字段列入 Skill `§5.5` + `task-contract.md` Phase contract lifecycle；Pilot 默认填 `TASK_006-P0P1 / 1 / EXPERIMENTAL / work/task_contracts/TASK_006-P0P1-v1.json` |
| final-report §H | 含 `verified_by : <Audit CC / Hermes / 自身测量>`（混合四种角色） | 拆为 5 个互斥字段 `declared_level` / `evidence_generated_by` / `math_reviewed_by` / `git_verified_by` / `promotion_authorized_by` / `pending_by`；明确角色归属锁定 + 未执行必须写 `NOT_RUN` / `PENDING` |
| SKILL.md §8 clean HEAD wording | 写"git status --porcelain 输出为空，允许 work/ untracked"（近似但语义模糊） | 改为按 `git diff --name-only` / `--cached` / conflicts / `allowed_untracked_paths` 逐项排除 |
| `NEXT_TASK.md` | pre-fix head = `6075884`；引用"四项 milestone"与 §三/§四 pre-fix 列 | pre-fix head = `34d8e8f`；五项 milestone；新增 Hermes 校验项 13–16 |

## Hermes 必须核验的事实（必须用 PR head，不用自我引用 SHA）

本轮 P1B FIX 形成后，Hermes 应核验 **PR #12 的最终 head**（具体
SHA 以 GitHub PR head 为准；不得从本任务文档字面读取）：

1. `git rev-parse origin/task/TASK_GOV_003-bounded-verification` =
   PR #12 head。
2. `git status --porcelain` 只允许 `work/` 的 untracked 出现；
   tracked 不允许有未提交修改。
3. `git diff main --stat` 显示的变更文件列表 ⊆ 上述允许列表。
4. `git log main..HEAD --oneline` 含 1× `DOCS:` + 4× `FIX:` commit
   （P1 `34d8e8f` + P1B `b0375bf` + Final consistency `3f87b92` +
   本轮 wording closure）；prefix 都正确。
5. `git push` 状态：`local = remote = PR head`。尚未 force-push。
6. PR 状态：Open / Draft / unmerged；base 分支 = `main`。
7. PR body 包含 3 stress scenarios + 不冒充声明 + HEAD / base /
   changed files + **First Fix Closure** + **Second Fix Closure**。
8. `outputs/submission/result*.xlsx` 不在变更中。
9. `work/` runtime artifacts 状态（不要求整个目录被 .gitignore
   忽略；按具体路径核验）：
   - not tracked（未被 git 跟踪）；
   - not staged（未进 index）；
   - not committed（未进 commit 历史）；
   - not pushed（未推送到 origin）；
   - 仅位于 `allowed_untracked_paths` 授权范围；
   - 是否 gitignored 按具体路径事实核验（不是按整个 `work/`
     整体是否 gitignored 推断）；
   - 不要求整个 `work/` 被 `.gitignore` 忽略。
   本轮任务未修改 `.gitignore`。
10. `templates/task-contract.md` 中的主模板 ```json``` 代码块经
    `python -c "import json,re,...; json.loads(...)"` 验证为合法 JSON。
11. `task-contract.md` 主 JSON 模板：
    `phase_id == "TASK_006-P0P1"`、`target_acceptance_level == "EXPERIMENTAL"`、
    `output_artifacts` 不含 `result1.xlsx`、
    `forbidden_paths` 含 `outputs/submission/`、
    `checkpoint_path == "work/q3_pilot/checkpoint.json"`。
12. Pilot 模板中 `allowed_modified_paths` /
    `allowed_untracked_paths` / `forbidden_paths` 三列表均无
    `*` / `?` / `[` / `]` 通配符
    （`HARNESS_PATH_LISTS_NO_GLOB`）。
13. `final-report.md` 不再含 `verified_by : <Audit CC / Hermes / 自身测量>`；
    含 `evidence_generated_by`、`math_reviewed_by`、`git_verified_by`、
    `promotion_authorized_by`、`pending_by`。
14. `SKILL.md` 不再写 "git status --porcelain 输出为空，允许 work/ untracked"
    字面；不再写 P0/P1 → P2 自动跳转的允许性。
15. `SKILL.md` §5.5 / `task-contract.md` Phase contract lifecycle 列出
    11 步 phase-boundary re-freeze 顺序，并写明 "phase-boundary
    re-freeze ≠ mid-run budget mutation"。
16. Pilot 模板严禁含：`FORMAL_RESULT_VERIFIED` /
    `outputs/submission/result1.xlsx` / `result1.xlsx 已生成` /
    `Q3 正式预算` / `formal search 已授权`。

## Hermes 输出

返回四项之一：

| 输出 | 含义 | 后续 |
|---|---|---|
| **PASS** | 1–16 全部通过 | MAIN / 用户决定 Ready / merge |
| **PASS WITH P2** | 仅文档细节需微调 | 仅文档层二次 commit；不改 Skill 主体 |
| **P1 BLOCK** | 范围 / allow-list / Skill 内容错 | 阻塞，等 MAIN / 用户修正 |
| **INCOMPLETE** | 数据未齐全 | 等回填后再核 |

## Hermes 禁止

- 修改任何 Skill / template / `NEXT_TASK.md` / PR body；
- 触发 commit / push / amend / rebase / merge；
- 把 PR 标记为 Ready / merge / close；
- 启动 TASK_006 / Q3 / result1.xlsx 生成；
- 触碰到任何 result*.xlsx 模板；
- 触碰 work/ tracked 文件化。

## STOP CONDITION（任务终止）

- Hermes 输出 PASS / PASS WITH P2，由 MAIN / 用户显式决定
  Ready / merge；
- 合并后由 MAIN 显式立项 TASK_006（第一 phase = `TASK_006-P0P1`）。

本任务不自动进入下一阶段；不擅自扩大任务；不冒充 TASK_006 已
启动；不冒充本轮 P1B FIX 自动校验 `bounded_verification` 字段
（Harness v1 当前不校验该字段，靠 Builder 自检 + 独立 Audit CC
复核）；不冒充 `verified_by` 仍存在（已拆分为四个互斥字段）。
