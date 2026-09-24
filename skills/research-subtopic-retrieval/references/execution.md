# 执行说明

## 命令（先解析绝对路径）

- 首页：`python scripts/fetch_scopus.py search --query "<query>" --out <组合目录>/round_N_raw.json [--env-file <外置env>]`
- 全量：`python scripts/fetch_scopus.py fetch-all --query "<query>" --out-dir <组合目录>/batches --final <组合目录>/final_raw.json [--env-file <外置env>]`
- 串行追加：`python scripts/build_evidence_db.py append --final <组合目录>/final_raw.json --label "<标签>" --query "<query>" --db <项目>/reports/literature_db.csv --out <项目>/directions/<slug>/search --context <项目>/project_context.json [--weak]`
- 校验：`python scripts/build_evidence_db.py self-check --dir <项目>/directions/<slug>/search --db <项目>/reports/literature_db.csv --context <项目>/project_context.json`

append 是无锁的读改写，编排层须序列化共享库和编号游标的写入；检索/判门不写共享库，可并行。
脚本对空 entries 退出且不写产物；空结果留在组合记录中，不将它伪装为已成功追加。

## 文件布局

方向契约位于 directions/<slug>/direction.md。
search/ 内保存 search_strategy.md、pin_log.md、evidence.csv、meta.json。
每组合 search/<NN>-<label_slug>/ 保存 round_N_raw.json、verdict_round_N.md、iteration_log.json、batches/、final_raw.json。
