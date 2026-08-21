# -*- coding: utf-8 -*-
"""matplot_publisher：示波器波形数据出版级绘图 Skill 运行库。

六层流程：
    perceive → interpret → decide → validate（等待确认） → execute → crystallize

示例
----
>>> from matplot_publisher import MatplotPublisher
>>> pub = MatplotPublisher("data.mat", "ch1_data", sample_rate=1e6)
>>> files = pub.run_full_pipeline(interactive=False, assume_confirmed=True)
"""

import sys as _sys


def _configure_stdout() -> None:
    """Windows GBK 控制台也能打印报告中的 emoji。"""
    try:
        for stream in (_sys.stdout, _sys.stderr):
            if stream is not None and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass


_configure_stdout()

from .compose import compose_full_zoom_grid, compose_grid, compute_pulse_zoom_window
from .crystallization import crystallize, match_profile
from .decision import decide
from .execution import downsample, execute
from .interpretation import interpret
from .io import MatReader, discover_mat_variables
from .perception import perceive
from .pipeline import MatplotPublisher
from .profile_manager import ProfileManager
from .style import SSCI_COLORS, SavedFigure, apply_ieee_custom, ieee_custom
from .validation import validate

__version__ = "1.2.0"

__all__ = [
    "MatplotPublisher",
    "compose_grid",
    "compose_full_zoom_grid",
    "compute_pulse_zoom_window",
    "perceive",
    "interpret",
    "decide",
    "validate",
    "execute",
    "downsample",
    "crystallize",
    "match_profile",
    "MatReader",
    "discover_mat_variables",
    "ProfileManager",
    "SSCI_COLORS",
    "ieee_custom",
    "apply_ieee_custom",
    "SavedFigure",
]
