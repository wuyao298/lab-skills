---
name: research-validation
description: 完整验证：为用户选定课题或对应工作包设计 MVE、检索 ACU 实现证据并逐步骤细化（段9）。用于 LOOP A、闸门3或续跑验证链；实验执行、结果分析和论文写作不在本技能范围。
---

# 完整验证

在 `directions/<slug>/validation/` 构建研究设计→MVE→实现证据→逐步骤细化链。入口选择与闸门3由用户裁决，其余自动；段8 故事不限定验证范围。实验执行、结果分析、论文写作由后续任务承接，thesis/plan 只读。

先读 [段9 契约](references/segment9-contract.md)；写产物前读对应 [schema](references/artifact-contracts.md)。资源路径相对此技能目录，脚本与项目路径解析为绝对路径。prompts 原文交 subagent，项目输入附在末尾。模型与命令见 [执行说明](references/execution.md)。

执行—检验循环中的评审子 agent（含修复后复验）默认使用轻量模型、关闭 thinking；分派前读 [统一评审配置](references/review-agents.md)。

## 步骤

### Step 0：对象选择

列出全部课题及可用工作包映射；沿用本会话已明确的选择，否则请用户选 1..N 个对象与各自 9.7 范围，建议 A+B 全部步骤。工作包待补项须补齐或显式沿用 deepened 默认。写 selection.md 的映射、范围与用户原话。

**完成：** 至少一个合格对象获确认；不默认全量、不重新询问已确定事项。

### Step 1：研究设计

每对象先读 constraints（如有）。有工作包只写路径/版本/状态/constraints 指针；无则按 [设计提示词](prompts/01-research-design.md) 读取本对象课题、deepened、screening 生成 research_design.md。

**完成：** 每对象指针可解引用或两部分设计齐全，RE 合法、无占位符。

### Step 2：MVE

按 [MVE 提示词](prompts/02-mve.md) 读取本对象设计与允许 RE 材料，生成 mve_paths.md。

**完成：** A+B 路径齐全，每路径有量化 G/NG、低配替代、原理，两路径互补与成功/失败后动作明确。

### Step 3：全局元分析

单 subagent 按 [元分析提示词](prompts/03-meta-analysis.md) 读取全部选定对象设计与 MVE，生成 meta_analysis.md、search_strategies.md、acu_index.json。

**完成：** ACU 全局唯一、来源对象明确、实体来自方案原文，三策略 query 可运行，默认②实现优先；RE、year/doctype/来源过滤不入 query。

### Step 4：LOOP A（9.4）

必须读 [检索循环与裁决](references/loop-a.md) 后执行 prepare→原生子 agent 分级→collect；无子 agent 时顺序处理同一任务文件。每轮只查 open ACU 的 Scopus 首页 ≤25 条；完整有效结果中≥1篇高才 PASS，执行错误不计科研 FAIL。

**完成：** 全部 ACU 已结束，或连续两轮失败/第10轮仍未决的 ACU 已批量交闸门3。

### Step 5：闸门3（9.5）

按循环规则呈现改 query、合并、跳过、重写策略选项，记录用户裁决后只重跑受影响 ACU。未收到裁决保留 gate3_pending 与计数。

**完成：** 所有 ACU 为 covered / skipped / merged，才进入 9.6；未决时等待用户。

### Step 6：XE 知识库（9.6）

build_knowledge_base.py 机械收集各 covered ACU 首个 PASS 轮全部高文献，去重后生成 reproducibility_filter.md 和按对象切分的 knowledge_base/<object>.txt。

**完成：** XE 本轮唯一，已有 RE 双标注，来源 ACU 保留；不新签 RE、不改证据 CSV。

### Step 7：逐步骤细化（9.7）

按 selection 范围，以（对象×路径×步骤）独立任务读取本对象设计、MVE、知识库及原始 RE，使用 [细化提示词](prompts/06-mve-detail.md)。落分步文件、steps_manifest，再按序合并为 mve_step_detail.md。

**完成：** 每格七段齐全、XE/RE 合法、G/NG 可量化、主方案保留 MVE 战略。skipped 对应步骤仍细化，标「实现锚点缺失」与参数核实要求。

### 最终校验

check_validation.py 按契约 §13 核验，失败修复对应步骤后重验。

**完成：** 退出码0、全部选定对象/范围齐备，人工决定有真实记录；交付验证方案，不称实验已执行或主张已证实。

## 续跑入口

已有 validation/ 时，先读 [恢复规则](references/resume.md)；保留 covered/skipped/merged 和失败计数，只补未完成项。gate3_pending 优先处理；文件存在和 last_step 只是线索，以完整性及校验结果决定是否跳过。
