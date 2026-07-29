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

TASK_005 Q2 FORMAL SEARCH & RESULT FREEZE — P1 EVIDENCE GATE 已落地：
- 独立 schema 3 (gate_id `q2_search_formal_v1`)；
- declaration = `FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM`；
- 真实 formal execution contract：`run_formal_pipeline` 显式走
  `require_clean_worktree=True` + cli_overrides 注入 formal budget，
  实际 stage counts / completion / unique eval ids 全部从 pipeline 实际
  数据重建，绝不复制 expected config；
- 3 seeds (2025, 2026, 2027) × 1000 evals/seed × 5-stage pipeline；
- 跨 seed finalist pool 13 candidates，pilot best-known 显式注入
  (优先 `work/q2_pilot_calib/pilot_result.json`，fallback 确定性
  seed=2025 fixed-163 clean pilot 重跑)；
- 统一 fine cylinder re-evaluation（scan_step=0.005）→ winner；
- 时间步长稳定性：0.02 / 0.01 / 0.005 三档 delta=0.000s；
- **16 项 one-variable-at-a-time 扰动**（4 变量 × 2 方向 × 2 尺度），
  全部未改善 winner，local_perturbation_passed=True；
- 物理合法性校验通过；
- 22 个 FormalProfileTests + 20 个 P1 证据门测试全部通过；
- raw per-seed artifacts 已从 tracked tree 删除，仅保留
  `outputs/q2/q2_formal_summary.json` 和
  `outputs/q2/per_seed_summary.json`（compact summary），
  原始 `pilot_result.json` / `checkpoint_v2.json` 改写到 gitignored
  `work/q2_formal/seed_*/`；
- 全量 453 项 unittest 通过。

## 结果等级

TASK_005 output 是 **BEST-KNOWN**，**NOT A PROVEN GLOBAL OPTIMUM**。
要继续推进到 Q3 / Q4 / Q5 / result1/2/3.xlsx / 论文，必须先经过独立审查
（Audit CC / Hermes）签字，并另立 TASK_006。
