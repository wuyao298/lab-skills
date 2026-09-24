#!/usr/bin/env python3
"""research-topic-building 汇总组件：batch_NNN.md 的进阶分析矩阵段 → literature_analysis.md（文献集）。

环境无关：仅用标准库。

用法：
  python aggregate_analysis.py merge --dir <…>/analysis
  python aggregate_analysis.py check --dir <…>/analysis

merge  提取每个 batch_NNN.md 中「## 进阶分析矩阵」段（该标题后到下一个 ## 标题之间的表格），
       按批次拼接为 literature_analysis.md。
check  校验每批矩阵行覆盖该批 CSV 全部编号、无外引、无重复；literature_analysis.md 存在且含全部批次段。
"""

import argparse
import csv
import os
import re
import sys

MATRIX_HEADING = re.compile(r"^##\s*进阶分析矩阵\s*$")
SECTION_HEADING = re.compile(r"^##\s+")
RE_PATTERN = re.compile(r"\[RE(\d+)\]|(?:^|\s)RE(\d+)(?=\s|\||$|，|,|\.|：|:)")

BATCH_SIZE = 50


def extract_matrix_section(md_text):
    """返回「## 进阶分析矩阵」段内容（标题后到下一个 ## 标题前），找不到返回 None。"""
    lines = md_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if MATRIX_HEADING.match(line.strip()):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if SECTION_HEADING.match(lines[i].strip()):
            end = i
            break
    return "\n".join(lines[start + 1:end]).strip()


def matrix_re_ids(matrix_text):
    ids = set()
    for m in RE_PATTERN.finditer(matrix_text):
        ids.add(m.group(1) or m.group(2))
    return ids


def batch_files(out_dir, ext):
    return sorted(f for f in os.listdir(out_dir)
                  if f.startswith("batch_") and f.endswith(ext))


def cmd_merge(args):
    md_files = batch_files(args.dir, ".md")
    if not md_files:
        sys.exit("错误：analysis/ 下无 batch_NNN.md")
    sections = []
    missing = []
    for f in md_files:
        with open(os.path.join(args.dir, f), "r", encoding="utf-8") as fh:
            text = fh.read()
        matrix = extract_matrix_section(text)
        if matrix is None:
            missing.append(f)
            continue
        sections.append((f, matrix))

    out_lines = ["# 文献集进阶分析矩阵汇总（literature_analysis）", "",
                 "> 自动汇总自 `analysis/batch_NNN.md` 的「进阶分析矩阵」段；批次综合报告见各批次文件。", ""]
    for f, matrix in sections:
        out_lines.append(f"## {f[:-3]}（源 {f}）")
        out_lines.append("")
        out_lines.append(matrix)
        out_lines.append("")
    out_path = os.path.join(args.dir, "literature_analysis.md")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out_lines))
    print(f"merged {len(sections)}/{len(md_files)} batch matrices -> {out_path}")
    if missing:
        print(f"  缺矩阵段批次：{missing}")
        return 1
    return 0


def cmd_check(args):
    problems = []
    md_files = batch_files(args.dir, ".md")
    csv_files = batch_files(args.dir, ".csv")
    if not md_files:
        problems.append("无 batch_NNN.md")
    if not csv_files:
        problems.append("无 batch_NNN.csv")

    for csv_f in csv_files:
        with open(os.path.join(args.dir, csv_f), "r", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        md_f = csv_f[:-4] + ".md"
        if md_f not in md_files:
            problems.append(f"{csv_f} 缺对应 {md_f}")
            continue
        with open(os.path.join(args.dir, md_f), "r", encoding="utf-8") as fh:
            text = fh.read()
        matrix = extract_matrix_section(text)
        if matrix is None:
            problems.append(f"{md_f} 缺「## 进阶分析矩阵」段")
            continue
        md_ids = matrix_re_ids(matrix)
        csv_ids = {re.sub(r"[^0-9]", "", r.get("编号", "")) for r in rows}
        if md_ids != csv_ids:
            missing = csv_ids - md_ids
            extra = md_ids - csv_ids
            if missing:
                problems.append(f"{md_f} 矩阵缺 {len(missing)} 个编号：RE{min(missing)}…")
            if extra:
                problems.append(f"{md_f} 矩阵出现批次外编号 {len(extra)} 个：RE{min(extra)}…")

    la_path = os.path.join(args.dir, "literature_analysis.md")
    if not os.path.isfile(la_path):
        problems.append("缺 literature_analysis.md")
    else:
        with open(la_path, "r", encoding="utf-8") as fh:
            la_text = fh.read()
        for md_f in md_files:
            if f"（源 {md_f}）" not in la_text:
                problems.append(f"literature_analysis.md 缺批次段：{md_f}")

    if problems:
        print("CHECK FAIL")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"CHECK PASS ({len(md_files)} batch md, {len(csv_files)} batch csv)")
    return 0


def main():
    parser = argparse.ArgumentParser(description="进阶分析矩阵汇总与校验（research-topic-building）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_merge = sub.add_parser("merge")
    p_merge.add_argument("--dir", required=True)
    p_merge.set_defaults(func=cmd_merge)

    p_check = sub.add_parser("check")
    p_check.add_argument("--dir", required=True)
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
