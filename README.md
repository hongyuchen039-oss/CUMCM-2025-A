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
- TASK_003 完整圆柱遮蔽判定冻结与 Q1 对照实现完成, 等待外部审核
- 数学模型: 方案 A (点目标基线) + 方案 B (完整圆柱严格遮蔽) 均已实现并对照
- 数值结果:
  - 方案 A Q1 基线 = **1.435082 s** (BASELINE / EXPERIMENTAL)
  - 方案 B 完整圆柱 = **1.392384 s** (FULL-CYLINDER CANDIDATE / EXPERIMENTAL)
  - ΔT (B − A) = **−0.042698 s** (相对差异 −2.975%, 见 RESULTS.md)