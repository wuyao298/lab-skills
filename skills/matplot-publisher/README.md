# matplot-publisher

示波器波形数据出版级科研绘图 Skill：`.mat` 波形（100M 点级）→ 六层决策 → 预览确认 → PDF + 600 DPI PNG。

## 安装

```bash
pip install -r requirements.txt
```

`tsdownsample` / `glyphx` 未安装时可运行，自动降级为保守 Min-Max 和 PNG 预览。

## CLI

```bash
# 查看变量（只读元数据）
python -m matplot_publisher.cli inspect data.mat

# 完整流程（交互式，验证层等待确认）
python -m matplot_publisher.cli plot data.mat \
  --var ch1_data --sample-rate 1000000 \
  --points 100000 --out output/fig1

# 无人值守（测试用；交互时仍默认强制确认）
python -m matplot_publisher.cli plot data.mat --var ch1_data --yes
```

## Python API

```python
from matplot_publisher import MatplotPublisher

pub = MatplotPublisher("data.mat", "ch1_data", sample_rate=1e6, output_base="output/fig1")
files = pub.run_full_pipeline(
    interactive=True,
    user_hint="峰值精度",
    n_out=100_000,
)
print(files.pdf_path, files.png_path)
```

## 自检

```bash
python scripts/selfcheck.py
# selfcheck: OK
```

## 目录

- `matplot_publisher/`：六层运行库
- `references/`：决策规则与样式契约
- `profiles/`：成功方案归档
- `tests/`：三种形态波形测试
- `examples/make_test_data.py`：合成测试数据
