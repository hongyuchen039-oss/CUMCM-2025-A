"""Q2 单弹策略评估器 (TASK_004 FOUNDATION / NOT AN OPTIMIZATION RESULT).

本轮任务范围 (TASK_004 Foundation):

- 四变量合同: heading_rad, speed_mps, release_time_s, delay_s
- 唯一变元; 投放点 / 起爆时刻 / 起爆点 / 云团中心轨迹均由策略推导
- 候选合法性 (物理 / 合同) 与程序错误严格分离
- 搜索域无损剪枝 (t_detonate > t_arrival): 标记为 pruned_zero, 目标值为 0
- 评估窗口: [t_detonate, min(t_detonate + 20, t_arrival)]
- 目标: 完整圆柱严格遮蔽总时长, 复用 src/q1_cylinder.find_strict_intervals
- 三档 sample 等级 (coarse / medium / fine), 三档 scan_step 显式传入
- Q1 固定策略回归 (heading=π, speed=120, release=1.5, delay=3.6)
- 100 个候选本地 smoke (coarse), 仅向终端输出

显式不做:

- 不得声称 Q2 最优结果
- 不得写入 outputs/submission/result*.xlsx
- 不得修改 q1_baseline.py
- 不得复制完整圆柱几何实现, 仅通过闭包注入

参考:
- problem/FACTS.md (官方事实)
- src/q1_baseline.py (Q1 点目标基线与运动学)
- src/q1_cylinder.py (TASK_003 完整圆柱严格遮蔽, 含注入接口)
- CLAUDE.md (本项目长期规则)

只使用 Python 标准库.
"""

from __future__ import annotations

import math
import random
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Callable, List, Sequence, Tuple

from src.q1_baseline import (
    G, CLOUD_SINK, CLOUD_DURATION,
    U0,
    vector_add, vector_scale,
)
from src.q1_cylinder import (
    SAMPLE_GRADES,
    generate_cylinder_samples,
    find_strict_intervals,
    total_effective_duration,
)
from src.q1_baseline import missile_arrival_time

Vec = Tuple[float, float, float]
TrajFn = Callable[[float], Vec]


# === Q1 锚定: 标准云团中心函数复用签名 ===
# 云团中心公式 (FACTS.md §10):
#   C(t) = D + (0, 0, -3 * (t - t_detonate)),   t >= t_detonate
# 沿用 src/q1_baseline.cloud_center 的延长线行为: t < t_detonate 时
#   sink = max(0, t - t_detonate) = 0, 即 C(t) = D. 这是云团定义而非物理投射.
# 评估窗口由 find_strict_intervals 的 window_start/window_end 决定.


# === 决策变量: 唯一 4 个独立变量 ===
@dataclass(frozen=True)
class SingleBombStrategy:
    """Q2 单弹策略的 4 个独立变量.

    不得在其中再保存投放点 / 起爆点 / 起爆时刻 / 方向向量等推导量.
    """
    heading_rad: float
    speed_mps: float
    release_time_s: float
    delay_s: float


# === 单候选评估结果 ===
@dataclass(frozen=True)
class SingleBombEvaluation:
    """单候选评估的结构化结果.

    status 取值 (互斥):
      - "valid"        : 通过合法性 + 未被搜索域剪枝, intervals 是真实结果
      - "zero_window"  : 合法但评估窗口为空 (window_end <= window_start)
      - "pruned_zero"  : 合法但 t_detonate > t_arrival (搜索域无损剪枝)
      - "invalid"      : 物理 / 合同非法 (非有限, 越界, 起爆 z < 0)

    注意: 程序异常 (geometry 合同错误 / 空可见集 / 类型错误) 不
    归入 "invalid", 而是由 evaluate_single_bomb_strategy 直接抛出.
    Smoke CLI 可在外层捕获以统计 system_error.
    """
    strategy: SingleBombStrategy
    normalized_heading_rad: float
    valid: bool
    status: str
    reason: str
    release_point: Vec | None
    detonation_time_s: float | None
    detonation_point: Vec | None
    evaluation_window: Tuple[float, float] | None
    intervals: Tuple[Tuple[float, float], ...]
    total_duration_s: float
    sample_level: str
    scan_step_s: float
    elapsed_s: float


