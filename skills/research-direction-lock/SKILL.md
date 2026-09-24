---
name: research-direction-lock
description: 方向锁定：从已有 5 份领域报告经讨论选定一个研究方向，形成 direction.md（段5.1）。用于从报告选方向或收敛方向边界；课题孵化用 research-topic-building，新检索用 research-subtopic-retrieval。
---

# 方向锁定

用第一步报告讨论一个方向，交付 `<项目>/direction/direction.md`。证据只来自既有库；新检索交给 research-subtopic-retrieval。用户决定方向，报告提供证据。

资源路径相对此技能目录，产物路径相对项目根；调用脚本时解析为绝对路径。

执行—检验循环中的评审子 agent（含修复后复验）默认使用轻量模型、关闭 thinking；分派前读 [统一评审配置](references/review-agents.md)。

## 步骤

### Step 0：检查输入

`reports/` 内须有 report_1_overview、report_2_trends、report_3_gaps、report_4_feasibility、field_landscape 五份 `.md`，以及 literature_db.csv、meta.json。缺项列出并交回 research-field-report。

**完成：** 七个输入均可读。

### Step 1：建讨论桌

一个 subagent 按 [建桌提示词](prompts/01-board-construction.md) 读取五报告与文献库，生成 `direction/discussion_board.md`。候选来自既有推荐，初始雾区与否因区为空。

**完成：** 每票有来源、难度、模糊度及用 `scripts/evidence.py` 库内复核的 RE 锚点。

### Step 2：讨论

每轮先读 [讨论规则](references/discussion-rules.md) 与 [前沿重算提示词](prompts/02-frontier-recompute.md)，再读讨论桌和历史轮次，提编号问题与推荐答案。按用户原话更新票、雾区、否因和 `direction/rounds/round_N.md`；新场景先在既有库补证据。

**完成：** 用户锁定或显式延期；≤5 轮后仍未锁定则呈现收口/延期选项。延期保留讨论状态并结束，不进入契约定稿。

### Step 3：起草与确认

按 [契约提示词](prompts/03-contract-draft.md) 和 [六字段 schema](references/direction-contract.md) 写 direction.md，用户逐句确认；未否的其他候选降为支撑层，术语冲突先 pin。

**完成：** 六字段齐备，用户已确认锁定文本。

### Step 4：核验

逐个在 `<项目>/reports/literature_db.csv` 按编号精确匹配契约引用，并核对对应题录和摘要；检查轮次编号连续，有错补正后复核。`scripts/evidence.py` 仅支持关键词检索，编号校验直接读取 CSV，不给它传 `--re`。

**完成：** 契约、讨论桌、连续轮次记录齐备，RE 全部命中，返回方向契约路径。

关键词补证据使用 `scripts/evidence.py <关键词…> --db <项目>/reports/literature_db.csv`。讨论难度只展示、不作后勤筛选；支撑面在锁定后显式保留材料和其他工况证据，避免下游过度收窄。
