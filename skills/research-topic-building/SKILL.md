---
name: research-topic-building
description: 课题孵化：把方向 evidence.csv 分批分析，经三策略生成独立课题 MD（段5.3–5.6）；也用于从指定关键论文做单点突破。已有课题的方案深化用 research-scheme-deepening。
---

# 课题孵化

把方向证据集变为 `directions/<slug>/topics/` 课题池，自动完成段5.3–5.6。段6 默认接收全部课题，比较择优在深化之后。

资源路径相对此技能目录；命令见 [执行说明](references/execution.md)，执行时解析绝对路径。各任务原文读取自己的 prompts；生成任务的 runner/API 配置见执行说明，批次并发上限 100，按可用资源调度并保持输入隔离。

执行—检验循环中的评审子 agent（含修复后复验）默认使用轻量模型、关闭 thinking；分派前读 [统一评审配置](references/review-agents.md)。

## 主流程

### Step 0 / Step 1：输入与切分

读取 direction.md、search/evidence.csv、project_context.json；证据为空则交回 research-subtopic-retrieval。用 split_batches.py 分割，每批 ≤50 行，仅编号/标题/摘要。

**完成：** self-check 通过，批次全覆盖且无重漏；方向焦点从本项目契约提取。

### Step 2：分批分析

batch_analysis_runner.py 按 [分析提示词](prompts/01-batch-analysis.md) 每批独立生成 batch_NNN.md，只读本批 CSV。每份含进阶分析矩阵与综合报告；漏行补入矩阵，截断续写。

**完成：** 全部批次落盘且 [批次契约](references/batch-analysis-contract.md) 的 RE 覆盖检查通过。

### Step 3：矩阵汇总

aggregate_analysis.py merge 提取矩阵生成 analysis/literature_analysis.md；批次提案保留为中间产物。

**完成：** aggregate_analysis.py check 通过。

### Step 4：三策略

按 [报告映射](references/report-contracts.md) 启动 3 个独立 subagent，分别原文读取 meta/entry/innov 提示词。只输入各 batch_NNN.md 的综合报告段，多文件直喂、不合并；不输入原始摘要或矩阵汇总。

**完成：** 三报告齐备，课题数分别 6–9 / 6–9 / 4–6，立论 RE 可在方向证据集中核对。

### Step 5：逐题提取

启动一个独立 subagent，按 [提取提示词](prompts/06-topic-extraction.md) 和 [课题契约](references/topic-md-contract.md) 把每个提案全文落为独立 MD，保留五要素与策略特有字段，写 _extraction_manifest.md 对应来源报告与提案序号。

**完成：** 清单覆盖每份报告的全部提案，check_topics.py check 通过。

### Step 6：交付

汇总切分、矩阵和课题检查结果，修复失败项；输入未变的检查不重复执行。

**完成：** 每个提案恰好一个课题文件，引用和字段均通过，交付全部 topics/ 给段6。

## Step 7：单点突破旁路

用户指定关键论文时，直接读 [单篇提示词](prompts/05-single-paper.md) 与用户提供的论文内容，生成 3–5 个最小可行创新课题；按课题契约使用 `single-<NN>-<短标题>.md`，独立连续编号，并运行相同课题校验。此分支不自动运行三策略主流程。若缺合法 RE 锚点，先说明缺口并交接子问题检索，不自签 RE。
