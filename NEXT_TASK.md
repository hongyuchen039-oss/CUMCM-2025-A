# 当前唯一任务

## 本轮任务
**TASK_004 SEARCH PROTOTYPE AUDIT AND SALVAGE**
— 远程未审核 Search prototype commit (6f728d45b3bb776c19bbe8a857b26570eb79dc68) 的只读审计与决策。
本轮**不修改代码 / 测试 / CI**, 不重跑 205 项本地测试,
不等待 CI; CI 不作为合并硬门槛.

Foundation PR #5 已合并 (commit 8cfe770); Governance PR #6 已合并 (commit 72c7523).
当前 main = 72c7523. 全量 205/205 本地通过.

只记录真实完成证据 (本地实测):

- Q2 Foundation **88/88** 本地通过
- Q1 baseline **42/42** 本地通过
- Q1 cylinder **75/75** 本地通过
- 全量 **205/205** 本地通过
- profile-measure 正常 → **rc=0**
- warm-up 程序异常 → **rc=1**
- repeat 程序异常 → **rc=1**
- 参数错误 → **rc=2**
- 默认 smoke → **rc=0**

下一步: 监管 CC / Main CC / Hermes 对 Search prototype 做只读审计, 决定是否接受 / 抢救 / 丢弃.
本轮不等待 CI; 正式 Search 尚未运行; result*.xlsx 尚未生成.

### 范围 (本轮)
- 只读审计 6f728d45b3bb776c19bbe8a857b26570eb79dc68 (搜索算法 / 收敛标准 / 候选生成 / 性能预算)
- 该 commit 当前状态: **保留, 尚未接受, 未创建 PR, 不代表正式 Search, 不代表 Q2 数值结果**
- 不得在审计前 cherry-pick / merge / 重写 / 删改
- 不得删除该 commit, 不得删除远程分支
- 不生成 result1.xlsx
- 不启动 TASK_004 Search 正式施工

### 仅允许新建 / 修改 (本轮)
1. `START_HERE.md` (阶段同步)
2. `NEXT_TASK.md` (本文件)
3. `README.md` (状态同步)
4. `MODEL.md` (Foundation 状态同步)

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
- 决策路径: 接受 / 抢救 / 丢弃 (由 Main CC / Hermes 决定)
- 不得在本任务内决策

## 下一阶段 (待 Search prototype 审计决策后)

### TASK_004 SEARCH 正式施工 (待决策)

仅在 Search prototype 审计通过后才进入。

可能路径:
- 接受 prototype → 启动 Search 正式施工 (保留 commit, 拆 PR)
- 抢救 prototype → 改造后启动 Search (新建 PR, 旧 commit 保留)
- 丢弃 prototype → 重新设计 Search (旧 commit 保留, 不予合并)

决策前禁止启动 Search; 禁止在合并前预先接受 prototype.

## 历史上下文 (合并后归档)

### Foundation PR #5 合并

- HEAD: 1d39c79
- merge commit: 8cfe770c92485be0425379a984578f77ee6485a9
- 评审方: Hermes (只读)
- 合并方: MAIN 按用户授权
- 合并后状态: search_entry 阶段

### Governance PR #6 合并

- HEAD: 353dc4d8fd1f3d534f57e456cd8de95a3f1b8630
- merge commit: 72c75234789ea42fbe8bc69d577e4d74a8d0be89
- 评审方: Hermes (只读)
- 合并方: MAIN 按用户授权
- 合并后状态: governance skill 就绪, 可被后续任务引用
