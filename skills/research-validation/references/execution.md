# 执行说明

## 运行约定

LOOP A 与闸门3默认由主 agent 原生分派子 agent；模型由宿主配置，无需 opencode/DeepSeek 模型密钥。独立任务并发取宿主可用槽位与100上限的较小值，单任务只读指定输入。无子 agent 工具时主 agent 顺序执行相同任务文件。
Scopus 只走直连，首页参数 count=25、sort=relevance、view=COMPLETE；参数细节见 [Scopus API](scopus-api.md)。密钥来自环境/外置 env，不写入产物。

## 子 agent 配置

本技能全部执行—检验循环都按 [统一评审配置](review-agents.md)：标注、分级、常规检验/评审及修复后复验一般使用轻量模型，关闭 thinking。覆盖研究设计、MVE、元分析、LOOP A、知识库和逐步骤细化的检验环节；生成任务另选配置。

## 脚本命令

资源路径相对此技能目录；把所有脚本/输入/输出解析为绝对路径后运行。

- 检索：`python scripts/fetch_scopus.py search --query "<query>" --out <validation>/scopus_runs/<ACU>/round_N/results_raw.json [--env-file <外置env>]`
- LOOP 准备：`python scripts/loop_a_runner.py prepare --validation <validation> --workers 4 [--env-file <外置env>] [--dry]`
- LOOP 收取：`python scripts/loop_a_runner.py collect --validation <validation>`
- LOOP 状态：`python scripts/loop_a_runner.py status --validation <validation>`
- 知识库：`python scripts/build_knowledge_base.py --validation <validation> [--db <全局库CSV>] [--evidence <证据CSV>] [--acu-index <acu_index.json>]`
- 交付校验：`python scripts/check_validation.py --validation <validation> --project <项目> --slug <slug>`

build_knowledge_base.py 不接收 --context；只查询已有 RE，不签发新 RE。

LOOP 命令退出码：0=命令成功（可能仍等待 worker，并不表示整轮完成），2=输入/检索/结果错误，3=闸门待裁决。看 JSON 的 phase、pending、ready、errors、gate3_pending 判断下一步。`--workers` 仅控制检索，不控制 agent 数量。`round` 是 prepare 别名；不再像旧版那样直接完成模型分级。

历史 `strict_verdict.py` / `refetch_round.py` / `gate3_suggest.py` 仍保留 API 依赖，仅供明确选用的旧项目修复。正常流程不串联这些补丁脚本，也不要求安装对应模型服务。其他阶段的 API runner 同样是可选执行工具。

## 细化与交付

每步骤七段：步骤定位 / 优化目标 / 主方案 / 1–2 个不同战略取向备选与 Trade-offs / 战略选择建议 / 资源清单影响 / 量化 Go-No-Go。
XE 引用：四段式（有链接）/直接引用（有参数）/三段式（无参数并声明核实要求）；原始方案仍用 RE。
按 schema 维护 metadata.json、steps_manifest.json 等运行文件，schema 见 [产物契约](artifact-contracts.md)。

## 文件布局

```
validation/
├── selection.md                  # Step 0：对象清单 + 细化范围 + 用户原话
├── metadata.json                 # 运行时状态（对象清单、last_step、gate3_pending）
├── <object-slug>/
│   ├── research_design.md        # 自生成 ep1，或指向 thesis/plan 工作包的指针
│   ├── mve_paths.md
│   ├── mve_step_detail.md        # 9.7 合并产物
│   └── mve_steps/                # 9.7 分步中间产物 + steps_manifest.json
├── meta_analysis.md              # 全局阶段 + ACU + 依赖图
├── search_strategies.md          # 每 ACU 三策略 + 起手策略=②实现优先
├── acu_index.json                # ACU → 来源对象/query 的机器索引（运行时文件）
├── scopus_runs/<ACU>/round_N/    # raw、task、prompt、worker result、verdict
├── loop_a/                     # 活动轮快照、已完成轮审计、提交恢复日志
├── loop_state.json 
├── per_ACU_summary.json          # 每 ACU 计数与状态
├── retrieval_report.md           # LOOP A 总结
├── gate_3_decisions.md           # 闸门3 全部决策 + 用户原话
├── reproducibility_filter.md     # 9.6 高文献去重清单（XE 编号）
└── knowledge_base/<object>.txt   # 9.7 知识库（只含高文献，XE 编号）
```
