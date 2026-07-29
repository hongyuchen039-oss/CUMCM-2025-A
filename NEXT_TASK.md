# 当前唯一任务

## 任务编号
TASK_005 Q2 FORMAL EVIDENCE PATCH BUILT AND RERUN — WAITING FOR INDEPENDENT MATH/RESULT REVIEW

## 唯一目标
不修改本任务分支；不进入 Q3；不写 result1.xlsx；不声明全局最优。
等待独立审查（Audit CC / Hermes）复算 winner 物理量 + 稳定性 +
16 项 one-var 扰动 + finalist pool 解释性。仅在审查通过后另立
TASK_006（Q3 三弹串接 / result1.xlsx）。

## 为什么值得做
TASK_005 P1 闭环已在本任务分支完成（clean-HEAD 467314d）：
- 独立 schema 3 / gate_id `q2_search_formal_v1` / declaration
  `FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM`；
- 三 seeds (2025, 2026, 2027) × 1000 evals/seed × 5-stage pipeline 全部完成，
  formal_run_identity_sha256 三个 seed 各异；
- 跨 seed 13 finalists (cross-seed dedup tolerance 1e-6)；
- pilot best-known 已显式注入（priority 1 = work/q2_pilot_calib/pilot_result.json，
  priority 2 = deterministic seed=2025 fixed-163 clean pilot rerun，
  priority 3 = BLOCKED, 不静默 fallback)；
- 统一 fine cylinder re-evaluation (scan_step=0.005) → winner 与 pilot
  fixed-163 best-known 完全一致
  (h=3.121767217560497, s=115.43351397802584, r=1.7672692031529031,
  d=3.889202402720746, dur=2.48275905609131 s)；
- canonical_result_sha256 = `2efcc91486d4ce9d22bfdedc0a4d57c36857d506126bca40c1a31695a96d1b3a`
  (与 PRE-FIX 的 `fa279e3fcc6…` 不同)；
- 0.02 / 0.01 / 0.005 三档 duration delta=0.000s, stability_ok=True；
- **16 项 one-var-at-a-time 扰动 (4 vars × 2 signs × 2 scales) 全部执行**，
  5/16 改善 → local_perturbation_passed=False (winner 不是 16 项
  one-var 邻域局部极值, 但扰动值均 ≥ winner dur, 故保留 best-known)；
- 物理合法性校验通过（speed ∈ [70,140], release ≥ 0, delay 在落地约束内,
  heading ∈ [0, 2π)）；
- **307 项 unittest 全 PASS** (42 q1_baseline + 75 q1_cylinder + 148 q2 pilot +
  22 FormalProfileTests + 20 P1EvidenceGateTests), 本轮唯一一次全量回归；
- PR #11 "TASK_005: formalize and freeze Q2 best-known result" 已开 Draft.

## 输入
- src/q2_search.py（仅追加 formal block + 16 one-var 扰动代码,
  pilot fixed-163 不动）；
- configs/q2_search_formal_v1.json (新, schema 3)；
- scripts/run_q2_formal.py (新, 唯一 orchestrator, fail-closed 全部启用)；
- tests/test_q2_search.py（追加 22 个 FormalProfileTests + 20 个
  P1EvidenceGateTests, 共 42 个新测试, 原 148 个不动）；
- outputs/q2/q2_formal_summary.json + per_seed_summary.json (tracked)；
- work/q2_formal/ + work/q2_pilot_calib/（gitignored, raw artifacts）；
- START_HERE.md / NEXT_TASK.md / README.md / MODEL.md / RESULTS.md；
- Draft PR #11 "TASK_005: formalize and freeze Q2 best-known result".

## 允许修改
本轮（仅剩收口动作）：
- START_HERE.md / NEXT_TASK.md / README.md / MODEL.md / RESULTS.md；
- 1 个 REVIEW 风格 commit；
- PR #11 描述更新；
- 307 项 unittest 全量回归。

## 禁止修改
- configs/q2_search_gate_v1.json（pilot 不动）；
- src/q1_baseline.py / src/q1_cylinder.py / src/q2_single_bomb.py；
- tests/test_q1_baseline.py / tests/test_q1_cylinder.py /
  tests/test_q2_single_bomb.py；
