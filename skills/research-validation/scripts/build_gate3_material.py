#!/usr/bin/env python3
"""段 9 9.5 闸门3 材料生成（机械部分）。

对每个触发闸门3 的 ACU（consecutive_fails ≥ 2，或显式 --acu）预生成：
  当前 query / totalResults / 前 20 条标题+摘要 / verdict 级别统计 / verdict 自带后续建议 /
  策略菜单（策略一/策略三 备选 query）/ 合并候选（同阶段或名称近邻）/ 跳过风险。

输出：
  <validation>/gate3_material.json   （机器可读，供闸门3 决策与后续脚本）
  <validation>/gate3_material.md     （人读材料，用户裁决用）

用法：
  python build_gate3_material.py --validation <vroot> [--acu ACU-002 --acu ACU-008 ...]
      [--min-fails 2] [--suggestions <suggestions.json>]
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_knowledge_base import (load_json, norm, parse_table, raw_entry_index,  # noqa: E402
                                  read_text)


def round_dirs(acu_dir):
    out = []
    if not os.path.isdir(acu_dir):
        return out
    for name in os.listdir(acu_dir):
        m = re.fullmatch(r"round_(\d+)", name)
        if m and os.path.isdir(os.path.join(acu_dir, name)):
            out.append(int(m.group(1)))
    return sorted(out)


def last_round(acu_dir):
    rs = round_dirs(acu_dir)
    return rs[-1] if rs else None


def level_stats(verdict_text):
    st = {"高": 0, "中": 0, "建议排除": 0, "其他": 0}
    for cells in parse_table(verdict_text):
        if len(cells) < 2:
            continue
        lv = cells[1].strip().strip("*` ")
        if lv in st:
            st[lv] += 1
        else:
            st["其他"] += 1
    return st


def verdict_tail(verdict_text):
    """抓 verdict 末尾「结论与后续动作 / 调整方向」段落。"""
    m = re.search(r"##\s*结论与后续动作(.*)$", verdict_text, re.DOTALL)
    if m:
        return m.group(1).strip()[:2000]
    m = re.search(r"##\s*后续.*?(?=\n##|\Z)(.*)$", verdict_text, re.DOTALL)
    return m.group(1).strip()[:2000] if m else ""


def strategy_menu(ss_text, acu):
    """从 search_strategies.md 抽该 ACU 的三条策略 query。"""
    m = re.search(rf"^##\s*{re.escape(acu)}\b(.*?)(?=^##\s*ACU-\d{{3}}|\Z)", ss_text,
                  re.DOTALL | re.MULTILINE)
    if not m:
        return {}
    sec = m.group(0)
    out = {}
    parts = re.split(r"(策略[一二三])[：:]", sec)
    for i in range(1, len(parts) - 1, 2):
        name, body = parts[i], parts[i + 1]
        q = re.search(r"`(TITLE-ABS-KEY\([^`]+\))`", body)
        if q:
            out[name] = q.group(1)
    return out


def merge_candidates(acu_index, acu):
    """同阶段 ACU + 名称关键词重叠的 ACU，作为合并候选。"""
    me = acu_index[acu]
    out = []
    for other, info in acu_index.items():
        if other == acu:
            continue
        same_stage = info.get("stage") == me.get("stage")
        n1 = set(re.findall(r"[\u4e00-\u9fff]{2,}", me.get("name", "")))
        n2 = set(re.findall(r"[\u4e00-\u9fff]{2,}", info.get("name", "")))
        overlap = n1 & n2
        if same_stage or overlap:
            out.append({"acu": other, "name": info.get("name"), "stage": info.get("stage"),
                        "same_stage": same_stage, "name_overlap": sorted(overlap)[:5]})
    return out[:5]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validation", required=True)
    ap.add_argument("--acu", action="append", default=[])
    ap.add_argument("--min-fails", type=int, default=2)
    ap.add_argument("--suggestions", default=None, help="ep3-prompt2 建议的 JSON（ACU→{query,reason}）")
    args = ap.parse_args()

    vroot = os.path.abspath(args.validation)
    acu_index = load_json(os.path.join(vroot, "acu_index.json"))
    loop_state = load_json(os.path.join(vroot, "loop_state.json"))
    ss_text = read_text(os.path.join(vroot, "search_strategies.md"))
    sugg = load_json(args.suggestions) if args.suggestions and os.path.isfile(args.suggestions) else {}

    triggered = []
    for acu, info in acu_index.items():
        st = loop_state.get("acus", {}).get(acu, {})
        if args.acu:
            if acu in args.acu:
                triggered.append(acu)
        elif st.get("status") == "open" and st.get("consecutive_fails", 0) >= args.min_fails:
            triggered.append(acu)
    triggered.sort()

    material = {"triggered_acus": triggered, "min_fails": args.min_fails, "acus": {}}
    md = ["# 闸门3 材料（9.5）", "",
          f"> 触发 ACU：{', '.join(triggered) if triggered else '无'}"
          f"（连续 FAIL ≥ {args.min_fails} 轮；用户逐 ACU 四选一 a/b/c/d）", ""]

    for acu in triggered:
        adir = os.path.join(vroot, "scopus_runs", acu)
        rn = last_round(adir)
        rp = os.path.join(adir, f"round_{rn:02d}", "results_raw.json") if rn else ""
        vp = os.path.join(adir, f"round_{rn:02d}", "verdict.md") if rn else ""
        total, entries = 0, []
        if rp and os.path.isfile(rp):
            data = load_json(rp)
            sr = data.get("search-results") or {}
            try:
                total = int(sr.get("opensearch:totalResults", 0) or 0)
            except Exception:
                total = 0
            entries = sr.get("entry") or []
        vtext = read_text(vp) if vp and os.path.isfile(vp) else ""
        stats = level_stats(vtext) if vtext else {}
        tail = verdict_tail(vtext) if vtext else ""
        st = loop_state.get("acus", {}).get(acu, {})
        item = {
            "name": acu_index[acu].get("name"),
            "stage": acu_index[acu].get("stage"),
            "source_objects": acu_index[acu].get("source_objects"),
            "status": st.get("status"),
            "consecutive_fails": st.get("consecutive_fails"),
            "last_round": rn,
            "current_query": st.get("query") or acu_index[acu].get("query"),
            "total_results": total,
            "first_20": [
                {
                    "n": i,
                    "eid": e.get("eid", ""),
                    "title": norm(e.get("dc:title") or ""),
                    "year": (e.get("prism:coverDate") or "")[:4],
                    "journal": e.get("prism:publicationName") or "",
                    "abstract": norm((e.get("dc:description") or ""))[:400],
                }
                for i, e in enumerate(entries[:20], 1)
            ],
            "verdict_levels": stats,
            "verdict_tail": tail,
            "strategy_menu": strategy_menu(ss_text, acu),
            "merge_candidates": merge_candidates(acu_index, acu),
            "suggested_query": (sugg.get(acu) or {}).get("query", ""),
            "suggested_reason": (sugg.get(acu) or {}).get("reason", ""),
        }
        material["acus"][acu] = item

        md += [f"## {acu} {item['name']}", "",
               f"- 阶段：{item['stage']} ｜ 状态：{item['status']} ｜ 连续 FAIL：{item['consecutive_fails']}"
               f" ｜ 最近轮次：round_{rn:02d}",
               f"- 当前 query（策略二·实现优先）：`{item['current_query']}`",
               f"- totalResults：**{total}**（首页 {len(entries)} 条）",
               f"- verdict 级别统计：{stats}",
               ""]
        if item["suggested_query"]:
            md += ["**ep3-prompt2 建议的新 query**：", f"`{item['suggested_query']}`", "",
                   f"理由：{item['suggested_reason']}", ""]
        if item["strategy_menu"]:
            md += ["**策略菜单备选（9.3 已生成，可直接切换）**：", ""]
            for k in ("策略一", "策略二", "策略三"):
                if k in item["strategy_menu"]:
                    md.append(f"- {k}：`{item['strategy_menu'][k]}`")
            md.append("")
        if item["merge_candidates"]:
            md += ["**合并候选**：", ""]
            for c in item["merge_candidates"]:
                md.append(f"- {c['acu']} {c['name']}（{c['stage']}"
                          f"{'，同阶段' if c['same_stage'] else ''}"
                          f"{'，名称重叠：' + '/'.join(c['name_overlap']) if c['name_overlap'] else ''}）")
            md.append("")
        md += ["**前 20 条（标题 ｜ 年 ｜ 期刊 ｜ EID）**：", ""]
        for e in item["first_20"]:
            md.append(f"{e['n']}. {e['title'][:150]} ｜ {e['year']} ｜ {e['journal'][:40]} ｜ {e['eid']}")
        md.append("")
        if tail:
            md += ["**verdict 自带的后续建议（原文摘录）**：", "", tail, ""]
        md += ["**跳过风险（c 选项）**：该 ACU 对应的 MVE 步骤将失去实现锚点文献支撑，"
               "9.7 仍会细化但必须显式标注「实现锚点缺失」，参数只能按通用实践给并写核实声明。", "",
               "**决策（待用户填）**：□ a 改 query ｜ □ b 合并到 ____ ｜ □ c 跳过 ｜ □ d 重写策略", "",
               "---", ""]

    with open(os.path.join(vroot, "gate3_material.json"), "w", encoding="utf-8") as f:
        json.dump(material, f, ensure_ascii=False, indent=2)
    with open(os.path.join(vroot, "gate3_material.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"triggered={triggered}")
    print(f"-> {os.path.join(vroot, 'gate3_material.json')}")
    print(f"-> {os.path.join(vroot, 'gate3_material.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
