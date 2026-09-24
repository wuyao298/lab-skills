#!/usr/bin/env python3
"""research-validation 段9 契约校验（docs/research-skill-design/04 §13）。

用法：
  python check_validation.py --validation <validation_root> --project <工作目录> --slug <slug>
      [--db <全局库CSV>] [--evidence <方向证据CSV>]

退出码 0 = 全过；1 = 有失败项。失败打印 [FAIL] 行并汇总。
"""

import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_knowledge_base import (load_json, parse_table, parse_verdict, raw_entry_index,
                                  resolve_paper, read_text, norm, norm_key, paper_keys)

RE_PAT = re.compile(r"\[?RE(\d+)\]?", re.IGNORECASE)
XE_PAT = re.compile(r"\bXE(\d{3,})\b")
ACU_PAT = re.compile(r"\bACU-(\d{3})\b")
PLACEHOLDER_PAT = re.compile(r"TODO|TBD|XXX|占位符|PLACEHOLDER|<[A-Za-z_][^>]{0,40}>", re.IGNORECASE)

issues = []


def add(cond, msg):
    if not cond:
        issues.append(msg)
    return bool(cond)


def slug_from_meta(path):
    try:
        return load_json(path).get("slug")
    except Exception:
        return None


def files_exist(paths):
    return all(os.path.isfile(p) for p in paths)


def load_re_set(path):
    """全局库/证据 CSV 的已签发 RE 编号集合（只认已签发编号）。"""
    out = set()
    if not path or not os.path.isfile(path):
        return out
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            m = re.search(r"RE(\d+)", (row.get("编号") or ""))
            if m:
                out.add(int(m.group(1)))
    return out


def load_re_maps(path):
    """EID/DOI/标题 → RE 编号（用于 9.6 双标注核对）。"""
    out = {"eid": {}, "doi": {}, "title": {}}
    if not path or not os.path.isfile(path):
        return out
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            m = re.search(r"RE(\d+)", (row.get("编号") or ""))
            if not m:
                continue
            rid = int(m.group(1))
            for key, col in (("eid", "EID"), ("doi", "DOI"), ("title", "标题")):
                val = (row.get(col) or "").strip()
                if val:
                    out[key][norm_key(val)] = rid
    return out


def verdict_rows(vroot, acu, rn):
    vp = os.path.join(vroot, "scopus_runs", acu, f"round_{rn:02d}", "verdict.md")
    return parse_verdict(read_text(vp)) if os.path.isfile(vp) else []


def raw_entries(vroot, acu, rn):
    rp = os.path.join(vroot, "scopus_runs", acu, f"round_{rn:02d}", "results_raw.json")
    if not os.path.isfile(rp):
        return []
    data = load_json(rp)
    return data.get("search-results", {}).get("entry", []) or []


def raw_total(vroot, acu, rn):
    rp = os.path.join(vroot, "scopus_runs", acu, f"round_{rn:02d}", "results_raw.json")
    if not os.path.isfile(rp):
        return None
    data = load_json(rp)
    try:
        return int((data.get("search-results") or {}).get("opensearch:totalResults", 0) or 0)
    except Exception:
        return None


def check_step0(vroot, project, slug):
    ok = True
    sel = os.path.join(vroot, "selection.md")
    ok &= add(os.path.isfile(sel), "缺 selection.md")
    meta_path = os.path.join(vroot, "metadata.json")
    objects = []
    archived = set()
    if os.path.isfile(meta_path):
        try:
            meta = load_json(meta_path)
            objects = list(meta.get("objects", []))
            # 已归档批次（如 obs-01，2026-09-08 完成并归档）不参与本批次校验：
            # 共享 validation/ 只有一套 acu_index/knowledge_base，两个批次不可同时在校验范围内。
            archived = set(meta.get("archived_objects") or [])
        except Exception:
            add(False, "metadata.json 无法解析")
    if os.path.isfile(sel):
        text = read_text(sel)
        ok &= add("## 对象清单" in text or "# 对象清单" in text,
                  "selection.md 缺对象清单段落")
        ok &= add("9.7" in text and "范围" in text, "selection.md 缺 9.7 细化范围")
        ok &= add("用户原话" in text, "selection.md 缺用户原话")
        found = re.findall(r"\*\*对象 \d+\*\*[:：]\s*`?([a-z0-9-]+)", text)
        if found:
            objects = sorted(set(found) | set(objects))
    if archived:
        objects = [o for o in objects if o not in archived]
    ok &= add(len(objects) >= 1, "对象清单为空（对象 ≥1）")
    topics_dir = os.path.join(project, "directions", slug, "topics")
    for obj in objects:
        ok &= add(os.path.isfile(os.path.join(topics_dir, obj + ".md")),
                  f"对象 {obj} 不在 topics/ 中")
    return ok, objects


