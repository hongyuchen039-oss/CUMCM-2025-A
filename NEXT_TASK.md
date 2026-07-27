# 当前唯一任务

## 本轮任务
**TASK_004 FOUNDATION FINAL CLOSE: 关闭最后两项债务**
— DEBT-Q2-PROFILE-EXIT-001 (warm-up error → CLI rc=1) + GitHub CI 25 分钟
timeout 拆分 (单 job → 3 个并行 unittest job).
本轮不启动 Q2 搜索; 不进 Q3; 不写 Search 代码; 不生成 result1.xlsx.

---

### 债务登记状态

- **DEBT-Q2-PROFILE-EXIT-001** — **CLOSED** (本轮 Final Close)
  - 旧合同: warm-up-only error → CLI rc=0
  - 新合同: 任何程序异常 (warm-up 或 formal repeat) → CLI rc=1
  - 参数错误 → CLI rc=2 不变
  - 正常 → CLI rc=0 不变
  - 详细字段语义保留: `warm_up_error` (warm-up) 与 `n_system_error`/`system_errors` (repeat) 分开记录,
    但在 CLI 退出码上**严格同权**.

---

### 范围
- 实现 SingleBombStrategy (4 变量: heading_rad, speed_mps, release_time_s, delay_s)
- 推导量: release_point, detonation_time, detonation_point, cloud_center_fn

### 范围
- 实现 SingleBombStrategy (4 变量: heading_rad, speed_mps, release_time_s, delay_s)
- 推导量: release_point, detonation_time, detonation_point, cloud_center_fn
- 合法性 (物理 / 合同) 与程序错误严格分离
- 搜索域无损剪枝 (t_detonate > t_arrival, valid=True, status="pruned_zero")
- 单候选评估器: 复用 src/q1_cylinder.find_strict_intervals, 通过闭包注入新 cloud_center_fn
- Q1 固定策略回归 (heading=π, speed=120, release=1.5, delay=3.6)
- 100 个候选本地 smoke (coarse), 仅向终端输出, candidate_source=prevalidated_nonpruned
- 三档 sample 等级 (coarse / medium / fine), scan_step 显式传入
- 默认 smoke CLI 退出码: 0 无 system_error, 1 有 system_error, 2 参数错误

### 仅允许新建 / 修改
1. `src/q2_single_bomb.py` (主程序, 复用 src/q1_baseline + src/q1_cylinder)
2. `tests/test_q2_single_bomb.py` (85 测, 22 组 A-Q + U2/R2/S2 返工加固类)
3. `MODEL.md` (增加 Q2 单弹合同章节 + 本轮 FIX 7 P1 变更表)
4. `START_HERE.md` (状态同步)
5. `NEXT_TASK.md` (本文件)
6. `README.md` (状态同步)
7. PR #5 描述 (通过 gh pr edit 更新)

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
- 不得冻结正式 Search 预算 (粗外推已删除, 仅有本轮 3×3 实测)

### 本轮完成标准
1. 四变量无重复参数化 ✓
2. 投放点 / 起爆时刻 / 起爆点均为推导量 ✓
3. 合法性判断与程序错误分离 ✓
4. t_detonate > t_arrival 正确标记为 pruned_zero (valid=True) ✓
5. 完整圆柱几何核心未被复制 (通过回调注入) ✓
6. Q1 数值回归不变 ✓
7. EPS_GROUND 三区分类真实实现 (非测试放宽) ✓
8. Q1 直接对照测试 (端点容差 ≤ 1e-6 s) ✓
9. 多区间测试拆为 Q1 锚 + 合成 boundary 双测 ✓
10. system_error 反映到 CLI 退出码 ✓
11. 默认 smoke 标注 candidate_source + NOT AN OPTIMIZATION RESULT ✓
12. mixed-batch 8 类独立计数 ✓
13. coarse/medium/fine 实测 (warm-up + repeat=3 + samples 复用) ✓
14. Q1 baseline 42/42 测试全过 ✓
15. Q1 cylinder 75/75 测试全过 ✓
16. Q2 Foundation 85/85 测试全过 ✓
17. 全部 unittest 202/202 全过 ✓
18. 100 候选 smoke 完成 (EXIT=0) ✓
19. 默认 smoke 标注 candidate_source ✓
20. 不生成 result1.xlsx ✓
21. 不产生正式 Q2 最优声明 ✓
22. 文档当前阶段一致 (MODEL/START_HERE/NEXT_TASK/README) ✓
23. 工作流文件未修改 ✓
24. 工作区无非预期文件 ✓
25. (P1 返工) u0 与地面合法性统一 (validate_strategy 接受 u0, evaluate 二次分类非 silent) ✓
26. (P1 返工) profile-measure 暴露 system_error (warm_up_error + n_system_error + system_errors; main 返回 0/1/2) ✓
27. (P1 返工) 真实非零邻域 (Q1_NEIGHBORHOOD 内 ok+total>0; 全 0/全异常 → RuntimeError; 9 rows 分类) ✓
28. (Final Close) DEBT-Q2-PROFILE-EXIT-001 CLOSED: warm-up error → CLI rc=1 ✓
29. (Final Close) CI 25-min timeout 拆分: 3 个并行 unittest job (q1-baseline / q1-cylinder / q2-foundation) ✓

### 计算结果 (FOUNDATION SMOKE, NOT AN OPTIMIZATION RESULT)
- 候选数: 100; 种子: 2025; Profile: coarse (grade=coarse, scan_step=0.05 s)
- valid (status=ok) = 100; invalid = 0; pruned_zero = 0; system_error = 0
- 总耗时 = 13.008 s
- 单候选 mean = 0.1300 s; median = 0.1698 s; p90 = 0.1754 s; max = 0.2121 s
- 临时最高 objective = 0.000000 s (随机策略难产生严格遮蔽, 符合预期)
- 该结果**不**写入 RESULTS.md; **不**写入 result1.xlsx; 仅 CLI 终端输出

### 性能校准 (coarse/medium/fine 实测, NOT Search 预算)
- 3 候选 × 3 profile, warm-up=1, repeat=3, samples 复用
- Q1 锚点:      coarse 0.196 / medium 1.85 / fine 15.05 s (median)
- Q1 邻域:      coarse 0.196 / medium 1.82 / fine 14.86 s (median)
- 零目标:      coarse 0.182 / medium 1.76 / fine 13.63 s (median)
- 该结果**不**作为 Search 预算; 仅供 Foundation 校准; Search 预算需重启后再冻结.

## 下一阶段 (待审核后决定)

### TASK_004 Search: Q2 单弹最优策略正式搜索
进入条件:
1. Foundation PR 审核并合并
2. CI 持续 PASS
3. Foundation 性能已实测 (非外推) (本轮 3×3 = 9 行 median/min-max)
4. 搜索算法 / 收敛标准 / 性能预算重新冻结
5. 仍需外部 (陈虹宇) 显式授权才能启动 Search

TASK_004 Search 任务目的 (粗框架, 进入时细化):
- 在 (heading_rad, speed_mps, release_time_s, delay_s) 四维搜索空间上
  求 FY1 → M1 单弹最优策略
- 目标: 完整圆柱严格遮蔽总时长 (复用 TASK_003 strict_boundary_value)
- 关键决策: 搜索算法 (网格 / 局部 / 全局), 收敛标准, 候选生成约束
- 输出: result1.xlsx 之前必须冻结搜索算法与收敛标准

不得在没有 Foundation PR 合并前预先写 TASK_004 Search 代码.
