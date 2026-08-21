# -*- coding: utf-8 -*-
"""API 使用示例：先生成合成 .mat，再走完整六层流程。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 若 examples/data 不存在，先合成测试数据。
if not (Path(__file__).parent / "data" / "pulse.mat").exists():
    subprocess.run([sys.executable, str(Path(__file__).parent / "make_test_data.py")], check=True)

from matplot_publisher import MatplotPublisher  # noqa: E402

publisher = MatplotPublisher(
    file_path=str(Path(__file__).parent / "data" / "pulse.mat"),
    variable_name="ch1_data",
    x_variable="time",
    output_base=str(Path(__file__).parent / "output" / "fig1"),
    profile_dir=str(Path(__file__).parent / "profiles"),
    preview_dir=str(Path(__file__).parent / "preview"),
)

files = publisher.run_full_pipeline(
    interactive=False,       # 实际使用请设 True，验证层等待人工确认
    assume_confirmed=True,
    user_hint="峰值精度",
    n_out=10_000,
)

print(files.pdf_path)
print(files.png_path)
