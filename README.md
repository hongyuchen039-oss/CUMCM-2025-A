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

TASK_005 Q2 FORMAL SEARCH + BOUNDED REFINEMENT + CLEAN-HEAD VERIFICATION IDENTITY CLOSURE + INDEPENDENT AUDIT 已收口，canonical Q2 result 已晋升：

- **Q2 canonical candidate**:
  `heading_rad=3.126767217560497, speed_mps=116.43351397802584, release_time_s=1.2672692031529031, delay_s=3.789202402720746`
  `total_duration_s = 4.260970878601073`
  `interval (s) = (5.089825368500298, 9.350796247101371)`
- **等级**: `FORMAL BUDGET-LIMITED BEST-KNOWN Q2 CANDIDATE / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM`
- **晋升依据**: 独立 Audit 结论 B (audit passed with doc-only P2, promote after one documentation commit)
- **晋升范围**: 仅 doc-only P2 闭合；不重跑 3×1000；不重跑完整 16 项扰动；不重跑全量测试
- **旧候选** `(3.121767, 115.4335, 1.767269, 3.889202)` dur `2.48275905609131 s` 已降级为 `HISTORICAL FORMAL-SEARCH CANDIDATE`，因旧 16 项扰动 5/16 改善触发 bounded refinement

## Q2 多阶段证据分层

### 1. Q2 formal multi-seed search (TASK_005 P1 closure)
- 3 seeds (2025, 2026, 2027) × 1000 evals/seed × 5-stage pipeline
- 跨 seed finalist pool 13 candidates, pilot best-known 显式注入
- 统一 fine cylinder re-evaluation (scan_step=0.005) → 旧 winner (2.48275905609131 s)
- 时间步长稳定性：0.02 / 0.01 / 0.005 三档 delta=0.000 s
- **16 项 one-var-at-a-time 扰动**：5/16 改善（speed_mps −1 / release_time_s −1 / delay_s +0.1）→ 旧候选不是 16 项邻域局部极值，因此触发 bounded refinement（不是"全部未改善"）
- 物理合法性校验通过
- 22 FormalProfileTests + 20 P1EvidenceGateTests PASS

### 2. Bounded refinement (32 evaluations, ≤2100 s)
- 2 parent rehydration (formal winner + pert_09 best)
- 3-level coordinate search (heading ±0.02/0.01/0.005, speed ±1.0/0.5/0.25, release ±0.2/0.1/0.05, delay ±0.1/0.05/0.025)
- 单 sweep greedy, hard wall-clock gate, atomic checkpoint per eval
- 32/32 budget exhausted (BUDGET EXHAUSTED ≠ CODE FAILED)
- refined candidate dur=4.260970878601073 s（sweep scan_step=0.01）
- 20 RefinementGateTests PASS

### 3. Clean-head verification identity closure (5 evaluator calls)
- identity: worktree-clean + HEAD sha + script sha256 + q2_search code identity + refinement_config_sha256 + parent candidate identity + checkpoint_source_head_sha 全通过
- delay_s ±0.025 (2 evals): 4.258950 / 4.140284 s, neither improves best-known
- stability 0.02 / 0.010 / 0.005 (3 evals): 三档 duration 完全一致, eval_id 同
- physical_validity ok=True
- elapsed = 76.13 s (well under 300 s)
- declaration: BUDGET-LIMITED BEST-KNOWN / LOCAL CONVERGENCE NOT ESTABLISHED / NOT A PROVEN GLOBAL OPTIMUM

### 4. Independent Audit (6 evaluator calls, exact match)
- audit conclusion B: passed with doc-only P2
- identity chain 全通过
- 独立数学复算 6/6 精确一致
- 不需要重跑 3×1000 / 完整 16 项扰动 / 全量测试
- 仅需一个 doc-only commit 闭合 P2

## 测试证据分层

| 阶段 | 测试范围 | 结果 |
|---|---|---|
| formal P1 closure | 473/473 full regression | PASS |
| refinement | 210/210 tests.test_q2_search | PASS |
| clean-head verification | 5 evaluator calls (无测试) | identity / stability / physical validity PASS |
| independent Audit | 6 evaluator calls, exact match | PASS |

不把不同阶段测试数合并成一个虚假的当前测试数。

## 结果等级

TASK_005 canonical Q2 output 是 **FORMAL BUDGET-LIMITED BEST-KNOWN**，
**NOT A PROVEN GLOBAL OPTIMUM**，**LOCAL CONVERGENCE NOT ESTABLISHED**。
要继续推进到 Q3 / Q4 / Q5 / result1/2/3.xlsx / 论文，必须先经过 Hermes 只读核验
（不修改任何文件），然后由 MAIN / 用户决定 Ready / merge，并另立 TASK_006。