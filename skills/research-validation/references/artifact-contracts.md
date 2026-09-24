# 段9 产物契约（schema）

校验脚本 `scripts/check_validation.py` 按本文件检查。JSON 一律 UTF-8；CSV 用 `utf-8-sig`。

## selection.md

```markdown
# 验证对象选择（Step 0）

> 用户原话：<用户关于对象与 9.7 范围的原话>

## 对象清单

- **对象 1**：<object-slug> ｜ 课题：topics/<object-slug>.md ｜ 研究设计来源：工作包 <path> / 自生成 ep1
  - 9.7 细化范围：路径 A 全部步骤 + 路径 B 全部步骤（或列出 <path>_step_NN 白名单）
  - 工作包待补处理：<补齐内容，或「全部【待补】沿用 deepened.md 默认」>
```

- 对象 slug 必须与 `topics/<slug>.md` 一一对应；≥1 个对象；范围显式；用户原话在案。
- 可分批追加（「追加批次 N」小节）；已验对象不重跑。

## metadata.json（运行时状态）

```json
{
  "skill": "research-validation",
  "contract": "docs/research-skill-design/04-workflow-v1-segment9-validation.md",
  "project": "<工作目录相对/绝对路径>",
  "slug": "<direction slug>",
  "objects": ["<object-slug>"],
  "steps_completed": ["step0", "step1", "step2", "step3"],
  "last_step": "step4",
  "loop_round": 1,
  "gate3_pending": false
}
```

- `last_step` ∈ `step0..step7,check`；续跑从 `last_step` 开始。
- 闸门3 未决时 `gate3_pending=true`，禁止进入 9.6。

## research_design.md

- 自生成：ep1 两部分结构（`第一部分 研究基本盘——问题与假说` + `第二部分 核心实验方案——从设计到执行`），无表格（提示词原约束），每步 [REXXX] 溯源。
- 工作包指针：只写指针（工作包路径 + 版本/状态 + constraints 路径），不复制正文。

## mve_paths.md

必须含：
- `路径 A：问题-假设验证路径` + `路径 B：方案-假设验证路径`
- 每路径七项：核心假设识别 / 最小可行实验设计 / 关键成功/失败指标（G/NG 可量化）/ 所需最简资源 / 备选及简化方案（≥1 低配替代）/ 路径原理解释（实验目标与步骤写在 MVE 设计里）
- 末尾：两路径互补说明 + 成功后/失败后行动路径。

## meta_analysis.md

- 阶段按时间顺序；每阶段 1..N 个 ACU；`ACU-<NNN>` 全局唯一编号（三位零填充）。
- 每 ACU 一行/一段必须含 `来源对象：<object-slug>`（多对象用顿号/逗号分隔）。
- 锚点实体必须可在方案原文定位（校验时按锚点实体关键词在 research_design/mve_paths 里 grep）。
- 任务依赖图 + 并行可能 + 关键路径。

## search_strategies.md

每个 ACU 一段，必须含：

```markdown
## ACU-001 <ACU 名称>

- 锚点实体：...
- 关键词模块定义：模块1...（含扩展语义群与截词符）
- 组合策略菜单：
  - 策略一：精准打击 检索式：`TITLE-ABS-KEY(...)`
  - 策略二：实现优先（默认起手） 检索式：`TITLE-ABS-KEY(...)`
  - 策略三：双核探索 检索式：`TITLE-ABS-KEY(...)`
```

- 默认起手 = 策略二；三策略都可运行。
- 检索式校验：完整可运行、无占位符（无 `TODO`/`XXX`/`...`/`<...>`）、**无 `[RE` 编号、无 year/doctype/来源库过滤**。

## acu_index.json（运行时机器索引）

```json
{
  "ACU-001": {
    "name": "<ACU 名称>",
    "stage": "<阶段名称>",
    "source_objects": ["<object-slug>"],
    "query": "<策略二检索式原文>",
    "default_strategy": "②实现优先"
  }
}
```

由 9.3 编排器从 `search_strategies.md` 生成；LOOP A、9.6、check 都读它。查询必须是三策略中的一条（默认策略二）。

## scopus_runs/<ACU>/round_N/

- `results_raw.json`：Scopus 真实响应（`search-results.entry` 长度 ≤25；totalResults=0 也落盘）。
- `verdict.md`：ep4-A 输出。表头四列：`论文标识 | 级别 | 可复现的关键步骤与参数 | 可直接整合至我方案的具体步骤`；级别 ∈ {高, 中, 建议排除}。论文标识 = `EID:<eid>` 或 Scopus 条目序号（1..25），必须能反查到本轮 JSON 条目。

## 原生 agent 任务文件（新增运行协议）

每个非零结果的 `scopus_runs/<ACU>/round_N/` 额外含：

- `task.json`：version、task_id、acu、round、source_objects、entries、prompt_file、result_file、raw_sha；输入绑定当前 query、全部关联 MVE、原文 prompt 和真实 raw 内容。
- `verdict_prompt.md`：完整 ep4-A 原文 + 本任务输入 + JSON 输出适配。
- `verdict_result.json`：worker 唯一可写的交付文件。示例：

```json
{"task_id":"<复制task.json中的值>","verdict":[
  {"paper_id":"EID:2-s2.0-123","level":"高","key_steps":"H2摘要依据与参数","integration":"对象/路径/步骤"}
]}
```

verdict 必须逐篇覆盖全部输入，无重复和额外论文；paper_id 是输入 EID 或1-based序号；level 精确等于高/中/建议排除；其余两字段非空并提供依据。无需凑齐三个级别。收取程序拒绝未知 ID，不做按行位置改 ID 的修复。分级表由程序生成，方便沿用现有9.6/check。

