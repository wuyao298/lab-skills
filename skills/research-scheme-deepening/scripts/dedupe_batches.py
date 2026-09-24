#!/usr/bin/env python3
"""段 6 6.1 后处理：screening_batches/batch_NNN.md 全文件 RE 重复行去重（保留首次出现）。

注意：模型多轮续写会在文件里重复加「# 筛选表」/「## 筛选表」段头，导致多张表共存。
本脚本按行扫全文件，只对表行（首列是 [REXXX]）按 RE 去重，其他行原样保留。

用法：
  python dedupe_batches.py <topic_dir>
"""
import os
import re
import sys

RE_PATTERN = re.compile(r"\[RE(\d+)\]|(?:^|\s)RE(\d+)(?=\s|\||$|，|,|\.|：|:)")


def is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|")


def extract_re(line: str) -> str | None:
    s = line.strip()
    if not is_table_row(s):
        return None
    cells = [c.strip() for c in s.strip("|").split("|")]
    if len(cells) < 2:
        return None
    if cells[0].startswith("论文编号") or set(cells[0]) == {"-"}:
        return None
    m = RE_PATTERN.search(cells[0])
    if not m:
        return None
    return m.group(1) or m.group(2)


def dedupe_one(path: str) -> tuple[int, int]:
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    seen = set()
    n_total = 0
    n_kept = 0
    out = []
    for line in lines:
        rid = extract_re(line)
        if rid is None:
            out.append(line)
            continue
        n_total += 1
        if rid in seen:
            continue
        seen.add(rid)
        out.append(line)
        n_kept += 1

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return n_total, n_kept


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    topic_dir = sys.argv[1].rstrip("\\/")
    sb_dir = os.path.join(topic_dir, "screening_batches")
    if not os.path.isdir(sb_dir):
        print(f"no screening_batches at {sb_dir}")
        sys.exit(1)
    total_before = 0
    total_after = 0
    files = sorted(f for f in os.listdir(sb_dir) if f.startswith("batch_") and f.endswith(".md"))
    changed = []
    for fn in files:
        path = os.path.join(sb_dir, fn)
        before, after = dedupe_one(path)
        total_before += before
        total_after += after
        if before != after:
            changed.append((fn, before, after))
    for fn, b, a in changed:
        print(f"  {fn}: {b} -> {a} (removed {b - a} dup rows)")
    print(f"[dedupe] total: {total_before} -> {total_after} (removed {total_before - total_after} dup rows)")
    if not changed:
        print("[dedupe] no duplicates found — already clean")


if __name__ == "__main__":
    main()
