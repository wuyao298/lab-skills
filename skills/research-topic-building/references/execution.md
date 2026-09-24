# 执行说明

## 命令（先解析绝对路径）

`<方向>` = `<项目>/directions/<slug>`。

- 分割：`python scripts/split_batches.py split --evidence <方向>/search/evidence.csv --out <方向>/analysis`
- 分割校验：`python scripts/split_batches.py self-check --dir <方向>/analysis --evidence <方向>/search/evidence.csv`
- 分析：`python scripts/batch_analysis_runner.py --project <项目> --slug <slug> --focus "<本方向核心焦点>" [--from 1 --to N] [--workers 100]`
- 汇总：`python scripts/aggregate_analysis.py merge --dir <方向>/analysis`
- 覆盖校验：`python scripts/aggregate_analysis.py check --dir <方向>/analysis`
- 课题校验：`python scripts/check_topics.py check --dir <方向>/topics --evidence <方向>/search/evidence.csv --db <项目>/reports/literature_db.csv`

focus 来自当前 direction.md，不复制历史 MFC 示例。
analysis/ 保留批次 CSV、批次 MD 与 literature_analysis.md；方向内 reports/ 保留三策略报告；topics/ 保存独立课题及提取清单。
运行模型与 auth 约定见 batch_analysis_runner.py 头注释；默认 workers=min(批数,100)。 这是执行器的 API 缺省；筛选判断、契约检验与复验等评审子 agent 按 [统一评审配置](review-agents.md) 选择轻量模型、关闭 thinking，核对实际运行参数后再执行。
