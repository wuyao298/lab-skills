# -*- coding: utf-8 -*-
"""ieee_custom 样式契约。"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
from matplot_publisher.style import SSCI_COLORS, apply_ieee_custom


def test_style_contract():
    apply_ieee_custom()
    assert plt.rcParams["xtick.direction"] == "in"
    assert plt.rcParams["ytick.direction"] == "in"
    assert plt.rcParams["axes.spines.top"] is False
    assert plt.rcParams["axes.spines.right"] is False
    assert plt.rcParams["axes.labelsize"] == 14
    assert plt.rcParams["xtick.labelsize"] == 11
    assert plt.rcParams["axes.grid.axis"] == "y"
    assert plt.rcParams["grid.linestyle"] == "--"
    assert plt.rcParams["axes.xmargin"] == 0.0
    assert plt.rcParams["axes.ymargin"] == 0.0
    assert SSCI_COLORS == ["#E64B35", "#4DBBD5", "#0072B5", "#E18727", "#20854E"]
    assert next(iter(plt.rcParams["axes.prop_cycle"]))["color"] == SSCI_COLORS[0]
    plt.close("all")
