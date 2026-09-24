#!/usr/bin/env python3
"""research-subtopic-retrieval 证据数据库组件：final_raw.json → 方向证据 CSV（23 列）+ meta.json + project_context.json 更新。

环境无关：仅用标准库。21 列同构于全局库（schema 与规则沿用 build_database.py 口径），
附加「子问题标签」「来源检索式」两列；RE 编号全局续签（EID 已存在 → 复用，新文献 → last_issued_re+1）。

用法：
  python build_evidence_db.py append --final <组合目录>/final_raw.json --label "<子问题标签>" \
      --query "<检索式>" --db <工作目录>/reports/literature_db.csv \
      --out <工作目录>/directions/<slug>/search [--context <工作目录>/project_context.json] [--weak]
  python build_evidence_db.py self-check --dir <工作目录>/directions/<slug>/search \
      --db <工作目录>/reports/literature_db.csv [--context <工作目录>/project_context.json]

append     把 final_raw.json 的 entries 追加进 evidence.csv（EID 去重；全局库 EID 复用其 RE；新文献续签 RE），
           并更新 meta.json 与 project_context.json（last_issued_re / re_index / directions）。
self-check 校验 23 列 / EID 唯一 / RE 全局唯一与续签连续性 / meta 一致性 / project_context 一致性。
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime

BASE_COLUMNS = ["编号", "来源库", "标题", "作者（IEEE）", "来源名称", "文献类型", "是否综述",
                "卷", "期", "页码", "出版年", "出版月", "DOI", "ISSN", "出版社", "会议名",
                "摘要", "作者关键词", "被引次数", "EID", "原文链接"]
EXTRA_COLUMNS = ["子问题标签", "来源检索式"]
COLUMNS = BASE_COLUMNS + EXTRA_COLUMNS

REVIEW_SUBTYPES = {"re", "sh"}
IEEE_MONTHS = {1: "Jan.", 2: "Feb.", 3: "Mar.", 4: "Apr.", 5: "May", 6: "Jun.",
               7: "Jul.", 8: "Aug.", 9: "Sep.", 10: "Oct.", 11: "Nov.", 12: "Dec."}
RE_PATTERN = re.compile(r"\[RE(\d+)\]")


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
        entries = sr.get("entry") or data.get("entries") or []
        data = entries
    if not isinstance(data, list):
        sys.exit("错误：final_raw.json 应为 entry 数组、search-results 响应或 merge 产物（entries 键）")
    return data


def ieee_authors(creator):
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


def entry_to_row(entry, label, query, source_db="Scopus"):
    subtype = str(first(entry, "subtype") or "").lower()
    abstract = str(first(entry, "dc:description", "abstract") or "")
    issn = str(first(entry, "prism:issn") or first(entry, "prism:eIssn") or "")
    year, month = parse_cover_date(first(entry, "prism:coverDate"))
    doc_type = str(first(entry, "subtypeDescription") or "")
    conference = doc_type if doc_type.startswith("Conference") else ""
    row = {
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
        "子问题标签": label,
        "来源检索式": query,
        "_cover": str(first(entry, "prism:coverDate") or ""),
    }
    return row


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})


def read_csv_rows(path):
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def re_number(s):
    m = RE_PATTERN.search(str(s or ""))
    return int(m.group(1)) if m else None


def max_re_number(rows):
    nums = [re_number(r.get("编号")) for r in rows]
    nums = [n for n in nums if n is not None]
    return max(nums) if nums else 0


def load_context(path):
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_context(path, ctx):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)


def cmd_append(args):
    global_rows = read_csv_rows(args.db)
    if not global_rows:
        sys.exit(f"错误：全局库为空或不存在：{args.db}")
    eid_to_re_global = {r["EID"]: r["编号"] for r in global_rows if r.get("EID")}
    global_max = max_re_number(global_rows)

    os.makedirs(args.out, exist_ok=True)
    evidence_path = os.path.join(args.out, "evidence.csv")
    meta_path = os.path.join(args.out, "meta.json")
    evidence_rows = read_csv_rows(evidence_path)
    eid_to_re_evidence = {r["EID"]: r["编号"] for r in evidence_rows if r.get("EID")}
    existing_eids = set(eid_to_re_global) | set(eid_to_re_evidence)

    ctx = load_context(args.context) if args.context else None
    if ctx is None:
        ctx = {"project": os.path.basename(os.path.abspath(os.path.join(args.out, "..", ".."))),
               "segment": 5, "directions": {}, "last_issued_re": global_max,
               "re_index": {}, "topics": {}}
    last_issued = max(int(ctx.get("last_issued_re") or 0), global_max)

    entries = entries_from_final(args.final)
    if not entries:
        sys.exit("错误：final_raw.json 无 entry（结构不符或空文件），未写入任何产物")
    added, reused, skipped, new_assign = 0, 0, 0, 0
    for e in entries:
        eid = str(first(e, "eid") or "")
        if not eid:
            skipped += 1
            continue
        if eid in eid_to_re_evidence:
            skipped += 1
            continue
        if eid in eid_to_re_global:
            re_id = eid_to_re_global[eid]
            reused += 1
        else:
            last_issued += 1
            re_id = f"[RE{last_issued:03d}]"
            new_assign += 1
        row = entry_to_row(e, args.label, args.query)
        row["编号"] = re_id
        row.pop("_cover", None)
        row["_cover"] = str(first(e, "prism:coverDate") or "")
        evidence_rows.append(row)
        eid_to_re_evidence[eid] = re_id
        added += 1

    evidence_rows.sort(key=lambda r: r.get("_cover", ""), reverse=True)
    for r in evidence_rows:
        r.pop("_cover", None)
    write_csv(evidence_path, evidence_rows)

    meta = json.load(open(meta_path, "r", encoding="utf-8")) if os.path.isfile(meta_path) else \
        {"direction": os.path.basename(os.path.dirname(args.out)), "searches": []}
    meta["searches"].append({
        "label": args.label,
        "query": args.query,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "found": len(entries),
        "reused": reused,
        "added": new_assign,
        "skipped_dup": skipped,
        "weak_evidence": bool(args.weak),
    })
    meta["evidence_rows"] = len(evidence_rows)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if args.context:
        project_root = os.path.dirname(os.path.abspath(args.context))
        slug_dir = os.path.dirname(os.path.abspath(args.out))
        slug = os.path.basename(slug_dir)
        direction_md = os.path.join(slug_dir, "direction.md")
        ctx.setdefault("directions", {})[slug] = {
            "direction_md": os.path.relpath(direction_md, project_root)
            if os.path.isfile(direction_md) else "",
            "evidence_csv": os.path.relpath(evidence_path, project_root),
        }
        ctx["last_issued_re"] = last_issued
        global_re_set = {r["编号"] for r in global_rows}
        db_rel = os.path.relpath(os.path.abspath(args.db), project_root)
        for r in global_rows:
            if r.get("编号") and r.get("EID"):
                ctx.setdefault("re_index", {})[r["编号"]] = db_rel
        for r in evidence_rows:
            re_id = r.get("编号")
            if re_id and r.get("EID") and re_id not in global_re_set:
                ctx.setdefault("re_index", {})[re_id] = os.path.relpath(
                    evidence_path, project_root)
        save_context(args.context, ctx)

    print(f"found={len(entries)} reused={reused} new={new_assign} skipped_dup={skipped} "
          f"last_issued_re={last_issued} evidence_rows={len(evidence_rows)}")
    return 0


def cmd_self_check(args):
    problems = []
    evidence_path = os.path.join(args.dir, "evidence.csv")
    meta_path = os.path.join(args.dir, "meta.json")

    if not os.path.isfile(evidence_path):
        problems.append("缺 evidence.csv")
    evidence_rows = read_csv_rows(evidence_path)
    if evidence_rows:
        with open(evidence_path, "r", encoding="utf-8-sig") as f:
            fieldnames = csv.DictReader(f).fieldnames
        if fieldnames != COLUMNS:
            problems.append(f"列数/表头不符：{fieldnames}")
        eids = [r["EID"] for r in evidence_rows if r.get("EID")]
        if len(eids) != len(set(eids)):
            problems.append("EID 重复")
        res = [re_number(r["编号"]) for r in evidence_rows]
        res = [n for n in res if n is not None]
        if len(res) != len(set(res)):
            problems.append("RE 编号重复")
        if any(not r.get("子问题标签") for r in evidence_rows):
            problems.append("存在空「子问题标签」")
        if any(not r.get("来源检索式") for r in evidence_rows):
            problems.append("存在空「来源检索式」")

    global_rows = read_csv_rows(args.db)
    if not global_rows:
        problems.append(f"全局库为空或不存在：{args.db}")
    else:
        global_max = max_re_number(global_rows)
        global_eids = {r["EID"] for r in global_rows if r.get("EID")}
        global_res = {r["编号"] for r in global_rows}
        for r in evidence_rows:
            if r.get("EID") in global_eids:
                if r["编号"] not in global_res:
                    problems.append(f"全局库 EID {r['EID']} 未复用全局 RE（证据行编号 {r['编号']}）")
            elif re_number(r["编号"]) is not None and re_number(r["编号"]) <= global_max:
                problems.append(f"新文献 RE {r['编号']} 未从全局最大号 {global_max} 续签")

    if os.path.isfile(meta_path):
        meta = json.load(open(meta_path, "r", encoding="utf-8"))
        if meta.get("evidence_rows") != len(evidence_rows):
            problems.append(f"meta.evidence_rows={meta.get('evidence_rows')} != 实际 {len(evidence_rows)}")
    else:
        problems.append("缺 meta.json")

    if args.context and os.path.isfile(args.context):
        ctx = json.load(open(args.context, "r", encoding="utf-8"))
        if evidence_rows:
            ev_max = max_re_number(evidence_rows)
            ctx_last = int(ctx.get("last_issued_re") or 0)
            if ctx_last < ev_max:
                problems.append(f"project_context.last_issued_re={ctx_last} < 证据 CSV 最大 RE {ev_max}")

    if problems:
        print("SELF-CHECK FAIL")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("SELF-CHECK PASS")
    return 0


def main():
    parser = argparse.ArgumentParser(description="方向证据 CSV 构建与校验（research-subtopic-retrieval）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_append = sub.add_parser("append")
    p_append.add_argument("--final", required=True)
    p_append.add_argument("--label", required=True)
    p_append.add_argument("--query", required=True)
    p_append.add_argument("--db", required=True)
    p_append.add_argument("--out", required=True)
    p_append.add_argument("--context", default=None)
    p_append.add_argument("--weak", action="store_true", help="证据薄弱标注（3 轮迭代不达标）")
    p_append.set_defaults(func=cmd_append)

    p_check = sub.add_parser("self-check")
    p_check.add_argument("--dir", required=True)
    p_check.add_argument("--db", required=True)
    p_check.add_argument("--context", default=None)
    p_check.set_defaults(func=cmd_self_check)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
