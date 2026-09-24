# 三策略报告契约（段5.5）

> 定稿：#12（段5 定稿 v2）。3 个并行 subagent 按孵化三策略生成，输出 `directions/<slug>/reports/`（中间产物，保留）。

| 报告文件 | 策略 | 提示词 | 课题数 | 策略特有字段 |
|---|---|---|---|---|
| `report_1_meta_analysis.md` | 3.1 元分析与最终课题孵化 | `prompts/02-meta-analysis.md` | 6-9 | 机会点类型（共识交叉点/分歧融合点/集体盲区点，各 2-3 个） |
| `report_2_feasible_entry.md` | 3.2 高可行性入门课题 | `prompts/03-feasible-entry.md` | 6-9 | 难度等级（固定【初阶/验证性】） |
| `report_3_structured_innovation.md` | 3.3 结构化创新课题 | `prompts/04-structured-innovation.md` | 4-6 | 启发路径（六路径之一）+ 核心思考过程 |

## 输入（铁律）

- 全部 `analysis/batch_NNN.md` 多文件**并行直喂、不合并**；只用各文件的「## 综合报告」段
- **不直喂原文摘要**（禁止读 batch CSV / 证据 CSV）
- 立论依据的 [REXXX] 必须来自批次报告中出现过的编号（= 证据集编号）

## 提案通用字段（每课题必备）

论文标题 / 核心科学问题 / 研究设计与技术路线 / 预期创新性与价值 / 立论依据（[REXXX]）。

## 课题总数

- meta 6-9 + entry 6-9 + innov 4-6 = **16-24 个**；3.4 旁路产物 single-<NN> 不在此序列。
