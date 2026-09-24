#!/usr/bin/env python3
"""research-field-report 检索组件：直接调用 Scopus Search API（无需 MCP）。

环境无关：仅用标准库。API key 从环境变量 SCOPUS_API_KEY 读取，
或 --env-file 指向的 .env 文件（KEY=VALUE 行）。key 永不落盘、永不打印。

用法：
  python fetch_scopus.py search   --query "<高级检索式>" --out <工作目录>/round_1_raw.json
  python fetch_scopus.py fetch-all --query "<高级检索式>" --out-dir <工作目录>/batches --final <工作目录>/final_raw.json

search     拉取第一页（count=25, sort=author, view=COMPLETE），用于建库门判定；
           打印 totalResults，原始响应落盘 --out。
fetch-all  offset 循环拉取全量，每批 25 写 batches/batch_NNN.json，再调用
           scopus_search.py merge 合并去重为 final_raw.json。

429 退避：15s / 30s / 60s，每页最多重试 3 次；5xx 等 5s 重试 1 次。
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API_URL = "https://api.elsevier.com/content/search/scopus"
COUNT = 25
SORT = "author"
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


def fetch_page(query, start, api_key, count=COUNT):
    params = urllib.parse.urlencode({
        "query": query,
        "count": count,
        "start": start,
        "sort": SORT,
        "view": VIEW,
    })
    url = f"{API_URL}?{params}"
    headers = {"X-ELS-APIKey": api_key, "Accept": "application/json"}

    for attempt in range(1, 4):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt <= len(RETRY_429):
                time.sleep(RETRY_429[attempt - 1])
                continue
            if 500 <= e.code < 600 and attempt <= len(RETRY_5XX):
                time.sleep(RETRY_5XX[attempt - 1])
                continue
            raise
    raise RuntimeError("重试耗尽")


def total_results(data):
    sr = data.get("search-results") or {}
    return int(sr.get("opensearch:totalResults", 0) or 0)


def cmd_search(args):
    api_key = load_api_key(args.env_file)
    data = fetch_page(args.query, 0, api_key)
    total = total_results(data)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"totalResults={total}  saved={args.out}")
    return 0 if total > 0 else 1


def cmd_fetch_all(args):
    api_key = load_api_key(args.env_file)
    os.makedirs(args.out_dir, exist_ok=True)
    data = fetch_page(args.query, 0, api_key)
    total = total_results(data)
    if total == 0:
        sys.exit("错误：totalResults=0")
    batch_files = []
    start = 0
    first = True
    while start < total:
        if not first:
            data = fetch_page(args.query, start, api_key)
        first = False
        entries = (data.get("search-results") or {}).get("entry") or []
        batch = f"batch_{start + 1:03d}.json"
        path = os.path.join(args.out_dir, batch)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        batch_files.append(path)
        print(f"  {len(entries)} entries -> {batch} ({start + len(entries)}/{total})")
        start += COUNT
        time.sleep(0.2)
    print(f"batches={len(batch_files)} total={total}")
    if args.final:
        import subprocess
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scopus_search.py")
        cmd = [sys.executable, script, "merge", args.final] + batch_files
        subprocess.run(cmd, check=True)
        print(f"merged -> {args.final}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Scopus 直接检索（research-field-report）")
    parser.add_argument("--env-file", default=None, help=".env 文件路径（含 SCOPUS_API_KEY=...）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="拉取第一页用于建库门判定")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--out", required=True)
    p_search.set_defaults(func=cmd_search)

    p_all = sub.add_parser("fetch-all", help="offset 循环拉取全量并合并")
    p_all.add_argument("--query", required=True)
    p_all.add_argument("--out-dir", required=True, help="batches 输出目录")
    p_all.add_argument("--final", default=None, help="合并产物 final_raw.json 路径（缺省跳过合并）")
    p_all.set_defaults(func=cmd_fetch_all)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
