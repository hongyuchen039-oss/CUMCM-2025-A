# 当前唯一任务

## 本轮任务
**TASK_003 完整圆柱遮蔽判定冻结与 Q1 对照 (FULL-CYLINDER CANDIDATE / EXPERIMENTAL)** —
方案 B 完整圆柱正式模型冻结, 与 Q1 点目标基线对照完成, 等外部审核.

### 范围
- 实现完整圆柱表面采样 (单元中心法, coarse/medium/fine 三档)
- 实现凸体支持平面可见性测试 (n(X) · (M(t) − X) > 0)
- 实现严格遮蔽主判据 (所有可见表面采样被遮挡 ⇒ strict_occlusion)
- 实现覆盖率辅助诊断 (occluded_weight / visible_weight)
- 时间扫描 0.02 / 0.01 / 0.005 s 三档收敛 (复用 find_effective_intervals)
- 空间三档采样收敛 (coarse/medium/fine)
- 与 Q1 点目标基线对照 (ΔT = 方案 B − 方案 A)
- 生成 SVG (x-z 投影 + 时间对照面板)

### 仅允许新建
1. `src/q1_cylinder.py` (主程序, 复用 src/q1_baseline)
2. `tests/test_q1_cylinder.py` (单元测试 A-J 节, 46 测)
3. `outputs/q1/q1_cylinder_comparison.svg` (图像产物)

### 库限制
- 只使用 Python 标准库
- 不得强制安装 numpy / scipy / pandas / matplotlib

### 本轮明确不做
- 不生成 result1/2/3.xlsx (TASK_004 之前)
- 不启动 Q2 单弹优化
- 不修改官方原模板 / problem/*.pdf / 题目及模板/ / desktop.ini
- 不自动 merge 任何 PR
- 不动 main

### 本轮完成标准
1. 圆柱采样总权重 = 2πR_T H_T + 2πR_T² (误差 ≤ 1e-8) ✓
2. 法向量均为单位向量 (|n| = 1 ± 1e-12) ✓
3. 单元中心在 (0, H_T) 严格内部, 避免公共棱边 ✓
4. 46 个单元测试全过 ✓
5. 空间三档收敛: medium vs fine 总时长差 ≤ 5e-3 s, 区间数一致 ✓
6. 时间三档收敛: 三档起终点完全一致 ✓
7. 区间端点 max |f_cylinder(b)| ≤ 1e-4 ✓
8. SVG 合法可解析, 含圆柱标识 + 时间对照面板 + 图例 ✓
9. Q1 点目标基线 42/42 测试仍通过 (回归保证) ✓
10. commit + push 到 task/TASK_003-cylinder-freeze ✓ (待执行)
11. 更新同一 Draft PR #3 描述 ✓ (待执行)

### 计算结果 (来自 src/q1_cylinder.py 当前输出)
- 圆柱总时长 (fine, 12288 样本): **1.392384 s**
- 圆柱遮蔽区间 (fine): **(8.055704, 9.448088) s**
- 最大覆盖率 ρ_max = 1.000 @ t = 8.060 s
- 最大严格裕量 margin_max = 5.266 m @ t = 9.420 s
- 空间三档总时长: coarse 1.394606, medium 1.393131, fine 1.392384 s
- 时间三档总时长: 0.02/0.01/0.005 s 均 1.393131 s (medium 采样, 完全一致)
- ΔT (B − A) = **−0.042698 s**, 相对差异 **−2.975%**
- 等级: 仅 FULL-CYLINDER CANDIDATE / EXPERIMENTAL, 不得冒充 VERIFIED / FINAL

## 本轮后续 (待审核后决定)

PR #3 合并后进入 TASK_004: Q2 单弹最优策略.

TASK_004 任务目的:
- FY1 → M1 单弹最优化 (决策量: 航向, 速度, 投放点, 起爆点)
- 优化目标: 完整圆柱严格遮蔽总时长 (复用 TASK_003 strict_boundary_value)
- 起点: TASK_003 严格遮蔽边界函数 + Q1 点目标基线
- 关键决策: 搜索算法 (网格 / 局部 / 全局), 收敛标准

不得直接进入 Q2 单弹优化 (必须先冻结完整圆柱模型并合并 PR #3).