#!/usr/bin/env python3
"""research-validation 9.6：复现筛选 + XE 知识库（纯机械，不再二次分级）。

输入 = 每个 covered ACU 首个 PASS 轮 verdict.md 中的全部「高」文献。
- 去重键：EID → DOI → 标题（跨 ACU 保留一行，记来源 ACU）
- XE 编号：验证轮内本地编号 XE001... 全局唯一；EID 已在全局库/证据 CSV 有 RE 时双标注
- 不新签全局 RE、不追加证据 CSV
- 按对象切分 knowledge_base/<object-slug>.txt（对象 = acu_index.json 的 source_objects）

用法：
  python build_knowledge_base.py --validation <validation_root>
      [--acu-index <acu_index.json>]
      [--db <全局库CSV>] [--evidence <方向证据CSV>]
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import unicodedata

HEADERS = ["文献编号", "来源 ACU", "可复现的关键步骤与参数",
           "可直接整合至我方案的具体步骤"]


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    if s is None:
        return ""
    s = str(s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def norm_key(s):
    return re.sub(r"[\W_]+", "", norm(s))


def cell(row, idx):
    return row[idx].strip() if idx < len(row) else ""


def parse_table(text):
    """返回 [(cells,), ...]：markdown 表体行（跳过表头/分隔行）。"""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        joined = "".join(cells).replace(" ", "")
        if not joined or set(joined.replace("-", "")) == {":"}:
            continue
        if "论文标识" in cells[0] or "文献编号" in cells[0] or "论文编号" in cells[0]:
            continue
        rows.append(cells)
    return rows


def parse_verdict(text):
    """取高行。返回 [(paper_id, level, key_steps, integrate), ...]。"""
    out = []
    for cells in parse_table(text):
        if len(cells) < 2:
            continue
        pid, level = cell(cells, 0), cell(cells, 1)
        steps = cell(cells, 2) if len(cells) > 2 else ""
        integrate = cell(cells, 3) if len(cells) > 3 else ""
        lv = norm(level)
        if "排除" in lv:
            continue
        if "高" in lv and "中" not in lv and "建议" not in lv:
            out.append((pid, "高", steps, integrate))
        elif "高" in lv:
            # 形如「中（偏向高）」按中处理，不进 9.6
            continue
    return out


def raw_entry_index(entries):
    """Scopus 条目索引：EID / DOI / 标题 / 1-based 序号 / url。"""
    idx = {"eid": {}, "doi": {}, "title": {}, "ordinal": {}, "url": {}}
    for i, e in enumerate(entries, 1):
        eid = str(e.get("eid") or "").strip()
        doi = str(e.get("prism:doi") or "").strip()
        title = norm(e.get("dc:title") or "")
        url = str(e.get("prism:url") or "").strip()
        if eid:
            idx["eid"][norm_key(eid)] = e
        if doi:
            idx["doi"][norm_key(doi)] = e
        if title:
            idx["title"][norm_key(title)] = e
        idx["ordinal"][str(i)] = e
        if url:
            idx["url"][norm_key(url)] = e
    return idx


def resolve_paper(pid, idx):
    key = norm_key(pid)
    if key.startswith("eid"):
        key = key[3:]
    for field in ("eid", "doi", "url", "ordinal", "title"):
        if key in idx[field]:
            return idx[field][key]
    return None


def paper_keys(entry):
    eid = str(entry.get("eid") or "").strip()
    doi = str(entry.get("prism:doi") or "").strip()
    title = norm(entry.get("dc:title") or "")
    return eid, doi, title


def find_re(entry, db, evidence):
    """EID → DOI → 标题 查全局库/证据 CSV，返回 [REXXX] 或 ''。"""
    eid, doi, title = paper_keys(entry)
    eid_k = norm_key(eid)
    doi_k = norm_key(doi)
    title_k = norm_key(title)
    for rows in (db, evidence):
        if eid_k and eid_k in rows["eid"]:
            return rows["eid"][eid_k]
        if doi_k and doi_k in rows["doi"]:
            return rows["doi"][doi_k]
        if title_k and title_k in rows["title"]:
            return rows["title"][title_k]
    return ""


def load_re_table(path):
    rows = {"eid": {}, "doi": {}, "title": {}}
    if not path or not os.path.isfile(path):
        return rows
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for r in csv.DictReader(f):
            code = (r.get("编号") or "").strip()
            m = re.search(r"RE(\d+)", code)
            if not m:
                continue
            re_id = f"[RE{m.group(1)}]"
            eid = (r.get("EID") or "").strip()
            doi = (r.get("DOI") or "").strip()
            title = (r.get("标题") or "").strip()
            if eid:
                rows["eid"][norm_key(eid)] = re_id
            if doi:
                rows["doi"][norm_key(doi)] = re_id
            if title:
                rows["title"][norm_key(title)] = re_id
    return rows


def round_dirs(acu_dir):
    out = []
    if not os.path.isdir(acu_dir):
        return out
    for name in os.listdir(acu_dir):
        m = re.match(r"round_(\d+)$", name)
        if m and os.path.isdir(os.path.join(acu_dir, name)):
            out.append((int(m.group(1)), name))
    return sorted(out)


def first_pass_round(acu_dir, per_acu=None):
    """covered ACU 的首个 PASS 轮；无 per_ACU 时用 verdict 内高行自判。"""
    if per_acu and acu_dir in per_acu and per_acu[acu_dir].get("pass_round"):
        return int(per_acu[acu_dir]["pass_round"])
    best = None
    for rn, name in round_dirs(acu_dir):
        vp = os.path.join(acu_dir, name, "verdict.md")
        if os.path.isfile(vp):
            if parse_verdict(read_text(vp)):
                return rn
            best = best or rn
    return best


def main():
    ap = argparse.ArgumentParser(description="段9 9.6 复现筛选 + XE 知识库")
    ap.add_argument("--validation", required=True)
    ap.add_argument("--acu-index", default=None)
    ap.add_argument("--db", default=None)
    ap.add_argument("--evidence", default=None)
    args = ap.parse_args()

    vroot = os.path.abspath(args.validation)
    if not os.path.isdir(vroot):
        sys.exit(f"错误：validation 目录不存在：{vroot}")
    if os.path.isfile(os.path.join(vroot, "loop_a", "transaction.json")):
        sys.exit("错误：LOOP A 提交尚未恢复；先执行 collect。")
    acu_path = args.acu_index or os.path.join(vroot, "acu_index.json")
    if not os.path.isfile(acu_path):
        sys.exit(f"错误：缺 acu_index.json（{acu_path}）。先跑 9.3 生成。")
    acu_index = load_json(acu_path)
    per_acu_path = os.path.join(vroot, "per_ACU_summary.json")
    per_acu = load_json(per_acu_path) if os.path.isfile(per_acu_path) else {}
    loop_state_path = os.path.join(vroot, "loop_state.json")
    loop_state = load_json(loop_state_path) if os.path.isfile(loop_state_path) else {}
    acu_status = loop_state.get("acus", {})

    meta_path = os.path.join(vroot, "metadata.json")
    meta = load_json(meta_path) if os.path.isfile(meta_path) else {}
    active_path = os.path.join(vroot, "loop_a", "active.json")
    active = load_json(active_path) if os.path.isfile(active_path) else {}
    unresolved = [acu for acu in acu_index if
                  acu_status.get(acu, {}).get("status", per_acu.get(acu, {}).get("status"))
                  not in ("covered", "skipped", "merged")]
    if meta.get("gate3_pending") or active.get("phase") == "prepared" or unresolved:
        sys.exit("错误：LOOP A 活动轮或闸门仍有未决 ACU，不能进入9.6。")

    db = load_re_table(args.db)
    evidence = load_re_table(args.evidence)

    # covered ACU 才进入 9.6
    covered = []
    for acu in sorted(acu_index):
        status = acu_status.get(acu, {}).get("status", per_acu.get(acu, {}).get("status"))
        if status == "covered":
            covered.append(acu)
    if not covered:
        sys.exit("错误：没有 covered ACU（loop_state/per_ACU_summary 缺失或不一致）。")

    # 收集首个 PASS 轮全部「高」；同时保持出现顺序用于 XE 稳定签发
    collected = []  # (acu, round, pid, key_steps, integrate, entry)
    for acu in covered:
        acu_dir = os.path.join(vroot, "scopus_runs", acu)
        pass_round = first_pass_round(acu_dir, per_acu) if False else (int(per_acu.get(acu, {}).get("pass_round")) if per_acu.get(acu, {}).get("pass_round") else first_pass_round(acu_dir, per_acu))
        if pass_round is None:
            print(f"[WARN] {acu} 无 verdict 或 PASS 轮，跳过")
            continue
        vp = os.path.join(acu_dir, f"round_{pass_round:02d}", "verdict.md")
        rp = os.path.join(acu_dir, f"round_{pass_round:02d}", "results_raw.json")
        if not os.path.isfile(vp) or not os.path.isfile(rp):
            print(f"[WARN] {acu} round_{pass_round} 缺 verdict/results_raw，跳过")
            continue
        entries = load_json(rp).get("search-results", {}).get("entry", []) or []
        idx = raw_entry_index(entries)
        for pid, _lv, steps, integrate in parse_verdict(read_text(vp)):
            entry = resolve_paper(pid, idx)
            if entry is None:
                print(f"[WARN] {acu} round_{pass_round} 高行无法反查：{pid}")
                continue
            collected.append((acu, pass_round, 
pid, steps, integrate, entry))

    # EID → DOI → 标题去重
    seen = {}
    unique = []
    for acu, pass_round, pid, steps, integrate, entry in collected:
        eid, doi, title = paper_keys(entry)
        key = norm_key(eid) or norm_key(doi) or norm_key(title)
        if not key:
            continue
        if key in seen:
            seen[key]["acus"].add(acu)
            # One paper can support different steps in different ACUs/objects.
            for field, value in (("steps", steps), ("integrate", integrate)):
                if value and value != seen[key][field]:
                    seen[key][field] += f"；[{acu}] {value}"
            continue
        unique.append({"eid": eid, "doi": doi, "title": title,
                       "entry": entry, "steps": steps, "integrate": integrate,
                       "acus": {acu}, "acu_order": len(unique) + 1})
        seen[key] = unique[-1]

    # 按首次出现顺序稳定签发 XE；同文献补 RE
    by_acu_objects = {}
    for acu, info in acu_index.items():
        by_acu_objects[acu] = [o for o in info.get("source_objects", [])]

    filter_rows = []
    kb_rows = []
    for item in unique:
        acus = sorted(item["acus"])
        xe = f"XE{len(kb_rows) + 1:03d}"
        re_tag = find_re(item["entry"], db, evidence)
        label = f"{xe} {re_tag}".strip()
        steps = item["steps"] or (item["entry"].get("dc:description") or "")[:200]
        integrate = item["integrate"] or ""
        source = ", ".join(acus)
        filter_rows.append({
            "文献编号": label, "来源 ACU": source,
            "可复现的关键步骤与参数": steps,
            "可直接整合至我方案的具体步骤": integrate,
        })
        # 题录
        e = item["entry"]
        title = re.sub(r"\s+", " ", html.unescape(str(e.get("dc:title") or ""))).strip()
        year = str(e.get("prism:coverDate") or "")[:4]
        journal = e.get("prism:publicationName") or ""
        abstract = norm(e.get("dc:description") or "") or "（Scopus 响应无摘要）"
        objects = []
        for acu in acus:
            for o in by_acu_objects.get(acu, []):
                if o and o not in objects:
                    objects.append(o)
        if not objects:
            objects = ["_unmapped"]
        kb_rows.append({
            "label": label, "title": title, "eid": item["eid"], "doi": item["doi"],
            "year": year, "journal": journal, "abstract": abstract,
            "source": source, "steps": steps, "integrate": integrate,
            "objects": objects,
        })



    # reproducibility_filter.md
    fp = os.path.join(vroot, "reproducibility_filter.md")
    with open(fp, "w", encoding="utf-8") as f:
        f.write("# 复现筛选（9.6，只含高文献）\n\n")
        f.write("> 去重键：EID → DOI → 标题。中/排除一律不进入。XE = 验证轮本地编号；"
                "已 RE 文献双标注；不新签全局 RE、不追加证据 CSV。\n\n")
        f.write("| " + " | ".join(HEADERS) + " |\n")
        f.write("| " + " | ".join(["---"] * len(HEADERS)) + " |\n")
        for r in filter_rows:
            f.write("| " + " | ".join([r[h].replace("|", "\\|") for h in HEADERS]) + " |\n")

    # knowledge_base/<object>.txt
    kb_dir = os.path.join(vroot, "knowledge_base")
    os.makedirs(kb_dir, exist_ok=True)
    object_pool = sorted({o for r in kb_rows for o in r["objects"]})
    for obj in object_pool:
        op = os.path.join(kb_dir, f"{obj}.txt")
        with open(op, "w", encoding="utf-8") as f:
            f.write(f"# 段9 XE 知识库（{obj}）\n\n")
            f.write("> 只含 9.6 复现筛选后的高文献；9.7 只读本文件。\n\n")
            for r in kb_rows:
                if obj not in r["objects"]:
                    continue
                f.write(f"=== {r['label']} ===\n")
                f.write(f"标题：{r['title']}\n")
                f.write(f"EID：{r['eid']}\n")
                f.write(f"DOI：{r['doi']}\n")
                f.write(f"年份：{r['year']} ｜ 期刊：{r['journal']}\n")
                f.write(f"摘要：{r['abstract']}\n")
                f.write(f"来源 ACU：{r['source']}\n")
                f.write(f"可复现的关键步骤与参数：{r['steps']}\n")
                f.write(f"可直接整合至我方案的具体步骤：{r['integrate']}\n\n")

    # 机器索引（供 check_validation 与 9.7 引用检查）
    ip = os.path.join(vroot, "reproducibility_index.json")
    with open(ip, "w", encoding="utf-8") as f:
        json.dump({
            "covered_acus": covered,
            "entries": [
                {"xe": r["label"].split()[0], "re": (r["label"].split()[1]
                 if len(r["label"].split()) > 1 else ""),
                 "eid": r["eid"], "doi": r["doi"], "title": r["title"],
                 "source_acus": [a.strip() for a in r["source"].split(",")],
                 "objects": r["objects"]}
                for r in kb_rows
            ],
        }, f, ensure_ascii=False, indent=2)

    print(f"covered_acus={len(covered)} unique_high={len(kb_rows)}")
    print(f"filter -> {fp}")
    print(f"knowledge_base -> {kb_dir}（对象：{', '.join(object_pool) or '无'}）")
    return 0


def main_argv(argv):
    import argparse as _ap
    # 复用 main 的 argparse 逻辑不便拆分，直接重放 argv
    old = sys.argv
    sys.argv = ["build_knowledge_base.py"] + list(argv)
    try:
        return main()
    finally:
        sys.argv = old


if __name__ == "__main__":
    sys.exit(main())
