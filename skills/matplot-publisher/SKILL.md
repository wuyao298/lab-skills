---
name: matplot-publisher
description: 示波器波形数据出版级科研绘图：分析 .mat 波形（100M 点级）→ 六层决策（感知/理解/决策/验证/执行/固化）→ 预览确认 → PDF+600DPI PNG，全程 ieee_custom 样式。触发：示波器数据、.mat 波形、100M 点降采样、脉冲/过冲/振铃保真、出版级图表、matplot-publisher。
---

# matplot-publisher

把 `.mat` 示波器波形变成出版级 PDF + 600 DPI PNG。数据可能到 100M 点：**探针只抽样，处理只分块，正式出图前必须预览并等用户确认**。

## 铁律

1. 任何正式出图前：生成预览 + 保真度报告 → 等用户 `确认`。
2. 任何图表：调用 `matplot_publisher.style.apply_ieee_custom()`。
3. 任何不确定（用户意图、参数、区域边界）：**先问**，不猜。

## 文件地图

| 层 / 职责 | 代码 |
|---|---|
| 运行库根 | `matplot_publisher/` |
| 数据分批读取 | `io.py` |
| ① 感知 | `perception.py` |
| ② 理解 | `interpretation.py` |
| ③ 决策 | `decision.py` |
| ④ 验证 | `validation.py` |
| ⑤ 执行 | `execution.py` |
| ⑥ 固化 | `crystallization.py` + `profile_manager.py` |
| 编排 / CLI | `pipeline.py` + `cli.py` |
| ieee_custom 样式 | `style.py` |
| 多子图排版 | `compose.py`（`compose_grid` 通用 mosaic + `compose_full_zoom_grid` 波形专用 2×2 模板） |

决策规则表、命令系统在 `references/decision-rules.md`；样式契约在 `references/style-spec.md`。

## 步骤

### Step 1：检查输入

```bash
cd <skill 根目录>
python -m matplot_publisher.cli inspect data.mat
```

拿到变量名（如 `ch1_data`）、shape、dtype；确认 `--x` 或 `--sample-rate` 至少一个，否则向用户询问时间轴来源。

**完成**：变量名、时间轴来源、输出基名、目标点数 `n_out` 都已知。

### Step 2：感知层

运行或调用：

```bash
python -m matplot_publisher.cli plot data.mat --var ch1_data --sample-rate 1000000 --points 100000 --out output/fig1
```

感知层会输出《数据画像》：形态分类、密集区间、能量分布、异常点、缺失段。

**完成**：终端出现 `📊 数据画像`；探针只做「均匀抽样 + 分块脉冲补充扫描」，`n_sampled` ≤ `max_samples + 1_000_000` 且远小于总点数（不满足说明误用一次性全量加载，停止修正）。

### Step 3：理解层

输出《关注度权重表》。权重规则和用户意图关键词见 `references/decision-rules.md`。

若形态为 `pulse_dominated` / `mixed` 且用户未给 `--focus`，**必须**先问：

> 您更关注 A. 峰值精度，还是 B. 整体波形形态？

**完成**：每个数据区间都有 0~10 权重；用户意图已写入 `--focus` 或通过询问确定。

### Step 4：决策层

输出《执行方案说明书》：逐区域策略（lossless / m4 / minmax / boundary）、预算分配、`chunk_size`。预算规则见 `references/decision-rules.md`。

**完成**：方案中权重 ≥9 的区域全部 `strategy=lossless`；压缩区域全部指定分块算法与点数。

### Step 5：验证与确认层（★强制等待）

生成 150 DPI PNG 预览（可选 glyphx HTML），计算峰值偏差 / 斜率偏差 / 包络重合度 / 压缩率。

**通过标准**：峰值偏差 <1%，斜率偏差 <5%，包络重合度 >99%。

然后输出报告并等待：

```
❓ 请确认：输入 `确认` 进入正式出图；或 adjust n_out=150000 / adjust threshold=4 / preserve [a:b] / export_config
```

用户修改 → 回到 Step 4 重新决策 → 重新验证 → 再次等待确认。命令完整语义见 `references/decision-rules.md`。

**完成**：用户明确输入 `确认`（或 `/skip_validation` 显式跳过确认），`ValidationResult.confirmed=True`。

### Step 6：执行层

对确认后的方案分批降采样 → `apply_ieee_custom()` → `SavedFigure` 导出 PDF + 600 DPI PNG。样式细节见 `references/style-spec.md`。

**完成**：`output/fig1.pdf` 和 `output/fig1.png` 均存在；PNG dpi=600；图片四条轴脊线均可见、上/右轴无刻度、刻度向内。

### Step 6.5：波形专用 2×2 模板（可选）

若波形为「双变量脉冲」（如电压+电流、电压+应力），且需同时呈现完整时序概览与单脉冲细节，可调用 `compose_full_zoom_grid()` + `compute_pulse_zoom_window()`：

```python
from matplot_publisher import apply_ieee_custom, compose_full_zoom_grid, compute_pulse_zoom_window
import h5py

apply_ieee_custom()
fig, axs = compose_full_zoom_grid(figsize=(14, 10), top_label="Voltage", top_unit="V",
                                    bottom_label="Current", bottom_unit="A",
                                    time_label="Time (s)")
# axs["full_top"] / "zoom_top" / "full_bottom" / "zoom_bottom"

# 不对称缩放窗口：脉冲前少留白，脉冲后多留白（充分展示衰减振荡）
peak_idx, N = 5_372_744, 100_000_000
left, right = compute_pulse_zoom_window(peak_idx, N, pre_pad=300, post_pad=1500)

f = h5py.File("pp1_0001.mat", "r")
axs["full_top"].plot(t_full,    f["voltage"][:, 0][::5000],   color="#E64B35")
axs["zoom_top"].plot(t_zoom,    f["voltage"][left:right, 0],   color="#E64B35")
axs["full_bottom"].plot(t_full, f["i"][:, 0][::5000],          color="#4DBBD5")
axs["zoom_bottom"].plot(t_zoom, f["i"][left:right, 0],         color="#4DBBD5")
fig.savefig("output/fig1.pdf"); fig.savefig("output/fig1.png", dpi=600)
```

返回的 axes 已自动应用：四条轴脊线可见、仅左/下带刻度、y 轴 5% 留白、x 轴贴边、列内共享 x 轴。
`compute_pulse_zoom_window()` 默认 `pre_pad=300, post_pad=1500`，对应 3.33 MSa/s 下约 90 µs / 450 µs，可按脉冲宽度与振荡持续时间调整。

### Step 7：固化层

成功方案写入 `profiles/<morphology>_<date>_vX.Y.yaml`，输出 `profile_id`。

下次同类数据，感知后自动匹配（匹配度 ≥0.8 才提示）。用户同意 → 加载档案跳过 ③④ 直接执行；用户拒绝 → 走完整流程。

**完成**：`profile_id` 已打印，YAML 落盘，且 `python scripts/selfcheck.py` 输出 `selfcheck: OK`。

## 快速命令

```bash
python -m matplot_publisher.cli inspect data.mat
python -m matplot_publisher.cli plot data.mat --var ch1_data --sample-rate 1e6 --points 100000 --out output/fig1
python scripts/selfcheck.py
```

无 tsdownsample / glyphx 时自动降级为保守 Min-Max 和纯 PNG 预览；安装依赖见 `requirements.txt`。