# =============================================================================
#  Section 五: 航向归一化与基础几何
# =============================================================================
def normalize_heading(theta: float) -> float:
    """将 heading 归一化到 [0, 2π).

    处理:
    - 负角度 (例: -π/2 → 3π/2)
    - 2π (浮点 fmod 可能产生 2π, 直接归零)
    - 多周期 (例: 4π → 0)
    """
    if not math.isfinite(theta):
        raise ValueError(f"heading_rad 非有限: {theta!r}")
    two_pi = 2.0 * math.pi
    result = math.fmod(theta, two_pi)
    if result < 0.0:
        result += two_pi
    # fmod 在 result==two_pi 边界可能恰好返回 two_pi
    if result >= two_pi:
        result -= two_pi
    return result


def heading_to_unit_vector(theta: float) -> Vec:
    """u(θ) = (cosθ, sinθ, 0). 沿归一化航向.

    θ=0 → +x; θ=π/2 → +y; θ=π → -x; θ 逆时针为正.
    不得储存独立二维方向变量; 直接由 heading 推导.
    """
    nh = normalize_heading(theta)
    return (math.cos(nh), math.sin(nh), 0.0)


def fy1_velocity(theta: float, speed: float) -> Vec:
    """FY1 速度向量 = speed * u(θ), z=0 (等高度飞行)."""
    u = heading_to_unit_vector(theta)
    return vector_scale(u, speed)


def fy1_position(t: float, u0: Vec, v_fy1: Vec) -> Vec:
    """FY1 位置 F(t) = F0 + v * t (等高度匀速直线)."""
    if not math.isfinite(t):
        raise ValueError(f"t 非有限: {t!r}")
    return vector_add(u0, vector_scale(v_fy1, t))


# =============================================================================
#  Section 六: 运动学推导
# =============================================================================
def release_point(strategy: SingleBombStrategy, u0: Vec = U0) -> Vec:
    """投放点 R = F(t_release). 推导量, 不得独立储存."""
    v = fy1_velocity(strategy.heading_rad, strategy.speed_mps)
    return fy1_position(strategy.release_time_s, u0, v)


def detonation_time(strategy: SingleBombStrategy) -> float:
    """起爆时刻 t_d = t_release + δ. 推导量."""
    return strategy.release_time_s + strategy.delay_s


def detonation_point(strategy: SingleBombStrategy, u0: Vec = U0) -> Vec:
    """起爆点 D (形式 1): R + v δ u + (0, 0, -0.5 g δ²).

    投放后烟幕弹沿抛体运动, 起爆水平位置 = R + v δ u
    (这里 v u 即 FY1 共速, 水平气动忽略), 起爆 z = u0_z - 0.5 g δ².
    """
    v = fy1_velocity(strategy.heading_rad, strategy.speed_mps)
    r = release_point(strategy, u0)
    delta = strategy.delay_s
    d1 = vector_add(r, vector_scale(v, delta))
    d1 = (d1[0], d1[1], d1[2] - 0.5 * G * delta * delta)
    return d1


def detonation_point_eq2(strategy: SingleBombStrategy, u0: Vec = U0) -> Vec:
    """起爆点 D (形式 2): F0 + v (t_release + δ) u + (0, 0, -0.5 g δ²).

    数学上与 detonation_point 等价; 测试用于证明两种形式一致.
    """
    v = fy1_velocity(strategy.heading_rad, strategy.speed_mps)
    t_total = strategy.release_time_s + strategy.delay_s
    p = vector_add(u0, vector_scale(v, t_total))
    p = (p[0], p[1], p[2] - 0.5 * G * strategy.delay_s * strategy.delay_s)
    return p


def make_cloud_center_fn(strategy: SingleBombStrategy, d: Vec) -> TrajFn:
    """返回云团中心函数 c(t) = D + (0, 0, -3(t - t_d)) for t >= t_d.

    沿用 src/q1_baseline.cloud_center 哨兵行为: t < t_d 时返回 D 自身.
    起点 t_d 不抛异常, c(t_d) = d.
    """
    t_d = detonation_time(strategy)

    def cfn(t: float) -> Vec:
        if not math.isfinite(t):
            raise ValueError(f"t 非有限: {t!r}")
        sink = CLOUD_SINK * max(0.0, t - t_d)
        return (d[0], d[1], d[2] - sink)

    return cfn


