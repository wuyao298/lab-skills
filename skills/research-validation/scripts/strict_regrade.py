#!/usr/bin/env python3
"""段 9 9.4 严格重判：用 check_validation 的判定口径（parse_verdict + 条目反查）重算状态。

与 regrade_state.py 的差异：
  - PASS 判定 = verdict 中存在**级别列（第 2 列）为「高」且论文标识能在本轮 results_raw.json 反查**的行
    （= check_validation.check_step4 的口径，而不是 loop_a_runner.grade_pass 的宽松口径）
  - 保留 gate3 已决议的 skipped / merged 状态
  - per_ACU.rounds_run 按契约写成 int（已跑最大轮号）；fail_rounds = 所有无高行轮次

用法：python strict_regrade.py <validation_root>
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_knowledge_base import (load_json, parse_verdict, raw_entry_index,  # noqa: E402
                                  resolve_paper, read_text)


def round_dirs(acu_dir):
    out = []
    if not os.path.isdir(acu_dir):
        return out
    for name in os.listdir(acu_dir):
        m = re.fullmatch(r"round_(\d+)", name)
        if m and os.path.isdir(os.path.join(acu_dir, name)):
            out.append((int(m.group(1)), name))
    return sorted(out)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    vroot = os.path.abspath(sys.argv[1].rstrip("\\/"))
    acu_index = load_json(os.path.join(vroot, "acu_index.json"))
    loop_state = load_json(os.path.join(vroot, "loop_state.json"))
    per_acu = load_json(os.path.join(vroot, "per_ACU_summary.json"))

    covered, open_acus = [], []
    for acu in sorted(acu_index):
        adir = os.path.join(vroot, "scopus_runs", acu)
        rounds = round_dirs(adir)
        status_prev = loop_state.get("acus", {}).get(acu, {}).get("status")
        if status_prev in ("skipped", "merged"):
            print(f"  [KEEP] {acu}: {status_prev}")
            continue
        round_ok = {}
        last_total = 0
        for rn, name in rounds:
            vp = os.path.join(adir, name, "verdict.md")
            rp = os.path.join(adir, name, "results_raw.json")
            entries = []
            if os.path.isfile(rp):
                data = load_json(rp)
                entries = (data.get("search-results") or {}).get("entry") or []
                try:
                    last_total = int((data.get("search-results") or {}).get("opensearch:totalResults", 0) or 0)
                except Exception:
                    last_total = 0
            idx = raw_entry_index(entries)
            n_high = 0
            if os.path.isfile(vp):
                for pid, _lv, _s, _i in parse_verdict(read_text(vp)):
                    if resolve_paper(pid, idx) is not None:
                        n_high += 1
            round_ok[rn] = n_high > 0
        pass_round = next((rn for rn, ok in sorted(round_ok.items()) if ok), None)
        fails = [rn for rn, ok in sorted(round_ok.items()) if not ok]
        status = "covered" if pass_round else "open"
        max_round = max(round_ok) if round_ok else 0
        ls = loop_state["acus"].setdefault(acu, {})
        ls.update({
            "status": status,
            "pass_round": pass_round,
            "merged_into": ls.get("merged_into"),
            "consecutive_fails": 0 if pass_round else len(fails),
            "last_total_results": last_total,
        })
        if acu in acu_index:
            ls.setdefault("query", acu_index[acu].get("query"))
        pa = per_acu.setdefault(acu, {})
        pa.update({
            "status": status,
            "pass_round": pass_round,
            "consecutive_fails": 0 if pass_round else len(fails),
            "rounds_run": max_round,
            "fail_rounds": fails,
        })
        if pass_round:
            covered.append(acu)
        else:
            open_acus.append(acu)
        print(f"  [{'PASS' if pass_round else 'OPEN'}] {acu}: rounds={sorted(round_ok)} "
              f"pass_round={pass_round} fails={fails} total={last_total}")

    loop_state["round"] = max([max(round_dirs(os.path.join(vroot, "scopus_runs", a)), key=lambda x: x[0])[0]
                               for a in acu_index
                               if round_dirs(os.path.join(vroot, "scopus_runs", a))] or [0])
    per_acu.setdefault("_meta", {})["round"] = loop_state["round"]
    with open(os.path.join(vroot, "loop_state.json"), "w", encoding="utf-8") as f:
        json.dump(loop_state, f, ensure_ascii=False, indent=2)
    with open(os.path.join(vroot, "per_ACU_summary.json"), "w", encoding="utf-8") as f:
        json.dump(per_acu, f, ensure_ascii=False, indent=2)
    print(f"\n[done] round={loop_state['round']} covered={len(covered)} open={len(open_acus)}"
          f"{' → ' + ', '.join(open_acus) if open_acus else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