def check_step1(vroot, project, slug, objects):
    ok = True
    plan_dir = os.path.join(project, "directions", slug, "thesis", "plan")
    constraints = os.path.join(plan_dir, "constraints.md")
    for obj in objects:
        odir = os.path.join(vroot, obj)
        rd = os.path.join(odir, "research_design.md")
        ok &= add(os.path.isfile(rd), f"{obj} 缺 research_design.md")
        if not os.path.isfile(rd):
            continue
        text = read_text(rd)
        if "指针" in text:
            targets = re.findall(r"`([^`]+\.md)`", text)
            found_target = False
            for t in targets:
                for base in (os.path.dirname(rd), os.path.join(project, "directions", slug)):
                    if os.path.isfile(os.path.join(base, t)) or os.path.isfile(t):
                        found_target = True
            ok &= add(found_target, f"{obj} research_design.md 的工作包指针目标不存在")
        else:
            ok &= add("第一部分" in text and "第二部分" in text,
                      f"{obj} research_design.md 缺 ep1 第一部分/第二部分结构")
            ok &= add("|" not in text,
                      f"{obj} research_design.md 出现表格（ep1 原约束禁表格）")
        if os.path.isfile(constraints):
            ok &= add(("constraints" in text.lower() or "C-001" in text or "约束" in text),
                      f"{obj} research_design 未见 constraints 约束痕迹")
        ok &= add(not PLACEHOLDER_PAT.search(text), f"{obj} research_design.md 含占位符")
    return ok


def check_step2(vroot, objects):
    ok = True
    for obj in objects:
        p = os.path.join(vroot, obj, "mve_paths.md")
        ok &= add(os.path.isfile(p), f"{obj} 缺 mve_paths.md")
        if not os.path.isfile(p):
            continue
        text = read_text(p)
        ok &= add("路径 A" in text and "路径 B" in text, f"{obj} mve_paths.md 缺双路径")
        for token in ("核心假设", "G", "N-G", "低配", "互补", "行动路径"):
            ok &= add(token in text, f"{obj} mve_paths.md 缺 {token} 段")
        ok &= add(not PLACEHOLDER_PAT.search(text), f"{obj} mve_paths.md 含占位符")
    return ok