# =============================================================================
#  Section 七: 候选合法性
# =============================================================================
def validate_strategy(strategy: SingleBombStrategy) -> Tuple[bool, str]:
    """物理/合同无效检查.

    Returns:
        (valid, reason). True if valid; reason 描述非法原因.

    不涉及 t_d > t_arrival 搜索域剪枝 (那是任务 八 / Section 八).
    """
    s = strategy
    if not all(math.isfinite(getattr(s, f)) for f in
               ("heading_rad", "speed_mps", "release_time_s", "delay_s")):
        return False, "non_finite"
    if s.speed_mps < 70.0 or s.speed_mps > 140.0:
        return False, f"speed_mps={s.speed_mps} not in [70,140]"
    if s.release_time_s < 0.0:
        return False, f"release_time_s={s.release_time_s} < 0"
    if s.delay_s < 0.0:
        return False, f"delay_s={s.delay_s} < 0"
    # 起爆点 z 可为 0 (边界), 但 < 0 视为非法
    d = detonation_point(s)
    if d[2] < 0.0:
        return False, f"detonation z={d[2]} < 0"
    return True, "ok"


# =============================================================================
#  Section 八: 单候选完整评估
# =============================================================================
def evaluate_single_bomb_strategy(
    strategy: SingleBombStrategy,
    sample_level: str = "coarse",
    scan_step: float = 0.05,
    u0: Vec = U0,
    samples: Sequence | None = None,
    t_arrival: float | None = None,
) -> SingleBombEvaluation:
    """评估单弹策略的完整圆柱严格遮蔽总时长.

    Args:
        strategy: 4 个独立变量
        sample_level: "coarse" / "medium" / "fine" - 复用 SAMPLE_GRADES
        scan_step: 时间扫描步长 (s). 必须有限且 > 0, 否则 ValueError
        u0: FY1 初始位置 (默认 FACTS §8)
        samples: 可选, 预生成的圆柱表面样本 (主要用于回归测试避免重复采样)
        t_arrival: 可选, 导弹到达假目标的时刻 (默认实时计算)

    Returns:
        SingleBombEvaluation (status 在 invalid / pruned_zero / zero_window / valid 之间)
    """
    t0 = time.perf_counter()

    # 1. 输入合法性
    if sample_level not in SAMPLE_GRADES:
        raise ValueError(f"sample_level 必须 ∈ {list(SAMPLE_GRADES)}, 实际 {sample_level!r}")
    if not isinstance(scan_step, (int, float)) or not math.isfinite(scan_step):
        raise ValueError(f"scan_step 必须有限数值, 实际 {scan_step!r}")
    if scan_step <= 0:
        raise ValueError(f"scan_step 必须 > 0, 实际 {scan_step}")

    # 2. 策略合法性
    valid, reason = validate_strategy(strategy)
    if not valid:
        elapsed = time.perf_counter() - t0
        try:
            n_heading = normalize_heading(strategy.heading_rad)
        except ValueError:
            n_heading = float("nan")
        return SingleBombEvaluation(
            strategy=strategy, normalized_heading_rad=n_heading,
            valid=False, status="invalid", reason=reason,
            release_point=None, detonation_time_s=None, detonation_point=None,
            evaluation_window=None, intervals=(), total_duration_s=0.0,
            sample_level=sample_level, scan_step_s=scan_step, elapsed_s=elapsed,
        )

    # 3. 推导量
    n_heading = normalize_heading(strategy.heading_rad)
    r_pt = release_point(strategy, u0)
    t_d = detonation_time(strategy)
    d_pt = detonation_point(strategy, u0)

    # 4. 搜索域剪枝: t_detonate > t_arrival 无损标记
    if t_arrival is None:
        t_arrival = missile_arrival_time()
    if t_d > t_arrival:
        elapsed = time.perf_counter() - t0
        return SingleBombEvaluation(
            strategy=strategy, normalized_heading_rad=n_heading,
            valid=False, status="pruned_zero",
            reason=f"t_detonate={t_d:.6f} > t_arrival={t_arrival:.6f}",
            release_point=r_pt, detonation_time_s=t_d, detonation_point=d_pt,
            evaluation_window=None, intervals=(), total_duration_s=0.0,
            sample_level=sample_level, scan_step_s=scan_step, elapsed_s=elapsed,
        )

    # 5. 评估窗口 (右端截断到 t_arrival 与 t_detonate+20 的较小值)
    window_start = t_d
    window_end = min(t_d + CLOUD_DURATION, t_arrival)
    if window_end <= window_start:
        # 合法但窗口为空 (含 t_d == t_arrival)
        elapsed = time.perf_counter() - t0
        return SingleBombEvaluation(
            strategy=strategy, normalized_heading_rad=n_heading,
            valid=True, status="zero_window",
            reason=f"window empty [{window_start:.6f}, {window_end:.6f}]",
            release_point=r_pt, detonation_time_s=t_d, detonation_point=d_pt,
            evaluation_window=(window_start, window_end),
            intervals=(), total_duration_s=0.0,
            sample_level=sample_level, scan_step_s=scan_step, elapsed_s=elapsed,
        )

    # 6. 几何样本 (可外部注入, 主要用于回归测试)
    if samples is None:
        samples_list = generate_cylinder_samples(**SAMPLE_GRADES[sample_level])
    else:
        samples_list = list(samples)

    # 7. 云团中心闭包
    cf = make_cloud_center_fn(strategy, d_pt)

    # 8. 区间求解 (复用 src/q1_cylinder; 默认 boundary_func=strict_boundary_value)
    ivs = find_strict_intervals(
        samples_list,
        scan_step=scan_step,
        cloud_center_fn=cf,
        window_start=window_start,
        window_end=window_end,
        t_arrival=t_arrival,
    )

    total = total_effective_duration(ivs)
    elapsed = time.perf_counter() - t0

    return SingleBombEvaluation(
        strategy=strategy, normalized_heading_rad=n_heading,
        valid=True, status="ok", reason="evaluated",
        release_point=r_pt, detonation_time_s=t_d, detonation_point=d_pt,
        evaluation_window=(window_start, window_end),
        intervals=tuple(ivs),
        total_duration_s=total,
        sample_level=sample_level, scan_step_s=scan_step, elapsed_s=elapsed,
    )


