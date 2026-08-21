# -*- coding: utf-8 -*-
"""ieee_custom 出版样式 + stonerplots 风格 SavedFigure。

改样式只改本文件；改完运行 ``python scripts/selfcheck.py``。
"""

from contextlib import ExitStack
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

import scienceplots  # noqa: F401  -- 注册 science / ieee 样式

__all__ = [
    "SSCI_COLORS",
    "ieee_custom",
    "apply_ieee_custom",
    "SavedFigure",
    "place_legend_outside",
    "DEFAULT_FORMATS",
]

# 规格书指定默认循环（色盲友好，硬编码）。
SSCI_COLORS: List[str] = [
    "#E64B35",
    "#4DBBD5",
    "#0072B5",
    "#E18727",
    "#20854E",
]

DEFAULT_FORMATS: Sequence[str] = ("pdf", "png")

_COLOR_RC: Dict[str, Any] = {"axes.prop_cycle": plt.cycler("color", SSCI_COLORS)}

_FONT_RC: Dict[str, Any] = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 11,
    "text.usetex": False,
    "axes.labelsize": 14,
    "axes.titlesize": 14,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 10,
    "mathtext.fontset": "custom",
    "mathtext.rm": "Arial",
    "mathtext.it": "Arial:italic",
    "mathtext.bf": "Arial:bold",
}

_AXES_RC: Dict[str, Any] = {
    "axes.linewidth": 0.8,
    "axes.edgecolor": "black",
    "axes.labelcolor": "black",
    "axes.labelpad": 4.0,
    "axes.titlepad": 6.0,
    # 四条轴脊线全部可见（2025-11 确认需求）；上/右轴脊线无刻度、无标签。
    # 全脊线框 + 仅左/下带刻度 = 更清晰的坐标范围提示。
    "axes.spines.left": True,
    "axes.spines.bottom": True,
    "axes.spines.top": True,
    "axes.spines.right": True,
    "axes.xmargin": 0.0,
    "axes.ymargin": 0.0,
    "axes.autolimit_mode": "data",
}

_TICK_RC: Dict[str, Any] = {
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.top": False,
    "xtick.bottom": True,
    "ytick.left": True,
    "ytick.right": False,
    "xtick.major.size": 4.0,
    "ytick.major.size": 4.0,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
}

# 仅 Y 轴虚线网格；X 轴关闭。
_GRID_RC: Dict[str, Any] = {
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.linestyle": "--",
    "grid.color": "#D9D9D9",
    "grid.linewidth": 0.6,
    "grid.alpha": 0.7,
}

_LEGEND_RC: Dict[str, Any] = {
    "legend.frameon": False,
    "legend.loc": "center left",
    "legend.borderaxespad": 0.5,
    "legend.handlelength": 1.5,
    "legend.handletextpad": 0.5,
    "legend.labelspacing": 0.4,
}

_ARTIST_RC: Dict[str, Any] = {
    "lines.linewidth": 1.0,
    "lines.markersize": 5.0,
    "errorbar.capsize": 3.0,
}

_FIGURE_RC: Dict[str, Any] = {
    "figure.figsize": (8.0, 6.0),
    "figure.dpi": 150,
    "figure.facecolor": "white",
    "figure.edgecolor": "white",
}

_EXPORT_RC: Dict[str, Any] = {
    "savefig.dpi": 600,
    "savefig.format": "pdf",
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.01,
    "savefig.facecolor": "white",
    "savefig.transparent": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
}

ieee_custom: Dict[str, Any] = {
    **_COLOR_RC,
    **_FONT_RC,
    **_AXES_RC,
    **_TICK_RC,
    **_GRID_RC,
    **_LEGEND_RC,
    **_ARTIST_RC,
    **_FIGURE_RC,
    **_EXPORT_RC,
}


