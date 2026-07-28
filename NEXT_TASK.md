# 当前唯一任务

## 任务编号
TASK_004 Q2 REAL SEARCH CORE V1 — FINAL REMAINING-P1 CLOSURE / VERIFICATION CORRECTION BUILT / WAITING FOR CLEAN-HEAD 3-RUN VERIFICATION

## 唯一目标
提交 Verification Correction 单次收口 commit (`FIX: finish evaluation-safe Q2 search closure`) → clean-HEAD uninterrupted/interrupted/resume 三轮验证（无 `--allow-dirty-worktree`）→ push → 更新 PR #9 → 等待独立审查 GPT 复核。

## 为什么值得做
v1.2 Verification Correction 已落地:
- 真实 per-evaluation checkpoint (RP1 evaluation-safe); stage-end 再额外存一次 stage-completed 副本;
- stop_after_evaluations 必须精确停在 N, 不得等 stage 结束;
- resume rows 按 source_stage partition; prior-stage rows 不污染当前 stage 排名;
- budget 修正: `global_coarse_count=96` + ANCHOR_COUNT=1 → stage global_coarse 实际 97; total 固定 163; 写入 97 时因总数=164 被 raise 拒绝;
- tests/test_q2_search_rp1.py 中 49 项增量 RP1 测试已合并进 tests/test_q2_search.py, rp1 文件已删除;
- tests/test_q2_search.py 134 个单元测试 (85 v1.1 + 49 RP1) 通过.

但 clean-HEAD 3-run 验证(无 `--allow-dirty-worktree`)尚未执行(spec 要求 commit-before-pilot).

## 输入
- v1.2 Verification Correction 源码（src/q2_search.py + configs/q2_search_gate_v1.json + tests/test_q2_search.py; tests/test_q2_search_rp1.py 已删除）;
- git HEAD 待 commit;
- PR #9.

## 允许修改
本轮可写入：MODEL.md, START_HERE.md, NEXT_TASK.md, README.md, configs/q2_search_gate_v1.json, src/q2_search.py, tests/test_q2_search.py, tests/test_q2_search_rp1.py (本轮删除), work/ (untracked, 不入 PR), PR #9 描述; 其它冻结.

## 禁止修改
- Q1 与 Q2 Foundation 数学和代码 (q1_baseline/q1_cylinder/q2_single_bomb);
- RESULTS.md;
- problem/;
- result1/2/3.xlsx;
- main;
- Git 历史;
- .github/、outputs/、scripts/、CLAUDE.md、.claude/skills/.

禁止扩大预算（必须保持 163 evaluations 固定，含 anchor）、进入 Q3、声明全局最优、自动合并、自动转 Ready、使用 `--allow-dirty-worktree`、把旧 4a8ee08 / f81f436 pilot identity (`8861203e...` / `98 global_coarse` / `164 completed_count`) 写回 MODEL.md / PR 描述 / 代码.

## 必须执行
- 仅一次最终 commit (`FIX: finish evaluation-safe Q2 search closure`), 不得 baseline commit / 中间 commit / amend;
- commit BEFORE pilot (clean HEAD first);
- clean-HEAD pilot (A) uninterrupted → rc=0 + global_coarse=97 + total=163 + completed_count=163 + worktree_dirty=false + system_error=0 + fine finalists=2;
- clean-HEAD pilot (B) interrupted (`--stop-after-evaluations 50`) → rc=3 + completed_count=50 + interrupted_stage=global_coarse (不得继续到 97) + checkpoint_v2.json + controlled_interruption.json 完整;
- clean-HEAD pilot (C) resume from B → rc=0 + resumed_n_completed=50 + newly_evaluated=113 + total=163 + 无重复 ID + canonical_result_sha256 / run_identity_sha256 / lineage_manifest_sha256 / finalists / final_best 与 A 完全一致;
- 每轮之后 `git status --short` 必须为空 (不允许 dirty);
- 不得使用 `--allow-dirty-worktree`;
- push + 更新 PR #9 描述 (移除 4a8ee08 / f81f436 旧 identity, 记录 Verification Correction clean-HEAD 3-run 证据);
- 50-item 验收报告.

## 必须产出
- 一次冻结 commit (`FIX: finish evaluation-safe Q2 search closure`);
- work/q2_search_final_exact*/ 下三组 pilot artifacts (uninterrupted + interrupted + resume 三轮);
- PR #9 更新描述 (Verification Correction 证据);
- tests/test_q2_search.py 中 134 个测试全部 PASS.

## 验收标准
1. RP1-1..7 + P2 uniq output 全部闭合, 且在 Verification Correction 下语义重新验证 (per-eval ckpt / stage partition / 163 fixed budget / 47+1 项 RP1 测试合并回 test_q2_search / rp1 文件删除);
2. 134 个 Q2 search 单元测试通过 (85 v1.1 + 49 RP1 合并);
3. clean-HEAD uninterrupted/interrupted/resume 三轮验证全部 rc 正确, 数字符合上述要求;
4. uninterrupted 与 resumed canonical_result_sha256 / run_identity_sha256 / lineage_manifest_sha256 完全一致, finalists 与 final_best 完全一致, 无重复 evaluation_id;
5. 不修改 Q1/Q2 Foundation; 不写入 RESULTS.md; 不生成 result1/2/3.xlsx; 不使用 `--allow-dirty-worktree`;
6. PR changed files 严格为 8 个 (MODEL.md / NEXT_TASK.md / README.md / START_HERE.md / configs/q2_search_gate_v1.json / src/q2_search.py / tests/test_q2_search.py / tests/test_q2_search_rp1.py 的删除).

## 返工
RP1 + Verification Correction 闭合为本轮最后一次返工上限 (spec 明示).

## 停止条件
clean-HEAD 3-run 验证完成 + PR #9 更新后立即停止, 不自动转 Ready、不合并、不进入下一阶段、不启动 Audit CC / Hermes / TASK_GOV_002.