#!/usr/bin/env python3
"""
scopus-search 后处理工具

本脚本处理 Scopus API 原始 JSON 响应的本地操作。
真实检索由主代理通过 curl 直接调用 Scopus API 执行。

功能：
  1. parse_response      — 解析 Scopus JSON 响应，提取 totalResults + entries
  2. by_author_top_n     — 按第一作者字母序取前 N 篇（保留 Scopus 默认排序）
  3. merge_batches       — 合并多个批次的 raw 响应到一个 entry[] 数组
  4. write_final_raw     — 落盘最终 final_raw.json（保留全部字段）
  5. init_iteration_log  — 初始化 iteration_log.json

用法：
  python3 scopus_search.py parse <path-to-raw.json>
  python3 scopus_search.py merge <output_path> <batch1.json> <batch2.json> ...
  python3 scopus_search.py init-log <output_dir> --query "..." --topic-slug "..."
"""

import argparse
import json
import os
import sys
from datetime import datetime


# ── 1. 解析响应 ──────────────────────────────────────────────

def parse_response(raw_path: str) -> dict:
    """
    解析 Scopus API 响应。
    返回：{
      "total_results": int,
      "start_index": int,
      "items_per_page": int,
      "entries": [...]
    }
    """
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "search-results" not in data:
        raise ValueError(f"无效的 Scopus 响应：缺少 'search-results' 键。文件：{raw_path}")

    sr = data["search-results"]
    total = int(sr.get("opensearch:totalResults", 0))
    entries = sr.get("entry", [])

    # Scopus 单篇详情接口返回的 entry 是单个对象而非数组，规范化
    if isinstance(entries, dict):
        entries = [entries]

    return {
        "total_results": total,
        "start_index": int(sr.get("opensearch:startIndex", 0)),
        "items_per_page": int(sr.get("opensearch:itemsPerPage", len(entries))),
        "entries": entries
    }


# ── 2. 取前 N 篇 ──────────────────────────────────────────────

def by_author_top_n(parsed: dict, n: int = 20) -> list:
    """
    按第一作者字母序取前 N 篇。
    前提：响应已用 sort="author" 排序（Scopus 默认 A-Z）。
    若未排序，会做本地排序兜底。
    """
    entries = parsed["entries"]
    # 兜底本地排序（万一 Scopus 默认是按其他字段）
    entries_sorted = sorted(entries, key=lambda e: _first_author_lastname(e))
    return entries_sorted[:n]


def _first_author_lastname(entry: dict) -> str:
    """提取第一条作者的姓氏用于排序。"""
    creators = entry.get("dc:creator")
    if isinstance(creators, list) and creators:
        first = creators[0]
        if isinstance(first, dict):
            return first.get("$", "")
        if isinstance(first, str):
            return first
    return ""


# ── 3. 合并批次 ──────────────────────────────────────────────

def merge_batches(output_path: str, batch_paths: list):
    """
    合并多个批次的 raw JSON 为单一 final_raw.json。
    最终结构：
    {
      "meta": {
        "merged_at": "...",
        "batch_count": N,
        "total_entries": M,
        "source_batches": ["round_5_batch1.json", ...]
      },
      "entries": [所有 entry 合并，按作者姓字母序]
    }
    """
    all_entries = []
    source_batches = []

    for batch_path in batch_paths:
        if not os.path.exists(batch_path):
            print(f"[WARN] 批次文件不存在，跳过: {batch_path}")
            continue
        parsed = parse_response(batch_path)
        all_entries.extend(parsed["entries"])
        source_batches.append(os.path.basename(batch_path))

    # 去重（基于 eid 或 dc:title）
    seen = set()
    deduped = []
    for entry in all_entries:
        key = _entry_dedup_key(entry)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)

    # 按作者姓字母序排序
    deduped.sort(key=_first_author_lastname)

    final = {
        "meta": {
            "merged_at": datetime.now().isoformat(),
            "batch_count": len(source_batches),
            "total_entries": len(deduped),
            "raw_total_before_dedup": len(all_entries),
            "source_batches": source_batches,
            "schema": "raw_scopus"
        },
        "entries": deduped
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"[OK] 合并 {len(source_batches)} 批 → {len(deduped)} 条（去重 {len(all_entries)-len(deduped)} 条）")
    print(f"[OK] 输出: {output_path}")
    return final


def _entry_dedup_key(entry: dict) -> str:
    """去重键：eid 优先，其次 DOI，最后 title。"""
    eid = entry.get("eid", "")
    if eid:
        return f"eid:{eid}"
    doi = entry.get("prism:doi", "")
    if doi:
        return f"doi:{doi}"
    return f"title:{entry.get('dc:title', '')}"


# ── 4. 落盘最终 ──────────────────────────────────────────────

def write_final_raw(output_path: str, entries: list, source_batches: list):
    """直接由 entries 列表写 final_raw.json（merge_batches 的轻量版）。"""
    final = {
        "meta": {
            "merged_at": datetime.now().isoformat(),
            "total_entries": len(entries),
            "source_batches": source_batches,
            "schema": "raw_scopus"
        },
        "entries": entries
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"[OK] final_raw 写入: {output_path} ({len(entries)} 条)")


# ── 5. 初始化 iteration_log ──────────────────────────────────

