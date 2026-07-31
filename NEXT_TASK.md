# TASK_007-P0/P1 CONTRACT CORRECTION — MAIN REVIEW PENDING

> 唯一当前门是 **TASK_007-P0/P1 CONTRACT CORRECTION**: 修正 PR #14
> TASK_007 Q4 合同中的事实、identity 与 phase-map 缺口。原 PLAN commit
> `217985b` 已存在；本轮新增一个 FIX commit。
>
> **不**进入 Q4 evaluator 实现、**不**进入 Q4 搜索、**不**生成 result2.xlsx、
> **不**进入 TASK_007-P2/P3/P4/P5、**不**启动 Audit / Hermes、**不** Mark Ready、
> **不** merge、**不**启动 TASK_008。
>
> 本轮最高状态: **TASK_007-P0/P1 CONTRACT CORRECTION COMPLETE** /
> Q4 IMPLEMENTATION NOT STARTED / RESULT2.XLSX NOT GENERATED /
> P2 NOT STARTED / P3 NOT STARTED / P4 NOT STARTED / P5 NOT STARTED /
> SEEDS NOT FROZEN / BUDGET NOT FROZEN / Audit NOT STARTED / Hermes NOT STARTED.

## 阶段状态

| 阶段 | 状态 |
|---|---|
| TASK_006-P3 (Q3 result1.xlsx) | **COMPLETE + MERGED** (PR #13 → main @ `2839151c9ef027c200f84ec342e17d43874ca254`) |
| TASK_007-P0/P1 (Q4 foundation preflight + contract freeze + CONTRACT CORRECTION) | **CONTRACT CORRECTION COMPLETE — MAIN REVIEW PENDING — THIS PR** |
| TASK_007-P2 (Q4 evaluator + tiny pilot + runtime calibration) | **NOT STARTED** |
| TASK_007-P3 (Q4 formal bounded search) | **NOT STARTED** |
| TASK_007-P4 (candidate closure) | **NOT STARTED** |
| TASK_007-P5 (result2.xlsx write + round-trip) | **NOT STARTED** |
| TASK_008 | **NOT STARTED** |

## 起点身份 (CONTRACT CORRECTION 启动)

| 字段 | 值 |
|---|---|
| 起始 HEAD (main) | `2839151c9ef027c200f84ec342e17d43874ca254` (PR #13 mergeCommit) |
| 分支 | `task/TASK_007-q4-result2` |
| base_branch | `main` |
| base_sha | `2839151c9ef027c200f84ec342e17d43874ca254` |
| 原 PLAN commit | `217985bd4f03a1e023d37e896c4035c1a58f515f` |
| 本轮 FIX commit | (本轮生成, 第二个普通 commit, 非 amend) |
| task_id | `TASK_007-P0P1` |
| phase_id | `TASK_007-P0P1` |
| contract_version | 1 (本轮 v1 替换) |
| pr_number | 14 |
| pr_state_target | open, draft=true, merged=false, mergeable=true |
| worktree | `C:\Users\33560\Desktop\CUMCM_2025_A` |
| repository | `hongyuchen039-oss/CUMCM-2025-A` |

## 本轮范围 (CONTRACT CORRECTION, NOT IMPLEMENTATION)

修正原 TASK_007-P0/P1 v1 contract 中的具体缺口：

1. **`problem/FACTS.md §13.2` 修正** — 拆分"官方要求"vs"模板格式行"两个不同事实,
   显式声明:
   - 官方要求 = FY1、FY2、FY3 三条结果记录 ("FY1、FY2、FY3 各 1 枚");
   - 模板预留 4 个空白格式行 (rows 2, 3, 4, 5), 实际占用 3 行 (FY1, FY2, FY3) +
     1 个保留空白格式行 (row 5);
   - 正式 result2.xlsx 使用 rows 2, 3, 4 分别写 FY1, FY2, FY3;
   - row 5 保持官方模板原状和空白, **不删除、不重排、不写入** 第四条记录。
2. **`MODEL.md` 修正 Q4 数量措辞** — 改"每架 ≤ 1 枚"为
   "FY1、FY2、FY3 各投放**恰好 1 枚**烟幕干扰弹" (FACTS.md §5 原文)。
3. **`MODEL.md` 修正 TASK_007 phase map** — P0P1/P2/P3/P4/P5 全部定义:
   - P0P1 = preflight + 12-dim candidate contract freeze;
   - P2 = Q4 evaluator 实现 + 单元测试 + **tiny bounded pilot** + **runtime calibration**;
   - P3 = Q4 正式 bounded search (基于 P2 冻结的 seeds 数量 / 具体 seeds / wall-clock
     / evaluation cap / search config);
   - P4 = candidate closure + 局部 refined re-evaluation + 跨 seed 鲁棒性;
   - P5 = fine reconstruction + 写盘 `outputs/submission/result2.xlsx` +
     round-trip 验证 (含 row 5 保留 / B6 附注 / A1:J6 footprint)。
4. **`MODEL.md` 修正 `q4_evaluation_id` 绑定字段** — 扩展到 **21 字段**:
   candidate 12 个变量 + drone_order + sample_level + scan_step +
   candidate_schema_version + q2_evaluator_code_sha + q3_helper_code_sha +
   q4_pilot_config_sha + evaluator_call_count_per_q4 + prevalidation_call_count +
   objective + missile_target + missile_initial_position + missile_speed +
   missile_heading + true_target_geometry_id + smoke_cloud_radius +
   smoke_cloud_sink + smoke_cloud_duration + gravity + eps_interval_touching。
5. **`MODEL.md` 修正 evaluator 调用合同** — 两阶段:
   - 阶段 A prevalidation: 0 次 `evaluate_single_bomb_strategy` 调用 (轻量输入检查);
   - 阶段 B 顺序执行 3 次 `evaluate_single_bomb_strategy` (FY1 → FY2 → FY3);
   - 阶段 B 异常处理: 任一系统异常 → 整体抛出 + 位置标记 system_error; 不静默吞掉;
   - 成功执行的 evaluate_single_bomb_strategy 调用数必须 = 3。
6. **移除种子和预算的"frozen"含义** — 删除原"multi-seed 必须 ≥ 3"等冻结措辞;
   seeds 数量 / 具体 seed 列表 / wall-clock / evaluation cap / search config
   **均 NOT frozen**, 留到 P2 runtime calibration 后由 MAIN 在新 contract_version
   中冻结。
7. **`MODEL.md` 修正模板写盘合同** — 明确:
   - 写入区 = rows 2, 3, 4 (FY1 → row 2, FY2 → row 3, FY3 → row 4);
   - row 5 = 官方模板预存的空白格式行, **不删除、不重排、不写入** 任何数据;
   - 整体 workbook footprint = A1:J6 (header A1:J1 + rows 2-5 空白格式 + B6 附注);
   - B6 附注 (「注: 以 x 轴为正向, 逆时针方向为正, 取值 0~360（度)」) 保留原样;
   - 写盘流程 = `BytesIO` 打开官方模板副本 (不直接改磁盘官方模板), 写入后
     save 到 `outputs/submission/result2.xlsx`;
   - 写盘后必须**程序重读** 验证 (sheet name / A1:J1 header / rows 2-4 内容 /
     row 5 空白 / B6 附注原文 / A1:J6 footprint)。
8. **更新 `work/task_contracts/TASK_007-P0P1-v1.json`** — 包含 phase_map /
   21 binding fields / prevalidation_call_count=0 / successful_evaluation_call_count=3 /
   result2_template_structure / frozen_in_this_phase / not_frozen_in_this_phase /
   next_gate=MAIN_REVIEW。
9. **更新 PR #14 描述** — 反映 CONTRACT CORRECTION 范围、phase map、
   FACTS.md §13.2 修正、21 binding fields、evaluator 调用合同、模板写盘合同。
10. **保持 PR #14 = Draft** — 不得 Mark Ready; 不得 merge。

## 显式不做 (本轮 boundary)

- ❌ 创建 `src/q4_three_drones.py` / `tests/test_q4.py`;
- ❌ 实现 Q4 evaluator / search / pilot CLI;
- ❌ 运行 Q4 任何 evaluator / 任何搜索 / 任何 tiny pilot;
- ❌ 创建 `outputs/submission/result2.xlsx`;
- ❌ 修改 Q1 / Q2 / `src/q3_three_bombs.py` / `src/q3_search.py` 任何 foundation 文件;
- ❌ 修改 result1.xlsx 或其 evidence;
- ❌ 修改官方模板 ZIP、不解压模板到仓库;
- ❌ 创建 CI / 不修改 workflow;
- ❌ 安装任何依赖 (scipy / numpy / pandas 等);
- ❌ 启动 Audit CC / Hermes (MAIN 决定);
- ❌ Mark Ready / merge;
- ❌ 启动 TASK_008;
- ❌ 启动 TASK_007-P2 (Q4 evaluator + tiny pilot + runtime calibration);
- ❌ 启动 TASK_007-P3 (Q4 formal bounded search);
- ❌ 启动 TASK_007-P4 (candidate closure);
- ❌ 启动 TASK_007-P5 (result2.xlsx 写盘);
- ❌ Amend 原 PLAN commit `217985b`;
- ❌ Force push;
- ❌ 不得声称 FORMAL_RESULT_VERIFIED / local convergence / global optimum /
  Q4 IMPLEMENTED / Q4 SEARCHED / RESULT2.XLSX GENERATED / Q4 EVALUATOR VALIDATED /
  P2 STARTED / P3 STARTED / P4 STARTED / P5 STARTED / 官方答案 /
  seeds frozen / budget frozen。

## 身份链 (CONTRACT CORRECTION 锁定)

| 字段 | SHA / 值 |
|---|---|
| 起始 HEAD (main) | `2839151c9ef027c200f84ec342e17d43874ca254` |
| 原 PLAN commit | `217985bd4f03a1e023d37e896c4035c1a58f515f` |
| 本轮 FIX commit | (本轮生成, 第二个普通 commit, 非 amend) |
| 上一个 phase | `TASK_006-P3-HASH-SEMANTICS-FIX` (contract_version=7) |
| 本 phase | `TASK_007-P0P1` (contract_version=1, 本轮 v1 替换) |
| contract_snapshot_path | `work/task_contracts/TASK_007-P0P1-v1.json` (untracked, 本机保留) |

## 官方 result2.xlsx 模板 read-only 验证 (P0/P1 内已完成, 本轮保持)

| 字段 | 值 |
|---|---|
| 官方 ZIP SHA-256 | `f9879c0d36b7bdccb99fb330a8032e62851ab1a1f0a1636c92440a1cdaec658e` (14884 bytes, 3 members) |
| result2.xlsx member size | 5272 bytes |
| result2.xlsx member SHA-256 | `91fbc42459aa4c98838b0a4dbe740ec5b970436c3f86d8a22dd7303f127cf106` |
| result2.xlsx member 唯一 | YES (1/3) |
| sheet names | `['Sheet1']` |
| header 行 / 列 | row 1, A1:J1 |
| 模板空白格式行范围 | rows 2-5 (4 rows) |
| 实际写入区 | rows 2, 3, 4 (FY1 → row 2, FY2 → row 3, FY3 → row 4) |
| 保留空白格式行 | row 5 (官方模板预存, 不删除不重排不写入) |
| 附注 cell | B6 (注: 以 x 轴为正向, 逆时针方向为正, 取值 0~360（度）) |
| workbook 整体 footprint | A1:J6 |
| merged cells | 无 |
| freeze_panes | 无 |

详细验证日志: `work/q4_foundation/result2_template_readonly_check.json` (untracked)。

**FACTS.md §13.2 已修正** (本轮 tracked 变更): 拆分"官方要求"vs"模板格式行"两个不同事实,
明确 row 5 是官方模板预存空白格式行, 正式 result2.xlsx 只写 rows 2-4 三行。

## 当前 result level

- `TASK_007 Q4 FOUNDATION CONTRACT — CONTRACT_ONLY`
- `CONTRACT CORRECTION COMPLETE` (本轮范围)
- IMPLEMENTATION NOT STARTED
- RESULT2.XLSX NOT GENERATED
- TASK_007-P2 NOT STARTED
- TASK_007-P3 NOT STARTED
- TASK_007-P4 NOT STARTED
- TASK_007-P5 NOT STARTED
- TASK_008 NOT STARTED
- seeds 数量 / 具体 seed 列表 / wall-clock / evaluation cap / search config NOT FROZEN
- Audit NOT STARTED
- Hermes NOT STARTED
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
| `TASK_007-P0P1` | Q4 foundation preflight + contract freeze + CONTRACT CORRECTION (本轮) |
| `TASK_007-P2` | Q4 evaluator + tiny pilot + runtime calibration |
| `TASK_007-P3` | Q4 formal bounded search |
| `TASK_007-P4` | candidate closure + targeted refined re-evaluation + cross-seed robustness |
| `TASK_007-P5` | fine reconstruction + result2.xlsx 写盘 + round-trip 验证 |
| `TASK_008` | Q5 + result3.xlsx |
| `TASK_009` | unified recomputation / sensitivity / robustness / figures |
| `TASK_010` | paper / consistency / final package |

## 本轮允许的 tracked 文件变更 (3 个)

| 文件 | 类型 |
|---|---|
| `problem/FACTS.md` | §13.2 拆分官方要求 vs 模板格式行, 明确 row 5 保留 |
| `MODEL.md` | TASK_007 Q4 THREE-DRONE FOUNDATION CONTRACT 章节 (新增 phase map §0 + §1 Q4 数量措辞 + §4 evaluator 调用合同 + §6 21 字段 q4_evaluation_id + §7 模板写盘合同 + §8/§9 移除 frozen 含义) |
| `NEXT_TASK.md` | 重写为本轮 CONTRACT CORRECTION scope |

## 本轮允许的 untracked 文件 (3 个, 均放 work/)

| 文件 | 类型 |
|---|---|
| `work/task_context.json` | task_context preflight (TASK_007-P0P1, harness 验证) |
| `work/task_contracts/TASK_007-P0P1-v1.json` | 本 phase 不可变 contract snapshot (本轮 v1 替换) |
| `work/q4_foundation/result2_template_readonly_check.json` | 官方 result2.xlsx 模板 read-only 验证日志 |

## 关闭条件 (本门)

- ✅ Harness `verify_task_context.py` → `CONTEXT_VALID_CLEAN` 或
  `CONTEXT_VALID_AUTHORIZED_DIRTY`
- ✅ 原 PLAN commit `217985b` 存在 (未 amend、未 reset、未 force push)
- ✅ `problem/FACTS.md §13.2` 拆分"官方要求"vs"模板格式行", 明确 row 5 保留
- ✅ `MODEL.md` TASK_007 phase map (P0P1/P2/P3/P4/P5) 写入
- ✅ `MODEL.md` Q4 数量措辞改为"FY1、FY2、FY3 各投放恰好 1 枚"
- ✅ `MODEL.md` evaluator 调用合同 (阶段 A 0 次 + 阶段 B 顺序 3 次) 写入
- ✅ `MODEL.md` `q4_evaluation_id` 扩展到 21 字段
- ✅ `MODEL.md` 模板写盘合同 (rows 2-4 写 / row 5 保留 / B6 / A1:J6) 写入
- ✅ `MODEL.md` 移除"multi-seed 必须 ≥ 3"等 frozen 含义
- ✅ `work/task_contracts/TASK_007-P0P1-v1.json` 本地 v1 替换
  (untracked, 本机保留)
- ✅ `NEXT_TASK.md` 重写为本轮 CONTRACT CORRECTION scope
- ✅ 单次 FIX commit "FIX: close TASK_007 Q4 template identity and phase
  contract gaps" (第二个普通 commit, 非 amend, 非 force)
- ✅ push 到 origin
- ✅ PR #14 仍为 Draft, 描述更新
- ✅ PR #14 验证: state=open, draft=true, merged=false, mergeable=true,
  head=新 FIX commit, commits=2

不自动 (本轮 boundary):

- ❌ 启动 Q4 evaluator 实现 (TASK_007-P2)
- ❌ 启动 Q4 搜索 / tiny pilot / runtime calibration
- ❌ 启动 candidate closure (P4)
- ❌ 启动 result2.xlsx 写盘 (P5)
- ❌ 启动 Audit CC / Hermes
- ❌ Mark Ready / merge
- ❌ 启动 TASK_008
- ❌ 冻结 seeds 数量 / 具体 seed 列表 / wall-clock / evaluation cap /
  search config / pilot config
- ❌ 冒充 Q4 IMPLEMENTED / Q4 SEARCHED / RESULT2 GENERATED / P2 STARTED /
  P3 STARTED / P4 STARTED / P5 STARTED / FORMAL_RESULT_VERIFIED / 官方答案

## 下一门 (待 MAIN 显式授权)

**MAIN REVIEW OF CORRECTED TASK_007-P0/P1 CONTRACT** — 验证本轮 CONTRACT CORRECTION
的 9 项修正是否完整、是否仍 CONTRACT_ONLY、是否不冒充实现 / 搜索 / 写盘。

MAIN 显式授权后才能进入:
- TASK_007-P2 (Q4 evaluator + 单元测试 + tiny pilot + runtime calibration)
