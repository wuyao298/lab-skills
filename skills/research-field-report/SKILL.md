---
name: research-field-report
description: 领域建库：从研究领域关键词建立 Scopus 文献库并生成 5 份领域报告（科研工作流第一步）。用于尚未建库的领域调研；已有锁定方向的子问题补检索用 research-subtopic-retrieval。
---

# 领域建库与报告

交付 `<项目>/reports/` 内的 21 列 `literature_db.csv`、`meta.json` 和 5 份报告；建库门三轮未过时由用户裁决。

`scripts/`、`prompts/`、`references/` 均相对此技能目录；执行命令时把脚本与项目路径解析为绝对路径。提示词原文交给对应 subagent，只填项目输入，不改写内容约束。

执行—检验循环中的评审子 agent（含修复后复验）默认使用轻量模型、关闭 thinking；分派前读 [统一评审配置](references/review-agents.md)。

## 步骤

### Step 0 / Step 1：领域与检索式

收集领域名、命名变体、语义群、排除词；缺项按 [检索提示词](prompts/01-search-strategy.md) 生成候选。生成全时段 Scopus 检索式，排除词只用 TITLE，不加 year/doctype、不换源。

**完成：** 四类参数和完整可运行 query 齐备。

### Step 2：建库门

按 [判门协议](references/iteration-protocol.md) 取首页 25 条，由独立 subagent 判前 20 篇相关性；默认 totalResults ≥500 且相关 ≥50%。未过只调语义群/变体/排除词，共 ≤3 轮。

**完成：** PASS，或用户明确接受当前库。第三轮仍未过先呈现接受/调整/终止选项；等待决定，终止则结束本次运行。

### Step 3 / Step 4：全量导出与建库

按 [命令与文件布局](references/execution.md) 导出、去重、build；先读 [数据库 schema](references/database-schema.md)。RE 从 `[RE001]` 起，综述为 re+sh，编码 utf-8-sig。

**完成：** 导出数量核对通过，literature_db.csv、review_subset.csv、meta.json 已生成，表头与数量符合 schema。完整 self-check 在下一步切分后执行。

### Step 5：输入切分

用 split 生成 `reports/report_input_review.csv` 与 `reports/report_input_full_metadata.csv`。

**完成：** 行数分别等于 meta 的 review_count / total_count，全库输入无摘要，`build_database.py self-check` 通过；该检查依赖两个切分文件，不能提前作为建库完成门。

### Step 6：报告 1–4

按 [报告映射与隔离规则](references/report-contracts.md) 并行启动 4 个 subagent，每个只读自己的原文提示词和综述输入。资源不足时分批调度，保持输入隔离。

**完成：** 四个指定报告文件齐备。

### Step 7：领域态势

独立 subagent 读取 [态势提示词](prompts/06-report-5-landscape.md)、[期刊分层提示词](prompts/07-journal-tiering.md)、全库无摘要输入与 [JCR 表](references/journal-jcr-ranking.json)。

**完成：** `reports/field_landscape.md` 落盘。

### Step 8：校验交付

复核数据库，检查报告 1–4 是否混入全库统计；按报告契约检查内容。失败的报告重生成一次，残留问题记入项目根 `delivery_notes.md`。

**完成：** 5 份报告、库与 meta 齐备；交付说明注明通过项与未解决项，带问题交付不称全部通过。

## 按需读取

- API 参数或密钥注入：读 [Scopus API](references/scopus-api.md)；密钥仅走环境变量/外置 .env，不进入产物。
- 更换领域时需要示例：读 [MFC 检索示例](references/search-example-mfc.md)，只借结构，替换领域参数。
