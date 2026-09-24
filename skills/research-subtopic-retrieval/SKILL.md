---
name: research-subtopic-retrieval
description: 子问题检索：围绕已锁定 direction.md 拆实体、确认术语并重检索，产出方向 evidence.csv（段5.2）。用于构建方向证据集；全领域首次建库用 research-field-report，验证 ACU 的实现证据用 research-validation。
---

# 子问题检索

从已锁定方向生成 `<项目>/directions/<slug>/search/evidence.csv`（23 列）。全局 `reports/literature_db.csv` 冻结；新文献续签全局 RE，已有 EID 复用 RE。

资源路径相对此技能目录；执行 [命令](references/execution.md) 时解析绝对路径。提示词原文交给 subagent，只填输入；检索、判门、优化可并行，上限 100（受运行环境约束）。局部判门要求见 [判门协议](references/iteration-protocol.md)。

执行—检验循环中的评审子 agent（含修复后复验）默认使用轻量模型、关闭 thinking；分派前读 [统一评审配置](references/review-agents.md)。

## 步骤

### Step 0：检查输入

读取全局库、meta、方向契约与用户 idea。方向可在 `direction/direction.md` 或 `directions/<slug>/direction.md`；已有 slug 沿用，未定则纳入本次术语 pin。按 [证据契约](references/evidence-csv-contract.md) 检查/初始化 project_context。

**完成：** 输入可读，待确认项列明，编号游标不小于已签发 RE 最大值。

### Step 1：实体分解

一个 subagent 按 [实体提示词](prompts/01-entity-decomposition.md) 写 search_strategy.md：实体、语义群、A∧B∧C 核心与三个两两扩展、每组合标签（≤12 字）和完整 query。

**完成：** 检索式无占位符，全时段 TITLE-ABS-KEY，排除只用 TITLE。

### Step 2：术语 pin

一轮呈现实体、语义群、执行组合及未定 slug；默认建议核心+全部扩展。把用户确认原话与定稿清单写 pin_log.md，方向契约归位 `directions/<slug>/direction.md`。

**完成：** 用户已确认术语与执行清单，slug 已定；未收到答复则停在此处。

### Step 3a：并行检索

各组合独立按 [判门协议](references/iteration-protocol.md) 检索/判门；相关性 ≥50% 且 50 < totalResults ≤1000 才通过。失败按 [迭代提示词](prompts/02-search-iteration.md) 自动优化，共 ≤3 轮，再全量导出。三轮未过以证据薄弱标记继续导出。

**完成：** 每个组合有真实响应、判门记录和 final_raw.json，弱证据明确标记。

### Step 3b：串行入库

主 agent 按 pin 清单顺序逐组合运行 build_evidence_db.py append，显式传 project_context；弱证据传 `--weak`。共享 evidence.csv / meta / project_context 的写入必须一个完成再开始下一个，跨方向也不并发写同一游标。

**完成：** 所有非空组合已入库，复用/新签编号可追溯。空响应保留原始记录并列为未入库缺口，不伪造条目让 append 通过。

### Step 4：核验

跑 self-check，再按证据契约核对每个组合的执行/入库状态、来源 query、排序、meta 字段、EID↔RE 对应、project_context 路径/索引与全项目编号上界。脚本通过不代替这些契约项；有错修后重验，暂无法修复则明确列为交付缺口。

**完成：** 校验通过且全部组合已说明；若存在空响应等缺口，明确交付为不完整证据集。
