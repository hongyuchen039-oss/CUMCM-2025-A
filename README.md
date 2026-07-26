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
- TASK_003 完整圆柱遮蔽判定候选已实现, 与 Q1 对照完成, PR #3 audit-fix 已更新,
  完整圆柱正式候选等待审核冻结; PR #3 合并后才允许进入 TASK_004
- 数学模型: 方案 A (点目标基线) + 方案 B (完整圆柱严格遮蔽, FULL-CYLINDER CANDIDATE)
  均已实现并对照
- 数值结果 (本轮 FIX 后实测):
  - 方案 A Q1 基线 = **1.435082 s** (BASELINE / EXPERIMENTAL)
  - 方案 B 完整圆柱 = **1.392384 s** (FULL-CYLINDER CANDIDATE / EXPERIMENTAL)
  - ΔT (B − A) = **−0.042698 s** (相对差异 −2.975%, 见 RESULTS.md)
  - margin_max (0.001 s 局部网格估计) = **5.282478 m** @ t = 9.418317 s (非解析极值)
  - ρ_max = 1.000; ρ=1 平台 (0.01 s 诊断网格) 约 (8.06, 9.44) s, 跨度 1.380 s
  - 时间/空间收敛均 PASS (端点 max \|f\| = 1.03e-6)
  - 75 单元测试 (A-L, 含 2 个收敛失败路径测试) 全过 + 42 Q1 基线回归 全过