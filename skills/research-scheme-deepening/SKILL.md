---
name: research-scheme-deepening
description: 方案深化：对已有课题池筛选强相关文献，生成每课题 screening.md 与 deepened.md（段6）。用于细化已有研究方案；新课题孵化用 research-topic-building，MVE 与实现证据验证用 research-validation。
---

# 方案前置深化

对全部课题生成 `topics/<课题>/screening.md` 与 `deepened.md`。流程自动完成，之后由用户阅读择优；MVE、新检索与验证归 research-validation。

资源路径相对此技能目录，项目路径解析为绝对路径；[执行说明](references/execution.md) 列出 runner 命令与重跑选项。提示词保持原文，只替换项目占位符。生成任务的 runner/API 配置见执行说明；独立任务并发上限 100，受可用运行环境限制。

执行—检验循环中的评审子 agent（含修复后复验）默认使用轻量模型、关闭 thinking；分派前读 [统一评审配置](references/review-agents.md)。

## 步骤

### Step 0：输入

读取 topics/ 全部课题 MD、search/evidence.csv 与 analysis/batch_NNN.csv；课题已通过上游 check_topics，批次为编号/标题/摘要三列，每批 ≤50 篇。

**完成：** 课题数 N≥1、批数 B 已知，输入齐备；缺项交回对应上游技能。

### Step 1：分批筛选

运行 screen；每个（课题×批次）独立读取 [筛选提示词](prompts/01-screening.md)、本课题 MD 与本批 CSV。按 [筛选契约](references/screening-contract.md) 输出 screening_batches/batch_NNN.md，RE 仅来自本批；非法编号修复 ≤2 轮，截断续写 ≤3 轮。

**完成：** N×B 个批次结果齐备，失败任务明确列出。

### Step 2 / Step 3：合并与检查

运行 merge，再 check；检查批次一一对应、无非法 RE/重复行/⚠️，合并表与批次表行集一致。

**完成：** 每课题 screening.md 校验通过才进入深化。

### Step 4：深化

运行 deepen；每课题独立读取 [深化提示词](prompts/02-deepening.md)、该课题 MD 与 screening.md，产出进化版完整方案。

**完成：** 每课题 deepened.md 已生成；按 [深化契约](references/deepened-contract.md) 核对五要素、修改摘要、加粗修改，以及所有 RE 均在该课题 screening.md 内。再次运行 check；脚本未覆盖的契约项由 agent 核对，不能仅凭退出码通过认定齐备。

### Step 5：交付择优

返回全部 screening.md / deepened.md 路径与校验结果，保留批次中间产物。用户可比较择优或要求重生成具体课题。

**完成：** 全部课题交付或明确列出失败课题；用户尚未择优时记录待选择，不冒充已选定。
