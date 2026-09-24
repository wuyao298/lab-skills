#!/usr/bin/env python3
"""段 9 9.4 补件：为 totalResults=0 的轮次补写「空表 verdict」。

背景：loop_a_runner.process_one 在 totalResults=0 时只落 `results_raw.json`、不写 verdict，
而契约/check_validation 要求每个 round 目录同时有 results_raw.json + verdict.md，
且 0 高 = FAIL 必须记入 fail_rounds。本脚本只为**已有 raw、缺 verdict** 的轮次补一份
不编造任何条目的空表 verdict。

用法：
  python stub_zero_rounds.py --validation <validation_root> [--object <object-slug>]

只处理 raw 中 opensearch:totalResults == 0 的轮次；非 0 且缺 verdict 的轮次会报警但不写。
"""
import argparse
import json
import os
import re
import sys

TEMPLATE = """# LOOP A verdict · {acu} · round_{rn:02d}

> 对象：`{obj}`（方向 `mfc-selfhealing-multiscale`）
> 方案基线：`validation/{obj}/research_design.md` + `validation/{obj}/mve_paths.md`
> 文献来源（唯一）：本轮 Scopus 响应 `results_raw.json`
> 检索式：`{query}`

## 本轮响应状态

- `opensearch:totalResults` = 0，首页返回 0 条真实条目（`entry` 为无 `eid` 的占位项）。
- 按 04 提示词与契约：本轮无可分级对象，**高 0 / 中 0 / 建议排除 0**；只写空表，不编造任何文献行。
- 判定：本轮 **FAIL**（0 篇高）。

## 逐条分级

| 论文标识 | 级别 | 可复现的关键步骤与参数 | 可直接整合至我方案的具体步骤 |
| --- | --- | --- | --- |

## 结论与后续动作

- 本轮 0 条命中：检索式过窄，未产生可整合进路径 A / 路径 B 的证据行；是否改 query / 合并 / 跳过由闸门3 裁决。
- 本文件所有内容取自本轮 JSON 的 `opensearch:totalResults` / `opensearch:Query.@searchTerms` 与占位 `entry`。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validation", required=True)
    ap.add_argument("--object", default=None)
    args = ap.parse_args()
    base = os.path.abspath(args.validation)
    acu_index = {}
    p = os.path.join(base, "acu_index.json")
    if os.path.isfile(p):
        acu_index = json.load(open(p, encoding="utf-8"))
    obj = args.object
    if not obj:
        objs = {o for v in acu_index.values() for o in (v.get("source_objects") or [])}
        obj = sorted(objs)[0] if objs else "unknown"

    written, warned = 0, 0
    root = os.path.join(base, "scopus_runs")
    for acu in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        adir = os.path.join(root, acu)
        if not os.path.isdir(adir) or not re.fullmatch(r"ACU-\d{3}", acu):
            continue
        for name in sorted(os.listdir(adir)):
            m = re.fullmatch(r"round_(\d+)", name)
            if not m:
                continue
            rn = int(m.group(1))
            raw = os.path.join(adir, name, "results_raw.json")
            vp = os.path.join(adir, name, "verdict.md")
            if not os.path.isfile(raw) or os.path.isfile(vp):
                continue
            try:
                j = json.load(open(raw, encoding="utf-8"))
            except Exception:
                warned += 1
                print(f"[WARN] {acu} round_{rn}: raw 无法解析")
                continue
            sr = j.get("search-results", {}) or {}
            total = int(sr.get("opensearch:totalResults", 0) or 0)
            if total != 0:
                warned += 1
                print(f"[WARN] {acu} round_{rn}: total={total} 却缺 verdict，需人工/模型补判")
                continue
            query = ((sr.get("opensearch:Query") or {}).get("@searchTerms")
                     or acu_index.get(acu, {}).get("query") or "")
            open(vp, "w", encoding="utf-8").write(
                TEMPLATE.format(acu=acu, rn=rn, obj=obj, query=query))
            written += 1
            print(f"[STUB] {acu} round_{rn}: 0 结果空表 verdict 已补写")
    print(f"[done] stubs={written} warnings={warned}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
