# -*- coding: utf-8 -*-
"""第五层：执行层。分批降采样 + ieee_custom 出版级出图。"""

import time
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .io import MatReader
from .models import ExecutionPlan, OutputFiles
from .style import SavedFigure, apply_ieee_custom, place_legend_outside

try:  # 专业降采样库可选；失败时按规格降级为保守 Min-Max。
    import tsdownsample as tds  # type: ignore
except Exception:  # pragma: no cover - 依赖缺失路径
    tds = None

__all__ = ["downsample", "execute", "minmax_downsample"]


def minmax_downsample(x: np.ndarray, y: np.ndarray, n_out: int) -> Tuple[np.ndarray, np.ndarray]:
    """保守 Min-Max：每箱保留 min 与 max，保护包络与尖峰。"""
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    if n_out >= len(x):
        return x, y
    n_out = max(2, int(n_out))
    bins = max(1, n_out // 2)
    out_idx: List[int] = [0]
    edges = np.linspace(0, len(x), bins + 1, dtype=np.int64)
    for i in range(bins):
        left, right = int(edges[i]), int(edges[i + 1])
        if right <= left:
            continue
        seg = y[left:right]
        imin = left + int(np.argmin(seg))
        imax = left + int(np.argmax(seg))
        if imin == imax:
            out_idx.append(imin)
        else:
            out_idx.extend((min(imin, imax), max(imin, imax)))
    if out_idx[-1] != len(x) - 1:
        out_idx.append(len(x) - 1)
    idx = np.unique(np.asarray(out_idx, dtype=np.int64))
    return x[idx], y[idx]


def _ts_downsample(
    x: np.ndarray,
    y: np.ndarray,
    n_out: int,
    algorithm: str,
) -> Tuple[np.ndarray, np.ndarray]:
    """兼容 tsdownsample 旧函数 API（m4/lttb）与新类 API（M4Downsampler 等）。"""
    old_fn = getattr(tds, algorithm, None)
    if callable(old_fn):
        return old_fn(x, y, n_out=n_out)

    classes = {
        "m4": tds.M4Downsampler,
        "minmax": tds.MinMaxDownsampler,
        "lttb": tds.LTTBDownsampler,
    }
    cls = classes.get(algorithm)
    if cls is not None:
        if algorithm == "m4":
            n_out = max(4, int(n_out) - int(n_out) % 4)
        idx = cls().downsample(x, y, n_out=n_out)
        idx = np.asarray(idx, dtype=np.int64).ravel()
        return x[idx], y[idx]
    raise ValueError(f"未知算法：{algorithm}")


def _downsample_chunk(
    x: np.ndarray,
    y: np.ndarray,
    n_out: int,
    algorithm: str,
) -> Tuple[np.ndarray, np.ndarray]:
    if len(x) <= n_out:
        return x, y
    if tds is not None:
        try:
            return _ts_downsample(x, y, n_out, algorithm)
        except Exception:
            pass  # 专业库失败 -> 保守 Min-Max 降级
    if algorithm in ("m4", "minmax", "lttb"):
        return minmax_downsample(x, y, n_out)
    return x[:: max(1, len(x) // n_out)], y[:: max(1, len(y) // n_out)]


def downsample(
    reader: MatReader,
    plan: ExecutionPlan,
    progress: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """按方案逐区域、逐 chunk 降采样，全程不加载全量数据。"""
    xs: List[np.ndarray] = []
    ys: List[np.ndarray] = []

    for region in plan.regions:
        span = region.end - region.start + 1
        if span <= 0:
            continue
        region_n = int(region.n_out)
        if region.strategy == "lossless":
            for _, _, y, x in reader.iter_chunks(plan.chunk_size, region.start, region.end + 1):
                xs.append(np.asarray(x, dtype=np.float64).ravel())
                ys.append(np.asarray(y, dtype=np.float64).ravel())
            continue
        if region.strategy == "boundary":
            idx = np.asarray([region.start, region.end], dtype=np.int64)
            ys.append(reader.read_indices(idx))
            xs.append(reader.read_x_indices(idx))
            continue

        # 按 chunk 分摊该区域的输出预算，避免整段读入内存。
        for left, right, y, x in reader.iter_chunks(plan.chunk_size, region.start, region.end + 1):
            chunk_len = right - left
            chunk_n = max(2, int(round(region_n * chunk_len / span)))
            xd, yd = _downsample_chunk(x, y, chunk_n, region.algorithm)
            xs.append(xd)
            ys.append(yd)
            if progress and right % (plan.chunk_size * 5) == 0:
                print(f"  …已处理 {right:,}/{reader.n_points:,} 点", flush=True)

    x = np.concatenate(xs) if xs else np.asarray([], dtype=np.float64)
    y = np.concatenate(ys) if ys else np.asarray([], dtype=np.float64)
    order = np.argsort(x, kind="stable")
    x, y = x[order], y[order]
    keep = np.ones(len(x), dtype=bool)
    keep[1:] = (x[1:] != x[:-1]) | (y[1:] != y[:-1])
    return x[keep], y[keep]


def execute(
    x: np.ndarray,
    y: np.ndarray,
    output_base: str,
    formats: Iterable[str] = ("pdf", "png"),
    label: Optional[str] = None,
    xlabel: str = "Time (s)",
    ylabel: str = "Amplitude (V)",
    title: Optional[str] = None,
) -> OutputFiles:
    """用 ieee_custom 样式生成出版级 PDF + PNG。"""
    import matplotlib.pyplot as plt

    t0 = time.time()
    apply_ieee_custom()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(x, y, linewidth=1.0, label=label or None)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    if label:
        place_legend_outside(ax)

    base = Path(output_base).with_suffix("")
    base.parent.mkdir(parents=True, exist_ok=True)
    with SavedFigure(base, formats=formats, fig=fig, autoclose=True):
        fig.canvas.draw()

    files = OutputFiles(
        elapsed_seconds=time.time() - t0,
        paths={fmt: str(Path(f"{base}.{fmt}")) for fmt in formats},
    )
    files.pdf_path = files.paths.get("pdf")
    files.png_path = files.paths.get("png")
    return files
