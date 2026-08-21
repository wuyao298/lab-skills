# -*- coding: utf-8 -*-
"""第三层：决策层。权重表 -> 执行方案说明书。"""

from typing import Dict, List, Optional, Sequence

from .models import ExecutionPlan, PlanRegion, WeightTable

__all__ = ["decide"]

_DEFAULT_BUCKET_BUDGET = {9: 0.0, 6: 0.40, 3: 0.25, 1: 0.10, 0: 0.01}


def _bucket_for(weight: int) -> int:
    if weight >= 9:
        return 9
    if weight >= 6:
        return 6
    if weight >= 3:
        return 3
    if weight >= 1:
        return 1
    return 0


def choose_chunk_size(n_points: int, memory_gb: Optional[float] = None) -> int:
    """按内存档位选择单批点数；缺省按 16GB 档（5M）。"""
    if memory_gb is None:
        try:
            import psutil  # type: ignore

            memory_gb = float(psutil.virtual_memory().total) / 1e9
        except Exception:
            memory_gb = 16.0
    if memory_gb >= 32:
        size = 10_000_000
    elif memory_gb >= 16:
        size = 5_000_000
    elif memory_gb >= 8:
        size = 2_000_000
    else:
        size = 500_000
    return max(10_000, min(size, max(10_000, n_points)))


def _algorithm_for(weight: int, morphology: str) -> str:
    if weight >= 9:
        return "lossless"
    if morphology == "periodic":
        return "minmax"
    if weight >= 6:
        return "m4"
    if weight >= 3:
        return "m4"
    return "m4"


def decide(
    weights: WeightTable,
    n_points: int,
    target_n_out: int = 100_000,
    pulse_threshold: Optional[float] = None,
    chunk_size: Optional[int] = None,
    memory_gb: Optional[float] = None,
) -> ExecutionPlan:
    """把权重表转成逐区域策略和预算。"""
    regions = [r for r in weights.regions if r.start < r.end]

    plan_regions: List[PlanRegion] = []
    bucket_lengths: Dict[int, int] = {}
    bucket_regions: Dict[int, List[PlanRegion]] = {k: [] for k in _DEFAULT_BUCKET_BUDGET}

    for r in regions:
        length = r.end - r.start + 1
        bucket = _bucket_for(r.weight)
        strategy = "lossless" if r.weight >= 9 else ("boundary" if r.weight == 0 else "minmax")
        algorithm = _algorithm_for(r.weight, weights.morphology)
        pr = PlanRegion(r.start, r.end, r.weight, strategy, algorithm, 0, r.label)
        plan_regions.append(pr)
        bucket_lengths[bucket] = bucket_lengths.get(bucket, 0) + length
        bucket_regions[bucket].append(pr)

    lossless_n = sum(p.end - p.start + 1 for p in plan_regions if p.weight >= 9)
    remaining_budget = max(0, target_n_out - lossless_n)

    # 权重 0：每段只保留首尾 1 点。
    for p in bucket_regions[0]:
        p.n_out = 2

    # 6-8 / 3-5 / 1-2 按 40% / 25% / 10% 分配剩余预算；
    # 只存在一个桶时归一化为 100%，保证纯背景数据也能用满 n_out。
    active_buckets = [b for b in (6, 3, 1) if bucket_lengths.get(b, 0) > 0]
    active_frac = sum(_DEFAULT_BUCKET_BUDGET[b] for b in active_buckets) or 1.0
    # 每段压缩区至少保留足够点数，保证验证层的包络分箱不空。
    floor_per_region = max(2, min(target_n_out // 20, target_n_out))
    for bucket in active_buckets:
        budget = int(remaining_budget * _DEFAULT_BUCKET_BUDGET[bucket] / active_frac)
        weighted_sum = sum((p.end - p.start + 1) * p.weight for p in bucket_regions[bucket])
        if weighted_sum <= 0:
            continue
        for p in bucket_regions[bucket]:
            span = p.end - p.start + 1
            share = int(budget * (span * p.weight) / weighted_sum)
            p.n_out = max(floor_per_region, min(span, share))
            if p.weight >= 6:
                p.n_out = max(4, p.n_out)
    # 若所有预算都被压缩区域用掉，确保 lossless 仍按 100% 计算。
    for p in plan_regions:
        if p.weight >= 9:
            p.n_out = p.end - p.start + 1

    total_estimated = sum(p.n_out for p in plan_regions)
    chunk = chunk_size or choose_chunk_size(n_points, memory_gb)
    max_pulse_span = max((p.end - p.start for p in plan_regions if p.weight >= 9), default=0)
    overlap = 0.2 if max_pulse_span > n_points * 0.02 else 0.1
    threshold = float(pulse_threshold if pulse_threshold is not None else (5.0 if len(weights.regions) > 20 else 3.0))

    plan = ExecutionPlan(
        n_points=n_points,
        target_n_out=target_n_out,
        estimated_n_out=total_estimated,
        chunk_size=chunk,
        overlap_ratio=overlap,
        pulse_threshold=threshold,
        regions=plan_regions,
        algorithms=sorted({p.algorithm for p in plan_regions}),
    )
    plan.summary = _render_plan(plan)
    return plan


def _render_plan(plan: ExecutionPlan) -> str:
    lines = [
        "📋 执行方案说明书（决策层输出）：",
        f"- 总输出目标：{plan.target_n_out:,} 点",
        f"- 单批处理：{plan.chunk_size:,} 点，overlap={plan.overlap_ratio:.0%}",
    ]
    for p in plan.regions:
        lines.append(
            f"- {p.label or '区域'}（{p.start:,}–{p.end:,}，权重 {p.weight}）："
            f"{p.strategy} / {p.algorithm} / {p.n_out:,} 点"
        )
    lines.append(f"- 合计输出：约 {plan.estimated_n_out:,} 点")
    lines.append(f"- 执行引擎：{' + '.join(plan.algorithms)}")
    return "\n".join(lines)
