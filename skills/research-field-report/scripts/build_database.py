#!/usr/bin/env python3
"""research-field-report 数据库组件：final_raw.json → 21 列 CSV + meta.json + 报告输入切分。

环境无关：仅用标准库。21 列 schema、综述口径（re+sh）、meta.json 字段均为契约默认值。

用法：
  python build_database.py build --final <工作目录>/final_raw.json --query "<检索式>" --out <工作目录>/reports
  python build_database.py split --db <工作目录>/reports/literature_db.csv --out <工作目录>/reports
  python build_database.py self-check --dir <工作目录>/reports

build     构建 literature_db.csv（21 列、utf-8-sig、coverDate 倒序、[RE001] 起）+ meta.json
          + review_subset.csv（综述口径 re+sh 子集，同 21 列）
split     从 literature_db.csv 切分报告输入：
          report_input_review.csv（综述子集：标题,摘要,出版年,来源名称,作者关键词）
          report_input_full_metadata.csv（全库：标题,出版年,来源名称,作者关键词,文献类型，无摘要）
self-check 校验 21 列 / meta 字段 / RE 唯一 / 输入文件行数与口径一致
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime

COLUMNS = ["编号", "来源库", "标题", "作者（IEEE）", "来源名称", "文献类型", "是否综述",
           "卷", "期", "页码", "出版年", "出版月", "DOI", "ISSN", "出版社", "会议名",
           "摘要", "作者关键词", "被引次数", "EID", "原文链接"]

REVIEW_SUBTYPES = {"re", "sh"}
IEEE_MONTHS = {1: "Jan.", 2: "Feb.", 3: "Mar.", 4: "Apr.", 5: "May", 6: "Jun.",
               7: "Jul.", 8: "Aug.", 9: "Sep.", 10: "Oct.", 11: "Nov.", 12: "Dec."}


def first(obj, *keys):
    if not isinstance(obj, dict):
        return ""
    for k in keys:
        v = obj.get(k)
        if v is not None:
            return v
    return ""


def entries_from_final(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        sr = data.get("search-results") or {}
        data = sr.get("entry") or []
    if not isinstance(data, list):
        sys.exit("错误：final_raw.json 应为 entry 数组或 search-results 响应")
    return data


def ieee_authors(creator):
    """dc:creator（Scopus 返回第一作者字符串，如 'Qin S.' / 'Andreeva N.A.'）→ IEEE 名序。

    规则（与 2026-08-12 MFC 执行一致）：
      'Qin S.'         → 'S. Qin'（两段式：段1=姓，段2=名缩写，交换）
      'Andreeva N.A.'  → 'N. A. Andreeva'（交换 + 缩写加空格）
      'A. Albéndiz García' → 不变（段2 非缩写，已是名序）
      无作者 → '[Unknown]'；去中文字符。
    """
    names = []
    if isinstance(creator, list):
        for c in creator:
            v = c.get("$") if isinstance(c, dict) else str(c)
            if v:
                names.append(str(v))
    elif isinstance(creator, dict) and creator.get("$"):
        names.append(str(creator["$"]))
    elif creator:
        names.append(str(creator))

    out = []
    for name in names:
        name = re.sub(r"[\u4e00-\u9fff]", "", name).strip()
        if not name:
            continue
        if "," in name:
            parts = [p.strip() for p in name.split(",")]
            family = parts[0]
            given = [p for p in parts[1:] if p]
        else:
            toks = name.split()
            given = []
            while toks and toks[-1].endswith("."):
                given.insert(0, toks.pop())
            family = " ".join(toks)
        if given:
            given = re.sub(r"(?<=[A-Z])\.(?=[A-Z])", ". ", " ".join(given))
            out.append(f"{given} {family}")
        else:
            out.append(name)
    if not out:
        return "[Unknown]"
    return ", ".join(out)


def parse_cover_date(cover_date):
    """prism:coverDate '2025-09-01' → (year, ieee_month)"""
    m = re.match(r"^(\d{4})-?(\d{2})?", str(cover_date or ""))
    if not m:
        return "", ""
    year = m.group(1)
    month = ""
    if m.group(2):
        month = IEEE_MONTHS.get(int(m.group(2)), "")
    return year, month


def join_keywords(authkeywords):
    if not authkeywords:
        return ""
    kws = []
    if isinstance(authkeywords, list):
        for k in authkeywords:
            v = k.get("$") if isinstance(k, dict) else str(k)
            if v:
                kws.append(str(v))
    elif isinstance(authkeywords, dict) and authkeywords.get("$"):
        kws.append(str(authkeywords["$"]))
    else:
        kws.append(str(authkeywords))
    return " | ".join(kws).replace("; ", "|").replace(";", "|")


def entry_to_row(entry, source_db="Scopus"):
    subtype = str(first(entry, "subtype") or "").lower()
    abstract = str(first(entry, "dc:description", "abstract") or "")
    issn = str(first(entry, "prism:issn") or first(entry, "prism:eIssn") or "")
    year, month = parse_cover_date(first(entry, "prism:coverDate"))
    doc_type = str(first(entry, "subtypeDescription") or "")
    conference = doc_type if doc_type.startswith("Conference") else ""
    return {
        "来源库": source_db,
        "标题": str(first(entry, "dc:title") or ""),
        "作者（IEEE）": ieee_authors(entry.get("dc:creator")),
        "来源名称": str(first(entry, "prism:publicationName") or ""),
        "文献类型": str(first(entry, "subtypeDescription") or ""),
        "是否综述": "是" if subtype in REVIEW_SUBTYPES else "否",
        "卷": str(first(entry, "prism:volume") or ""),
        "期": str(first(entry, "prism:issueIdentifier") or ""),
        "页码": str(first(entry, "prism:pageRange") or ""),
        "出版年": year,
        "出版月": month,
        "DOI": str(first(entry, "prism:doi") or ""),
        "ISSN": issn,
        "出版社": "",
        "会议名": conference,
        "摘要": abstract,
        "作者关键词": join_keywords(entry.get("authkeywords")),
        "被引次数": str(int(float(str(first(entry, "citedby-count") or "0") or "0"))),
        "EID": str(first(entry, "eid") or ""),
        "原文链接": str(first(entry, "prism:url") or ""),
    }


def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def cmd_build(args):
    entries = entries_from_final(args.final)
    rows = []
    for e in entries:
        row = entry_to_row(e)
        row["_cover"] = str(first(e, "prism:coverDate") or "")
        rows.append(row)
    rows.sort(key=lambda r: r["_cover"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["编号"] = f"[RE{i:03d}]"
        r.pop("_cover", None)

    os.makedirs(args.out, exist_ok=True)
    db_path = os.path.join(args.out, "literature_db.csv")
    write_csv(db_path, COLUMNS, rows)

    review_rows = [r for r in rows if r["是否综述"] == "是"]
    write_csv(os.path.join(args.out, "review_subset.csv"), COLUMNS, review_rows)

    meta = {
        "review_count": len(review_rows),
        "total_count": len(rows),
        "build_date": datetime.now().strftime("%Y-%m-%d"),
        "query": args.query,
        "source_db": "Scopus",
        "review_subtype_criteria": "subtype in {re, sh} (Review / Short Survey); cr excluded as conference proceedings records (user decision 2026-08-12)",
        "csv_columns": len(COLUMNS),
    }
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"total={len(rows)} review(re+sh)={len(review_rows)} -> {db_path}")
    return 0


def cmd_split(args):
    with open(args.db, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    review_rows = [r for r in rows if r["是否综述"] == "是"]
    os.makedirs(args.out, exist_ok=True)

    write_csv(os.path.join(args.out, "report_input_review.csv"),
              ["标题", "摘要", "出版年", "来源名称", "作者关键词"],
              [{"标题": r["标题"], "摘要": r["摘要"], "出版年": r["出版年"],
                "来源名称": r["来源名称"], "作者关键词": r["作者关键词"]} for r in review_rows])

    write_csv(os.path.join(args.out, "report_input_full_metadata.csv"),
              ["标题", "出版年", "来源名称", "作者关键词", "文献类型"],
              [{"标题": r["标题"], "出版年": r["出版年"], "来源名称": r["来源名称"],
                "作者关键词": r["作者关键词"], "文献类型": r["文献类型"]} for r in rows])

    print(f"report_input_review.csv={len(review_rows)} rows (re+sh)")
    print(f"report_input_full_metadata.csv={len(rows)} rows (no abstract)")
    return 0


def cmd_self_check(args):
    problems = []
    db_path = os.path.join(args.dir, "literature_db.csv")
    meta_path = os.path.join(args.dir, "meta.json")

    if not os.path.isfile(db_path):
        problems.append("缺 literature_db.csv")
    else:
        with open(db_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if reader.fieldnames != COLUMNS:
            problems.append(f"列数/表头不符：{reader.fieldnames}")
        re_ids = [r["编号"] for r in rows]
        if len(re_ids) != len(set(re_ids)):
            problems.append("RE 编号重复")
        if rows and rows[0]["编号"] != "[RE001]":
            problems.append("RE 编号未从 [RE001] 起")
        review_count = sum(1 for r in rows if r["是否综述"] == "是")
        for name in ("report_input_review.csv", "report_input_full_metadata.csv"):
            p = os.path.join(args.dir, name)
            if not os.path.isfile(p):
                problems.append(f"缺 {name}")
            else:
                with open(p, "r", encoding="utf-8-sig") as f:
                    n = sum(1 for _ in f) - 1
                expect = review_count if name == "report_input_review.csv" else len(rows)
                if n != expect:
                    problems.append(f"{name} 行数 {n} != 预期 {expect}")

    if os.path.isfile(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        for k in ("review_count", "total_count", "build_date", "query", "source_db", "csv_columns"):
            if k not in meta:
                problems.append(f"meta.json 缺 {k}")
        if meta.get("csv_columns") != 21:
            problems.append(f"meta.csv_columns={meta.get('csv_columns')} != 21")
    else:
        problems.append("缺 meta.json")

    if problems:
        print("SELF-CHECK FAIL")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("SELF-CHECK PASS")
    return 0


def main():
    parser = argparse.ArgumentParser(description="文献数据库构建与切分（research-field-report）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build")
    p_build.add_argument("--final", required=True)
    p_build.add_argument("--query", required=True)
    p_build.add_argument("--out", required=True)
    p_build.set_defaults(func=cmd_build)

    p_split = sub.add_parser("split")
    p_split.add_argument("--db", required=True)
    p_split.add_argument("--out", required=True)
    p_split.set_defaults(func=cmd_split)

    p_check = sub.add_parser("self-check")
    p_check.add_argument("--dir", required=True)
    p_check.set_defaults(func=cmd_self_check)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
