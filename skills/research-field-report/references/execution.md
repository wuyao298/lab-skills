# 执行说明

## 命令（先解析绝对路径）

- 首页：`python scripts/fetch_scopus.py search --query "<query>" --out <项目>/round_N_raw.json [--env-file <外置env>]`
- 全量：`python scripts/fetch_scopus.py fetch-all --query "<query>" --out-dir <项目>/batches --final <项目>/final_raw.json [--env-file <外置env>]`
- 建库：`python scripts/build_database.py build --final <项目>/final_raw.json --query "<query>" --out <项目>/reports`
- 切分：`python scripts/build_database.py split --db <项目>/reports/literature_db.csv --out <项目>/reports`
- 校验：`python scripts/build_database.py self-check --dir <项目>/reports`

导出条数至少为建库门 totalResults 减去去重条数；去重按 EID→DOI→标题。429 由脚本退避。`SCOPUS_API_KEY` 仅由环境或外置 env 注入。

## 文件布局

项目根保存 round_N_raw.json、batches/、final_raw.json 与 delivery_notes.md。
reports/ 保存 literature_db.csv、review_subset.csv、meta.json、两个 report_input_*.csv 与五报告。
输入切分文件虽为中间产物，仍在 reports/，供报告任务按固定路径读取。
