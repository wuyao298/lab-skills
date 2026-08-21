# -*- coding: utf-8 -*-
"""第一层：感知层。四个探针全部抽样式分析，禁止全量加载。"""

from typing import Dict, List, Optional, Tuple

import numpy as np

from .io import MatReader
from .models import DataProfile

__all__ = ["perceive", "probe_morphology", "probe_density", "probe_energy", "probe_anomalies", "PEAK_MAD_MULTIPLIER"]

# 脉冲探针高度门；3×MAD 用于异常探针报告毛刺，8×MAD 才视为真脉冲。
PEAK_MAD_MULTIPLIER = 8.0


def _finite(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.float64).ravel()
    y = y[np.isfinite(y)]
    return y if y.size else np.zeros(1, dtype=np.float64)


def _sample_indices(n_points: int, sample_ratio: float, max_samples: int) -> np.ndarray:
    n = min(int(round(n_points * sample_ratio)), max_samples)
    n = max(min(n, n_points), min(1000, n_points))
    return np.unique(np.linspace(0, n_points - 1, n, dtype=np.int64))


def probe_morphology(y_sample: np.ndarray, sample_rate: Optional[float]) -> Tuple[str, float, float]:
    """形态探针：峰度 / 偏度 / 频谱规则分类。"""
    from scipy import stats

    y = _finite(y_sample)
    kurt = float(stats.kurtosis(y))
    skew = float(stats.skew(y))
    rng = float(np.ptp(y))

    if rng <= np.finfo(float).eps:
        return "random_noise", kurt, skew

    centred = y - np.mean(y)
    n = min(len(centred), 100_000)
    spectrum = np.abs(np.fft.rfft(centred[:n] * np.hanning(n)))
    total = float(np.sum(spectrum))
    dominant_ratio = float(np.max(spectrum) / total) if total > 0 else 0.0

    # 阶跃检测：首/尾 20% 均值差占全幅值比例高时判为 step_like。
    left_mean = float(np.mean(y[: max(1, len(y) // 5)]))
    right_mean = float(np.mean(y[-max(1, len(y) // 5):]))
    step_ratio = abs(left_mean - right_mean) / max(rng, 1e-12)

    if kurt > 8 or dominant_ratio > 0.55:
        return "pulse_dominated", kurt, skew
    if step_ratio > 0.25 or abs(skew) > 2:
        return "step_like", kurt, skew
    if 0.35 <= dominant_ratio <= 0.55:
        return "periodic", kurt, skew
    if kurt < 1.5 and abs(skew) < 1:
        return "random_noise", kurt, skew
    return "mixed", kurt, skew


def probe_density(
    reader: MatReader,
    indices: np.ndarray,
    n_bins: int = 20,
) -> List[Tuple[int, int]]:
    """密度探针：点间隔分布，标记前 5% 密集区间。

    均匀采样（仅 sample_rate）时密度处处相同，返回空表。
    """
    if not reader.x_variable:
        return []
    x = reader.read_x_indices(indices)
    x = x[np.isfinite(x)]
    if x.size < 3:
        return []
    gaps = np.diff(np.sort(x))
    if float(np.median(gaps)) <= 0:
        return []
    density = 1.0 / np.maximum(gaps, 1e-12)
    edges = np.linspace(np.min(x), np.max(x), n_bins + 1)
    hist, _ = np.histogram(x[:-1], bins=edges, weights=density)
    top = int(max(1, np.ceil(n_bins * 0.05)))
    dense_bins = np.argsort(hist)[::-1][:top]
    regions: List[Tuple[int, int]] = []
    for b in dense_bins:
        regions.append((int(edges[b]), int(edges[b + 1])))
    return regions


def probe_energy(y_sample: np.ndarray, sample_rate: Optional[float], n_segments: int = 10) -> Dict[str, float]:
    """能量探针：STFT 主频，输出时间段 -> 主频。"""
    from scipy import signal

    y = _finite(y_sample)
    rate = float(sample_rate) if sample_rate else 1.0
    if y.size < 64:
        return {}
    nperseg = max(32, min(1024, int(y.size // n_segments)))
    try:
        f, _, zxx = signal.stft(y, fs=rate, nperseg=nperseg, noverlap=nperseg // 2)
        power = np.abs(zxx)
        seg_len = max(1, int(np.ceil(power.shape[1] / n_segments)))
        out: Dict[str, float] = {}
        for i, left in enumerate(range(0, power.shape[1], seg_len)):
            right = min(left + seg_len, power.shape[1])
            band = power[:, left:right]
            dom = f[int(np.argmax(np.sum(band, axis=1)))]
            out[f"seg_{i}"] = float(dom)
        return out
    except Exception:
        return {}


def _pulse_scan_indices(
    reader: MatReader,
    y_base: np.ndarray,
    max_extra: int = 1_000_000,
    scan_chunk: int = 1_000_000,
) -> np.ndarray:
    """稀疏脉冲补充扫描：分块找高幅值块，只对可疑块细采样。

    均匀 1% 采样可能恰好跳过窄脉冲；此探针顺序读块（不驻留全量），
    对超过 8×MAD 的块追加最多 max_extra 个细采样索引。
    """
    y = _finite(y_base)
    if y.size < 10:
        return np.asarray([], dtype=np.int64)
    med = float(np.median(y))
    mad = float(np.median(np.abs(y - med))) + 1e-12
    threshold = med + PEAK_MAD_MULTIPLIER * mad

    suspicious = []
    for left, right, y_chunk, _ in reader.iter_chunks(scan_chunk, include_x=False):
        yc = _finite(y_chunk)
        if yc.size and float(np.max(np.abs(yc - med))) > threshold:
            suspicious.append((left, right))

    if not suspicious:
        return np.asarray([], dtype=np.int64)

    # 可疑块均分补充采样预算，避免第一个脉冲块耗尽预算后漏掉后续脉冲。
    per_block = max(100, max_extra // len(suspicious))
    extra: List[np.ndarray] = []
    for left, right in suspicious:
        span = right - left
        if span <= per_block:
            idx = np.arange(left, right, dtype=np.int64)
        else:
            idx = np.linspace(left, right - 1, per_block, dtype=np.int64)
        extra.append(idx)
    return np.unique(np.concatenate(extra))


def probe_anomalies(
    y_sample: np.ndarray,
    indices: np.ndarray,
    reader: MatReader,
    mad_multiplier: float = 3.0,
) -> Tuple[List[int], List[Tuple[int, int]]]:
    """异常探针：3×MAD 毛刺 + 缺失段。"""
    y = np.asarray(y_sample, dtype=np.float64).ravel()
    idx = np.asarray(indices, dtype=np.int64).ravel()
    finite = np.isfinite(y)
    y_f, idx_f = y[finite], idx[finite]

    anomaly_indices: List[int] = []
    missing: List[Tuple[int, int]] = []
    if y_f.size:
        med = float(np.median(y_f))
        mad = float(np.median(np.abs(y_f - med))) + 1e-12
        threshold = mad_multiplier * mad
        anomaly_indices = [int(i) for i in idx_f[np.abs(y_f - med) > threshold][:200]]

    if reader.x_variable and reader.n_points > 2:
        all_idx = np.arange(reader.n_points, dtype=np.int64)
        sample_idx = np.sort(np.unique(np.clip(indices, 0, reader.n_points - 1)))
        x = reader.read_x_indices(sample_idx)
        if x.size > 2 and np.all(np.isfinite(x)):
            gaps = np.diff(x)
            med_gap = float(np.median(gaps))
            if med_gap > 0:
                for pos in np.where(gaps > 10 * med_gap)[0][:20]:
                    missing.append((int(sample_idx[pos]), int(sample_idx[pos + 1])))
    return anomaly_indices, missing


def perceive(
    reader: MatReader,
    sample_ratio: float = 0.01,
    max_samples: int = 1_000_000,
    mad_multiplier: float = 3.0,
) -> DataProfile:
    """运行全部探针，返回 DataProfile。"""
    n = reader.n_points
    base_indices = _sample_indices(n, sample_ratio, max_samples)
    y_base = reader.read_indices(base_indices)
    scan_indices = _pulse_scan_indices(reader, y_base)
    indices = np.unique(np.concatenate([base_indices, scan_indices]))
    y_sample = reader.read_indices(indices)
    morphology, kurt, skew = probe_morphology(y_sample, reader.sample_rate)
    dense_regions = probe_density(reader, indices)
    energy_map = probe_energy(y_sample, reader.sample_rate)
    anomaly_indices, missing_segments = probe_anomalies(y_sample, indices, reader, mad_multiplier)

    from scipy import signal

    peak_indices: List[int] = []
    try:
        y_f = _finite(y_sample)
        med = float(np.median(y_f))
        mad = float(np.median(np.abs(y_f - med))) + 1e-12
        # 脉冲探针用更严的高度门（8×MAD）：3×MAD 留给异常探针报告毛刺，
        # 否则纯噪声中的随机起伏会被误判为脉冲。
        peaks, _ = signal.find_peaks(y_f, height=med + PEAK_MAD_MULTIPLIER * mad, distance=max(1, len(y_f) // 1000))
        if peaks.size:
            # 把 sample 内峰位置映射回全局索引
            mapped = [int(indices[p]) for p in peaks[:50] if p < len(indices)]
            peak_indices = mapped
    except Exception:
        peak_indices = []

    profile = DataProfile(
        file_path=reader.path,
        file_format=reader.format,
        variable_name=reader.variable_name,
        x_variable=reader.x_variable,
        sample_rate=reader.sample_rate,
        n_points=n,
        n_sampled=int(len(indices)),
        morphology=morphology,
        kurtosis=kurt,
        skewness=skew,
        peak_indices=peak_indices,
        dense_regions=dense_regions,
        energy_map=energy_map,
        anomaly_indices=anomaly_indices,
        missing_segments=missing_segments,
    )
    profile.summary = _render_profile(profile)
    return profile


def _render_profile(p: DataProfile) -> str:
    lines = [
        "📊 数据画像（感知层输出）：",
        f"- 文件格式：{p.file_format}",
        f"- 变量名：{p.variable_name}",
        f"- 总点数：{p.n_points:,}",
        f"- 数据大小：{p.n_points * 8 / 1e6:.1f} MB (float64)",
        f"- 形态分类：{p.morphology}",
    ]
    if p.dense_regions:
        lines.append(f"- 密集区间：{len(p.dense_regions)} 段（前 5% 密集）")
    if p.energy_map:
        dom = max(p.energy_map.values())
        lines.append(f"- 能量分布：主频约 {dom:g} Hz")
    if p.anomaly_indices:
        lines.append(f"- 异常检测：{len(p.anomaly_indices)} 个幅值异常点")
    if p.missing_segments:
        lines.append(f"- 数据缺失：{len(p.missing_segments)} 段")
    return "\n".join(lines)
