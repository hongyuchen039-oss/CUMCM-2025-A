# 项目驾驶舱

## 最终目标
完成 2025 CUMCM A 题 Q1–Q5 的可信建模、数值策略、result1/2/3.xlsx 与论文。

## 当前问题
Q2 单架 FY1 投放一枚烟幕弹的最优策略。

## 当前阶段
TASK_004 Q2 REAL SEARCH CORE V1
— FINAL REMAINING-P1 CLOSURE / VERIFICATION CORRECTION BUILT
/ WAITING FOR CLEAN-HEAD 3-RUN VERIFICATION + REVIEW.

## 最后可信成果
Q1 点目标与完整圆柱结果已冻结；Q2 单候选真实评估器已接入；Real Search Core v1.2 已完成 RP1 全部闭合（effective config / structured code identity / evaluation-safe per-evaluation checkpoint + stage-end extra ckpt / resume rows partitioned by source_stage / canonical_result_sha256 / two-finalist lineage / dirty-worktree rejection / 163 fixed budget via anchor-aware accounting）；tests/test_q2_search.py 134 个单元测试通过（85 v1.1 + 49 RP1；tests/test_q2_search_rp1.py 已合并并删除）。

## 当前最大不确定性
Verification Correction 已落地但尚未执行 clean-HEAD uninterrupted/interrupted/resume 三轮实测（待本轮最终 commit 后执行）；不接受 `--allow-dirty-worktree`。

## 当前唯一任务
提交 v1.2 Verification Correction 闭合 (`FIX: finish evaluation-safe Q2 search closure`) → clean-HEAD pilot (uninterrupted/interrupted/resume) 三轮验证 → push → 更新 PR #9 → 等待独立审查 GPT 复核。

## 当前阻断
等待 v1.2 Verification Correction 收口 commit + 无 `--allow-dirty-worktree` 的 clean-HEAD 3-run 验证。

## 下一里程碑
clean-HEAD pilot + interrupted + resume 验证通过后更新 PR #9。

## 尚未进入
正式大预算 Q2 Search、Q2 正式结果冻结、Q3、result1.xlsx、Q4、Q5、论文。