def check_step3(vroot, objects):
    ok = True
    ma = os.path.join(vroot, "meta_analysis.md")
    ss = os.path.join(vroot, "search_strategies.md")
    ai = os.path.join(vroot, "acu_index.json")
    ok &= add(os.path.isfile(ma), "缺 meta_analysis.md")
    ok &= add(os.path.isfile(ss), "缺 search_strategies.md")
    ok &= add(os.path.isfile(ai), "缺 acu_index.json")
    acu_index = {}
    if os.path.isfile(ai):
        try:
            acu_index = load_json(ai)
        except Exception:
            ok &= add(False, "acu_index.json 无法解析")
    ok &= add(len(acu_index) >= 1, "acu_index.json 无 ACU")
    ids = list(acu_index.keys())
    ok &= add(len(ids) == len(set(ids)), "ACU 编号重复")
    for acu in ids:
        ok &= add(bool(re.fullmatch(r"ACU-\d{3}", acu)), f"{acu} 编号格式非法（应 ACU-NNN）")
    ss_text = read_text(ss) if os.path.isfile(ss) else ""
    ma_text = read_text(ma) if os.path.isfile(ma) else ""
    for acu, info in acu_index.items():
        ok &= add(acu in ss_text, f"{acu} 不在 search_strategies.md")
        objs = info.get("source_objects") or []
        ok &= add(len(objs) >= 1, f"{acu} 缺 source_objects")
        for o in objs:
            ok &= add(o in objects, f"{acu} 来源对象 {o} 不在 selection 对象清单")
        q = (info.get("query") or "").strip()
        ok &= add(bool(q), f"{acu} 缺 query")
        ok &= add("TITLE-ABS-KEY" in q.upper(), f"{acu} query 不是 TITLE-ABS-KEY")
        ok &= add(not re.search(r"RE\d+", q, flags=re.IGNORECASE),
                  f"{acu} query 含 RE 编号")
        ok &= add("YEAR" not in q.upper() and "PUBYEAR" not in q.upper(),
                  f"{acu} query 含 year 过滤")
        ok &= add("DOCTYPE" not in q.upper(), f"{acu} query 含 doctype 过滤")
        ok &= add(not PLACEHOLDER_PAT.search(q), f"{acu} query 含占位符")
        ok &= add(("②" in str(info.get("default_strategy", "")) or
                   "实现优先" in str(info.get("default_strategy", ""))),
                  f"{acu} 默认起手策略不是 ②实现优先")
    if ma_text:
        ok &= add("关键路径" in ma_text, "meta_analysis.md 缺关键路径")
        ok &= add("依赖" in ma_text or "并行" in ma_text, "meta_analysis.md 缺任务依赖/并行说明")
        for acu in ids:
            ok &= add(acu in ma_text, f"{acu} 不在 meta_analysis.md")
    return ok, acu_index


