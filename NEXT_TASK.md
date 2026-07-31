# TASK_007-P0/P1 Q4 THREE-DRONE FOUNDATION PREFLIGHT AND CONTRACT FREEZE

> 唯一当前门是 TASK_007-P0/P1: Q4 三机协同 (FY1/FY2/FY3 各 1 枚 → M1) 的
> foundation preflight + 12 维 candidate 评估合同冻结。
> **不**进入 Q4 evaluator 实现、**不**进入 Q4 搜索、**不**生成 result2.xlsx。
> 本轮最高状态: TASK_007-P0/P1 CONTRACT FROZEN / IMPLEMENTATION NOT STARTED /
> RESULT2.XLSX NOT GENERATED。

## 阶段状态

| 阶段 | 状态 |
|---|---|
| TASK_006-P3 (Q3 result1.xlsx) | **COMPLETE + MERGED** (PR #13 → main @ `2839151c9ef027c200f84ec342e17d43874ca254`) |
| TASK_007-P0/P1 (Q4 foundation preflight + contract freeze) | **IN PROGRESS — THIS PR** |
| TASK_007-P2 (Q4 formal bounded search) | **NOT STARTED** |
| TASK_007-P3 (result2.xlsx generation) | **NOT STARTED** |
| TASK_008 | **NOT STARTED** |

## 起点身份 (P0/P1 启动)

| 字段 | 值 |
|---|---|
| 起始 HEAD (main) | `2839151c9ef027c200f84ec342e17d43874ca254` (PR #13 mergeCommit) |
| 起始 HEAD (本任务分支) | `2839151c9ef027c200f84ec342e17d43874ca254` (branched from main, ahead=0, behind=0) |
| 分支 | `task/TASK_007-q4-result2` |
| base_branch | `main` |
| base_sha | `2839151c9ef027c200f84ec342e17d43874ca254` |
| task_id | `TASK_007-P0P1` |
| phase_id | `TASK_007-P0P1` |
| contract_version | 1 |
| expected_head | `2839151c9ef027c200f84ec342e17d43874ca254` |
| worktree | `C:\Users\33560\Desktop\CUMCM_2025_A` |
| repository | `hongyuchen039-oss/CUMCM-2025-A` |
| pr_number | (创建后填入) |

## 本轮范围 (CONTRACT ONLY)

按 MODEL.md "TASK_007 Q4 THREE-DRONE FOUNDATION CONTRACT" §10 完整冻结以下合同：

1. **12 维 `ThreeDroneCandidate`**: 3 × 4 (heading_rad / speed_mps /
   release_time_s / delay_s), 每架独立 (Q4 与 Q3 共享 heading/speed 的 §3 [约定]
   严格相反)。
2. **三架 heading / speed 独立**: 显式声明与 Q3 共享规则的差异（FACTS.md §9
   "每架无人机的航向、速度可不相同"）。
3. **Q2 evaluator u0 复用**: 确认 `evaluate_single_bomb_strategy` /
   `validate_strategy` / `release_point` / `detonation_point` 全部接受并使用
   `u0` 参数，Q4 = 3 次单弹 evaluator 调用 + 每架传入对应 u0 (FY1 / FY2 / FY3)。
4. **interval-union 目标**: `measure(I_FY1 ∪ I_FY2 ∪ I_FY3)` (NOT sum)；
   复用 Q3 `normalize_intervals` / `union_intervals` / `total_union_duration`。
5. **`ThreeDroneEvaluation` 输出合同**: valid / status / drone_evaluations
   (长度=3) / union_intervals / total_union_duration_s /
   q4_evaluation_id (SHA-256 over 12-dim + drone_order + sample_level +
   scan_step + candidate_schema_version + q2 code sha + q3 helper sha +
   q4 pilot config sha)。
6. **result2.xlsx 写盘合同**: 3 行数据 (FY1/FY2/FY3 drone_order), 列 A=drone_id,
   B=heading_deg, C=speed_mps, D-F=release xyz, G-I=detonation xyz,
   J=per-drone own duration (NOT union); sheet name `Sheet1` / header row /
   B6 note 全部保留。
7. **未来预算冻结规则 (NOT 数字)**: TASK_007-P2 必须基于 Q3 P2 实测 wall-clock
   **重新冻结** task-specific 数值；不得沿用 Q3 数字。
8. **候选源占位 (待 P2 frozen)**: 8 类 candidate_source 字段在 P2 启动前由
   MAIN 冻结。

## 显式不做 (本轮 boundary)

- 不创建 `src/q4_three_drones.py` / `tests/test_q4.py`；
- 不实现 Q4 evaluator / search / pilot CLI；
- 不运行任何 Q4 evaluator / 任何搜索；
- 不创建 `outputs/submission/result2.xlsx`；
- 不修改 Q1 / Q2 / `src/q3_three_bombs.py` / `src/q3_search.py` 任何
  foundation 文件；
- 不修改 result1.xlsx 或其 evidence；
- 不修改官方模板 ZIP、不解压模板到仓库；
- 不创建 CI / 不修改 workflow；
- 不安装任何依赖 (scipy / numpy / pandas 等)；
- 不启动 Audit CC / Hermes (MAIN 决定)；
- 不 Mark Ready / merge；
- 不启动 TASK_008；
- 不声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum /
  Q4 IMPLEMENTED / Q4 SEARCHED / RESULT2 GENERATED / Q4 EVALUATOR VALIDATED /
  官方答案。

## 身份链 (P0/P1 锁定)

| 字段 | SHA / 值 |
|---|---|
| 起始 HEAD (main) | `2839151c9ef027c200f84ec342e17d43874ca254` |
| 本任务起始 HEAD | `2839151c9ef027c200f84ec342e17d43874ca254` (ahead=0, behind=0) |
| 上一个 phase | `TASK_006-P3-HASH-SEMANTICS-FIX` (contract_version=7) |
| 本 phase | `TASK_007-P0P1` (contract_version=1) |
| contract_snapshot_path | `work/task_contracts/TASK_007-P0P1-v1.json` (untracked, 本机保留) |

## 官方 result2.xlsx 模板 read-only 验证 (P0/P1 内完成)

| 字段 | 值 |
|---|---|
| 官方 ZIP SHA-256 | `f9879c0d36b7bdccb99fb330a8032e62851ab1a1f0a1636c92440a1cdaec658e` (14884 bytes, 3 members) |
| result2.xlsx member size | 5272 bytes |
| result2.xlsx member SHA-256 | `91fbc42459aa4c98838b0a4dbe740ec5b970436c3f86d8a22dd7303f127cf106` |
| result2.xlsx member 唯一 | YES (1/3) |
| sheet names | `['Sheet1']` |
| header 行 / 列 | row 1, A1:J1 |
| reserved data 行范围 | rows 2-5 (4 rows; FACTS.md §13.2 写 3, 实际 4) |
| note 行 / cell | row 6 / B6 |
| merged cells | 无 |
| freeze_panes | 无 |

详细验证日志: `work/q4_foundation/result2_template_readonly_check.json` (untracked)。

注: FACTS.md §13.2 写 "数据行 3 行 (FY1/FY2/FY3 各一条)"，但实际模板预留 4 行
(rows 2-5)。本 P0/P1 不修改 FACTS.md；FACTS.md §13.2 更新留到未来 FACTS-only commit
(在 P0/P1 范围之外)。Q4 candidate 生成只写 3 行 (FY1/FY2/FY3)，第 4 行留空，
不影响最终 result2.xlsx。

注: FACTS.md §13.4 写方向角规则附注在 row 6；实际 cell 是 B6 而非 A6。
cell offset (B 列 vs A 列) 与 FACTS.md 文字描述有差异，但**附注文本**内容一致；
附注文本保留原样，不在本 PR 改写模板内容。

## 当前 result level

- `TASK_007 Q4 FOUNDATION CONTRACT — CONTRACT_ONLY`
- IMPLEMENTATION NOT STARTED
- RESULT2.XLSX NOT GENERATED
- NOT Q4 IMPLEMENTED
- NOT Q4 SEARCHED
- NOT Q4 EVALUATOR VALIDATED
- NOT FORMAL_RESULT_VERIFIED
- NOT local convergence
- NOT global optimum
- NOT 官方答案

## result1.xlsx 状态 (保留不变)

| 字段 | 值 |
|---|---|
| result1.xlsx output SHA | `b938a90b96181be14990d5bd3395c2cff72e93035828542617571ddc1d754847` |
| result1_run_identity_sha256 | `82065aa5fe4d4e6036691a053b38732b9ff1f50497083e3306e262e82a4bfc65` |
| 状态 | GENERATED + ROUND-TRIP-VERIFIED (TASK_006-P3, NOT touched by TASK_007-P0/P1) |

## 任务编号 (固定)

| 编号 | 范围 |
|---|---|
| `TASK_006` | Q3 + result1.xlsx |
| `TASK_007` | Q4 + result2.xlsx |
| `TASK_008` | Q5 + result3.xlsx |
| `TASK_009` | unified recomputation / sensitivity / robustness / figures |
| `TASK_010` | paper / consistency / final package |

## 本轮允许的 tracked 文件变更 (3 个)

| 文件 | 类型 |
|---|---|
| `.gitignore` | 增加 `work/task_contracts/`, `work/q3_*/`, `work/q4_*/`, `work/p3_closeout/` ignore 规则 |
| `MODEL.md` | 增加 "TASK_007 Q4 THREE-DRONE FOUNDATION CONTRACT" 章节 (§1~§12) |
| `NEXT_TASK.md` | 重写为本任务 (P0/P1 contract scope) |

## 本轮允许的 untracked 文件 (3 个, 均放 work/)

| 文件 | 类型 |
|---|---|
| `work/task_context.json` | task_context preflight (TASK_007-P0P1, harness 验证) |
| `work/task_contracts/TASK_007-P0P1-v1.json` | 本 phase 不可变 contract snapshot |
| `work/q4_foundation/result2_template_readonly_check.json` | 官方 result2.xlsx 模板 read-only 验证日志 |

## 关闭条件 (本门)

- ✅ Harness `verify_task_context.py` → `CONTEXT_VALID_CLEAN` 或
  `CONTEXT_VALID_AUTHORIZED_DIRTY`
- ✅ `.gitignore` 覆盖 `work/task_contracts/`, `work/q3_*/`, `work/q4_*/`,
  `work/p3_closeout/`; `git ls-files work` 为空
- ✅ 官方 result2.xlsx 模板 read-only 验证完成 (SHA + 结构 + reserved row 范围)
- ✅ Q2 evaluator u0 复用路径静态审计通过
- ✅ 12 维 `ThreeDroneCandidate` 合同写入 MODEL.md
- ✅ interval-union 目标 / `ThreeDroneEvaluation` 输出合同 / result2.xlsx 写盘合同
  全部冻结到 MODEL.md
- ✅ `work/task_contracts/TASK_007-P0P1-v1.json` 本地保留 (untracked)
- ✅ `NEXT_TASK.md` 重写为本任务 contract scope
- ✅ 单次 PLAN commit "PLAN: freeze TASK_007 Q4 three-drone contract and
  preflight governance"
- ✅ push 到 origin
- ✅ 1 个 Draft PR 创建 / 更新 (PR title:
  "TASK_007: freeze Q4 three-drone strategy contract")

不自动 (本轮 boundary):

- ❌ 启动 Q4 evaluator 实现 (TASK_007-P2)
- ❌ 启动 Q4 搜索 / pilot
- ❌ 生成 result2.xlsx (TASK_007-P3)
- ❌ 启动 Audit CC / Hermes
- ❌ Mark Ready / merge
- ❌ 启动 TASK_008

下一步 (待 MAIN 显式授权): TASK_007-P2 (Q4 formal bounded search +
12-dim candidate schema / search config / multi-seed / checkpoint freeze)。