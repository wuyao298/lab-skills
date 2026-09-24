# Scopus API Reference

按需读取。端点、参数、响应、错误。

## 端点 & 鉴权

```
GET https://api.elsevier.com/content/search/scopus
```

| Header | 值 |
|--------|-----|
| `X-ELS-APIKey` | `$SCOPUS_API_KEY`（来自 `skills/.env`） |
| `X-ELS-Insttoken` | 机构 token（可选） |
| `Accept` | `application/json` |

## 查询参数

| 参数 | 说明 |
|------|------|
| `query` | Scopus 高级检索字符串（必填） |
| `date` | `YYYY-YYYY`，如 `2021-2026` |
| `count` | 1–25 |
| `offset` | 分页偏移 |
| `sort` | `author`/`-author`/`citedby-count`/`-citedby-count`/`pubdate` |
| `view` | `STANDARD`/`COMPLETE`（含 abstract+references，本 skill 必须 COMPLETE） |
| `field` | 字段白名单，逗号分隔；不传则返回全量 |

## 响应结构

```json
{
  "search-results": {
    "opensearch:totalResults": "1234",
    "opensearch:startIndex": "0",
    "opensearch:itemsPerPage": "25",
    "entry": [
      {
        "dc:title": "...",
        "dc:creator": [{"$": "Smith J."}],
        "dc:description": "abstract...",
        "prism:coverDate": "2024-03-15",
        "prism:publicationName": "Nature",
        "prism:doi": "10.1038/...",
        "citedby-count": "89",
        "affiliation": [{"afid": "...", "affilname": "...", "city": "...", "country": "..."}],
        "authkeywords": "...",
        "author-keywords": "...",
        "idxterms": "...",
        "subtypeDescription": "Review",
        "eid": "2-s2.0-...",
        "prism:url": "..."
      }
    ]
  }
}
```

⚠️ 数字字段多为字符串（`"89"`），用 `int()` 或 `.strip()` 处理。

## curl 模板

```bash
curl -s "https://api.elsevier.com/content/search/scopus" \
  --data-urlencode "query=TITLE-ABS-KEY(...)" \
  --data-urlencode "date=2021-2026" \
  --data-urlencode "count=25" \
  --data-urlencode "sort=author" \
  --data-urlencode "view=COMPLETE" \
  -H "X-ELS-APIKey: $SCOPUS_API_KEY" \
  -H "Accept: application/json"
```

## 错误处理

| 状态码 | 处理 |
|--------|------|
| 200 | 正常 |
| 400 | query 语法错/太长 → 降级：拆括号→扁平化→退到 KEY 字段 |
| 401 | API Key 无效 → 检查 `skills/.env` |
| 403 | IP 限制 → 机构权限问题 |
| 429 | 配额满 → 等 15s+ |
| 5xx | 等后重试一次 |

## 已知陷阱

- `view=STANDARD` 无 abstract → 必须 `COMPLETE`
- `citedby-count` 是字符串
- `dc:creator` 可能 null（匿名论文）
- `prism:doi` 可能缺失 → 用 `eid` 作唯一标识
- offset 超 5000 可能不稳 → 改用 cursor
