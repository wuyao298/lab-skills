#!/usr/bin/env python3
"""段 9 9.4 LOOP A 后处理：扫所有 verdict.md，重判「高/中/建议排除」分布，更新 per_ACU 状态。

容忍多种格式：
  - 4 列表（论文标识 | 级别 | 可复现步骤 | 整合步骤）
  - 3 列表 + 文字段（论文编号 | 可复现 | 整合 + 行末"建议排除/高优先级"）
  - 文本中带「高」「中」「建议排除」标记

输出：打印每个 verdict 的 高/中/排除 计数 + 是否 PASS（≥1 高）。
"""
import json
import os
import re
import sys
from collections import Counter


def find_tables(text: str) -> list:
    """提取所有 markdown 表格（每行以 | 开头）。"""
    tables = []
    cur = []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            cur.append(line)
        else:
            if cur:
                tables.append(cur)
                cur = []
    if cur:
        tables.append(cur)
    return tables


def grade_table(table_lines: list) -> Counter:
    """从表中找 高/中/建议排除 计数。"""
    cnt = Counter()
    for line in table_lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0].startswith("论文") or cells[0].startswith("编号"):
            continue
        if set(cells[0]) == {"-"} or set(cells[0]) == {":"}:
            continue
        # 扫所有 cell，找高/中/排除
        # 注意：可能 4 列表里第 2 列 = 级别；可能 3+1 列表里第 4 列 = 优先级
        text_blob = " ".join(cells)
        if "建议排除" in text_blob or "建议 排除" in text_blob:
            cnt["建议排除"] += 1
        elif "高优先级" in text_blob or "高" == cells[1] if len(cells) > 1 else False:
            cnt["高"] += 1
        elif "中优先级" in text_blob or "中" == cells[1] if len(cells) > 1 else False:
            cnt["中"] += 1
    return cnt


def grade_text(text: str) -> Counter:
    """从全文「筛选结论」「高/中/排除」段落统计。"""
    cnt = Counter()
    # 抓行：可能含「建议排除」「高优先级」「中优先级」等关键词
    for line in text.splitlines():
        if "建议排除" in line:
            cnt["建议排除"] += 1
        if re.search(r"\b高\b", line) or "高优先级" in line:
            cnt["高_text"] += 1
        if re.search(r"\b中\b", line) or "中优先级" in line:
            cnt["中_text"] += 1
    return cnt


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    base_dir = sys.argv[1].rstrip("\\/")
    scopus_dir = os.path.join(base_dir, "scopus_runs")
    if not os.path.isdir(scopus_dir):
        print(f"no scopus_runs at {scopus_dir}")
        sys.exit(1)

    summary = {}
    files = []
    for root, _, fs in os.walk(scopus_dir):
        for fn in fs:
            if fn == "verdict.md":
                files.append(os.path.join(root, fn))
    for f in sorted(files):
        rel = os.path.relpath(f, scopus_dir)
        text = open(f, encoding="utf-8").read()
        tables = find_tables(text)
        tab_cnt = Counter()
        for t in tables:
            tab_cnt += grade_table(t)
        txt_cnt = grade_text(text)
        passed = tab_cnt["高"] >= 1
        summary[rel] = {
            "tables": len(tables),
            "high_table": tab_cnt["高"],
            "mid_table": tab_cnt["中"],
            "exclude_table": tab_cnt["建议排除"],
            "high_text": txt_cnt["高_text"],
            "pass": passed
        }
        marker = "[PASS]" if passed else "[FAIL]"
        print(f"  {marker} {rel} : tables={len(tables)}, high={tab_cnt['高']}, mid={tab_cnt['中']}, exclude={tab_cnt['建议排除']}, high_text={txt_cnt['高_text']}")

    out_path = os.path.join(base_dir, "regrade_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n[regrade] {sum(s['pass'] for s in summary.values())} pass / {len(summary)} total → {out_path}")


if __name__ == "__main__":
    main()
