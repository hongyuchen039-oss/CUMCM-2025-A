# CUMCM 2025 A — 烟幕干扰弹的投放策略

本项目研究无人机投放烟幕干扰弹，对来袭导弹实施有效遮蔽的建模与优化策略。

## 项目入口

- [START_HERE.md](./START_HERE.md) — 当前状态与唯一任务
- [MODEL.md](./MODEL.md) — 模型、假设与算法合同
- [RESULTS.md](./RESULTS.md) — 已验证结果与可信等级
- [NEXT_TASK.md](./NEXT_TASK.md) — 当前执行边界与验收标准
- [problem/FACTS.md](./problem/FACTS.md) — 官方题目事实与模板要求
- [CLAUDE.md](./CLAUDE.md) — 仓库长期工作规则

## 当前状态

Q1 与 Q2 单候选评估基础已经完成；Q2 Real Search Core v1.2 已完成 RP1 全量闭合（effective config / structured code identity / evaluation-safe checkpoint / canonical_result_sha256 / two-finalist lineage / dirty-worktree rejection）；133 个单元测试通过；pilot 固定 163 evaluations 预算；当前等待 clean-HEAD pilot + interrupted + resume 实测与独立审查 GPT 复核。

## 结果等级

pilot 与 best-known candidate 仅用于验证搜索核心：
NOT A FORMAL Q2 RESULT / NOT A PROVEN GLOBAL OPTIMUM。