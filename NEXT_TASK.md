# TASK_GOV_003 — BOUNDED VERIFICATION SKILL v0.1 — HERMES HANDOFF

> 本任务在 `task/TASK_GOV_003-bounded-verification` 分支上完成 doc-only commit，
> 内容仅限 `.claude/skills/bounded-verification/SKILL.md` + 两个 templates +
> `CLAUDE.md` + `START_HERE.md` + `NEXT_TASK.md`。
> 不修改任何代码 / 测试 / 结果文件；不启动 Q3；不合并 PR；不进入下一任务。

## 当前任务边界

- Base: `main` = `5604bb086668ac6a857fc2c5ad86b0b8eb2713ae`
- Branch: `task/TASK_GOV_003-bounded-verification`
- Head: 当前 commit （待 DOCS commit 后回填）

### 允许的修改

| 路径 | 用途 |
|---|---|
| `.claude/skills/bounded-verification/SKILL.md` | 新增 |
| `.claude/skills/bounded-verification/templates/task-contract.md` | 新增 |
| `.claude/skills/bounded-verification/templates/final-report.md` | 新增 |
| `CLAUDE.md` | 在 §0 必读 Skill 列表中追加 bounded-verification 引用 |
| `START_HERE.md` | 替换为 TASK_GOV_003 阶段说明 |
| `NEXT_TASK.md` | 替换为本文件 |

### 禁止的修改

`src/`、`tests/`、`scripts/`、`configs/`、`outputs/`、`problem/`、
`MODEL.md`、`RESULTS.md`、`README.md`、`.gitignore`、
任何 `result*.xlsx`、任何 `work/*.json` 的 tracked 化。

## Hermes 必须核验的事实

只读核验本任务 PR `#<TBD>` 的 Git 状态；不得 commit / push / amend：

1. `git rev-parse HEAD` 与 PR head 一致；与本分支最新 commit SHA 一致。
2. `git status --porcelain` 只允许 `.claude/skills/bounded-verification/`、
   `CLAUDE.md`、`START_HERE.md`、`NEXT_TASK.md`、`work/` 的 untracked 出现；
   tracked 不允许有修改。
3. `git diff main --stat` 显示的变更文件列表 = 上述允许列表。
4. `git log main..HEAD --oneline` 仅包含 1 个 `DOCS:` commit，prefix 正确。
5. `git push` 状态：`local = remote = PR head`。尚未 force-push。
6. PR 状态：Open / Draft / unmerged；base 分支 = `main`。
7. PR 描述必须包含：3 stress scenarios（A / B / C）说明 + 不冒充声明 +
   HEAD / base / changed files 列表。
8. `outputs/submission/result*.xlsx` 不在变更中。
9. `work/` 仍是 untracked / gitignored，未被误提交。
10. SKILL.md 第 §17 引用 `templates/final-report.md` 的路径在仓库
    `.claude/skills/bounded-verification/templates/final-report.md` 实际存在。

## Hermes 输出

返回四项之一：

| 输出 | 含义 | 后续 |
|---|---|---|
| **PASS** | 1–10 全部通过 | MAIN / 用户决定 Ready / merge |
| **PASS WITH P2** | 仅文档细节需微调 | 仅文档层二次 commit；不改 Skill 主体 |
| **P1 BLOCK** | 范围 / allow-list / SKILL 内容错 | 阻塞，等 MAIN / 用户修正 |
| **INCOMPLETE** | 数据未齐全 | 等回填后再核 |

## Hermes 禁止

- 修改任何 Skill / template / CLAUDE.md / START_HERE.md / NEXT_TASK.md；
- 触发 commit / push / amend / rebase / merge；
- 把 PR 标记为 Ready / merge / close；
- 启动 TASK_006 / Q3 / result1.xlsx 生成；
- 触碰到任何 result*.xlsx 模板。

## STOP CONDITION（任务终止）

- Hermes 输出 PASS / PASS WITH P2，由 MAIN / 用户显式决定 Ready / merge；
- 合并后由 MAIN 显式立项 TASK_006。

本任务不自动进入下一阶段；不擅自扩大任务；不冒充 TASK_006 已启动。
