#!/usr/bin/env python3
"""段 9 9.5 闸门3：ep3-prompt2（检索式优化建议）批量生成。

对每个触发闸门3 的 ACU，用 `prompts/05-gate3-refine.md` 原文 + 项目输入（检索目标/检索式/
前 20 条真实 Scopus 结果）调一次模型，产出「建议新检索式 + 理由」，写入 JSON 供
build_gate3_material.py --suggestions 使用。

用法：
  python gate3_suggest.py --validation <vroot> --out <suggestions.json>
      [--acu ACU-002 --acu ACU-008] [--min-fails 2] [--workers 2]
"""
import argparse
import concurrent.futures
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loop_a_runner as L  # noqa: E402
from build_knowledge_base import load_json, norm, read_text  # noqa: E402

FORMAT = """

## 检索目标

ACU：{acu} — {name}
研究对象/方案：金属化 BOPP 薄膜脉冲电容器状态依赖活化能（Ea 漂移）的寿命预测验证方案。
本 ACU 需要支撑的 MVE 能力：{stage} 阶段「{name}」的实现锚点（可复现的设备/参数/流程/算法）。

## 检索式

```
{query}
```

## 检索结果（totalResults={total}，以下为首页前 {n} 条：序号 | 标题 | 摘要 | 年 | 期刊 | EID）

{entries}

## 输出格式（硬性要求）

只输出下面两段，不要任何其他内容：

### 建议新检索式

```
TITLE-ABS-KEY(...)
```

### 理由

- 逐条说明每处改动（增/删/改词、逻辑关系调整）与它如何提高查准率或查全率。
- 新检索式必须完整可运行：只含 TITLE-ABS-KEY(...)，不得出现 year / doctype / 来源库过滤，不得出现 RE 编号或占位符。
- 只能基于上面给出的检索结果事实推理，不得编造论文。
"""


def build_prompt(acu, info, query, total, entries_text, n):
    body = read_text(os.path.join(L.SKILL_DIR, "prompts", "05-gate3-refine.md"))
    return body + FORMAT.format(acu=acu, name=info.get("name", ""), stage=info.get("stage", ""),
                                query=query, total=total, n=n, entries=entries_text)


def parse_suggestion(text):
    m = re.search(r"###\s*建议新检索式(.*?)###\s*理由(.*)$", text, re.DOTALL)
    if not m:
        m2 = re.search(r"(TITLE-ABS-KEY\([^`\n]+\))", text)
        return (m2.group(1).strip() if m2 else ""), text.strip()[:1500]
    head, tail = m.group(1), m.group(2)
    q = re.search(r"`{1,3}\s*(TITLE-ABS-KEY\(.*?\))\s*`{1,3}", head, re.DOTALL)
    if not q:
        q = re.search(r"(TITLE-ABS-KEY\(.*?\))", head, re.DOTALL)
    return (q.group(1).strip() if q else ""), tail.strip()[:2000]


def process(acu, key, base_dir, acu_index, loop_state):
    adir = os.path.join(base_dir, "scopus_runs", acu)
    rounds = sorted(int(re.fullmatch(r"round_(\d+)", d).group(1)) for d in os.listdir(adir)
                    if os.path.isdir(os.path.join(adir, d)) and re.fullmatch(r"round_(\d+)", d))
    rn = rounds[-1] if rounds else 1
    rp = os.path.join(adir, f"round_{rn:02d}", "results_raw.json")
    if not os.path.isfile(rp):
        return acu, {"query": "", "reason": "缺 results_raw.json"}
    data = load_json(rp)
    sr = data.get("search-results") or {}
    total = int(sr.get("opensearch:totalResults", 0) or 0)
    entries = sr.get("entry") or []
    lines = []
    for i, e in enumerate(entries[:20], 1):
        lines.append(f"{i} | {norm(e.get('dc:title'))} | {norm(e.get('dc:description'))[:500]} | "
                     f"{(e.get('prism:coverDate') or '')[:4]} | {e.get('prism:publicationName') or ''} | "
                     f"EID:{e.get('eid', '')}")
    query = loop_state.get("acus", {}).get(acu, {}).get("query") or acu_index[acu].get("query", "")
    prompt = build_prompt(acu, acu_index[acu], query, total, "\n".join(lines), len(entries[:20]))
    text = L.call_llm(key, [{"role": "user", "content": prompt}])[0]
    q, reason = parse_suggestion(text)
    print(f"  [{acu}] total={total} suggested={'yes' if q else 'NO'}")
    return acu, {"query": q, "reason": reason, "raw": text}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validation", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--acu", action="append", default=[])
    ap.add_argument("--min-fails", type=int, default=2)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    base_dir = os.path.abspath(args.validation)
    acu_index = load_json(os.path.join(base_dir, "acu_index.json"))
    loop_state = load_json(os.path.join(base_dir, "loop_state.json"))
    targets = args.acu or [a for a, st in loop_state.get("acus", {}).items()
                           if st.get("status") == "open" and st.get("consecutive_fails", 0) >= args.min_fails]
    targets = sorted(set(targets))
    key = L.load_key()
    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(process, a, key, base_dir, acu_index, loop_state): a for a in targets}
        for fut in concurrent.futures.as_completed(futs):
            acu, res = fut.result()
            out[acu] = res
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[done] {len(out)} suggestions -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
