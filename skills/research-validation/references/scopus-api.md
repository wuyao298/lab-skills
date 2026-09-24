# Scopus API（段9 LOOP A 专用）

## 端点与鉴权

```
GET https://api.elsevier.com/content/search/scopus
```

| Header | 值 |
|---|---|
| `X-ELS-APIKey` | `$SCOPUS_API_KEY`（环境变量，或 `--env-file` 指向 `.env` 文件；key 永不落盘/打印/入库） |
| `Accept` | `application/json` |

## 固定参数（契约铁律）

| 参数 | 值 | 说明 |
|---|---|---|
| `query` | `TITLE-ABS-KEY(<策略检索式>)` | `search_strategies.md`/`acu_index.json` 给的策略二（闸门3 后可换 a/d 新 query） |
| `count` | `25` | 每轮每 ACU 只拉首页 25 条，**不全量导出** |
| `sort` | `relevance` | LOOP A 专用 |
| `view` | `COMPLETE` | 必须（要 abstract） |
| `date` | **不传** | 段9 不加 year |
| `subj`/`doctype` 等过滤 | **不传** | 不加 doctype / 来源库过滤 |

RE 编号不进入 query（`[RE` 出现即非法）。

## 429 退避与错误链

- 429：等待 15s → 30s → 60s，每页最多重试 3 次。
- 5xx：等 5s 重试 1 次。
- 400：query 语法错/过长 → 降级链：拆括号 → 扁平化 → 退到 KEY 字段；仍失败 → 该轮记 FAIL（进连续失败计数）。
- 401/403：检查 key / 机构权限；该轮记 FAIL，不编造结果。
- totalResults=0：响应正常落盘，该轮记 FAIL（0 高）。

## 响应使用

- 读 `search-results.opensearch:totalResults`（字符串）与 `search-results.entry`（数组，≤25）。
- verdict subagent 输入条目字段：`dc:title` / `dc:description` / `prism:coverDate` / `prism:publicationName` / `eid` / `prism:doi`。
- 数字字段多为字符串；`dc:description` 可能缺失；`prism:doi` 可能缺失（用 EID）。
- 所有文献信息只来自真实响应，禁止编造。

## 脚本

```bash
python scripts/fetch_scopus.py search \
  --query 'TITLE-ABS-KEY(...)' \
  --out <validation>/scopus_runs/ACU-001/round_1/results_raw.json \
  [--env-file /path/to/.env]
```

- 输出：原始响应落盘 `--out`；stdout 打印 `totalResults=N`。
- `fetch_scopus.py` 只做首页检索；全量导出是 research-field-report / research-subtopic-retrieval 的职责，段9 不做。
