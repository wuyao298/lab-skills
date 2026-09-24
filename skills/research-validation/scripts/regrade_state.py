#!/usr/bin/env python3
"""段 9 9.4 状态修正：按新 grade_pass 重判每个 verdict.md（round 01 + round 02），
更新 loop_state.json + per_ACU_summary.json 的 pass_round / status / consecutive_fails。

逻辑：取每个 ACU 最早出现 ≥1 高 的轮次为 pass_round，标 covered；其余轮次为 fail。
"""
import json
import os
import re
import sys


def grade_pass(text: str) -> bool:
    high_count = 0
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0].startswith("论文") or cells[0].startswith("编号"):
            continue
        if set(cells[0]) == {"-"} or set(cells[0]) == {":"}:
            continue
        if len(cells) >= 2 and cells[1] == "高":
            high_count += 1
            continue
        if any(("高" == c.strip() or "高优先级" in c) for c in cells):
            high_count += 1
            continue
    return high_count > 0


def parse_total(text: str) -> int:
    m = re.search(r"opensearch:totalResults[\"']?\s*[:=]\s*(\d+)", text)
    if m:
        return int(m.group(1))
    return 0


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    base_dir = sys.argv[1].rstrip("\\/")
    scopus_dir = os.path.join(base_dir, "scopus_runs")
    loop_state = json.load(open(os.path.join(base_dir, "loop_state.json"), encoding="utf-8"))
    per_acu = json.load(open(os.path.join(base_dir, "per_ACU_summary.json"), encoding="utf-8"))

    # cutoff: 只算 2026-09-09 当天及以后的 verdict（entry-01）
    import datetime
    cutoff = datetime.datetime(2026, 9, 9, 0, 0, 0).timestamp()

    acu_list = list(loop_state["acus"].keys())
    summary = {}
    for acu in acu_list:
        round_dirs = []
        adir = os.path.join(scopus_dir, acu)
        if not os.path.isdir(adir):
            continue
        for d in sorted(os.listdir(adir)):
            m = re.match(r"round_(\d+)", d)
            if m and os.path.isdir(os.path.join(adir, d)):
                round_dirs.append((int(m.group(1)), os.path.join(adir, d)))
        round_dirs.sort()
        # 过滤：只保留 entry-01 cutoff 之后的 round（即今天 10:xx 后的文件）
        round_dirs = [(rn, d) for rn, d in round_dirs
                      if os.path.exists(os.path.join(d, "verdict.md"))
                      and os.path.getmtime(os.path.join(d, "verdict.md")) >= cutoff]
        if not round_dirs:
            continue
        # 找最早 PASS
        pass_round = None
        max_round = 0
        for rn, d in round_dirs:
            max_round = max(max_round, rn)
            verdict = os.path.join(d, "verdict.md")
            if os.path.exists(verdict) and grade_pass(open(verdict, encoding="utf-8").read()):
                if pass_round is None:
                    pass_round = rn
        # 算 consecutive_fails
        # = pass_round 之后连续失败轮数
        if pass_round is not None:
            status = "covered"
            fails_after = [rn for rn, _ in round_dirs if rn > pass_round]
            # 简单算：max_round - pass_round
            consecutive_fails = max_round - pass_round
        else:
            status = "open"
            consecutive_fails = max_round
        # 取 latest total_results
        latest_raw = os.path.join(scopus_dir, acu, f"round_{max_round:02d}", "results_raw.json")
        last_total = 0
        if os.path.exists(latest_raw):
            try:
                data = json.load(open(latest_raw, encoding="utf-8"))
                last_total = int((data.get("search-results") or {}).get("opensearch:totalResults", 0) or 0)
            except Exception:
                pass
        # 写回 state
        loop_state["acus"][acu]["status"] = status
        loop_state["acus"][acu]["pass_round"] = pass_round
        loop_state["acus"][acu]["consecutive_fails"] = consecutive_fails
        loop_state["acus"][acu]["last_total_results"] = last_total
        per_acu[acu]["status"] = status
        per_acu[acu]["pass_round"] = pass_round
        per_acu[acu]["consecutive_fails"] = consecutive_fails
        per_acu[acu]["rounds_run"] = max_round
        per_acu[acu]["fail_rounds"] = [rn for rn, _ in round_dirs if rn != (pass_round or -1)]
        if pass_round is None:
            per_acu[acu]["fail_rounds"] = [rn for rn, _ in round_dirs]
        summary[acu] = {
            "status": status, "pass_round": pass_round,
            "consecutive_fails": consecutive_fails, "max_round": max_round,
            "last_total": last_total
        }
        marker = "[PASS]" if status == "covered" else "[OPEN]"
        print(f"  {marker} {acu}: pass_round={pass_round} max_round={max_round} fails={consecutive_fails} total={last_total}")

    loop_state["round"] = max(s["max_round"] for s in summary.values()) if summary else 0
    per_acu["_meta"]["round"] = loop_state["round"]
    with open(os.path.join(base_dir, "loop_state.json"), "w", encoding="utf-8") as f:
        json.dump(loop_state, f, ensure_ascii=False, indent=2)
    with open(os.path.join(base_dir, "per_ACU_summary.json"), "w", encoding="utf-8") as f:
        json.dump(per_acu, f, ensure_ascii=False, indent=2)
    print(f"\n[done] loop_state.round = {loop_state['round']}, {sum(1 for s in summary.values() if s['status'] == 'covered')}/{len(summary)} covered")


if __name__ == "__main__":
    main()
