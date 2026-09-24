# 批次分析与汇总契约（段5.3 + 5.4）

> 定稿：#12（段5 定稿 v2）。分割由 `scripts/split_batches.py split` 强制执行；汇总由 `scripts/aggregate_analysis.py merge` 强制执行。

## batch_NNN.csv（分割输入）

- 来源：方向证据 CSV（`directions/<slug>/search/evidence.csv`，23 列）
- 每批 **50 篇**（末批可不足 50），批数 = ceil(总行数 / 50)，文件名 `batch_001.csv` 起三位序号
- 每篇只保留 3 列：**编号 / 标题 / 摘要**（防上下文爆炸；RE 序号 = 编号列原样）
- 编码 `utf-8-sig`；分割按证据 CSV 行序（coverDate 倒序）；全部分割产物覆盖证据集全部行、无重无漏

## batch_NNN.md（分批深度分析输出）

由 subagent 按 `prompts/01-batch-analysis.md` 产出，段固定：

```
## 进阶分析矩阵        → 表格：论文编号 | 关键研究方法与材料 | 核心性能指标 (量化) | 创新性与局限性分析 | 对我课题的启发点
## 综合报告            → 研究趋势总结 / 研究空白识别 / 课题提案（3-5 个，中间产物）
```

铁律：

- 矩阵**每篇必现**，论文编号与该批 CSV 一一对应、不漏不多
- 矩阵段必须是紧接 `## 进阶分析矩阵` 标题之后的 Markdown 表格，直到下一个 `## ` 标题为止（aggregate 脚本按此段切取）
- 批次自带课题提案 = 中间产物，不单独提取进 topics/

## literature_analysis.md（矩阵汇总 = 文献集）

`aggregate_analysis.py merge` 自动产出：把全部 `batch_NNN.md` 的「进阶分析矩阵」段按批次拼接：

```markdown
# 文献集进阶分析矩阵汇总（literature_analysis）

> 自动汇总自 analysis/batch_NNN.md 的进阶分析矩阵段；综合报告见各批次文件。

## batch_001（源 batch_001.md）
| 论文编号 | … |

## batch_002（源 batch_002.md）
| 论文编号 | … |
```

- 汇总只收矩阵段，**不收**综合报告段（综合报告由三策略 subagent 多文件直喂）
- `aggregate_analysis.py check` 校验：每批矩阵行集合 = 该批 CSV 编号集合（全覆盖、无外引）
