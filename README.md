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

Q1 与 Q2 单候选评估基础已经完成；Q2 Real Search Core v1.2 Verification Correction 已落地（真实 per-evaluation checkpoint + stage-end 额外 ckpt / resume rows 按 source_stage partition / 163 fixed budget via anchor-aware accounting: global_coarse_count=96 随机 + ANCHOR_COUNT=1 → stage global_coarse=97 + global_medium=8 + local_coarse=48 + local_medium=8 + fine=2 = 163；试写 `global_coarse_count=97` 因实际总数=164 必 raise；tests/test_q2_search_rp1.py 已合并并删除，49 项增量 RP1 测试全部移入 tests/test_q2_search.py）；134 个单元测试通过；当前等待 clean-HEAD uninterrupted/interrupted/resume 三轮实测（无 `--allow-dirty-worktree`）与独立审查 GPT 复核。

## 结果等级

pilot 与 best-known candidate 仅用于验证搜索核心：
NOT A FORMAL Q2 RESULT / NOT A PROVEN GLOBAL OPTIMUM。