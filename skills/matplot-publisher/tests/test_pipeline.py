# -*- coding: utf-8 -*-
"""端到端：预览 → 确认 → 出图 → 固化。"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
from matplot_publisher import MatplotPublisher


def test_full_pipeline(pulse_mat, tmp_path):
    pub = MatplotPublisher(
        pulse_mat,
        "ch1_data",
        x_variable="time",
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
    assert files.pdf_path and Path(files.pdf_path).exists()
    assert files.png_path and Path(files.png_path).exists()
    assert list((tmp_path / "profiles").glob("*.yaml"))
    plt.close("all")