def init_iteration_log(
    output_dir: str,
    original_query: str,
    topic_slug: str = "",
    year_range: str = "",
    min_total: int = 500,
    min_relevant: int = 10,
    max_iterations: int = 3
):
    """初始化 iteration_log.json，含 pass_criteria + 迭代历史数组。"""
    log = {
        "topic_slug": topic_slug,
        "original_query": original_query,
        "year_range": year_range,
        "created_at": datetime.now().isoformat(),
        "pass_criteria": {
            "min_total": min_total,
            "min_relevant": min_relevant,
            "max_iterations": max_iterations
        },
        "rounds": [],
        "force_pass_history": []
    }

    log_path = os.path.join(output_dir, "iteration_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print(f"[OK] iteration_log 初始化: {log_path}")
    return log


def append_round(log_path: str, round_num: int, query: str, total_results: int,
                 verdict: str, relevant_count: int = None, notes: str = ""):
    """在 iteration_log.json 追加一轮记录。"""
    with open(log_path, "r", encoding="utf-8") as f:
        log = json.load(f)

    log["rounds"].append({
        "round": round_num,
        "query": query,
        "total_results": total_results,
        "relevant_count_top20": relevant_count,
        "verdict": verdict,
        "timestamp": datetime.now().isoformat(),
        "notes": notes
    })

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


# ── 6. 迭代决策 ────────────────────────────────────────────────

def decide_next_step(round_num: int, verdict: str,
                     pass_criteria: dict = None) -> str:
    """
    主代理第 3 步决策逻辑。
    返回：
      - "refine_and_retry"   → 优化 query 进入下一轮
      - "pass_and_fetch"     → 通过，进入分批拉取
      - "force_pass_and_fetch" → 已达最大轮数，强制进入拉取
      - "stop_max_iterations_force" → 同上（保留别名）

    参数：
      round_num: 当前轮号（1-based）
      verdict: "PASS" 或 "FAIL"
      pass_criteria: 来自 iteration_log.json，含 max_iterations
    """
    if pass_criteria is None:
        pass_criteria = {"max_iterations": 3}

    max_iters = pass_criteria.get("max_iterations", 3)

    if verdict == "PASS":
        return "pass_and_fetch"

    # verdict == FAIL
    if round_num >= max_iters:
        return "force_pass_and_fetch"

    return "refine_and_retry"


# ── 7. 标记 force_pass ─────────────────────────────────────────

def record_force_pass(log_path: str, round_num: int, total: int, relevant: int,
                      notes: str = ""):
    """在 iteration_log.json 的 force_pass_history 追加一条。"""
    with open(log_path, "r", encoding="utf-8") as f:
        log = json.load(f)

    log["force_pass_history"].append({
        "round": round_num,
        "total_results": total,
        "relevant_count_top20": relevant,
        "recorded_at": datetime.now().isoformat(),
        "notes": notes
    })

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


# ── CLI 入口 ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="scopus-search 后处理工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # parse
    p_parse = subparsers.add_parser("parse", help="解析 Scopus JSON 响应")
    p_parse.add_argument("raw_path")
    p_parse.add_argument("--top", type=int, default=20, help="取前 N 篇（姓名排序）")

    # merge
    p_merge = subparsers.add_parser("merge", help="合并多个批次 raw JSON")
    p_merge.add_argument("output_path")
    p_merge.add_argument("batch_paths", nargs="+")

    # init-log
    p_init = subparsers.add_parser("init-log", help="初始化 iteration_log.json")
    p_init.add_argument("output_dir")
    p_init.add_argument("--query", required=True)
    p_init.add_argument("--topic-slug", default="")
    p_init.add_argument("--year-range", default="")
    p_init.add_argument("--min-total", type=int, default=500)
    p_init.add_argument("--min-relevant", type=int, default=10)
    p_init.add_argument("--max-iterations", type=int, default=3)

    # append-round
    p_round = subparsers.add_parser("append-round", help="追加一轮迭代记录")
    p_round.add_argument("log_path")
    p_round.add_argument("--round", type=int, required=True)
    p_round.add_argument("--query", required=True)
    p_round.add_argument("--total", type=int, required=True)
    p_round.add_argument("--relevant", type=int, default=None)
    p_round.add_argument("--verdict", required=True)
    p_round.add_argument("--notes", default="")

    args = parser.parse_args()

    if args.command == "parse":
        parsed = parse_response(args.raw_path)
        print(f"[OK] total: {parsed['total_results']}, entries: {len(parsed['entries'])}")
        top = by_author_top_n(parsed, args.top)
        print(f"[OK] 前 {args.top} 篇（按作者姓字母序）:")
        for i, e in enumerate(top, 1):
            title = e.get("dc:title", "")
            print(f"  {i}. {title[:80]}")

    elif args.command == "merge":
        merge_batches(args.output_path, args.batch_paths)

    elif args.command == "init-log":
        init_iteration_log(
            args.output_dir, args.query, args.topic_slug, args.year_range,
            args.min_total, args.min_relevant, args.max_iterations
        )

    elif args.command == "append-round":
        append_round(
            args.log_path, args.round, args.query, args.total,
            args.relevant, args.verdict, args.notes
        )


if __name__ == "__main__":
    main()
