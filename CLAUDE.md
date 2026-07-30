# Claude Code 项目规则

本文件作为项目默认长期规则。本轮用户明确任务可以细化执行范围，
但不得绕过凭据安全、分支保护、禁止强推和禁止自动合并等边界。

## 0.5 任务上下文预检 (TASK_GOV_002)

任何 BUILD / 审查 / 下游施工会话开始前，必须先运行：

```text
python scripts/verify_task_context.py --context work/task_context.json
```

只有输出为 `CONTEXT_VALID_CLEAN` 或 `CONTEXT_VALID_AUTHORIZED_DIRTY`
才允许继续。`CONTEXT_INVALID` 时立即停止，不得自行 reset / stash /
restore / rebase / 改写 context 绕过。

## 0. 每个新项目 / 新阶段启动必读

在创建新分支、worktree、专用 Agent 或下游任务前，必须先阅读并执行：

- `.claude/skills/project-mainline-governance/SKILL.md`
- `.claude/skills/bounded-verification/SKILL.md`（仅当任务包含 expensive evaluator / optimization / 长时间搜索 / 预算约束运行时）

project-mainline-governance 固化本项目已经付出代价得到的流程教训，尤其用于防止：

- 当前阶段未关闭就提前启动下游阶段；
- 把“未来阶段”错误拆成多个长期并行角色；
- 施工会话没有 Bash / Write / Edit，却继续提交占位实施报告；
- 设计报告版本循环取代真实代码、测试、commit 和 benchmark；
- 把 CI、格式问题、P2 问题或重复文档审查升级为主线阻断；
- 将本地自报误写成 GitHub 已核验事实；
- 多个写入者同时操作同一 worktree；
- 任务结束后自动进入下一阶段。

bounded-verification 固化 numerical-evaluation / optimization 任务的预算冻结、
clean-HEAD 验证、checkpoint/resume 身份链、失败 / 停止分类、可信等级与
Builder / Audit / Hermes 边界。任何 expensive task 启动前必须按本 Skill 填写
`work/task_context.json`，并在过程中遵守 §4 FAST / TASK / FULL 分层与 §10
heartbeat / pipefail 规范。

每个新项目必须把上述 Skill 复制到同一路径，并在根级 Agent 规则中引用。
若本文件与上述任一 Skill 在流程细节上冲突，以更严格且更接近用户当前明确指令的一项为准。

## 0.1 建模产出优先，CI 默认非必要

本项目以最终建模产出为目的。默认优先级是：

```text
可信模型
→ 可复现实验
→ Q1～Q5 数值结果
→ result1/2/3.xlsx
→ 图表
→ 论文
```

CI 不是项目成果，也不是数学正确性的主要证明。

除非用户明确要求，或存在多人频繁合并、部署发布、分支保护、快速回归等明确需求：

```text
CI_REQUIRED = NO
```

默认采用：

```text
本地真实测试 / 收敛 / benchmark
+ 只读监管 CC 独立复核
+ Hermes 核验 branch / SHA / changed files / push / PR
+ 关键里程碑全量回归
```

若使用 CI，应保持轻量，只做编译、快速单元测试和必要 smoke。
昂贵的空间收敛、时间收敛、正式搜索、Excel 回读和论文一致性检查放在本地里程碑验收。

单纯 CI timeout 或 cancelled，在本地全量验证真实通过、无 assertion failure、只读监管复核通过时，原则上属于 P2/P3，不得自动阻断建模主线。

不得为了 CI：

- 删除真实测试；
- 放宽数学断言；
- 把全部真实验证替换为 mock；
- 长期调试 workflow 而不推进模型；
- 将运行速度问题冒充数学失败。

## 0.2 Agent / CC 最小化

默认只保留：

- MAIN：总览主线、冻结当前任务、最终决策；
- BUILD CC：当前任务唯一施工者。

按需启用：

- 只读监管 / Audit CC：只审真实 artifact 的 P0/P1；
- Hermes：只核验 Git / GitHub 状态。

非必要不得新开专用 CC。创建新 CC 前必须证明：

1. 有独立且必要的 artifact；
2. 现有角色无法合理完成；
3. 新 CC 具备所需工具；
4. 降低的风险大于沟通成本；
5. 有明确停止条件；
6. 用户或 MAIN 明确批准。

不得因为未来存在 Search、论文、可视化等阶段，就自动创建 Search CC、Search MAIN、Search Audit 等角色群。
优先复用现有 MAIN、BUILD、只读监管和 Hermes。

## 1. 仓库与目录

- 项目根目录：`C:\Users\33560\Desktop\CUMCM_2025_A`
- GitHub 仓库：`https://github.com/hongyuchen039-oss/CUMCM-2025-A.git`
- 远程名：`origin`
- 不允许修改 origin 地址。

## 2. 分支策略