收取时对同一份结果字节解析与计算摘要，再写 `verdict_result.accepted.json` 接受快照。worker 后续写入不改变已接受结果；缺失或损坏的 verdict.md 可以从快照机械重建，无需重调 agent。原始检索与接受快照被改时停止并报告，不冒用新文件。

`loop_a/active.json` 保存当轮输入摘要、任务状态和轮初状态快照；`round_NN.json` 保存完成轮审计。`transaction.json` 只在提交过程中存在；下一次写命令先恢复它。`.loop_a.lock` 文件存在不代表仍锁定，实际锁由操作系统随进程释放。

部分结果收取时该 ACU 状态即可更新；全局 loop_state.round 仍是上一完整轮，直到当轮所有任务有有效结果才推进，Gate3 也在整轮收齐后批量开放。执行错误不生成 fail_rounds。最终交付前须先收齐活动轮；不在部分收取状态下运行最终 check。任务完成只能以校验通过为准，不能以 worker 自报成功或文件存在为准。

## loop_state.json

```json
{
  "version": 1,
  "round": 2,
  "max_rounds": 10,
  "acus": {
    "ACU-001": {
      "query": "<当前 query>",
      "status": "open|covered|skipped|merged",
      "merged_into": null,
      "pass_round": 1,
      "consecutive_fails": 0,
      "last_total_results": 42
    }
  },
  "skipped_acus": ["ACU-007"],
  "gate_history": [
    {"round": 2, "triggered_acus": ["ACU-003"], "decision_file": "gate_3_decisions.md"}
  ]
}
```

- `status=covered` 必须 `pass_round ≥ 1`；`status=skipped` 必须出现在 `skipped_acus`；`status=merged` 必须 `merged_into` 非空。
- 连续失败计数只由闸门3 决议 a/b/d 清零；续跑不清零。

## per_ACU_summary.json

```json
{
  "ACU-001": {
    "source_objects": ["<object-slug>"],
    "rounds_run": 2,
    "fail_rounds": [1, 2],
    "consecutive_fails": 2,
    "pass_round": 1,
    "status": "covered",
    "merged_into": null,
    "queries": ["<round1 query>", "<round2 query>"]
  }
}
```

与 `loop_state.json` 逐 ACU 一致。

## retrieval_report.md

LOOP A 总结：每轮每 ACU 检索 totalResults、PASS/FAIL、verdict 摘要、出循环原因、剩余 open ACU 的去向（covered/skipped/merged/gate3）。

## gate_3_decisions.md

- 触发 ACU 清单 + 每 ACU 四选项材料（当前 query、totalResults、前 20 条标题/摘要、verdict 摘要、建议新 query+理由、合并候选、跳过风险、重写策略建议）。
- 逐 ACU 用户决策与**用户原话**；a/b/d 清计数，c 标 skipped（不删 MVE 步骤）。

## reproducibility_filter.md

表头：`文献编号 | 来源 ACU | 可复现的关键步骤与参数 | 可直接整合至我方案的具体步骤`

- `文献编号` = `XE001`（本验证轮本地编号，全局唯一），已 RE 文献同时标 `[REXXX]`（如 `XE001 [RE257]`）。
- `来源 ACU` = 逗号分隔全部命中 ACU（如 `ACU-003, ACU-012`）。
- 行集 = 各 covered ACU 首个 PASS 轮 verdict 中全部「高」文献，按 EID → DOI → 标题去重后并集；中/排除一律不进入。

## knowledge_base/<object>.txt

每对象一个文件，9.7 只读本对象文件。条目：

```text
=== XE001 [RE257]（如已有 RE） ===
标题：...
EID：2-s2.0-...
DOI：...（可空）
年份：... ｜ 期刊：...
摘要：...
来源 ACU：ACU-001, ACU-003
可复现的关键步骤与参数：...
可直接整合至我方案的具体步骤：...
```

- 只含 reproducibility_filter.md 的高文献；一个对象 = 该对象相关 ACU 的 XE 并集。
- XE 编号、题录、摘要必须来自 `scopus_runs/*/round_*_results_raw.json` 真实响应，禁止编造。

## <object>/mve_steps/

- `<object>/mve_steps/steps_manifest.json`：

```json
{
  "object": "<object-slug>",
  "scope": "A+B all steps",
  "steps": [
    {"path": "A", "step_no": 1, "file": "A_step_01.md", "source_acus": ["ACU-001"], "skipped": false}
  ]
}
```

- 分步文件 `<path>_step_NN.md` 必须含 ep4-B 七段：`1. 步骤定位` / `2. 优化目标` / `3. 【主方案】MVE核心路径` / `4. 【备选战略】` / `5. 战略选择建议` / `6. 对资源清单的影响` / `7. 验证与检查点 (Go/No-Go Criteria)`。
- 引用：XE 在知识库内；RE 在全局库/证据集内；skip 步骤标「实现锚点缺失」；Go/No-Go 可量化。

## <object>/mve_step_detail.md

按 `steps_manifest.json` 顺序合并分步文件全文（保留七段），头部注明对象、范围、合并自 `mve_steps/`。

## 校验脚本覆盖

`check_validation.py` 至少检查：文件齐全；对象/ACU/XE 编号唯一；query 无 RE/year/doctype/占位符；RE/XE 引用合法；verdict 级别合法且 PASS 判定正确；loop/per_ACU 一致；9.6 只含高且去重；9.7 步骤覆盖与七段结构；闸门3 无未决 ACU 进 9.6。
