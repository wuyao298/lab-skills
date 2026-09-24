#!/usr/bin/env python3
"""段 9 9.4 补跑：对**单个 ACU 的指定轮次**重新检索 + 重新出 verdict。

用途（2026-09-09 entry-01 批次）：
  上一轮 LOOP A 的 ACU-006 因 fetch_scopus 返回非 0 但旧 `results_raw.json` 仍存在，
  直接用了 obs-01 遗留的响应（@searchTerms 与 entry-01 的 ACU-006 query 不一致），
  导致 verdict 建立在错误检索结果上。本脚本按 acu_index.json 的 query 重新抓取并重判。

用法：
  python refetch_round.py --validation <validation_root> --object <object-slug> \
      --acu ACU-006 --round 1 [--query "<override>"]

行为：
  - 复用 loop_a_runner.process_one（同一检索参数、同一 verdict 提示词），不修改 runner
  - 覆盖 scopus_runs/<ACU>/round_NN/results_raw.json 与 verdict.md
  - 打印 totalResults / entries / pass，供编排器判定
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loop_a_runner as L  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validation", required=True)
    ap.add_argument("--object", required=True)
    ap.add_argument("--acu", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--query", default=None)
    args = ap.parse_args()

    base_dir = os.path.abspath(args.validation)
    acu_index = json.load(open(os.path.join(base_dir, "acu_index.json"), encoding="utf-8"))
    if args.acu not in acu_index:
        sys.exit(f"{args.acu} 不在 acu_index.json")
    query = args.query or acu_index[args.acu]["query"]

    mve_path = os.path.join(base_dir, args.object, "mve_paths.md")
    mve_text = L.read_text(mve_path) if os.path.exists(mve_path) else ""
    key = L.load_key()

    print(f"[refetch] {args.acu} round_{args.round:02d}\n  query={query}")
    r = L.process_one(args.acu, query, args.round, mve_text, key, base_dir)
    print(json.dumps(r, ensure_ascii=False))

    # 校验：落盘响应的 @searchTerms 必须等于本轮 query（防止再吃到陈旧文件）
    raw = os.path.join(base_dir, "scopus_runs", args.acu, f"round_{args.round:02d}", "results_raw.json")
    if os.path.exists(raw):
        j = json.load(open(raw, encoding="utf-8"))
        got = (j.get("search-results", {}).get("opensearch:Query", {}) or {}).get("@searchTerms", "")
        ok = got.strip() == query.strip()
        print(f"[verify] @searchTerms matches query: {ok}")
        if not ok:
            print(f"  got: {got[:200]}")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
