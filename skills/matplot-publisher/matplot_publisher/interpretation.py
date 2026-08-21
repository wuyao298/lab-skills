# -*- coding: utf-8 -*-
"""第二层：理解层。数据画像 -> 关注度权重表（权重 0~10）。"""

import re
from typing import List, Optional, Sequence, Tuple

from .models import DataProfile, WeightedRegion, WeightTable

__all__ = ["interpret"]


def _parse_preserve_ranges(text: str, n_points: int) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    for match in re.finditer(r"\[?\s*(\d+)\s*[:：,]\s*(\d+)\s*\]?", text):
        a = max(0, int(match.group(1)))
        b = min(n_points - 1, int(match.group(2)))
        if b > a:
            ranges.append((a, b))
    return ranges


def _cluster(values: Sequence[int], radius: int, n_points: int) -> List[Tuple[int, int]]:
    clusters: List[List[int]] = []
    for v in sorted(int(x) for x in values if 0 <= x < n_points):
        if not clusters or v - clusters[-1][-1] > radius:
            clusters.append([v])
        else:
            clusters[-1].append(v)
    out = []
    for group in clusters:
        left = max(0, group[0] - radius)
        right = min(n_points - 1, group[-1] + radius)
        out.append((left, right))
    return out


def interpret(
    profile: DataProfile,
    user_hint: Optional[str] = None,
) -> WeightTable:
    """生成关注度权重表；不确定时通过 question 请求用户澄清。"""
    n = profile.n_points
    hint = (user_hint or "").lower()
    focus_peaks = any(k in hint for k in ("峰值", "过冲", "peak", "脉冲幅度", "精度"))
    focus_overall = any(k in hint for k in ("整体", "形态", "时序", "overall", "shape"))
    focus_noise = any(k in hint for k in ("底噪", "噪声", "noise", "基线"))
    time_match = re.search(r"t\s*[=＝]\s*([0-9.eE+-]+)", hint)
    focus_time = float(time_match.group(1)) if time_match else None
    preserve_ranges = _parse_preserve_ranges(hint, n)

    pulse_radius = max(4, n // 10_000)          # 脉冲核心：约 ±0.01%
    transition_radius = max(1, n // 200)        # 过渡带：约 ±0.5%
    pulse_centers = profile.peak_indices or profile.anomaly_indices

    specials: List[WeightedRegion] = []
    morphology = profile.morphology

    if morphology == "pulse_dominated":
        pulse_weight = 8 if focus_overall else 10
        for left, right in _cluster(pulse_centers, pulse_radius, n):
            specials.append(WeightedRegion(left, right, pulse_weight, "脉冲区域", "无损保留"))
            # 过渡带：脉冲前后 0.5% 总长
            trans_left = max(0, left - transition_radius)
            trans_right = min(n - 1, right + transition_radius)
            if trans_left < left:
                specials.append(WeightedRegion(trans_left, left - 1, 8, "过渡带", "精细 Min-Max"))
            if trans_right > right:
                specials.append(WeightedRegion(right + 1, trans_right, 8, "过渡带", "精细 Min-Max"))
    elif morphology == "step_like":
        if profile.peak_indices:
            edge = profile.peak_indices[0]
        elif profile.anomaly_indices:
            edge = profile.anomaly_indices[0]
        else:
            edge = n // 2
        radius = max(1, n // 100)
        specials.append(WeightedRegion(max(0, edge - radius), min(n - 1, edge + radius), 9, "边沿区域", "无损/精细"))
    elif morphology == "periodic":
        for left, right in _cluster(profile.peak_indices, max(1, n // 500), n):
            specials.append(WeightedRegion(left, right, 8, "振荡包络峰", "峰值保持"))
        for left, right in _cluster(profile.anomaly_indices, max(1, n // 500), n):
            specials.append(WeightedRegion(left, right, 4, "振荡包络谷", "标准 Min-Max"))
    elif morphology == "mixed":
        # 混合形态默认按脉冲处理，但要求用户澄清关注点。
        for left, right in _cluster(pulse_centers, pulse_radius, n):
            specials.append(WeightedRegion(left, right, 10, "疑似脉冲", "无损保留"))

    if focus_time is not None and profile.sample_rate:
        centre = int(focus_time * profile.sample_rate)
        radius = max(1000, n // 100)
        specials.append(WeightedRegion(max(0, centre - radius), min(n - 1, centre + radius), 9, "用户关注区", "精细处理"))

    for left, right in preserve_ranges:
        specials.append(WeightedRegion(left, right, 10, "用户标记区", "无损直通"))

    if focus_noise:
        tail_start = int(n * 0.8)
        specials.append(WeightedRegion(tail_start, n - 1, 7, "底噪区", "精细保留噪声"))

    for left, right in profile.missing_segments:
        specials.append(WeightedRegion(left, right, 0, "缺失段", "忽略"))

    specials.sort(key=lambda r: (r.start, -r.weight))
    merged: List[WeightedRegion] = []
    for region in specials:
        if region.start >= region.end:
            continue
        if not merged:
            merged.append(region)
            continue
        last = merged[-1]
        if region.start <= last.end + 1:
            old_weight = last.weight
            last.end = max(last.end, region.end)
            last.weight = max(old_weight, region.weight)
            if region.weight >= old_weight:
                last.label, last.reason = region.label, region.reason
        else:
            merged.append(region)

    # 用背景区域填补空隙。
    regions: List[WeightedRegion] = []
    cursor = 0
    background_weight = 2 if morphology != "periodic" else 4
    for r in merged:
        if cursor < r.start:
            regions.append(WeightedRegion(cursor, r.start - 1, background_weight, "背景", "压缩"))
        regions.append(r)
        cursor = r.end + 1
    if cursor < n:
        regions.append(WeightedRegion(cursor, n - 1, background_weight, "背景", "压缩"))

    needs_clarification = (morphology in ("pulse_dominated", "mixed")) and not hint
    question = (
        "检测到脉冲/瞬态特征。您更关注：\n"
        "A. 每个脉冲的峰值和过冲幅度（峰值精度优先）\n"
        "B. 整体的波形形态和时序（形态完整优先）\n"
        "请选择 A 或 B。"
    )

    return WeightTable(
        morphology=morphology,
        focus=hint or "未指定",
        regions=regions,
        needs_clarification=needs_clarification,
        question=question,
        summary=_render_weights(regions),
    )


def _render_weights(regions: Sequence[WeightedRegion]) -> str:
    lines = ["🎯 关注度权重表（理解层输出）："]
    for r in regions:
        lines.append(f"- {r.label}（{r.start:,}–{r.end:,}）：权重 {r.weight}（{r.reason}）")
    return "\n".join(lines)
