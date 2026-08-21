# -*- coding: utf-8 -*-
"""测试数据：三种形态的小型 .mat。"""

from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

SR = 100_000.0
N = 50_000


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("matdata")
    t = np.arange(N) / SR

    rng = np.random.default_rng(0)
    pulse = rng.normal(0, 0.02, N)
    for c in (10_000, 25_000, 40_000):
        pulse[c - 10 : c + 10] += 5 * np.exp(-0.5 * np.linspace(-4, 4, 20) ** 2)

    sine = np.sin(2 * np.pi * 100 * t)
    step = rng.normal(0, 0.02, N)
    step[N // 2 :] += 1.0

    for name, y in (("pulse", pulse), ("sine", sine), ("step", step)):
        savemat(str(d / f"{name}.mat"), {"ch1_data": y, "time": t})
    return d


@pytest.fixture()
def pulse_mat(data_dir):
    return str(Path(data_dir) / "pulse.mat")


@pytest.fixture()
def sine_mat(data_dir):
    return str(Path(data_dir) / "sine.mat")


@pytest.fixture()
def step_mat(data_dir):
    return str(Path(data_dir) / "step.mat")
