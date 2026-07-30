# TASK_GOV_003 — BOUNDED VERIFICATION SKILL v0.1 — P1 CONTRACT COMPATIBILITY FIX

> 本轮是 TASK_GOV_003 的 **P1 contract compatibility fix**。
> 修复 `SKILL.md` / `templates/task-contract.md` /
> `templates/final-report.md` / `NEXT_TASK.md` 的契约一致性。
> 不修改 `CLAUDE.md` / `START_HERE.md`；不修改 Harness；不启动 TASK_006；
> 不重跑测试 / evaluator / Q2 / Q3。

## 当前任务边界

- Base: `main` = `5604bb086668ac6a857fc2c5ad86b0b8eb2713ae`
- Pre-fix head (audit base): `607588473973595bab83ff18753e4557ae055f70`
  （即 PR #12 上的前一个 DOCS commit；本轮 FIX 的起点）
- Branch: `task/TASK_GOV_003-bounded-verification`
- PR: `#12`

### 本轮允许修改（仅 4 个文件）

| 路径 | 用途 |
|---|---|
| `.claude/skills/bounded-verification/SKILL.md` | 修复 §3 表 / §4 FULL 条件 / §5 schema（外层 + nested）/ §6/§7 历史 reference 化 |
| `.claude/skills/bounded-verification/templates/task-contract.md` | 改 YAML 示例为合规 JSON 模板（含外层 Harness v1 + nested bounded_verification） |
| `.claude/skills/bounded-verification/templates/final-report.md` | 允许"约 / ≈"，但要求原始精确值 + rule + artifact 来源 |
| `NEXT_TASK.md` | 回填 pre-fix head + PR #12，删除占位标记 |

### 禁止修改

`CLAUDE.md`、`START_HERE.md`、`scripts/verify_task_context.py`、`configs/`、
`src/`、`tests/`、`outputs/`、`problem/`、`MODEL.md`、`RESULTS.md`、
`README.md`、`.gitignore`、任何 `result*.xlsx`、任何 `work/*.json` 的
tracked 化。

## 本轮修复要点（pre-fix vs post-fix）

| 维度 | pre-fix | post-fix |
|---|---|---|
| task-contract.md 顶层格式 | YAML 文本 | 完整合法 JSON |
| task-contract.md schema | 自由字段集 | 外层 Harness v1 + nested `bounded_verification` |
| Harness 是否校验预算字段 | 误以为"是" | **否**，明确为 instruction-only |
| SKILL.md §3 / §4 FULL trigger | EXPENSIVE 写"仅 result*.xlsx 时" | 4 项 milestone 统一条件（共享数学核心修改 / formal/canonical result freeze / result1/2/3.xlsx freeze / 最终论文一致性 / MAIN 显式授权） |
| SKILL.md §6/§7 预算数字 | 写成全项目上限 | 标记为 **TASK_005 historical reference**，task-specific 数值优先；不得自动沿用 |
| final-report.md "约" 措辞 | 明确禁止 | 允许，但必须配精确值 + rule + artifact 来源 |
| NEXT_TASK.md 占位符 | 占位标记（待回填） | 回填 pre-fix head 6075884 + PR #12 |

## Hermes 必须核验的事实（必须用 PR head，不用自我引用 SHA）

本轮 FIX 形成后，Hermes 应核验 **PR #12 的最终 head**（不是任何
文档内的字面字符串；具体 SHA 以 GitHub PR head 为准）：

1. `git rev-parse origin/task/TASK_GOV_003-bounded-verification` =
   PR #12 head。
2. `git status --porcelain` 只允许 `work/` 的 untracked 出现；
   tracked 不允许有未提交修改。
3. `git diff main --stat` 显示的变更文件列表 ⊆ 上述允许列表。
4. `git log main..HEAD --oneline` 包含恰好 1 个 `DOCS:` commit +
   1 个 `FIX:` commit；两个 commit 的 prefix 都正确。
5. `git push` 状态：`local = remote = PR head`。尚未 force-push。
6. PR 状态：Open / Draft / unmerged；base 分支 = `main`。
7. PR body 包含 3 stress scenarios + 不冒充声明 + HEAD / base /
   changed files + **Fix Closure 小节**。
8. `outputs/submission/result*.xlsx` 不在变更中。
9. `work/` 仍是 untracked / gitignored，未被误提交。
10. `templates/task-contract.md` 中的主模板 ```json``` 代码块经
    `python -c "import json,re,...; json.loads(...)" ` 验证为合法 JSON。
11. `SKILL.md` 不再出现旧版 FULL trigger 旧字面（详 §三/§四 pre-fix 列）、
    也不再用全局上限代替 task-specific 预算数字。
    项目阶段全局上限代替 task-specific 数值 等被禁字眼。
12. `final-report.md` 不再写 "不得出现 '约'"。

## Hermes 输出

返回四项之一：

| 输出 | 含义 | 后续 |
|---|---|---|
| **PASS** | 1–12 全部通过 | MAIN / 用户决定 Ready / merge |
| **PASS WITH P2** | 仅文档细节需微调 | 仅文档层二次 commit；不改 Skill 主体 |
| **P1 BLOCK** | 范围 / allow-list / SKILL 内容错 | 阻塞，等 MAIN / 用户修正 |
| **INCOMPLETE** | 数据未齐全 | 等回填后再核 |

## Hermes 禁止

- 修改任何 Skill / template / `NEXT_TASK.md`；
- 触发 commit / push / amend / rebase / merge；
- 把 PR 标记为 Ready / merge / close；
- 启动 TASK_006 / Q3 / result1.xlsx 生成；
- 触碰到任何 result*.xlsx 模板。

## STOP CONDITION（任务终止）

- Hermes 输出 PASS / PASS WITH P2，由 MAIN / 用户显式决定 Ready / merge；
- 合并后由 MAIN 显式立项 TASK_006。

本任务不自动进入下一阶段；不擅自扩大任务；不冒充 TASK_006 已启动；
不冒充本 FIX 已自动校验 `bounded_verification` 字段（Harness v1
当前不校验该字段，靠 Builder 自检 + Audit CC 复核）。
