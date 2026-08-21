# ieee_custom 样式契约

数值唯一源：`matplot_publisher/style.py`。selfcheck 会校验下列契约。

| 元素 | 契约 |
|---|---|
| 刻度方向 | `xtick.direction` / `ytick.direction` = `in` |
| 轴脊线 | **四条全部可见**（2025-11 确认需求）；上/右脊线无刻度、无标签 |
| 字体 | sans-serif：Arial → Helvetica → DejaVu Sans |
| 字号 | 轴标签 14pt；刻度标签 11pt；图例 10pt |
| 颜色循环 | `#E64B35, #4DBBD5, #0072B5, #E18727, #20854E`（SSCI 色盲友好） |
| 坐标范围 | `axes.xmargin=0`、`axes.ymargin=0`，autoscale 贴数据边界；**留白只走 y 轴**（`ax.margins(x=0, y=0.05)`），x 轴贴边 |
| 网格 | 仅 Y 轴虚线网格（`axes.grid.axis=y`，`grid.linestyle=--`） |
| 图例 | 图外右侧；`frameon=False`；因 `bbox_to_anchor` 不是 rcParam，用 `style.place_legend_outside(ax)` |
| 图尺寸 / 导出 | figsize 8×6 in（单轴）；波形 2×2 模板默认 14×10 in；PDF 矢量 + PNG 600 DPI；`savefig.bbox=tight` |
| 多子图 | 波形主图为单轴；需要多面板时用 `compose_grid()`（通用 mosaic）或 `compose_full_zoom_grid()`（波形专用 2×2：全波形 + 脉冲放大） |

## 强制调用顺序

```python
from matplot_publisher.style import apply_ieee_custom, SavedFigure, place_legend_outside

apply_ieee_custom()          # 必须在绘图前
fig, ax = plt.subplots()
ax.plot(x, y)
place_legend_outside(ax)     # 有图例时
with SavedFigure("fig1", formats=["pdf", "png"]):
    fig.canvas.draw()
```

## 波形专用 2×2 模板（脉冲 / 阶跃类波形推荐）

```python
from matplot_publisher import (
    apply_ieee_custom,
    compose_full_zoom_grid,
    compute_pulse_zoom_window,
)
import h5py

apply_ieee_custom()
fig, axs = compose_full_zoom_grid(figsize=(14, 10), top_label="Voltage", top_unit="V",
                                    bottom_label="Current", bottom_unit="A",
                                    time_label="Time (s)")
# axs["full_top"]    左上  完整波形（变量 A）
# axs["zoom_top"]    右上  脉冲放大（变量 A）
# axs["full_bottom"] 左下  完整波形（变量 B）
# axs["zoom_bottom"] 右下  脉冲放大（变量 B）

# 不对称缩放窗口：脉冲前少留白，脉冲后多留白（展示衰减振荡尾部）
peak_idx = 5_372_744
N = 100_000_000
left, right = compute_pulse_zoom_window(peak_idx, N, pre_pad=300, post_pad=1500)

f = h5py.File("pp1_0001.mat", "r")
axs["full_top"].plot(t_full,    f["voltage"][:, 0][::5000],   color="#E64B35")
axs["zoom_top"].plot(t_zoom,    f["voltage"][left:right, 0],   color="#E64B35")
axs["full_bottom"].plot(t_full, f["i"][:, 0][::5000],          color="#4DBBD5")
axs["zoom_bottom"].plot(t_zoom, f["i"][left:right, 0],         color="#4DBBD5")
fig.savefig("output/fig1.pdf"); fig.savefig("output/fig1.png", dpi=600)
```

返回的 axes 已自动应用：
- 四条轴脊线全部可见
- 仅左/下轴带刻度与标签
- y 轴 5% 留白，x 轴贴边
- 列内共享 x 轴（`sharex='col'`）
- 上行 x 轴刻度数字隐藏（与下行共享刻度，避免重复）

`compute_pulse_zoom_window()` 默认参数 `pre_pad=300, post_pad=1500`（约 90 µs / 450 µs @ 3.33 MSa/s），
可根据脉冲宽度与振荡持续时间调整。

## 自检

```bash
python scripts/selfcheck.py
```

必须输出 `selfcheck: OK`。
