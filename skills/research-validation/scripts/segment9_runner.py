#!/usr/bin/env python3
"""段 9 9.1/9.2/9.3 LLM 驱动（编排器薄壳）。

- 读 prompts/<name>.md 原文
- 注入对象输入（topic MD + deepened.md + screening 摘要）
- 调 deepseek-direct（OPENCODE_GO_API/KEY 环境变量）
- 落盘到 validation/<object>/ 或 validation/

子命令：
  rd   9.1 研究设计 → validation/<object>/research_design.md
  mve  9.2 MVE → validation/<object>/mve_paths.md
  ma   9.3 元分析 + 检索式 → validation/meta_analysis.md + search_strategies.md + acu_index.json

用法：
  python segment9_runner.py rd  --project <proj> --slug <slug> --object <slug>
  python segment9_runner.py mve --project <proj> --slug <slug> --object <slug>
  python segment9_runner.py ma  --project <proj> --slug <slug> --objects o1,o2
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

API = os.environ.get("OPENCODE_GO_API", "https://api.deepseek.com/v1/chat/completions")
MODEL = os.environ.get("DEEPENING_MODEL", "deepseek-chat")
AUTH = os.path.expanduser(r"~\.local\share\opencode\auth.json")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MAX_TOKENS = int(os.environ.get("SEGMENT9_MAX_TOKENS", "16000"))

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "Chrome/131.0 Safari/537.36")


def load_key():
    if os.environ.get("OPENCODE_GO_KEY"):
        return os.environ["OPENCODE_GO_KEY"]
    return json.load(open(AUTH, encoding="utf-8"))["opencode-go"]["key"]


def read_text(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def compress_screening(screening_text: str, max_papers: int = 200, max_chars: int = 60000) -> str:
    """把 screening.md 压缩成论文清单（RE | 类别 | 标题），去掉摘要。

    保留批注头 + 表格里的 RE/类别/标题三列，把启发点/局限性/方法全部丢。
    总体压到 ≤ max_chars。
    """
    lines = screening_text.splitlines()
    out = []
    in_table = False
    paper_count = 0
    header_re = re.compile(r"^\s*\|")  # 表格行
    cell_re = re.compile(r"\|")
    for line in lines:
        if not header_re.match(line):
            # 段标题、空行
            if "##" in line or line.strip() == "":
                out.append(line)
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            out.append(line)
            continue
        first = cells[0]
        if first.startswith("论文编号") or set(first) == {"-"}:
            # 表头/分隔行
            out.append("| RE | 类别 | 标题 |")
            out.append("| --- | --- | --- |")
            in_table = True
            continue
        m = re.match(r"\[?RE(\d+)\]?", first)
        if not m:
            out.append(line)
            continue
        rid = "RE" + m.group(1)
        category = cells[1] if len(cells) > 1 else ""
        # 标题 = cells[2]（原表第 3 列）；cells[3..5] 是方法/指标/局限性/启发点，全丢
        title = cells[2] if len(cells) > 2 else ""
        # 截短标题
        if len(title) > 200:
            title = title[:200] + "…"
        out.append(f"| [{rid}] | {category} | {title} |")
        paper_count += 1
        if paper_count >= max_papers:
            out.append(f"\n> …(以下 {max_papers}+ 篇已省略)")
            break
    text = "\n".join(out)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n> …(已截断)"
    return text


def call_llm(key, messages, max_retries=3, max_tokens=None):
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_TOKENS
    payload = {"model": MODEL, "messages": messages, "max_tokens": max_tokens}
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(API, data=body, headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + key,
                "User-Agent": USER_AGENT,
            })
            with urllib.request.urlopen(req, timeout=1800) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"], data["choices"][0].get("finish_reason")
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(10 * (attempt + 1))


def run_with_continuation(key, prompt, must_contain=None, max_continuations=3):
    """一次 LLM 调用 + 截断续写。"""
    if must_contain is None:
        must_contain = []
    content, finish = call_llm(key, [{"role": "user", "content": prompt}])
    rounds = 1
    while (finish == "length" or any(m not in content for m in must_contain)) and rounds < max_continuations + 1:
        if rounds > max_continuations:
            break
        cont, finish = call_llm(key, [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": content[-6000:]},
            {"role": "user", "content":
             "你的输出不完整（可能被截断或缺关键段）。请从上一段被截断的位置继续，"
             "完成剩余内容。不要重复已输出的内容。"},
        ])
        content = content + "\n" + cont
        rounds += 1
    return content, rounds


# ── 9.1 research design ─────────────────────────────────────────

def cmd_rd(args):
    prompt_path = os.path.join(SKILL_DIR, "prompts", "01-research-design.md")
    template = read_text(prompt_path)
    topic_path = os.path.join(args.project, "directions", args.slug, "topics", args.object + ".md")
    deepened_path = os.path.join(args.project, "directions", args.slug, "topics", args.object, "deepened.md")
    screening_path = os.path.join(args.project, "directions", args.slug, "topics", args.object, "screening.md")
    out_path = os.path.join(args.project, "directions", args.slug, "validation", args.object, "research_design.md")

    topic_text = read_text(topic_path)
    deepened_text = read_text(deepened_path)
    screening_text = read_text(screening_path)
    screening_short = compress_screening(screening_text, max_papers=200, max_chars=60000)

    # 9.1 prompt 末尾是「我的初步想法」+ 占位符。回退路径把 topic MD 嵌入 + deepened + screening 作上下文
    assembled = template.replace(
        "**这是我的初步想法：**\n\n【此处填入你按模板整理的初步研究想法】",
        "**这是我的初步想法（回退路径 = 课题 MD 全文 + 段 6 进化版方案 + 段 6 论文集）：**\n\n"
        + topic_text
        + "\n\n---\n\n## 进化版方案（段 6 6.2 产物）\n\n"
        + deepened_text
        + "\n\n---\n\n## 强相关文献清单（段 6 6.1 产物，RE + 类别 + 标题；摘要已省去）\n\n"
        + screening_short
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if args.dry:
        print(f"[dry] rd {args.object} assembled_chars={len(assembled)}")
        return 0
    key = load_key()
    content, rounds = run_with_continuation(
        key, assembled,
        must_contain=["第一部分", "第二部分", "步骤一", "步骤二", "步骤三"]
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[rd] {args.object} out_chars={len(content)} rounds={rounds} -> {out_path}")
    return 0


# ── 9.2 MVE ─────────────────────────────────────────────────────

def cmd_mve(args):
    prompt_path = os.path.join(SKILL_DIR, "prompts", "02-mve.md")
    template = read_text(prompt_path)
    rd_path = os.path.join(args.project, "directions", args.slug, "validation", args.object, "research_design.md")
    out_path = os.path.join(args.project, "directions", args.slug, "validation", args.object, "mve_paths.md")

    rd_text = read_text(rd_path)
    assembled = template
    for placeholder in ["{RESEARCH_DESIGN}", "{TOPIC_TEXT}", "{RESEARCH_DESIGN_TEXT}",
                        "{DESIGN_TEXT}", "{MY_RESEARCH_DESIGN}"]:
        assembled = assembled.replace(placeholder, rd_text)
    if "{INPUT_NOTE}" in assembled:
        assembled = assembled.replace("{INPUT_NOTE}", rd_text)
    else:
        assembled += "\n\n## 输入参考：9.1 研究设计全文\n\n" + rd_text

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if args.dry:
        print(f"[dry] mve {args.object} assembled_chars={len(assembled)}")
        return 0
    key = load_key()
    content, rounds = run_with_continuation(
        key, assembled,
        must_contain=["路径 A", "路径 B", "核心假设"]
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[mve] {args.object} out_chars={len(content)} rounds={rounds} -> {out_path}")
    return 0


# ── 9.3 meta-analysis + search strategies ───────────────────────

def cmd_ma(args):
    prompt_path = os.path.join(SKILL_DIR, "prompts", "03-meta-analysis.md")
    template = read_text(prompt_path)
    objects = [o.strip() for o in args.objects.split(",") if o.strip()]
    inputs = []
    for obj in objects:
        rd_path = os.path.join(args.project, "directions", args.slug, "validation", obj, "research_design.md")
        mve_path = os.path.join(args.project, "directions", args.slug, "validation", obj, "mve_paths.md")
        rd_text = read_text(rd_path)
        mve_text = read_text(mve_path)
        inputs.append(f"## 对象 {obj} 的 9.1 研究设计\n\n{rd_text}\n\n## 对象 {obj} 的 9.2 MVE\n\n{mve_text}")
    inputs_combined = "\n\n---\n\n".join(inputs)

    assembled = template
    for placeholder in ["{INPUTS}", "{RESEARCH_DESIGN}", "{ALL_INPUTS}", "{INPUTS_TEXT}"]:
        assembled = assembled.replace(placeholder, inputs_combined)
    if "{INPUT_NOTE}" in assembled:
        assembled = assembled.replace("{INPUT_NOTE}", inputs_combined)
    else:
        assembled += "\n\n## 输入参考：所有对象的 9.1 + 9.2 全文\n\n" + inputs_combined

    if args.dry:
        print(f"[dry] ma objects={objects} assembled_chars={len(assembled)}")
        return 0
    key = load_key()
    content, rounds = run_with_continuation(
        key, assembled,
        must_contain=["ACU-", "锚点实体", "策略一", "策略二", "策略三"]
    )

    out_dir = os.path.join(args.project, "directions", args.slug, "validation")
    os.makedirs(out_dir, exist_ok=True)
    ma_path = os.path.join(out_dir, "meta_analysis.md")
    ss_path = os.path.join(out_dir, "search_strategies.md")
    with open(ma_path, "w", encoding="utf-8") as f:
        f.write(content)
    # 9.3 产物既含元分析又含检索式。简单切分：按 "## ACU-XXX" 段分
    parts = re.split(r"(?=^## ACU-\d+)", content, flags=re.MULTILINE)
    ma_only = []
    ss_lines = ["# 检索式策略（按 ACU）\n"]
    for part in parts:
        if part.startswith("## ACU-"):
            ss_lines.append(part.strip() + "\n")
        else:
            ma_only.append(part)
    with open(ss_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ss_lines))
    with open(ma_path, "w", encoding="utf-8") as f:
        f.write("".join(ma_only).strip() + "\n")

    # 解析 acu_index.json（默认起手 = 策略二·实现优先）
    acu_index = {}
    for part in parts:
        if not part.startswith("## ACU-"):
            continue
        m = re.match(r"^## (ACU-\d+)\s+(.+?)$", part.strip().splitlines()[0])
        if not m:
            continue
        acu_id, name = m.group(1), m.group(2).strip()
        strat2_match = re.search(
            r"策略二[：:]?\s*实现优先.*?检索式[：:]?\s*[`']?(TITLE-ABS-KEY\([^`]+\))[`']?",
            part, re.DOTALL)
        if not strat2_match:
            strat2_match = re.search(
                r"策略二.*?TITLE-ABS-KEY\([^)]+\)",
                part, re.DOTALL)
        query = strat2_match.group(1) if strat2_match else ""
        acu_index[acu_id] = {
            "name": name,
            "stage": "",
            "source_objects": objects,
            "query": query,
            "default_strategy": "②实现优先"
        }
    acu_path = os.path.join(out_dir, "acu_index.json")
    with open(acu_path, "w", encoding="utf-8") as f:
        json.dump(acu_index, f, ensure_ascii=False, indent=2)
    print(f"[ma] objects={objects} out_chars={len(content)} rounds={rounds} -> {ma_path}, {ss_path}, {acu_path}")
    print(f"[ma] acu_index: {len(acu_index)} entries")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_rd = sub.add_parser("rd")
    p_mve = sub.add_parser("mve")
    p_ma = sub.add_parser("ma")
    for p in [p_rd, p_mve]:
        p.add_argument("--project", required=True)
        p.add_argument("--slug", required=True)
        p.add_argument("--object", required=True)
        p.add_argument("--dry", action="store_true")
    p_ma.add_argument("--project", required=True)
    p_ma.add_argument("--slug", required=True)
    p_ma.add_argument("--objects", required=True)
    p_ma.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    {"rd": cmd_rd, "mve": cmd_mve, "ma": cmd_ma}[args.cmd](args)
    return 0


if __name__ == "__main__":
    main()