- scripts/verify_task_context.py；
- tests/test_verify_task_context.py；
- problem/；
- outputs/submission/；
- result1/2/3.xlsx；
- .github/；
- CLAUDE.md / .claude/；
- main / Git 历史；
- 旧 pilot identity（4a8ee08 / f81f436 / 8861203e… / 98 global_coarse /
  164 completed_count）不得回写 MODEL.md / PR 描述 / 代码；
- 旧 PRE-FIX canonical_result_sha256（fa279e3fcc6…）不得覆盖当前
  2efcc91486d4… 数字；
- 旧 4-方向扰动（仅 4 条对角线）不得回写, 必须保持 16 项 one-var 描述.

禁止：自动合并 / 自动转 Ready / 自行写入 result1.xlsx / 启动 Q3 / 扩大
formal 预算到 2000（> 3600s wall-clock gate）/ 声明全局最优 / 改写
正式历史。

## 必须执行
1. 收口：START_HERE.md / NEXT_TASK.md / RESULTS.md 已切到 P1 闭环；
2. 1 个 REVIEW 风格 commit（不拆分、不 amend、不 baseline commit）；
3. push 到 task/TASK_005-q2-formal-search；
4. 更新 PR #11 描述（含 canonical_result_sha256 + 16 one-var 结果）；
5. 307 项 unittest 全量回归 `python -m unittest discover -s tests -p "test_*.py" -v`；
6. 报告：`TASK_005 FORMAL EVIDENCE PATCH BUILT AND RERUN — WAITING FOR INDEPENDENT MATH/RESULT REVIEW`；
7. 停止（不自动进入下一阶段，不自动合并，不启动 Q3 / Audit CC / Hermes / TASK_GOV_002）。

## 必须产出
- 1 个收口 commit（REVIEW 前缀）；
- PR #11 "TASK_005: formalize and freeze Q2 best-known result" 草稿已更新；
- 307 项 unittest 全部 PASS（42 q1_baseline + 75 q1_cylinder + 148 q2 pilot +
  22 formal + 20 P1）；
- 收口报告（含 old/new HEAD, 两个新 commit, 实际 changed files, 已删
  tracked artifacts, clean-HEAD 证据, per-seed actual counts, formal
  config/run identity, pilot injection source, finalist pool, winner 物理量,
  scan 稳定性, 16 one-var 扰动汇总, 测试数/timing, Harness 状态, Q3
  未启动, result.xlsx 未生成, PR Draft, worktree clean）；
- 独立审查 checklist（winner 物理量复算 / 稳定性 / 16 one-var 扰动 /
  finalist pool 解释性）。

## 验收标准
1. 42 q1_baseline + 75 q1_cylinder + 148 q2 pilot + 22 formal + 20 P1 =
   307 项全 PASS；
2. PR #11 是 Open / Draft；
3. declaration = `FORMAL BEST-KNOWN Q2 CANDIDATE / NOT A PROVEN GLOBAL OPTIMUM`；
4. final_best_status = `OK_FINE_RESULT` (3 seeds 全部)；
5. 不写入 result1/2/3.xlsx，不启动 Q3，不声明全局最优；
6. pilot best-known 数值与 formal winner 数值一致
   (h=3.121767217560497, s=115.43351397802584, r=1.7672692031529031,
   d=3.889202402720746, dur=2.48275905609131 s)；
7. stability_ok=True, perturbation.n_total_perturbations=16,
   perturbation.any_improves=True (5/16),
   perturbation.local_perturbation_passed=False,
   physical_validity.ok=True；
8. canonical_result_sha256 = 2efcc91486d4… (与 PRE-FIX fa279e3fcc6… 不同)；
9. 入口文档同步（START_HERE.md / NEXT_TASK.md / README.md / MODEL.md / RESULTS.md）。

## 停止条件
独立审查清单交付 + 307 项全量回归 PASS + PR #11 已开 Draft 后立即停止，
不自动合并、不进入 Q3 / TASK_006、不启动 Audit CC / Hermes / TASK_GOV_002。