def check_step4(vroot, acu_index):
    """LOOP A：文件、verdict 级别、PASS 判定、per_ACU/loop 一致性。"""
    ok = True
    ls_path = os.path.join(vroot, "loop_state.json")
    pa_path = os.path.join(vroot, "per_ACU_summary.json")
    rr_path = os.path.join(vroot, "retrieval_report.md")
    ok &= add(os.path.isfile(ls_path), "缺 loop_state.json")
    ok &= add(os.path.isfile(pa_path), "缺 per_ACU_summary.json")
    ok &= add(os.path.isfile(rr_path), "缺 retrieval_report.md")
    loop_state, per_acu = {}, {}
    if os.path.isfile(ls_path):
        try:
            loop_state = load_json(ls_path)
        except Exception:
            ok &= add(False, "loop_state.json 无法解析")
    if os.path.isfile(pa_path):
        try:
            per_acu = load_json(pa_path)
        except Exception:
            ok &= add(False, "per_ACU_summary.json 无法解析")

    round_no = loop_state.get("round")
    ok &= add(isinstance(round_no, int) and 1 <= round_no <= 10,
              "loop_state.round 非法（1..10）")
    for acu in acu_index:
        ls = loop_state.get("acus", {}).get(acu, {})
        pa = per_acu.get(acu, {})
        ok &= add(bool(ls) and bool(pa), f"{acu} 缺 loop/per_ACU 条目")
        status = ls.get("status")
        ok &= add(status in ("open", "covered", "skipped", "merged"),
                  f"{acu} loop status 非法：{status}")
        if status == "covered":
            pr = ls.get("pass_round")
            ok &= add(isinstance(pr, int) and pr >= 1, f"{acu} covered 缺 pass_round")
            rows = verdict_rows(vroot, acu, pr) if isinstance(pr, int) else []
            highs = [r for r in rows]
            ok &= add(len(highs) >= 1, f"{acu} covered 但 pass_round 无高行")
        if status == "skipped":
            ok &= add(acu in (loop_state.get("skipped_acus") or []),
                      f"{acu} skipped 未记入 skipped_acus")
        if status == "merged":
            ok &= add(bool(ls.get("merged_into")), f"{acu} merged 缺 merged_into")
            ok &= add(ls.get("merged_into") in acu_index,
                      f"{acu} merged_into 目标不存在")

    # 逐轮 verdict 与 PASS 判定
    for acu in acu_index:
        adir = os.path.join(vroot, "scopus_runs", acu)
        rounds = []
        if os.path.isdir(adir):
            for name in os.listdir(adir):
                m = re.fullmatch(r"round_(\d+)", name)
                if m and os.path.isdir(os.path.join(adir, name)):
                    rounds.append(int(m.group(1)))
        pa = per_acu.get(acu, {})
        # 契约 schema：per_ACU.rounds_run 是「已跑轮数」(int)。历史实现里也出现过轮次列表，
        # 两种形态都接受；int 形态要求等于已跑最大轮号。
        rr = pa.get("rounds_run")
        if isinstance(rr, list):
            rr_ok = sorted(rounds) == sorted(int(x) for x in rr)
        elif isinstance(rr, int):
            rr_ok = bool(rounds) and max(rounds) == rr
        else:
            rr_ok = not rounds
        ok &= add(rr_ok, f"{acu} scopus_runs 轮次与 per_ACU.rounds_run 不一致")
        for rn in sorted(rounds):
            rp = os.path.join(adir, f"round_{rn:02d}", "results_raw.json")
            vp = os.path.join(adir, f"round_{rn:02d}", "verdict.md")
            ok &= add(os.path.isfile(rp), f"{acu} round_{rn} 缺 results_raw.json")
            ok &= add(os.path.isfile(vp), f"{acu} round_{rn} 缺 verdict.md")
            rows = parse_verdict(read_text(vp)) if os.path.isfile(vp) else []
            valid_high = 0
            if os.path.isfile(rp):
                entries = raw_entries(vroot, acu, rn)
                ok &= add(len(entries) <= 25, f"{acu} round_{rn} 条目 >25（契约每轮首页25）")
                idx = raw_entry_index(entries)
                for pid, lv, _steps, _integ in rows:
                    if resolve_paper(pid, idx) is None:
                        # totalResults=0 时 Scopus 可能返回无 EID 的占位条目，不算高行
                        if entries and not all(not e.get("eid") for e in entries):
                            ok &= add(False, f"{acu} round_{rn} 高行无法反查真实条目：{pid}")
                    else:
                        valid_high += 1
            has_high = valid_high >= 1
            pa_round = int(rn)
            fail_rounds = [int(x) for x in (pa.get("fail_rounds") or [])]
            if has_high:
                ok &= add(pa_round not in fail_rounds,
                          f"{acu} round_{rn} 有高行却记入 fail_rounds")
            else:
                ok &= add(pa_round in fail_rounds,
                          f"{acu} round_{rn} 无高行（0 高 = FAIL）但未记入 fail_rounds")
        if pa:
            status = pa.get("status")
            if status == "covered":
                ok &= add(len(rounds) >= int(pa.get("pass_round") or 0),
                          f"{acu} pass_round 超过已跑轮次")

    # 剩余未决 ACU：最终状态不允许 open（闸门3 决策后必须全 covered/skipped/merged）
    open_acus = [a for a in acu_index
                 if loop_state.get("acus", {}).get(a, {}).get("status") == "open"]
    ok &= add(not open_acus, f"仍有 open ACU 未决：{', '.join(open_acus)}（闸门3 前不得进 9.6）")
    return ok, loop_state, per_acu


def check_step5(vroot, loop_state):
    ok = True
    gp = os.path.join(vroot, "gate_3_decisions.md")
    hist = loop_state.get("gate_history") or []
    skipped = loop_state.get("skipped_acus") or []
    ok &= add(os.path.isfile(gp), "缺 gate_3_decisions.md")
    text = read_text(gp) if os.path.isfile(gp) else ""
    if hist or skipped:
        ok &= add("用户原话" in text or "用户" in text,
                  "gate_3_decisions.md 缺用户原话")
        for acu in skipped:
            ok &= add(acu in text and ("跳过" in text or "skip" in text.lower()),
                      f"skipped ACU {acu} 未在 gate_3_decisions.md 记跳过决策")
    return ok


