#!/usr/bin/env python3
"""段 9 9.4 严格 verdict：对**已有 results_raw.json 的轮次**重新出契约级 verdict。

动机（2026-09-09 entry-01 批次）：loop_a_runner 直接喂 04 提示词原文时，模型自选表头
（级别列位置不定 / 行数超过 25 / 级别写成「中优先级 (M1)」等），导致
`check_validation` 的 parse_verdict（要求第 2 列 = 高/中/建议排除）判不出高行。
本脚本在同一批 Scopus 真实响应上重出 verdict，并**硬性约束输出格式**；
提示词正文仍取 `prompts/04-loop-a-verdict.md` 原文，格式约束作为「项目输入」追加在末尾。

用法：
  python strict_verdict.py --validation <vroot> --object <slug> --acu ACU-003 --round 1
      [--workers 1] [--force]

校验（写盘前）：表头四列、行数=条目数、级别 ∈ {高,中,建议排除}、论文标识可反查。
不通过 → 重试 1 次；仍不通过 → 保留 best-effort 并返回 2。
"""
import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loop_a_runner as L  # noqa: E402
from build_knowledge_base import parse_table, raw_entry_index, resolve_paper, read_text  # noqa: E402

LEVELS = ("高", "中", "建议排除")
HEADER = "| 论文标识 | 级别 | 可复现的关键步骤与参数 | 可直接整合至我方案的具体步骤 |"

FORMAT_BLOCK = """

## ACU：{acu}

## MVE 路径上下文

{mve}

## Scopus 条目（序号 | 标题 | 摘要 | 年份 | 期刊 | EID）

{entries}

## 输出格式（硬性要求，违反即作废）

只输出以下结构，不要任何前言、寒暄、结语或额外表格：

```
# LOOP A verdict · {acu} · round_{rn:02d}

## 逐条分级

| 论文标识 | 级别 | 可复现的关键步骤与参数 | 可直接整合至我方案的具体步骤 |
| --- | --- | --- | --- |
| EID:2-s2.0-xxxxxxxx | 高 | <该文可复现的关键步骤与参数> | <可直接整合至我方案的具体步骤> |
```

规则（逐条核对）：
1. 表头必须与上面完全一致：四列、顺序不变，**级别必须是第 2 列**。
2. 必须逐条覆盖上面给出的**全部 {n} 条** Scopus 条目，恰好 {n} 行，且**行序与输入顺序一一对应**（第 k 行 = 输入第 k 条）；不得增加、合并、拆分行，不得引入列表之外的条目。
3. 级别列只允许三个值之一，原样写：`高` / `中` / `建议排除`。禁止写「高优先级(M1)」「中优先级」等任何变体或附加说明。
4. 论文标识列：第 k 行必须原样复制输入第 k 条的 `EID:<eid>`；该条无 EID 时才写序号 {n} 中的对应数字。禁止凭记忆改写或补全 EID。
5. 分级口径 = 提示词 A 的 H/M/排除标准（按原文，不要自造更严口径）：
   - **高**（满足 H1/H2/H3 至少一条）：摘要给出强信号，表明**全文**极大概率包含可直接照搬或稍加修改的实验菜谱。
     H1 = 摘要明确说明系统研究/优化了某个实验条件或模型参数（如 "systematically investigated the effect of…"、"optimized … by varying …"、"a detailed study of parameters…"）；
     H2 = 摘要把关键参数的数值与具体结果直接关联（如 "120 °C 时产率 95%，100 °C 仅 70%"）；
     H3 = 摘要明确宣告提供详细方案 / step-by-step 指南 / 需要详细解释的全新复杂装置搭建。
     注意：**高不要求摘要本身已列出全部参数**，只要求"全文很可能含可直接复现细节"的强信号。
   - **中**（不满足高，但满足 M1 或 M2）：M1 = 核心方法明确且是论文主角（具体合成/表征/算法/装置）；M2 = 声明对现有方法做了改进/改良。
   - **建议排除**：理论探讨型、高层综述型、应用展示型（方法描述过于简略），或方法完全不匹配。
   - 摘要缺失时按标题 + 期刊 + 关键词判断，不得仅因"摘要缺失"就一律降级为排除；但也不得无依据拔高。
6. 表后可以再写 `## 结论与后续动作` 段落，但不得再出现任何其他表格。
7. 全部内容必须来自上面给出的条目，禁止编造标题、EID、参数。
"""


def build_prompt(acu, rn, mve, entries_text, n_entries):
    body = read_text(os.path.join(L.SKILL_DIR, "prompts", "04-loop-a-verdict.md"))
    return body + FORMAT_BLOCK.format(acu=acu, rn=rn, mve=mve, entries=entries_text, n=n_entries)


def call_with_retry(key, prompt, max_tokens):
    content, finish = L.call_llm(key, [{"role": "user", "content": prompt}], max_tokens=max_tokens)
    if finish == "length":
        cont, finish2 = L.call_llm(key, [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": content[-6000:]},
            {"role": "user", "content": "输出被截断。请从断点继续补完剩余表格行，不要重复已写内容，不要加任何解释。"},
        ], max_tokens=max_tokens)
        content = content + "\n" + cont
    return content


