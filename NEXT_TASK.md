# 当前唯一任务

## 本轮任务
**TASK_004 FOUNDATION: Q2 单弹评估器基础 (NOT AN OPTIMIZATION RESULT)**
— 四变量合同 + 单候选完整圆柱评估器 + 100 候选本地 smoke + 回归测试.
本轮不启动 Q2 搜索; 仅在 Foundation PR 合并 + CI 持续 PASS 后启动 Search.

### 范围
- 实现 SingleBombStrategy (4 变量: heading_rad, speed_mps, release_time_s, delay_s)
- 推导量: release_point, detonation_time, detonation_point, cloud_center_fn
- 合法性 (物理 / 合同) 与程序错误严格分离
- 搜索域无损剪枝 (t_detonate > t_arrival)
- 单候选评估器: 复用 src/q1_cylinder.find_strict_intervals, 通过闭包注入新 cloud_center_fn
- Q1 固定策略回归 (heading=π, speed=120, release=1.5, delay=3.6)
- 100 个候选本地 smoke (coarse), 仅向终端输出
- 三档 sample 等级 (coarse / medium / fine), scan_step 显式传入

### 仅允许新建 / 修改
1. `src/q2_single_bomb.py` (主程序, 复用 src/q1_baseline + src/q1_cylinder)
2. `tests/test_q2_single_bomb.py` (49 测, 14 组 A-N)
3. `MODEL.md` (增加 Q2 单弹合同章节)
4. `START_HERE.md` (状态同步)
5. `NEXT_TASK.md` (本文件)
6. `README.md` (状态同步)

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
- 不修改 src/q1_baseline.py / src/q1_cylinder.py (未动 Q1 数值即可复用)
- 不修改 outputs/q1/q1_cylinder_comparison.svg (本轮 smoke 不覆盖此图)
- 不得把 smoke 临时最佳候选写入 RESULTS.md

### 本轮完成标准
1. 四变量无重复参数化 ✓
2. 投放点 / 起爆时刻 / 起爆点均为推导量 ✓
3. 合法性判断与程序错误分离 ✓
4. t_detonate > t_arrival 正确标记为 pruned_zero ✓
5. 完整圆柱几何核心未被复制 (通过回调注入) ✓
6. Q1 数值回归不变 ✓
7. Q1 baseline 42/42 测试全过 ✓
8. Q1 cylinder 75/75 测试全过 ✓
9. 新增 Q2 49/49 测试全过 ✓
10. 全部 unittest 166/166 全过 ✓
11. 100 候选 smoke 完成或如实报告性能阻塞 ✓ (100/100 完成, 12.81 s)
12. 不生成 result1.xlsx ✓
13. 不产生正式 Q2 最优声明 ✓
14. 文档当前阶段一致 (MODEL/START_HERE/NEXT_TASK/README) ✓
15. 工作流文件未修改 ✓
16. 工作区无非预期文件 ✓

### 计算结果 (FOUNDATION SMOKE, NOT AN OPTIMIZATION RESULT)
- 候选数: 100; 种子: 2025; Profile: coarse (grade=coarse, scan_step=0.05 s)
- valid (status=ok) = 100; invalid = 0; pruned_zero = 0; system_error = 0
- 总耗时 = 12.810 s
- 单候选 mean = 0.1281 s; median = 0.1681 s; p90 = 0.1706 s; max = 0.1985 s
- 临时最高 objective = 0.000000 s (随机策略难产生严格遮蔽, 符合预期)
- 该结果**不**写入 RESULTS.md; **不**写入 result1.xlsx; 仅 CLI 终端输出

## 下一阶段 (待审核后决定)

### TASK_004 Search: Q2 单弹最优策略正式搜索
进入条件:
1. Foundation PR 审核并合并
2. CI 持续 PASS
3. Foundation smoke 性能已记入下一阶段预算 (本次 100 候选 ≈ 12.8 s 总量)
4. 搜索算法 / 收敛标准 / 性能预算重新冻结
5. 仍需外部 (陈虹宇) 显式授权才能启动 Search

TASK_004 Search 任务目的 (粗框架, 进入时细化):
- 在 (heading_rad, speed_mps, release_time_s, delay_s) 四维搜索空间上
  求 FY1 → M1 单弹最优策略
- 目标: 完整圆柱严格遮蔽总时长 (复用 TASK_003 strict_boundary_value)
- 关键决策: 搜索算法 (网格 / 局部 / 全局), 收敛标准, 候选生成约束
- 输出: result1.xlsx 之前必须冻结搜索算法与收敛标准

不得在没有 Foundation PR 合并前预先写 TASK_004 Search 代码.