def _style_axes(ax: Any) -> None:
    """rcParams 无法追溯生效的部分，在已有 Axes 上直接补做。

    四条轴脊线全部可见；刻度仅出现在左/下两侧；上/右轴脊线保留
    作为坐标范围提示，但不显示刻度与标签（出版级「全脊线」风格）。
    """
    try:
        for spine_name in ("left", "bottom", "top", "right"):
            ax.spines[spine_name].set_visible(True)
            ax.spines[spine_name].set_linewidth(0.8)
            ax.spines[spine_name].set_color("black")
        # 仅左/下轴显示刻度与标签；上/右轴保留脊线但无刻度。
        ax.tick_params(axis="x", direction="in", top=False, bottom=True,
                        labeltop=False, labelbottom=True)
        ax.tick_params(axis="y", direction="in", right=False, left=True,
                        labelright=False, labelleft=True)
        ax.grid(axis="y", linestyle="--", linewidth=0.6, color="#D9D9D9", alpha=0.7)
        ax.set_xmargin(0)
        ax.set_ymargin(0)
    except (AttributeError, KeyError, ValueError):
        pass


def apply_ieee_custom(overrides: Optional[Mapping[str, Any]] = None) -> None:
    """一键应用 ieee_custom 出版样式。

    overrides 在 ieee_custom 之后生效，适合单次临时调整 rcParam。
    """
    plt.style.use(["science", "ieee"])
    mpl.rcParams.update(ieee_custom)
    if overrides:
        mpl.rcParams.update(overrides)

    for fignum in list(plt.get_fignums()):
        for ax in plt.figure(fignum).axes:
            _style_axes(ax)


def place_legend_outside(ax: Any, **kwargs: Any) -> Any:
    """图例放图外右侧、无边框（bbox_to_anchor 不是 rcParam，需显式调用）。"""
    kw: Dict[str, Any] = {
        "loc": "center left",
        "bbox_to_anchor": (1.02, 0.5),
        "frameon": False,
    }
    kw.update(kwargs)
    return ax.legend(**kw)


class SavedFigure:
    """with 块内应用 ieee_custom，退出时按格式保存当前/指定 figure。"""

    def __init__(
        self,
        filename: Union[str, Path],
        formats: Optional[Union[str, Iterable[str]]] = None,
        style: Optional[Union[str, Iterable[str]]] = None,
        fig: Optional[Figure] = None,
        autoclose: bool = False,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.filename = Path(filename)
        self.formats = self._normalise(formats, DEFAULT_FORMATS)
        self.style = self._normalise(style, ("science", "ieee"))
        self.fig = fig
        self.autoclose = bool(autoclose)
        self.extra = dict(extra or {})
        self._stack: Optional[ExitStack] = None

    @staticmethod
    def _normalise(
        value: Optional[Union[str, Iterable[str]]],
        default: Sequence[str],
    ) -> List[str]:
        if value is None:
            return list(default)
        if isinstance(value, str):
            items = [p.strip().lstrip(".") for p in value.split(",") if p.strip()]
        else:
            items = [str(p).strip().lstrip(".") for p in value]
        if not items:
            raise ValueError("formats/style 不能为空")
        return items

    def __enter__(self) -> "SavedFigure":
        self._stack = ExitStack()
        self._stack.__enter__()
        self._stack.enter_context(plt.style.context(self.style))
        self._stack.enter_context(mpl.rc_context(rc=ieee_custom))
        if self.extra:
            self._stack.enter_context(mpl.rc_context(rc=self.extra))

        for fignum in list(plt.get_fignums()):
            for ax in plt.figure(fignum).axes:
                _style_axes(ax)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        try:
            if exc_type is None:
                fig = self.fig if self.fig is not None else plt.gcf()
                stem = self.filename.with_suffix("")
                stem.parent.mkdir(parents=True, exist_ok=True)
                for fmt in self.formats:
                    out = Path(f"{stem}.{fmt}")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    fig.savefig(str(out))
        finally:
            if self._stack is not None:
                self._stack.close()
                self._stack = None
        if self.autoclose:
            plt.close(self.fig if self.fig is not None else plt.gcf())
        return False
