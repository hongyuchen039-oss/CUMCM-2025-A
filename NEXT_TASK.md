# 当前唯一任务

## 本轮任务
**TASK_004 SEARCH PROTOTYPE READ-ONLY AUDIT AND SALVAGE DECISION**
— 远程未审核 Search prototype commit (6f728d45b3bb776c19bbe8a857b26570eb79dc68) 的只读审计与处置决策.

本任务**全程只读**; 不修改任何仓库文件; 不 commit / push / 创建或修改 PR;
不 merge / cherry-pick / rebase / reset; 不运行正式 Search; 不生成结果文件.

PR #8 (本次状态同步) 合并后, Main CC 保持待命, 不进入施工.

Foundation PR #5 已合并 (commit 8cfe770); Governance PR #6 已合并 (commit 72c7523).
当前 main = 72c7523. 全量 205/205 本地通过.

### 角色合同 (已合并到 main)

- **Audit CC**: 只读审核 Search prototype 的真实代码 / 测试 / 算法 / 数学合同 /
  性能预算 / 可复用性; 输出审计结论与建议; 不修改仓库; 不作最终决定.
- **Hermes**: 只读核验 prototype 分支 / commit SHA / changed files / 与 main 的分叉
  关系 / 是否存在 PR; 不评价搜索算法; 不修改仓库; 不作最终决定.
- **MAIN**: 综合 Audit CC 与 Hermes 证据, 作出最终处置决定:
  1. 整体采用;
  2. 局部抢救;
  3. 不采用并重写.
- **用户**: 批准任何后续写入 / 分支对齐 / 代码修改 / PR 操作.
- **Main CC / BUILD CC**: 在用户批准后执行 MAIN 冻结的施工方案;
  不是本轮只读审核者; 不是最终决策者; 当前保持停止和待命.

### 当前任务写入边界

- 本任务为只读;
- 不允许修改任何仓库文件;
- 不允许 commit / push / 创建或修改 PR;
- 不允许 merge / cherry-pick / rebase / reset;
- 不运行正式 Search;
- 不生成结果文件;
- Main CC 保持待命;
- PR #8 是进入该任务前的一次性状态同步, 不属于审核阶段施工内容.

### 范围 (本轮)

- 只读审计 6f728d45b3bb776c19bbe8a857b26570eb79dc68 (搜索算法 / 收敛标准 / 候选生成 / 性能预算)
- 该 commit 当前状态: **保留, 尚未接受, 未创建 PR, 不代表正式 Search, 不代表 Q2 数值结果**
- 不得在审计前 cherry-pick / merge / 重写 / 删改
- 不得删除该 commit, 不得删除远程分支
- 不生成 result1.xlsx
- 不启动 TASK_004 Search 正式施工

### 库限制
- 只使用 Python 标准库
- 不得强制安装 numpy / scipy / pandas / matplotlib

### 本轮明确不做
- 不生成 result1/2/3.xlsx
- 不启动 Q2 单弹优化 / 搜索算法
- 不修改官方原模板 / problem/*.pdf / 题目及模板/ / desktop.ini
- 不自动 merge 任何 PR
- 不动 main
- 不修改 `.github/workflows/ci.yml`
- 不修改 src/q1_baseline.py / src/q1_cylinder.py / src/q2_single_bomb.py
- 不修改 tests/* (Q1 baseline / Q1 cylinder / Q2 foundation)
- 不修改 outputs/q1/q1_cylinder_comparison.svg
- 不 cherry-pick / 不重写 6f728d45b3bb776c19bbe8a857b26570eb79dc68
- 不删除 6f728d45b3bb776c19bbe8a857b26570eb79dc68
- 不 force push / 不重写历史 / 不删除远程分支

### Foundation 已冻结的实际交付 (PR #5)

1. Q2 单弹评估器 (`src/q2_single_bomb.py`) 已合并
2. Q2 单弹单元测试 88 测 (22 组 A-Q + U2/R2/S2 加固类) 已合并
3. profile-measure 退出码合同 (0/1/2) 已合并
4. EPS_GROUND 三区分类已合并
5. mixed-batch 8 类独立计数已合并
6. 默认 smoke 标注 candidate_source + NOT AN OPTIMIZATION RESULT 已合并
7. 后续 merge 仍为 NOT AN OPTIMIZATION RESULT
8. 文档当前阶段一致 (MODEL / START_HERE / NEXT_TASK / README)

### Search Prototype 远程未审核 commit 现状

- commit: `6f728d45b3bb776c19bbe8a857b26570eb79dc68`
- 状态: **保留, 尚未接受, 未创建 PR**
- 待审计的内容: 搜索算法 / 收敛标准 / 候选生成 / 性能预算 / 数学结论
- 决策路径: 整体采用 / 局部抢救 / 不采用并重写 (由 MAIN 决定)
- 无论选择哪条路径, 旧 prototype commit 和远程分支均保留; "不采用"不等于删除历史
- 不得在本任务内决策; 不得在合并前预先接受 prototype

## 下一阶段 (待 Search prototype 审计决策后)

### TASK_004 SEARCH 正式施工 (待决策)

仅在 Search prototype 审计决策后才进入。

可能路径:
- 整体采用 → 启动 Search 正式施工
- 局部抢救 → 改造后启动 Search
- 不采用并重写 → 重新设计 Search (旧 commit 与远程分支保留)

决策前禁止启动 Search; 禁止在合并前预先接受 prototype.
