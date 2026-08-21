# -*- coding: utf-8 -*-
"""多子图排版：compose_grid / compose_full_zoom_grid。"""

from typing import Any, Dict, Optional, Sequence, Tuple, Union

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from .style import _style_axes

__all__ = [
    "compose_grid",
    "compose_full_zoom_grid",
    "compute_pulse_zoom_window",
    "PANEL_LABEL_MODES",
]

PANEL_LABEL_MODES = ("auto", "upper", "lower", "paren")


def _add_panel_labels(axes: Sequence[Any], mode: str, fontsize: Optional[float]) -> None:
    if mode in ("auto", "upper"):
        labels = [chr(ord("A") + i) for i in range(len(axes))]
    elif mode == "lower":
        labels = [chr(ord("a") + i) for i in range(len(axes))]
    elif mode == "paren":
        labels = [f"({chr(ord('a') + i)})" for i in range(len(axes))]
    else:
        raise ValueError(f"未知 panel_labels 模式 {mode!r}")
    for ax, label in zip(axes, labels):
        ax.text(
            -0.05,
            1.08,
            label,
            transform=ax.transAxes,
            fontsize=fontsize or mpl.rcParams["font.size"],
            fontweight="bold",
            ha="right",
            va="top",
        )


def compose_grid(
    layout: Union[str, Sequence[Sequence[str]]],
    figsize: Sequence[float] = (8.0, 6.0),
    *,
    width_ratios: Optional[Sequence[float]] = None,
    height_ratios: Optional[Sequence[float]] = None,
    share: Union[bool, str] = False,
    panel_labels: Union[str, bool] = "auto",
    suptitle: Optional[str] = None,
) -> Tuple[Figure, Dict[str, Any]]:
    """mosaic 多子图；自动加 A/B/C 标签并应用 ieee_custom 边框规则。"""
    fig = plt.figure(figsize=figsize, layout="constrained")
    sharex: Any = False
    sharey: Any = False
    if share is True or share == "all":
        sharex, sharey = True, True
    elif share == "row":
        sharey = "row"
    elif share == "col":
        sharex = "col"

    gridspec_kw: Dict[str, Any] = {}
    if width_ratios:
        gridspec_kw["width_ratios"] = list(width_ratios)
    if height_ratios:
        gridspec_kw["height_ratios"] = list(height_ratios)

    mosaic = layout if isinstance(layout, str) else [list(row) for row in layout]
    axd = fig.subplot_mosaic(mosaic, sharex=sharex, sharey=sharey, gridspec_kw=gridspec_kw or None)
    for ax in axd.values():
        _style_axes(ax)
    if suptitle:
        fig.suptitle(suptitle)
    if panel_labels:
        ordered = [axd[k] for k in sorted(axd.keys())]
        _add_panel_labels(ordered, "auto" if panel_labels is True else str(panel_labels), None)
    return fig, axd


# ----------------------------------------------------------------------
# 波形专用模板：「全波形 + 脉冲放大」2×2 布局
# ----------------------------------------------------------------------
# 适用场景：双变量脉冲波形（电压 + 电流 / 电压 + 应力 / …），
#          需要同时呈现完整时序概览 + 单脉冲细节。
# 布局规则：
#   - 上行：变量 A（默认电压）；下行：变量 B（默认电流）。
#   - 左列：完整波形；右列：脉冲局部放大。
#   - 列内共享 x 轴；行间独立 y 轴（量纲/量级通常不同）。
#   - 四条轴脊线全部可见，上/右无刻度；y 轴 5% 留白，x 轴贴边。

