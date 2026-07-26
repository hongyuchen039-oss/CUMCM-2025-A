# CUMCM 2025 A — 烟幕干扰弹的投放策略

2025 年高教社杯全国大学生数学建模竞赛 A 题。

## 入口

- [START_HERE.md](./START_HERE.md) — 当前状态、风险、需你决定
- [MODEL.md](./MODEL.md) — 题目、模型思路、假设、局限
- [RESULTS.md](./RESULTS.md) — 当前结果与可信等级
- [NEXT_TASK.md](./NEXT_TASK.md) — 唯一当前任务
- [CLAUDE.md](./CLAUDE.md) — Claude Code 长期工作规则
- [problem/FACTS.md](./problem/FACTS.md) — 官方题目事实

## 状态

CI：GitHub Actions 自动运行 Python 编译、单元测试与 Q1 smoke test。

- TASK_003 完整圆柱遮蔽判定已完成审核并通过 PR #3 合并
- TASK_INFRA_001 CI 已通过 PR #4 合并并进入 main
- 完整圆柱模型合同已经冻结，可供 TASK_004 复用
- **TASK_004 FOUNDATION 已完成并通过 7 个 P1 加固**: 71 个本地单元测试全过
- TASK_004 Search 阶段尚未启动; 本轮不生成 result1.xlsx
- 数学模型: 方案 A (点目标基线) + 方案 B (完整圆柱严格遮蔽, FULL-CYLINDER CANDIDATE)
  均已实现并对照; Q2 评估器复用完整圆柱接口 (回调注入, 无几何复制)
- 数值结果 (TASK_003 实测):
  - 方案 A Q1 基线 = **1.435082 s** (BASELINE / EXPERIMENTAL)
  - 方案 B 完整圆柱 = **1.392384 s** (FULL-CYLINDER CANDIDATE / EXPERIMENTAL)
  - ΔT (B − A) = **−0.042698 s** (相对差异 −2.975%, 见 RESULTS.md)
  - margin_max (0.001 s 局部网格估计) = **5.282478 m** @ t = 9.418317 s (非解析极值)
  - ρ_max = 1.000; ρ=1 平台 (0.01 s 诊断网格) 约 (8.06, 9.44) s, 跨度 1.380 s
  - 时间/空间收敛均 PASS (端点 max \|f\| = 1.03e-6)
- 单元测试计数: 188 个全过 (42 Q1 baseline + 75 Q1 cylinder + 71 Q2 foundation)