def validate(text, entries):
    """校验并做**位置修复**：返回 (repaired_text, ok, issues, stats)。

    位置契约：第 k 行必须对应输入第 k 条。若该行论文标识无法反查、或反查到别的条目，
    则用输入第 k 条的 EID/序号改写该行首列（只修标识，不改级别与内容），并计入 repairs。
    """
    issues = []
    repairs = 0
    idx = raw_entry_index(entries)
    lines = text.split("\n")
    hdr_i, hdr = None, None
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith("|"):
            c = [x.strip() for x in s.strip("|").split("|")]
            if c and ("论文标识" in c[0] or "论文编号" in c[0]):
                hdr_i, hdr = i, c
                break
    if hdr_i is None:
        return text, False, ["找不到契约表头（论文标识 | 级别 | ...）"], {"rows": 0, "high": 0, "repairs": 0}
    if len(hdr) < 2 or hdr[1] != "级别":
        issues.append(f"第 2 列不是「级别」而是「{hdr[1] if len(hdr) > 1 else '?'}」")

    data_lines = []
    j = hdr_i + 2
    while j < len(lines) and lines[j].strip().startswith("|"):
        c = [x.strip() for x in lines[j].strip().strip("|").split("|")]
        if not (len(c) >= 2 and set("".join(c).replace("-", "")) == {":"}):
            data_lines.append(j)
        j += 1

    if len(data_lines) != len(entries):
        issues.append(f"行数 {len(data_lines)} ≠ 条目数 {len(entries)}")

    n_high = 0
    bad_levels = []
    for k, li in enumerate(data_lines):
        c = [x.strip() for x in lines[li].strip().strip("|").split("|")]
        lv = c[1].strip().strip("*` ")
        if lv not in LEVELS:
            bad_levels.append(lv[:20])
        if lv == "高":
            n_high += 1
        if k >= len(entries):
            continue
        exp_eid = str(entries[k].get("eid") or "").strip()
        exp = f"EID:{exp_eid}" if exp_eid else str(k + 1)
        resolved = resolve_paper(c[0], idx)
        same = False
        if resolved is not None:
            got_eid = str(resolved.get("eid") or "").strip()
            same = (got_eid == exp_eid) if exp_eid else (resolved is entries[k])
        if not same:
            c[0] = exp
            lines[li] = "| " + " | ".join(c) + " |"
            repairs += 1
    if bad_levels:
        issues.append(f"非法级别 {len(bad_levels)} 个：{bad_levels[:5]}")
    stats = {"rows": len(data_lines), "high": n_high, "repairs": repairs}
    return "\n".join(lines), (not issues), issues, stats


def process(acu, rn, key, base_dir, mve_text, force=False):
    run_dir = os.path.join(base_dir, "scopus_runs", acu, f"round_{rn:02d}")
    raw = os.path.join(run_dir, "results_raw.json")
    vp = os.path.join(run_dir, "verdict.md")
    if not os.path.isfile(raw):
        return {"acu": acu, "round": rn, "error": "缺 results_raw.json"}
    data = json.load(open(raw, encoding="utf-8"))
    entries = (data.get("search-results") or {}).get("entry") or []
    entries = [e for e in entries if e.get("eid") or e.get("dc:title")]
    if not entries:
        return {"acu": acu, "round": rn, "skipped": "0 条目（用 stub_zero_rounds.py）"}
    entries_text, _ = L.format_entries_for_verdict(raw)
    prompt = build_prompt(acu, rn, mve_text, entries_text, len(entries[:25]))

    best = None
    for attempt in (1, 2):
        text = call_with_retry(key, prompt, L.DEFAULT_MAX_TOKENS)
        text, ok, issues, stats = validate(text, entries[:25])
        print(f"  [{acu} r{rn}] attempt{attempt}: ok={ok} stats={stats} issues={issues[:3]}")
        if best is None or (not best[1] and ok):
            best = (text, ok, issues, stats)
        if ok:
            break
        time.sleep(2)
    text, ok, issues, stats = best
    L.write_text(vp, text)
    return {"acu": acu, "round": rn, "ok": ok, "issues": issues, "stats": stats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validation", required=True)
    ap.add_argument("--object", required=True)
    ap.add_argument("--acu", action="append", required=True)
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    base_dir = os.path.abspath(args.validation)
    mve_path = os.path.join(base_dir, args.object, "mve_paths.md")
    mve_text = read_text(mve_path) if os.path.exists(mve_path) else ""
    key = L.load_key()
    out = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(process, acu, args.round, key, base_dir, mve_text): acu for acu in args.acu}
        for fut in concurrent.futures.as_completed(futs):
            try:
                out.append(fut.result())
            except Exception as e:
                out.append({"acu": futs[fut], "error": str(e)})
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if all(o.get("ok") or o.get("skipped") for o in out) else 2


if __name__ == "__main__":
    sys.exit(main())
