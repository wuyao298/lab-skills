#!/usr/bin/env python3
"""research-topic-building 课题校验组件：topics/ 目录契约校验（命名/字段/RE 锚点实测）。

环境无关：仅用标准库。

用法：
  python check_topics.py check --dir <…>/topics --evidence <…>/search/evidence.csv --db <工作目录>/reports/literature_db.csv

check  校验：
  - 文件名模式 (meta|entry|innov|single)-<NN>-<短标题>.md；NN 每策略连续无缺
  - 每文件含立论依据且非空、含 [REXXX] 引用
  - 每个 [REXXX] 在证据 CSV 或全局库实测存在
  - _extraction_manifest.md 存在
"""

import argparse
import csv
import os
import re
import sys

NAME_PATTERN = re.compile(r"^(meta|entry|innov|single)-(\d{2})-[a-z0-9-]+\.md$")
RE_PATTERN = re.compile(r"\[RE(\d+)\]")
REQUIRED_HEADINGS = ["论文标题", "核心科学问题", "研究设计与技术路线", "预期创新性与价值", "立论依据"]


def read_csv_rows(path):
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def cmd_check(args):
    problems = []
    files = [f for f in os.listdir(args.dir) if f.endswith(".md")]
    topic_files = [f for f in files if NAME_PATTERN.match(f)]

    if not topic_files:
        problems.append("topics/ 下无符合命名模式的课题 MD")
    seen_names, strategy_nums = set(), {}
    for f in files:
        if f.startswith("_"):
            continue
        if not NAME_PATTERN.match(f):
            problems.append(f"非法文件名：{f}")
            continue
        if f in seen_names:
            problems.append(f"重名文件：{f}")
        seen_names.add(f)
        m = NAME_PATTERN.match(f)
        strategy, nn = m.group(1), int(m.group(2))
        strategy_nums.setdefault(strategy, []).append(nn)

    for strategy, nums in strategy_nums.items():
        nums = sorted(set(nums))
        if nums != list(range(1, len(nums) + 1)):
            problems.append(f"策略 {strategy} NN 不连续：{nums}")
        if strategy != "single":
            expected_range = {"meta": (6, 9), "entry": (6, 9), "innov": (4, 6)}[strategy]
            if not (expected_range[0] <= len(nums) <= expected_range[1]):
                problems.append(f"策略 {strategy} 课题数 {len(nums)} 超出 {expected_range}")

    evidence_rows = read_csv_rows(args.evidence)
    global_rows = read_csv_rows(args.db)
    valid_res = {f"[RE{n}]" for r in evidence_rows
                 for n in re.findall(r"[0-9]+", str(r.get("编号")))}
    valid_res |= {f"[RE{n}]" for r in global_rows
                  for n in re.findall(r"[0-9]+", str(r.get("编号")))}

    for f in topic_files:
        with open(os.path.join(args.dir, f), "r", encoding="utf-8") as fh:
            text = fh.read()
        for heading in REQUIRED_HEADINGS:
            if f"## {heading}" not in text and f"# {heading}" not in text:
                problems.append(f"{f} 缺字段：{heading}")
        cited = RE_PATTERN.findall(text)
        if not cited:
            problems.append(f"{f} 立论依据无 [REXXX] 引用")
        for re_id in cited:
            token = f"[RE{int(re_id):03d}]"
            if token not in valid_res:
                problems.append(f"{f} 引用不存在编号：{token}")

    if not os.path.isfile(os.path.join(args.dir, "_extraction_manifest.md")):
        problems.append("缺 _extraction_manifest.md")

    if problems:
        print("CHECK FAIL")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"CHECK PASS ({len(topic_files)} topic files)")
    return 0


def main():
    parser = argparse.ArgumentParser(description="课题 MD 契约校验（research-topic-building）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check")
    p_check.add_argument("--dir", required=True)
    p_check.add_argument("--evidence", required=True)
    p_check.add_argument("--db", required=True)
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
