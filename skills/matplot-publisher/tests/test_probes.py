# -*- coding: utf-8 -*-
"""三种形态：感知层探针。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matplot_publisher.io import MatReader
from matplot_publisher.perception import perceive


def _profile(path):
    with MatReader(path, "ch1_data", x_variable="time") as reader:
        return perceive(reader, sample_ratio=0.02)


def test_pulse_dominated(pulse_mat):
    profile = _profile(pulse_mat)
    assert profile.morphology == "pulse_dominated"
    assert profile.n_sampled <= profile.n_points
    assert profile.peak_indices


def test_periodic(sine_mat):
    profile = _profile(sine_mat)
    assert profile.morphology in ("periodic", "pulse_dominated", "mixed")


def test_step_like(step_mat):
    profile = _profile(step_mat)
    assert profile.morphology in ("step_like", "mixed", "pulse_dominated")
    assert profile.n_points == 50_000
