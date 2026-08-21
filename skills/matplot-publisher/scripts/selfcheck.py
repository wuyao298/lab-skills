# -*- coding: utf-8 -*-
"""matplot-publisher 自检。

在 skill 根目录运行：
    python scripts/selfcheck.py

通过标准：最后输出 ``selfcheck: OK``。
"""

import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.io import savemat  # noqa: E402

from matplot_publisher import (  # noqa: E402
    MatplotPublisher,
    SSCI_COLORS,
    apply_ieee_custom,
    compose_full_zoom_grid,
    compose_grid,
    compute_pulse_zoom_window,
)


def _check(condition, message):
    if not condition:
        raise AssertionError(f"FAIL: {message}")


def main():
    apply_ieee_custom()
    _check(plt.rcParams["xtick.direction"] == "in", "xtick.direction != in")
    # 2025-11 确认需求：四条轴脊线全部可见；上/右轴无刻度、无标签。
    _check(plt.rcParams["axes.spines.top"] is True, "top spine 应可见（仅无刻度）")
    _check(plt.rcParams["axes.spines.right"] is True, "right spine 应可见（仅无刻度）")
    _check(plt.rcParams["axes.labelsize"] == 14, "轴标签字号应为 14")
    _check(plt.rcParams["xtick.labelsize"] == 11, "刻度字号应为 11")
    _check(plt.rcParams["axes.grid.axis"] == "y", "应只开 Y 轴网格")
    _check(plt.rcParams["grid.linestyle"] == "--", "网格应为虚线")
    _check(SSCI_COLORS[0] == "#E64B35", "默认循环第一色错误")

    fig, axd = compose_grid("AB;CD", figsize=(6, 4))
    _check(sorted(axd.keys()) == ["A", "B", "C", "D"], "compose_grid 键错误")
    for ax in axd.values():
        _check(ax.spines["top"].get_visible() is True, "top spine 应可见")
        _check(ax.spines["right"].get_visible() is True, "right spine 应可见")
    plt.close(fig)

    # 波形专用模板：2×2 全波形 + 脉冲放大
    fig2, axs = compose_full_zoom_grid()
    _check(
        set(axs.keys()) == {"full_top", "zoom_top", "full_bottom", "zoom_bottom"},
        "compose_full_zoom_grid 键错误",
    )
    for ax in axs.values():
        _check(ax.spines["top"].get_visible() is True, "模板：top spine 应可见")
        _check(ax.spines["right"].get_visible() is True, "模板：right spine 应可见")
        # 上行不显示 x 轴刻度数字
    _check(
        not axs["full_top"].xaxis.get_majorticklabels()[0].get_visible()
        if axs["full_top"].xaxis.get_majorticklabels()
        else True,
        "模板：full_top 不应显示 x 轴刻度数字",
    )
    plt.close(fig2)

    # 脉冲放大窗口助手：不对称填充
    left, right = compute_pulse_zoom_window(peak_index=5000, total_samples=10_000,
                                            pre_pad=300, post_pad=1500)
    _check(left == 4700 and right == 6500, "zoom 窗口计算错误")
    _check(
        compute_pulse_zoom_window(100, 10_000)[0] == 0,
        "peak 靠前时左边界应截断到 0",
    )
    _check(
        compute_pulse_zoom_window(9990, 10_000, pre_pad=50, post_pad=200)[1] == 10_000,
        "peak 靠后时右边界应截断到 total_samples",
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        n = 20_000
        y = np.random.default_rng(0).normal(0, 0.02, n)
        for c in (5_000, 12_000):
            y[c - 10 : c + 10] += 5 * np.exp(-0.5 * np.linspace(-4, 4, 20) ** 2)
        mat_path = tmp_path / "pulse.mat"
        savemat(str(mat_path), {"ch1_data": y})

        pub = MatplotPublisher(
            str(mat_path),
            "ch1_data",
            sample_rate=100_000.0,
            output_base=str(tmp_path / "out" / "fig1"),
            profile_dir=str(tmp_path / "profiles"),
            preview_dir=str(tmp_path / "preview"),
        )
        files = pub.run_full_pipeline(
            interactive=False,
            assume_confirmed=True,
            user_hint="峰值精度",
            n_out=2000,
        )
        _check(files.pdf_path and Path(files.pdf_path).exists(), "PDF 未生成")
        _check(files.png_path and Path(files.png_path).exists(), "PNG 未生成")
        _check(list((tmp_path / "profiles").glob("*.yaml")), "档案 YAML 未生成")
        _check(list((tmp_path / "preview").glob("preview*.png")), "预览 PNG 未生成")

    plt.close("all")
    print("selfcheck: OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(str(exc))
        sys.exit(1)