# =============================================================================
#  Section 十三: 候选生成 (固定种子, 可复现)
# =============================================================================
def generate_candidates(count: int, seed: int = 2025,
                         u0: Vec = U0,
                         include_q1_baseline: bool = False) -> List[SingleBombStrategy]:
    """生成 count 个经过合法性 + 搜索域剪枝的合法候选.

    - heading 覆盖 [0, 2π)
    - speed 覆盖 [70, 140]
    - release_time ∈ [0, t_arrival - 1] (留出起爆时间)
    - delay ∈ [0, 30]
    - 仅保留: validate_strategy 通过 AND t_detonate < t_arrival
    - 默认不包含 Q1 固定基线策略 (CLI 中可选用)
    """
    if count <= 0:
        raise ValueError(f"count 必须 > 0, 实际 {count}")
    t_arrival = missile_arrival_time()
    rng = random.Random(seed)
    out: List[SingleBombStrategy] = []
    guard = 0
    cap = max(count * 50, 1000)
    while len(out) < count:
        guard += 1
        if guard > cap:
            raise RuntimeError(
                f"候选生成死循环: 在 {cap} 次尝试内仅生成 {len(out)} 个候选 "
                f"(目标 {count}). 检查搜索域定义.")
        cand = SingleBombStrategy(
            heading_rad=rng.uniform(0.0, 2.0 * math.pi),
            speed_mps=rng.uniform(70.0, 140.0),
            release_time_s=rng.uniform(0.0, max(1e-3, t_arrival - 1.0)),
            delay_s=rng.uniform(0.0, 30.0),
        )
        v, _ = validate_strategy(cand)
        if not v:
            continue
        t_d = detonation_time(cand)
        if t_d >= t_arrival:
            continue
        out.append(cand)
    if include_q1_baseline:
        # Q1 固定策略作为第 0 个候选, 便于回归
        q1 = SingleBombStrategy(
            heading_rad=math.pi, speed_mps=120.0,
            release_time_s=1.5, delay_s=3.6)
        if q1 not in out:
            out.insert(0, q1)
    return out


# =============================================================================
#  Section 十三 + 十七: Profile 与 Smoke
# =============================================================================
PROFILE_GRADES = {
    "coarse": "coarse",
    "medium": "medium",
    "fine": "fine",
}
PROFILE_SCAN_STEPS = {
    "coarse": 0.05,
    "medium": 0.02,
    "fine": 0.01,
}