def compose_full_zoom_grid(
    figsize: Sequence[float] = (14.0, 10.0),
    top_label: str = "Voltage",
    top_unit: str = "V",
    bottom_label: str = "Current",
    bottom_unit: str = "A",
    time_label: str = "Time (s)",
    full_title_suffix: str = "Full Waveform",
    zoom_title_suffix: str = "First Pulse Zoom",
    y_margin: float = 0.05,
) -> Tuple[Figure, Dict[str, Any]]:
    """构造「全波形 + 脉冲放大」2×2 布局，返回 figure 与按语义命名的 axes。

    返回的 axes 字典包含四个键：
        - ``full_top``    ：上行左列（变量 A 完整波形）
        - ``zoom_top``    ：上行右列（变量 A 脉冲放大）
        - ``full_bottom`` ：下行左列（变量 B 完整波形）
        - ``zoom_bottom`` ：下行右列（变量 B 脉冲放大）
    """
    fig, axes = plt.subplots(2, 2, figsize=tuple(figsize), sharex="col", sharey=False)

    # 行 0：top（变量 A）；行 1：bottom（变量 B）
    full_top, zoom_top = axes[0, 0], axes[0, 1]
    full_bottom, zoom_bottom = axes[1, 0], axes[1, 1]

    # 应用全脊线 + 仅左/下刻度 + y 留白样式
    for ax in (full_top, zoom_top, full_bottom, zoom_bottom):
        _style_axes(ax)
        ax.margins(x=0.0, y=float(y_margin))

    # 标题与轴标签（中文/英文均可，由调用方覆盖）
    full_top.set_title(f"{top_label} — {full_title_suffix}")
    full_top.set_ylabel(f"{top_label} ({top_unit})")
    zoom_top.set_title(f"{top_label} — {zoom_title_suffix}")

    full_bottom.set_title(f"{bottom_label} — {full_title_suffix}")
    full_bottom.set_xlabel(time_label)
    full_bottom.set_ylabel(f"{bottom_label} ({bottom_unit})")
    zoom_bottom.set_title(f"{bottom_label} — {zoom_title_suffix}")
    zoom_bottom.set_xlabel(time_label)

    # 仅下行显示 x 轴刻度数字（与 sharex='col' 配合：上行刻度文字隐去）
    full_top.tick_params(axis="x", labelbottom=False)
    zoom_top.tick_params(axis="x", labelbottom=False)

    return fig, {
        "full_top": full_top,
        "zoom_top": zoom_top,
        "full_bottom": full_bottom,
        "zoom_bottom": zoom_bottom,
    }


def compute_pulse_zoom_window(
    peak_index: int,
    total_samples: int,
    pre_pad: int = 300,
    post_pad: int = 1500,
) -> Tuple[int, int]:
    """计算脉冲放大窗口的索引范围（左闭右开）。

    采用「不对称填充」：脉冲前留较少样本（避免空白浪费横轴），
    脉冲后留较多样本（充分展示衰减振荡尾部与稳定过程）。

    Parameters
    ----------
    peak_index : int
        脉冲峰值在原始数组中的绝对索引（通常来自 `signal.find_pe`）。
    total_samples : int
        原始数组的总样本数（用于右边界截断）。
    pre_pad : int, default 300
        峰值左侧的样本数（≈ 脉冲阶跃前的留白）。
    post_pad : int, default 1500
        峰值右侧的样本数（≈ 衰减振荡尾部的可见长度）。

    Returns
    -------
    (left, right) : Tuple[int, int]
        半开区间 ``[left, right)``，可直接用于 ``f[var][left:right]`` 切片。

    Examples
    --------
    >>> left, right = compute_pulse_zoom_window(5372744, 100_000_000)
    >>> data = f["voltage"][left:right]
    """
    if peak_index < 0 or peak_index >= total_samples:
        raise ValueError(
            f"peak_index={peak_index} 超出 [0, {total_samples}) 范围"
        )
    if pre_pad < 0 or post_pad < 0:
        raise ValueError("pre_pad / post_pad 必须 ≥ 0")
    left = max(0, peak_index - int(pre_pad))
    right = min(int(total_samples), peak_index + int(post_pad))
    return left, right
