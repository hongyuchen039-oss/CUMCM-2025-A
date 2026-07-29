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

Q1 与 Q2 单候选评估基础已经完成；Q2 Real Search Core v1.2 Verification Correction 已冻结在 main（pilot fixed-163 / 真实 per-evaluation checkpoint / resume rows 按 source_stage partition / 本任务分支不再修改）。

TASK_005 Q2 FORMAL SEARCH & RESULT FREEZE 已在本分支独立完成：
- 独立 schema 3 (gate_id `q2_search_formal_v1`)；
- declaration = `FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM`；
- 3 seeds (2025, 2026, 2027) × 1000 evals/seed × 5-stage pipeline；
- 跨 seed 13 finalists，pilot best-known 已显式注入并复评为 winner；
- 0.02 / 0.01 / 0.005 三档 duration delta=0.000s；
- 4 方向扰动均未改善 winner（局部收敛）；
- 物理合法性校验通过；
- 22 个 FormalProfileTests 通过，148 个 pilot 测试未删除或放宽。

## 结果等级

TASK_005 output 是 **BEST-KNOWN**，**NOT A PROVEN GLOBAL OPTIMUM**。
要继续推进到 Q3 / Q4 / Q5 / result1/2/3.xlsx / 论文，必须先经过独立审查
（Audit CC / Hermes）签字，并另立 TASK_006。
