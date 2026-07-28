# 当前唯一任务

## 本轮任务
**TASK_004 Q2 REAL SEARCH CORE V1** — Q2 Real Search Core v1 部分抢救施工.
本轮基于 Search prototype (`6f728d45b3bb776c19bbe8a857b26570eb79dc68`) 进行抢救,
已通过普通 merge 把 main 同步到 task/TASK_004-search, prototype 仍为 ancestor.

用户在 Foundation Final Close 之后明确授权:
- 允许 Main CC / BUILD CC 对既有 Search 分支施工;
- 允许 commit / push / 创建 Draft PR;
- 禁止自动转 Ready / 禁止自动 merge / 禁止 rebase / 禁止 force push;
- 禁止删除任何远程分支;
- 完成后立即停止.

等级: **PILOT / NOT A FORMAL Q2 RESULT** /
**BEST-KNOWN CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM**.

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
  本轮是唯一仓库写入者; 不得在审计前预先接受 prototype.

### 当前任务写入边界

- 允许施工: .gitignore, configs/q2_search_gate_v1.json, src/q2_search.py,
  tests/test_q2_search.py, MODEL.md, NEXT_TASK.md, START_HERE.md, README.md
  (允许按需新增 src/q2_search_eval.py)
- 禁止修改: CLAUDE.md, .claude/skills/project-mainline-governance/SKILL.md,
  problem/, RESULTS.md, src/q1_baseline.py, src/q1_cylinder.py,
  src/q2_single_bomb.py, tests/test_q1_baseline.py, tests/test_q1_cylinder.py,
  tests/test_q2_single_bomb.py, .github/workflows/ci.yml, outputs/q1/,
  outputs/submission/, 任何官方材料, PR #7, main 分支
- 禁止: 自动转 Ready, merge, rebase, force push, reset, 删除任何远程分支
- 禁止: 删除 Search prototype commit 与远程分支
- 禁止: 启动 Q3 / 启动 Q4 / 启动 Q5 / 启动更大预算 Search
- 禁止: 写入 RESULTS.md / 生成 result1/2/3.xlsx

### 范围 (本轮)

- 把 Search prototype 改造成能够调用真实 evaluate_single_bomb_strategy 的
  可复现搜索核心
- 真实评估器接入 (evaluate_with_real_evaluator)
- 串行 real-search pipeline (workers=1, evaluator=real)
- deterministic candidate generation (anchor + global + local)
- manifest identity (seed / domain / algorithm version / candidate vectors)
- checkpoint v2 (resume identity 校验)
- coarse → medium → local refinement → fine
- 小规模真实 pilot (固定 seed / 固定预算, 总运行时间 < 5 分钟)
- 本地测试 + commit + push + Draft PR

### 库限制
- 只使用 Python 标准库
- 不得强制安装 numpy / scipy / pandas / matplotlib

### 本轮明确不做
- 不生成 result1/2/3.xlsx
- 不启动 Q2 单弹优化 / 搜索算法以外的任何正式施工
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
- 不修改 PR #7 / PR #5 / PR #6 / PR #8

### Foundation 已冻结的实际交付 (PR #5)

1. Q2 单弹评估器 (`src/q2_single_bomb.py`) 已合并
2. Q2 单弹单元测试 88 测 (22 组 A-Q + U2/R2/S2 加固类) 已合并
3. profile-measure 退出码合同 (0/1/2) 已合并
4. EPS_GROUND 三区分类已合并
5. mixed-batch 8 类独立计数已合并
6. 默认 smoke 标注 candidate_source + NOT AN OPTIMIZATION RESULT 已合并
7. 后续 merge 仍为 NOT AN OPTIMIZATION RESULT
8. 文档当前阶段一致 (MODEL / START_HERE / NEXT_TASK / README)

### Search Prototype 与 main 同步状态

- prototype commit: `6f728d45b3bb776c19bbe8a857b26570eb79dc68`
- main 同步 merge commit: `453c0980f785f9b506a1e11a33dfb21228e99796`
- 当前 HEAD: `453c098` (本轮 main 同步完成)
- prototype 仍为 ancestor (通过 `git merge-base --is-ancestor` 验证)
- 远程分支 `task/TASK_004-search` 保留

## 下一阶段 (待本轮 Pilot 完成)

### TASK_004 SEARCH 后续 (待 Pilot 验收后)

- 独立审查 GPT / Audit CC / Hermes 报告只读结果
- MAIN 决定后续路径: 整体采用 / 局部抢救 / 不采用并重写
- 任何后续路径不删除 prototype commit, 不删除远程分支
- 后续阶段才可能升 VERIFIED / FINAL; 本轮仍为 PILOT
