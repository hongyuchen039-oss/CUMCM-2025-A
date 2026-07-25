# 当前唯一任务

## 本轮任务
**TASK_002 Q1 点目标最小可运行基线 (BASELINE / EXPERIMENTAL)**

依据审核通过的 PR #1（已 merge 到 main）进入。

### 范围
- 实现 Q1 运动学 + 点目标遮蔽判定 (方案 A 基线)
- 验证 §13 手算量：投放点 R = (17620, 0, 1800)、起爆点 D = (17188, 0, 1736.496)（容忍 ≤ 1e-6 m）
- 三档扫描步长 0.02/0.01/0.005 s 的收敛性 (max Δt ≤ 0.01 s)
- 生成 SVG 图 (x-z 投影, 含 M1/FY1/烟幕弹/云团/遮蔽区间标注)

### 仅允许新建
1. `src/q1_baseline.py` （主程序）
2. `tests/test_q1_baseline.py` （单元测试 A-H 节）
3. `outputs/q1/q1_baseline_plot.svg` （图像产物）

### 库限制
- 只使用 Python 标准库
- 不得强制安装 numpy / scipy / pandas / matplotlib

### 本轮明确不做
- 不生成 result1/2/3.xlsx (TASK_003 之前)
- 不实现方案 B 完整圆柱正式模型 (Q2 之前冻结)
- 不实现 Q2 最优化
- 不修改官方原模板 / problem/*.pdf / 题目及模板/ / desktop.ini
- 不自动 merge 任何 PR
- 不动 main

### 本轮完成标准
1. 手算 R, D 与代码输出一致 (容忍 ≤ 1e-6 m)
2. M1 速度方向正确 (|v| = 300, 不是 (-300,0,0))
3. 29 个单元测试全过
4. 三档扫描步长结果稳定 (max Δt ≤ 0.01 s)
5. SVG 合法可解析, 含关键点标签
6. commit + push 到 task/TASK_002-q1-baseline
7. 创建 Draft PR (含 12 问审查清单)

### 计算结果 (来自 src/q1_baseline.py 当前输出)
- 投放点: (17620.000000, 0, 1800.000000) m
- 起爆点: (17188.000000, 0, 1736.496000) m
- M1 速度: (-298.511157, 0, -29.851116) m/s, |v|=300 m/s
- M1 到达假目标理论时刻: 66.999 s
- 遮蔽区间 (方案 A 点目标): (8.013006, 9.448088) s
- **有效遮蔽总时长 (BASELINE / EXPERIMENTAL): 1.435082 s**
- 等级: 仅 BASELINE / EXPERIMENTAL, 不得冒充 VERIFIED / FINAL

## 本轮后续 (待审核后再决定)
- GPT 复审 12 问审查清单
- 待审通过后: 决定是否推进到 TASK_003 (Q2) 或仍冻结在 Q1 基线对拍