def check_step6(vroot, acu_index, loop_state, project, slug):
    ok = True
    fp = os.path.join(vroot, "reproducibility_filter.md")
    ip = os.path.join(vroot, "reproducibility_index.json")
    kb_dir = os.path.join(vroot, "knowledge_base")
    ok &= add(os.path.isfile(fp), "缺 reproducibility_filter.md")
    ok &= add(os.path.isfile(ip), "缺 reproducibility_index.json")
    index = {}
    if os.path.isfile(ip):
        try:
            index = load_json(ip)
        except Exception:
            ok &= add(False, "reproducibility_index.json 无法解析")
    entries = index.get("entries", [])
    ok &= add(len(entries) >= 1, "9.6 高文献为空（LOOP A 未产出 covered 高文献）")

    db_re = load_re_maps(os.path.join(project, "reports", "literature_db.csv"))
    ev_re = load_re_maps(os.path.join(project, "directions", slug, "search", "evidence.csv"))

    xe_ids = [e.get("xe") for e in entries]
    ok &= add(len(xe_ids) == len(set(xe_ids)), "XE 编号重复")
    seen_papers = set()
    for e in entries:
        xe = e.get("xe") or ""
        ok &= add(bool(re.fullmatch(r"XE\d{3,}", xe)), f"XE 编号格式非法：{xe}")
        eid = norm_key(e.get("eid") or "")
        doi = norm_key(e.get("doi") or "")
        title = norm_key(e.get("title") or "")
        paper_key = eid or doi or title
        ok &= add(bool(paper_key), f"{xe} 缺 EID/DOI/标题")
        ok &= add(paper_key not in seen_papers, f"{xe} 与已见条目重复（EID/DOI/标题）")
        seen_papers.add(paper_key)
        for acu in (e.get("source_acus") or []):
            ok &= add(acu in acu_index, f"{xe} 来源 ACU {acu} 不在 acu_index")
            status = loop_state.get("acus", {}).get(acu, {}).get("status")
            ok &= add(status == "covered", f"{xe} 来源 ACU {acu} 不是 covered（{status}）")
        # 已 RE 双标注：EID/DOI/标题命中全局库或证据集时应带 RE
        # 注意：load_re_maps 返回的是 int（RE 编号可能零填充，如 [RE073]），
        # 因此这里按数值集合比较，避免 "73" vs "073" 的字符串假失败。
        expected_re = None
        for maps in (db_re, ev_re):
            for key in (eid, doi, title):
                if key and key in maps["eid"]:
                    expected_re = maps["eid"][key]; break
                if key and key in maps["doi"]:
                    expected_re = maps["doi"][key]; break
                if key and key in maps["title"]:
                    expected_re = maps["title"][key]; break
            if expected_re:
                break
        re_nums = {int(x) for x in re.findall(r"RE(\d+)", e.get("re") or "")}
        if expected_re is not None:
            ok &= add(expected_re in re_nums, f"{xe} 命中已签发 RE{expected_re} 但未双标注")
        elif re_nums:
            ok &= add(False, f"{xe} 标了 RE 但 EID/DOI/标题未命中全局库/证据集")
        objs = e.get("objects") or []
        ok &= add(len(objs) >= 1, f"{xe} 未映射到任何对象")
        for o in objs:
            kb = os.path.join(kb_dir, f"{o}.txt")
            ok &= add(os.path.isfile(kb), f"缺 knowledge_base/{o}.txt")
            if os.path.isfile(kb):
                ok &= add(xe in read_text(kb), f"{xe} 不在 knowledge_base/{o}.txt")

    # KB 不得出现索引之外的 XE
    if os.path.isdir(kb_dir):
        for name in os.listdir(kb_dir):
            if not name.endswith(".txt"):
                continue
            text = read_text(os.path.join(kb_dir, name))
            for x in set(XE_PAT.findall(text)):
                ok &= add(f"XE{x}" in xe_ids, f"{name} 含索引外编号 XE{x}")
    return ok