def run_smoke(count: int = 100, seed: int = 2025, profile: str = "coarse"
              ) -> dict:
    """FOUNDATION SMOKE / NOT AN OPTIMIZATION RESULT.

    仅向内存返回统计, 不写入文件, 不写入 RESULTS.md, 不写入 xlsx.

    Args:
        count: 候选数 (本轮默认 100, 不得超过 300)
        seed: 固定 random.Random 种子
        profile: "coarse" | "medium" | "fine"

    Returns:
        dict 包含 counts / timing 统计 / 临时最高 / system_errors (若有)
    """
    if profile not in PROFILE_GRADES:
        raise ValueError(f"profile 必须 ∈ {list(PROFILE_GRADES)}, 实际 {profile!r}")
    grade = PROFILE_GRADES[profile]
    scan_step = PROFILE_SCAN_STEPS[profile]
    candidates = generate_candidates(count, seed)

    evaluations: List[SingleBombEvaluation] = []
    n_invalid = 0
    n_pruned = 0
    n_zero_window = 0
    n_system_error = 0
    system_errors: List[Tuple[SingleBombStrategy, str, str]] = []

    total_t0 = time.perf_counter()
    for cand in candidates:
        try:
            ev = evaluate_single_bomb_strategy(cand, sample_level=grade,
                                                scan_step=scan_step)
        except Exception as e:  # 系统异常, 不归入 invalid, 由 smoke 统计
            n_system_error += 1
            if len(system_errors) < 5:
                system_errors.append((cand, type(e).__name__, str(e)))
            continue

        if ev.status == "invalid":
            n_invalid += 1
        elif ev.status == "pruned_zero":
            n_pruned += 1
        elif ev.status == "zero_window":
            n_zero_window += 1
            evaluations.append(ev)  # 视为合法零目标
        else:
            evaluations.append(ev)
    elapsed_total = time.perf_counter() - total_t0

    times = [ev.elapsed_s for ev in evaluations]
    if times:
        ts = sorted(times)
        median = statistics.median(ts)
        p90_idx = max(0, int(math.ceil(0.9 * len(ts))) - 1)
        p90 = ts[p90_idx]
        slowest = max(ts)
        mean_t = sum(ts) / len(ts)
    else:
        median = p90 = slowest = mean_t = 0.0

    best: SingleBombEvaluation | None = None
    if evaluations:
        best = max(evaluations, key=lambda e: e.total_duration_s)

    return {
        "count": count,
        "seed": seed,
        "profile": profile,
        "grade": grade,
        "scan_step": scan_step,
        "n_valid_ok": sum(1 for e in evaluations if e.status == "ok"),
        "n_valid_zero_window": n_zero_window,
        "n_invalid": n_invalid,
        "n_pruned_zero": n_pruned,
        "n_system_error": n_system_error,
        "system_errors": system_errors,
        "total_elapsed_s": elapsed_total,
        "mean_s": mean_t,
        "median_s": median,
        "p90_s": p90,
        "max_s": slowest,
        "best": best,
        "evaluations": evaluations,
    }


# =============================================================================
#  Q1 固定策略回归 (Section 十二)
# =============================================================================
Q1_FIXED_STRATEGY = SingleBombStrategy(
    heading_rad=math.pi,
    speed_mps=120.0,
    release_time_s=1.5,
    delay_s=3.6,
)
# Q1 期望锚定值 (与 src/q1_baseline.compute_q1 一致, 由手算公式直接得到)
Q1_EXPECTED = {
    "fy1_velocity": (-120.0, 0.0, 0.0),
    "release_point": (17620.0, 0.0, 1800.0),
    "detonation_time": 5.1,
    "detonation_point": (17188.0, 0.0, 1736.496),
}


