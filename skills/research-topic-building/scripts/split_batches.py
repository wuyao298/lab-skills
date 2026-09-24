#!/usr/bin/env python3
"""research-topic-building 分割组件：方向证据 CSV → 每批 50 篇的批次文件（只留编号/标题/摘要）。

环境无关：仅用标准库。

用法：
  python split_batches.py split --evidence <…>/search/evidence.csv --out <…>/analysis
  python split_batches.py self-check --dir <…>/analysis --evidence <…>/evidence.csv

split      按证据 CSV 行序（coverDate 倒序）每 50 篇一批，产出 batch_NNN.csv（编号/标题/摘要）。
self-check 校验批次全覆盖证据集、无重无漏、每批 ≤50 行、三列齐备。
"""

import argparse
import csv
import os
import sys

BATCH_SIZE = 50
BATCH_COLUMNS = ["编号", "标题", "摘要"]


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=BATCH_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in BATCH_COLUMNS})


def batch_path(out_dir, n):
    return os.path.join(out_dir, f"batch_{n:03d}.csv")


def cmd_split(args):
    rows = read_csv_rows(args.evidence)
    if not rows:
        sys.exit("错误：证据 CSV 为空或不存在")
    os.makedirs(args.out, exist_ok=True)
    n_batches = 0
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i:i + BATCH_SIZE]
        n_batches += 1
        write_csv(batch_path(args.out, n_batches), chunk)
    print(f"evidence_rows={len(rows)} batches={n_batches} (<= {BATCH_SIZE}/batch)")
    return 0


def collect_batch_files(out_dir):
    files = sorted(f for f in os.listdir(out_dir) if f.endswith(".csv") and f.startswith("batch_"))
    return files


def cmd_self_check(args):
    problems = []
    evidence_rows = read_csv_rows(args.evidence)
    if not evidence_rows:
        problems.append("证据 CSV 为空或不存在")

    files = collect_batch_files(args.dir)
    if not files:
        problems.append("无批次文件（batch_NNN.csv）")

    seen, total = set(), 0
    for f in files:
        with open(os.path.join(args.dir, f), "r", encoding="utf-8-sig") as fh:
            fieldnames = csv.DictReader(fh).fieldnames
            fh.seek(0)
            rows = list(csv.DictReader(fh))
        if fieldnames != BATCH_COLUMNS:
            problems.append(f"{f} 列不符：{fieldnames}")
        if len(rows) > BATCH_SIZE:
            problems.append(f"{f} 行数 {len(rows)} > {BATCH_SIZE}")
        for r in rows:
            rid = r.get("编号", "")
            if rid in seen:
                problems.append(f"{f} 编号重复：{rid}")
            seen.add(rid)
            total += 1

    ev_ids = {r.get("编号", "") for r in evidence_rows}
    if seen != ev_ids:
        missing = ev_ids - seen
        extra = seen - ev_ids
        if missing:
            problems.append(f"证据集缺失 {len(missing)} 行未入批次：{sorted(missing)[:5]}…")
        if extra:
            problems.append(f"批次出现证据集外编号 {len(extra)} 个：{sorted(extra)[:5]}…")

    if problems:
        print("SELF-CHECK FAIL")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"SELF-CHECK PASS ({len(files)} batches, {total} rows, evidence={len(evidence_rows)})")
    return 0


def main():
    parser = argparse.ArgumentParser(description="方向证据分割（research-topic-building）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_split = sub.add_parser("split")
    p_split.add_argument("--evidence", required=True)
    p_split.add_argument("--out", required=True)
    p_split.set_defaults(func=cmd_split)

    p_check = sub.add_parser("self-check")
    p_check.add_argument("--dir", required=True)
    p_check.add_argument("--evidence", required=True)
    p_check.set_defaults(func=cmd_self_check)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