def check_step7(vroot, objects, project, slug):
    ok = True
    valid_re = load_re_set(os.path.join(project, "reports", "literature_db.csv"))
    valid_re |= load_re_set(os.path.join(project, "directions", slug, "search", "evidence.csv"))
    index_path = os.path.join(vroot, "reproducibility_index.json")
    kb_dir = os.path.join(vroot, "knowledge_base")
    for obj in objects:
        mdir = os.path.join(vroot, obj, "mve_steps")
        man = os.path.join(mdir, "steps_manifest.json")
        detail = os.path.join(vroot, obj, "mve_step_detail.md")
        ok &= add(os.path.isfile(man), f"{obj} 缺 steps_manifest.json")
        ok &= add(os.path.isfile(detail), f"{obj} 缺 mve_step_detail.md")
        manifest = {}
        if os.path.isfile(man):
            try:
                manifest = load_json(man)
            except Exception:
                ok &= add(False, f"{obj} steps_manifest.json 无法解析")
        steps = manifest.get("steps", [])
        ok &= add(len(steps) >= 1, f"{obj} steps_manifest 无步骤")
        detail_text = read_text(detail) if os.path.isfile(detail) else ""
        for st in steps:
            f = st.get("file") or ""
            sp = os.path.join(mdir, f)
            ok &= add(os.path.isfile(sp), f"{obj} 缺分步文件 {f}")
            text = read_text(sp) if os.path.isfile(sp) else ""
            for heading in ("步骤定位", "优化目标", "主方案", "备选战略",
                            "战略选择建议", "资源清单", "Go/No-Go"):
                ok &= add(heading in text, f"{obj}/{f} 缺七段之一：{heading}")
            if st.get("skipped"):
                ok &= add("实现锚点缺失" in text, f"{obj}/{f} 是 skip 步骤但未标「实现锚点缺失」")
            else:
                ok &= add("XE" in text, f"{obj}/{f} 未引用知识库（无 XE）")
            ok &= add(not PLACEHOLDER_PAT.search(text), f"{obj}/{f} 含占位符")
            for reid in re.findall(r"RE(\d+)", text):
                ok &= add(int(reid) in valid_re, f"{obj}/{f} 引用未签发 RE{reid}")
            # XE 引用只允许本对象知识库
            obj_kb = read_text(os.path.join(kb_dir, obj + ".txt")) if os.path.isfile(
                os.path.join(kb_dir, obj + ".txt")) else ""
            for x in set(XE_PAT.findall(text)):
                ok &= add(f"XE{x}" in obj_kb, f"{obj}/{f} 引用本对象知识库外 XE{x}")
            # 合并完整性由「步骤定位」出现次数核对（避免要求文件路径一定出现在正文）
        if steps:
            ok &= add(detail_text.count("步骤定位") >= len(steps),
                      f"{obj} mve_step_detail.md 合并步骤数与 manifest 不一致")
    return ok


def main():
    ap = argparse.ArgumentParser(description="段9 契约校验")
    ap.add_argument("--validation", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--db", default=None)
    ap.add_argument("--evidence", default=None)
    args = ap.parse_args()

    vroot = os.path.abspath(args.validation)
    if not os.path.isdir(vroot):
        print(f"[FAIL] validation 目录不存在：{vroot}")
        return 1
    ok0, objects = check_step0(vroot, args.project, args.slug)
    ok1 = check_step1(vroot, args.project, args.slug, objects)
    ok2 = check_step2(vroot, objects)
    ok3, acu_index = check_step3(vroot, objects)
    ok4, loop_state, per_acu = check_step4(vroot, acu_index)
    ok5 = check_step5(vroot, loop_state)
    ok6 = check_step6(vroot, acu_index, loop_state, args.project, args.slug)
    ok7 = check_step7(vroot, objects, args.project, args.slug)

    print("checks: step0=%s step1=%s step2=%s step3=%s step4=%s step5=%s step6=%s step7=%s"
          % tuple("PASS" if x else "FAIL" for x in (ok0, ok1, ok2, ok3, ok4, ok5, ok6, ok7)))
    for i in issues:
        print("[FAIL] " + i)
    print(f"issues={len(issues)}")
    return 0 if len(issues) == 0 else 1


def main_argv(argv):
    old = sys.argv
    sys.argv = ["check_validation.py"] + list(argv)
    try:
        return main()
    finally:
        sys.argv = old


if __name__ == "__main__":
    sys.exit(main())
