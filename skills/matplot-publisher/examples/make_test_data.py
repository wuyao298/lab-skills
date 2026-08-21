# -*- coding: utf-8 -*-
"""生成三种形态的小型 .mat 测试数据。"""

from pathlib import Path

import numpy as np
from scipy.io import savemat

OUT = Path(__file__).resolve().parent / "data"
OUT.mkdir(exist_ok=True)
SR = 1_000_000.0
N = 200_000
t = np.arange(N) / SR


def save(name: str, y: np.ndarray) -> None:
    savemat(str(OUT / f"{name}.mat"), {"ch1_data": y, "time": t})
    print(OUT / f"{name}.mat")


# 1. pulse_dominated：三个稀疏脉冲 + 底噪。
y_pulse = np.random.default_rng(0).normal(0, 0.02, N)
for centre in (40_000, 90_000, 150_000):
    y_pulse[centre - 20 : centre + 20] += np.exp(-0.5 * np.linspace(-4, 4, 40) ** 2) * 5
save("pulse", y_pulse)

# 2. periodic：正弦 + 轻微包络。
y_sine = np.sin(2 * np.pi * 1000 * t) * (1 + 0.05 * np.sin(2 * np.pi * 10 * t))
save("sine", y_sine)

# 3. step_like / random_noise：阶跃 + 噪声平台。
y_step = np.random.default_rng(2).normal(0, 0.02, N)
y_step[100_000:] += 1.0
save("step", y_step)
