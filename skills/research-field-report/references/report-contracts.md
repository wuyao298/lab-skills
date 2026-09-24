# 报告契约：5 份报告的定义与生成方式（research-field-report）

> 定稿：#5（报告集与建库门）+ #7（执行修订：并行隔离、re+sh）。报告**内容要求**不在此文件——
> 每份报告的内容约束只存在于其提示词文件（`prompts/`），本文件只管编排契约（文件、输入、校验）。

## 报告集与文件命名（写死）

| 文件 | 报告 | 提示词 | 输入 |
|---|---|---|---|
| `reports/report_1_overview.md` | 领域现状与入门 | `prompts/02-report-1-overview.md` | 综述子集 |
| `reports/report_2_trends.md` | 研究趋势与选题策略 | `prompts/03-report-2-trends.md` | 综述子集 |
| `reports/report_3_gaps.md` | 综述空白点与创新机会 | `prompts/04-report-3-gaps.md` | 综述子集 |
| `reports/report_4_feasibility.md` | 研究生可行性选题方案 | `prompts/05-report-4-feasibility.md` | 综述子集 |
| `reports/field_landscape.md` | 领域态势报告（四维 + 前沿方向难度分层） | `prompts/06-report-5-landscape.md` + `prompts/07-journal-tiering.md` | 全库 metadata + JCR 表 |

- 报告统一存放于工作目录 `reports/` 子目录
- 完整标题清单 = literature_db.csv 本身（脚本产物，不算报告）

## 输入切分与隔离（防上下文污染，用户决策 2026-08-12）

- **报告 1-4** 只喂综述子集 `reports/report_input_review.csv`（re+sh，标题+摘要+年份+期刊+关键词）
- **报告 5** 只喂全库 `reports/report_input_full_metadata.csv`（739 篇级，**无摘要**）+ `references/journal-jcr-ranking.json`
- 每个报告 subagent 的提示词硬指定**只读其对应输入文件路径**（`reports/` 内），禁止读取工作目录内任何其他文件
- **产出集中**：文献库文件（`literature_db.csv` / `review_subset.csv` / `meta.json` / 报告输入）与 5 份报告同放 `reports/`（产出目录），禁止散落根目录或另开子文件夹——后续段按固定路径引用文献库

## 生成方式：并行 subagent 严格隔离

- 5 个 subagent 并行生成（1-4 各自独立，5 独立）
- 每个 subagent 只收到：自己的提示词文件 + 自己的输入文件路径；不共享上下文
- 报告 5 的「期刊选题偏好」维度：期刊分层（`prompts/07-journal-tiering.md`）+ JCR 表（`journal-jcr-ranking.json`）校核，并入领域态势报告

## 校验（自动化，不打断用户）

1. `build_database.py self-check`：21 列、meta 字段、RE 唯一、输入文件行数
2. 污染 grep 校验：全库级统计（如 total_count、年份分布峰值）只允许出现在 `field_landscape.md`，报告 1-4 出现即污染
3. 失败 → 自动重生成对应报告一次 → 仍失败 → 在交付说明标注

## 报告验收

- 默认自动通过（无人工闸门）；用户可随时抽查
- 校验记录写入工作目录交付说明（如 `delivery_notes.md`）
