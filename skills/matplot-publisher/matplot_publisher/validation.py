# -*- coding: utf-8 -*-
"""第四层：验证与确认层。预览 + 保真度报告。"""

from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from .execution import downsample
from .io import MatReader
from .models import ExecutionPlan, ValidationResult
from .perception import PEAK_MAD_MULTIPLIER
from .style import apply_ieee_custom

__all__ = ["validate", "make_preview", "compute_fidelity"]

_PASS_PEAK = 0.01
_PASS_SLOPE = 0.05
_PASS_IOU = 0.99


def make_preview(
    x: np.ndarray,
    y: np.ndarray,
    plan: ExecutionPlan,
    output_path: str,
    title: str = "Preview - confirm before final export",
) -> str:
    """150 DPI PNG 预览，高权重区域用浅色底标注。"""
    import matplotlib.pyplot as plt

    apply_ieee_custom()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(x, y, linewidth=0.8)
    for region in plan.regions:
        if region.weight >= 9:
            ax.axvspan(region.start, region.end, color="#E64B35", alpha=0.08)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude (V)")
    ax.set_title(title)
    out = Path(output_path).with_suffix(".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    import matplotlib.pyplot as _plt

    _plt.close(fig)
    return str(out)


def make_glyphx_preview(x: np.ndarray, y: np.ndarray, output_path: str) -> Optional[str]:
    """可选：glyphx 交互式 HTML 预览。未安装则返回 None。"""
    try:
        import glyphx as gx  # type: ignore
    except Exception:
        return None
    try:
        fig = gx.Figure()
        # glyphx 2.x 对 numpy 数组的 truthiness 有兼容问题；转 list 规避。
        fig.add(gx.LineSeries(list(np.asarray(x)), list(np.asarray(y)), threshold=100_000))
        out = Path(output_path).with_suffix(".html")
        fig.save(str(out))
        return str(out)
    except Exception:
        return None


def _baseline(reader: MatReader, max_points: int = 1_000_000) -> Tuple[np.ndarray, np.ndarray]:
    n = reader.n_points
    if n <= max_points:
        idx = np.arange(n, dtype=np.int64)
    else:
        idx = np.unique(np.linspace(0, n - 1, max_points, dtype=np.int64))
    return reader.read_x_indices(idx), reader.read_indices(idx)


def _peak_values(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    from scipy import signal

    if len(y) < 3:
        return np.asarray([]), np.asarray([])
    med = np.median(y)
    mad = np.median(np.abs(y - med)) + 1e-12
    peaks, _ = signal.find_peaks(
        y,
        height=med + PEAK_MAD_MULTIPLIER * mad,
        distance=max(1, len(y) // 1000),
    )
    return np.asarray(x)[peaks], np.asarray(y)[peaks]


def compute_fidelity(
    reader: MatReader,
    x_down: np.ndarray,
    y_down: np.ndarray,
    n_bins: int = 200,
) -> Tuple[float, float, float, float]:
    """返回 peak_deviation, slope_deviation, envelope_iou, compression_ratio。"""
    x_raw, y_raw = _baseline(reader)
    rx, ry = _peak_values(x_raw, y_raw)
    dx, dy = _peak_values(x_down, y_down)

    if len(ry) and len(dy):
        nearest = np.searchsorted(x_down, rx).clip(0, len(y_down) - 1)
        peak_dev = float(np.max(np.abs(ry - y_down[nearest]) / (np.abs(ry) + 1e-12)))
    elif len(ry) == 0 and len(dy) == 0:
        peak_dev = 0.0
    else:
        peak_dev = 1.0

    raw_slope = np.max(np.abs(np.gradient(y_raw, x_raw))) if len(y_raw) > 2 else 1e-12
    down_slope = np.max(np.abs(np.gradient(y_down, x_down))) if len(y_down) > 2 else 0.0
    slope_dev = float(abs(raw_slope - down_slope) / (abs(raw_slope) + 1e-12))

    edges = np.linspace(min(x_raw.min(), x_down.min()), max(x_raw.max(), x_down.max()), n_bins + 1)
    iou_sum = 0.0
    valid = 0
    for i in range(n_bins):
        mask_r = (x_raw >= edges[i]) & (x_raw < edges[i + 1])
        mask_d = (x_down >= edges[i]) & (x_down < edges[i + 1])
        if not np.any(mask_r) and not np.any(mask_d):
            continue
        lo_r = float(np.min(y_raw[mask_r])) if np.any(mask_r) else None
        hi_r = float(np.max(y_raw[mask_r])) if np.any(mask_r) else None
        lo_d = float(np.min(y_down[mask_d])) if np.any(mask_d) else None
        hi_d = float(np.max(y_down[mask_d])) if np.any(mask_d) else None
        if None in (lo_r, hi_r, lo_d, hi_d):
            iou = 0.0
        else:
            union_lo, union_hi = min(lo_r, lo_d), max(hi_r, hi_d)
            inter = max(0.0, min(hi_r, hi_d) - max(lo_r, lo_d))
            union = max(1e-12, union_hi - union_lo)
            iou = inter / union
        iou_sum += iou
        valid += 1
    iou = iou_sum / max(1, valid)
    compression = len(x_down) / max(1, reader.n_points)
    return peak_dev, slope_dev, iou, compression


def validate(
    reader: MatReader,
    plan: ExecutionPlan,
    preview_dir: str,
    preview_name: str = "preview",
    use_glyphx: bool = False,
) -> ValidationResult:
    """生成预览和保真度报告；正式出图前必须经用户确认。"""
    preview_dir_path = Path(preview_dir)
    preview_dir_path.mkdir(parents=True, exist_ok=True)

    x_down, y_down = downsample(reader, plan, progress=True)
    preview_png = make_preview(x_down, y_down, plan, str(preview_dir_path / preview_name))
    preview_paths: List[str] = [preview_png]
    if use_glyphx:
        html = make_glyphx_preview(x_down, y_down, str(preview_dir_path / preview_name))
        if html:
            preview_paths.append(html)

    peak, slope, iou, compression = compute_fidelity(reader, x_down, y_down)
    passed = peak < _PASS_PEAK and slope < _PASS_SLOPE and iou > _PASS_IOU
    report = (
        "📊 保真度验证报告（验证层输出）：\n"
        f"- 峰值偏差：{peak:.2%}（标准 < {_PASS_PEAK:.0%}）{'✅' if peak < _PASS_PEAK else '❌'}\n"
        f"- 边沿斜率偏差：{slope:.2%}（标准 < {_PASS_SLOPE:.0%}）{'✅' if slope < _PASS_SLOPE else '❌'}\n"
        f"- 包络重合度：{iou:.2%}（标准 > {_PASS_IOU:.0%}）{'✅' if iou > _PASS_IOU else '❌'}\n"
        f"- 压缩率：{reader.n_points:,} → {len(x_down):,} 点（压缩 {1 - compression:.2%}）\n"
        f"- 结论：{'✅ 降采样方案通过保真度验证' if passed else '❌ 未通过，建议提高 n_out 或细化高权重区域'}"
    )
    return ValidationResult(
        preview_paths=preview_paths,
        peak_deviation=peak,
        slope_deviation=slope,
        envelope_iou=iou,
        compression_ratio=compression,
        passed=passed,
        confirmed=False,
        report=report,
        x_down=x_down,
        y_down=y_down,
    )
