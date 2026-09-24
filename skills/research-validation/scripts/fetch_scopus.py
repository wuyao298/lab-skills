#!/usr/bin/env python3
"""research-validation 段9 LOOP A 检索：Scopus Search API 首页 25 条（relevance）。

固定契约（docs/research-skill-design/04-workflow-v1-segment9-validation.md）：
- query = search_strategies.md 的 ACU 检索式（编排器用 TITLE-ABS-KEY(...) 原样传入）
- count=25, sort=relevance, view=COMPLETE；不加 year/doctype/来源库
- 每轮每 ACU 只拉首页 25 条，不全量导出；真实响应落盘 --out
- 429 退避 15s/30s/60s；5xx 重试 1 次；totalResults=0 也落盘并返回 1

用法：
  python fetch_scopus.py search --query "<检索式>" --out <validation>/scopus_runs/<ACU>/round_N/results_raw.json [--env-file <path>]
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.elsevier.com/content/search/scopus"
COUNT = 25
SORT = "relevance"
VIEW = "COMPLETE"
RETRY_429 = (15, 30, 60)
RETRY_5XX = (5,)


def load_api_key(env_file):
    key = os.environ.get("SCOPUS_API_KEY", "").strip()
    if key:
        return key
    if env_file and os.path.isfile(env_file):
        with open(env_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("SCOPUS_API_KEY="):
                    return line[len("SCOPUS_API_KEY="):].strip().strip('"').strip("'")
    sys.exit("错误：未找到 SCOPUS_API_KEY（环境变量或 --env-file 中的 .env）。")


def fetch_page(query, api_key, timeout=90):
    params = urllib.parse.urlencode({
        "query": query,
        "count": COUNT,
        "sort": SORT,
        "view": VIEW,
    })
    url = f"{API_URL}?{params}"
    headers = {"X-ELS-APIKey": api_key, "Accept": "application/json"}
    retries_429 = retries_5xx = 0
    while True:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and retries_429 < len(RETRY_429):
                delay = RETRY_429[retries_429]
                retries_429 += 1
                time.sleep(delay)
                continue
            if 500 <= e.code < 600 and retries_5xx < len(RETRY_5XX):
                delay = RETRY_5XX[retries_5xx]
                retries_5xx += 1
                time.sleep(delay)
                continue
            raise


def total_results(data):
    sr = data.get("search-results") or {}
    return int(sr.get("opensearch:totalResults", 0) or 0)


def entries(data):
    return (data.get("search-results") or {}).get("entry") or []


def main():
    parser = argparse.ArgumentParser(description="段9 LOOP A Scopus 首页检索")
    parser.add_argument("--env-file", default=None, help=".env 文件路径（含 SCOPUS_API_KEY=...）")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search", help="首页 25 条（relevance / COMPLETE），真实响应落盘")
    p.add_argument("--env-file", default=None, help=".env 文件路径（含 SCOPUS_API_KEY=...）")
    p.add_argument("--query", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=lambda a: cmd_search(a))

    args = parser.parse_args()
    sys.exit(args.func(args))


def cmd_search(args):
    api_key = load_api_key(args.env_file)
    data = fetch_page(args.query, api_key)
    total = total_results(data)
    n = len(entries(data))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"totalResults={total} entries={n} saved={args.out}")
    return 0 if total > 0 else 1


if __name__ == "__main__":
    main()