# =============================================================================
#  CLI (Section 十七)
# =============================================================================
def _print_help() -> None:
    print(__doc__)
    print("用法:")
    print("  python -m src.q2_single_bomb --smoke-count 100 --seed 2025 --profile coarse")
    print()
    print("参数:")
    print("  --smoke-count N   候选数 (1..300, 必要)")
    print("  --seed N          随机种子 (默认 2025)")
    print("  --profile NAME    coarse | medium | fine (默认 coarse)")
    print("  -h, --help        显示本帮助")


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # 显式解析 (无 argparse 依赖)
    smoke_count = None
    seed = 2025
    profile = "coarse"
    show_help = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            show_help = True
            i += 1
            continue
        if a == "--smoke-count":
            if i + 1 >= len(argv):
                print("--smoke-count 缺少值", file=sys.stderr)
                return 2
            try:
                smoke_count = int(argv[i + 1])
            except ValueError:
                print(f"--smoke-count 必须整数, 实际 {argv[i + 1]!r}", file=sys.stderr)
                return 2
            i += 2
            continue
        if a == "--seed":
            if i + 1 >= len(argv):
                print("--seed 缺少值", file=sys.stderr)
                return 2
            try:
                seed = int(argv[i + 1])
            except ValueError:
                print(f"--seed 必须整数, 实际 {argv[i + 1]!r}", file=sys.stderr)
                return 2
            i += 2
            continue
        if a == "--profile":
            if i + 1 >= len(argv):
                print("--profile 缺少值", file=sys.stderr)
                return 2
            profile = argv[i + 1]
            i += 2
            continue
        print(f"未知参数: {a}", file=sys.stderr)
        return 2

    if show_help:
        _print_help()
        return 0

    if smoke_count is None:
        print("缺少必要参数 --smoke-count", file=sys.stderr)
        _print_help()
        return 2

    if smoke_count <= 0 or smoke_count > 300:
        print(f"--smoke-count 必须 1..300, 实际 {smoke_count}", file=sys.stderr)
        return 2

    if profile not in PROFILE_GRADES:
        print(f"--profile 必须 {list(PROFILE_GRADES)}, 实际 {profile!r}",
              file=sys.stderr)
        return 2

    print("=" * 70)
    print("Q2 SINGLE-BOMB FOUNDATION SMOKE / NOT AN OPTIMIZATION RESULT")
    print("=" * 70)
    print(f"  候选数:    {smoke_count}")
    print(f"  种子:      {seed}")
    print(f"  Profile:   {profile} (grade={PROFILE_GRADES[profile]}, "
          f"scan_step={PROFILE_SCAN_STEPS[profile]} s)")
    print()

    res = run_smoke(count=smoke_count, seed=seed, profile=profile)

    n_total = res["n_valid_ok"] + res["n_valid_zero_window"] \
              + res["n_invalid"] + res["n_pruned_zero"] + res["n_system_error"]
    print(f"  valid (status=ok)            = {res['n_valid_ok']}")
    print(f"  valid (status=zero_window)   = {res['n_valid_zero_window']}")
    print(f"  invalid (物理/合同)          = {res['n_invalid']}")
    print(f"  pruned_zero (t_d > arrival)  = {res['n_pruned_zero']}")
    print(f"  system_error                 = {res['n_system_error']}")
    print(f"  合计 = {n_total} (目标 {smoke_count})")
    if res["system_errors"]:
        print()
        print("  System errors (前 5 例):")
        for cand, name, msg in res["system_errors"]:
            print(f"    [{name}] {cand}: {msg[:80]}")
    print()
    print(f"  总耗时       = {res['total_elapsed_s']:.3f} s")
    if res["n_valid_ok"] > 0:
        print(f"  单候选 mean  = {res['mean_s']:.4f} s")
        print(f"  单候选 median= {res['median_s']:.4f} s")
        print(f"  单候选 p90   = {res['p90_s']:.4f} s")
        print(f"  单候选 max   = {res['max_s']:.4f} s")

    if res["best"] is not None:
        b = res["best"]
        s = b.strategy
        print()
        print("-" * 70)
        print("  临时最高 objective (FOUNDATION SMOKE):")
        print(f"    total_duration   = {b.total_duration_s:.6f} s")
        print(f"    heading_rad      = {s.heading_rad:.9f}")
        print(f"    speed_mps        = {s.speed_mps:.6f}")
        print(f"    release_time_s   = {s.release_time_s:.6f}")
        print(f"    delay_s          = {s.delay_s:.6f}")
        print(f"    sample_level     = {b.sample_level}")
        print(f"    scan_step_s      = {b.scan_step_s}")
        print(f"    intervals        = {b.intervals}")
        print()
        print("  *** NOT AN OPTIMIZATION RESULT ***")
        print("  *** DO NOT USE AS Q2 FINAL ANSWER ***")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