- 正式任务必须在独立分支上完成：`task/<TASK_ID>-<short-name>`
- 不在 `main` 或 `master` 上直接修改或提交。
- 同一任务只维护一个 Draft PR。
- 不自动合并 PR；不自动进入下一任务。
- 不重写 Git 历史；不强制 push；不删除远程分支。

## 3. 同步规则

- 本地保存不会自动同步到 GitHub，必须 commit + push。
- 每次 push 前必须 `git status` 与 `git diff` 复查。
- 不得使用 `git add .` 无差别暂存。
- 只显式暂存本任务范围内的文件。

## 4. 提交前缀

只在有意义的检查点提交，使用以下前缀之一：

- `PLAN:`   任务范围、方法和完成标准已明确
- `WORKING:` 最小版本可运行，验证未完成
- `VERIFIED:` 测试、边界、反例验证通过
- `REVIEW:`  本轮内容已整理，可交审核
- `FIX:`     根据测试或审核意见完成修复
- `DOCS:`    只改说明，不动数学模型和正式结果

禁止提交：`update`、`change`、`try`、`fix again`、`final`、`final2`、`new final` 等无意义提交。

## 5. 凭据与安全

严禁读取、输出、记录、上传或间接获取：

- GitHub PAT、OAuth Token、API Key、SSH 私钥
- `gh auth token` 或 `gh auth status --show-token`
- `git credential fill`、Windows Credential Manager 内容
- `.env`、`*.key`、`*.pem`、`*.token`、浏览器 Cookie

严禁操作：格式化磁盘、修改注册表、修改系统环境变量、修改代理、
关闭安全软件、全局安装软件、读取或修改项目目录外文件。

## 6. 题目材料

区分两类材料，禁止混淆：

1. **官方原始材料**（仅本机保留，不修改、不提交、不上传 GitHub）：
   - 官方 PDF `problem/A题原题.pdf`；
   - 官方模板 ZIP `题目及模板/2025高教社杯数学建模A题_结果模板.zip`；
   - ZIP 内的空白 `result1.xlsx` / `result2.xlsx` / `result3.xlsx`。
2. **项目生成的正式结果**（必须可由代码重新生成，保存到 `outputs/submission/`）：
   - `outputs/submission/result1.xlsx`（Q3 里程碑）；
   - `outputs/submission/result2.xlsx`（Q4 里程碑）；
   - `outputs/submission/result3.xlsx`（Q5 里程碑）。
   - 在对应任务的 PR 中**允许并要求**提交；
   - 提交前必须由程序重新读回，验证文件名、工作表、表头、数据行数、单位和关键单元格内容；
   - 不得覆盖官方空白模板。

- 题目事实写入 `problem/FACTS.md`，每个事实记录 PDF 页码或附件来源。
- 模板字段结构（表头与方向角规则）记录在 `problem/FACTS.md §13`。
- 不得用网络搜索或第三方论文补全官方原题。
- 不得把模型假设伪装成官方事实。
- 不得猜测官方未给出的参数（如重力加速度未在 PDF 中给出时不要写 9.8）。

## 7. 数学与建模底线

任何正式内容必须明确区分：

- 官方事实
- 模型假设
- 数学推导
- 数值设置
- 实验结果

不得删除失败测试，不得放宽约束，不得仅验证样例。
涉及核心数学变化时必须在 PR 描述中说明原方法、新方法、原因、影响、验证、风险。

## 8. 文件增长限制

- 普通任务原则上最多新建 3 个正式文件。
- 不创建 Decision Log、Gate、签名、Signoff Report、审核 ZIP、报告的报告。
- 临时内容放 `.ai/logs/` 或在本任务结束前清理，不入 GitHub。
- 完整审核包只在问完成、模型冻结、论文初稿、最终交付时生成。

## 9. 学生入口文件

项目所有者平时只需查看：

- `START_HERE.md`  —— 当前状态一页说明
- `MODEL.md`       —— 题目、模型直觉、关键公式、假设、局限
- `RESULTS.md`     —— 关键结果、单位、图表、合理性、可信等级
- `NEXT_TASK.md`   —— 永远只保留一个当前任务

不得把 Git 历史、审批状态、完整日志塞入上述文件。

## 10. 每轮汇报格式

每轮完成只向用户汇报：

- 做了什么
- 为什么这样做
- 当前结果
- 测试情况
- 结果是否可信
- 发现的风险
- 需要用户决定什么
- 建议下一步

不得用大量文件名和日志代替解释。

## 11. 停止条件

完成当前任务、测试、commit、push 和 PR 更新后立即停止。
不自动合并，不自动进入下一任务，不擅自扩大任务，不因自主模式绕过任何安全边界。

## 12. 删除正式文件

删除任何已存在的正式文件前必须先说明：

- 要删什么
- 为什么删
- 是否有替代文件
- 对项目的影响

并等待用户明确同意。
