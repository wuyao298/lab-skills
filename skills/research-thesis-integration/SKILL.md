---
name: research-thesis-integration
description: 论文故事整合：将全部已深化课题经用户裁决合并为博士论文总标题、核心论点、故事与章级结构（段8）。用于跨课题整合研究主线；单课题深化用 research-scheme-deepening，验证方案用 research-validation。
---

# 论文故事整合

把全部已深化课题的合理元素合并成博士论文故事，交付 `directions/<slug>/thesis/` 下 argument、story、structure 三产物与 cards/、rounds/。段8 不替代段9 验证；开题报告是另行约定的可选拓展。

资源路径相对此技能目录，命令见 [执行说明](references/execution.md)，解析绝对路径执行。卡片生成的 runner/API 配置见执行说明，并发上限 100，受可用资源限制；单次调用只读一个课题。

执行—检验循环中的评审子 agent（含修复后复验）默认使用轻量模型、关闭 thinking；分派前读 [统一评审配置](references/review-agents.md)。

## 步骤

### Step 0：验证输入

thesis_runner.py validate 检查全部课题 MD、每课题 deepened.md / screening.md 与方向 evidence.csv。

**完成：** 输入齐备且课题数 N≥1；缺项交回 research-topic-building 或 research-scheme-deepening。

### Step 1：提取卡片

thesis_runner.py cards 原文读取 [卡片提示词](prompts/01-element-cards.md) 与该课题两文件，生成 cards/<课题>.md。非法 RE 修复 ≤2 轮，截断续写 ≤3 轮。

**完成：** N 份卡片齐备，四段完整，RE 仅来自各自 screening.md，无 ⚠️。

### Step 2：减雾讨论

每轮读 [讨论规则](references/discussion-rules.md)、[提案提示词](prompts/02-proposal-round.md)、全部卡片和历史 rounds；提出 3–5 个编号问题及推荐答案。用户裁决后写 round_N.md（原话、判读、动作、雾区快照），仅对雾区涉及课题增量提取卡片。RE 用 evidence.py 在方向库实测。

**完成：** 雾区清空且合并与主线由用户确定。连续两轮未减少则请用户收口或延期；延期保存状态，不推进定稿。

### Step 3：总标题与核心论点

按 [argument 提示词](prompts/03-argument-draft.md) 写 thesis_argument.md，至少两个标题候选，由用户选定总标题与主线并记录。

**完成：** 文件含用户选定版。

### Step 4：故事与结构

按 [story 提示词](prompts/04-story-draft.md)、[structure 提示词](prompts/05-structure-draft.md) 依次写 thesis_story.md 与 thesis_structure.md，保留课题/实验映射、章间逻辑与 RE 溯源；交用户终稿审阅。

**完成：** 三产物经用户审阅通过；不满意则重生成受影响内容。

### Step 5：核验交付

跑 thesis_runner.py check 并按 [产物契约](references/thesis-contract.md) 核对：卡片与课题 1:1、引用合法、三文件字段齐备、rounds 连续、雾区快照齐备且终态清空；失败修后复验。

**完成：** 校验通过并返回三产物路径；讨论记录中的人工决定仍须真实存在，脚本通过不能代替确认。
