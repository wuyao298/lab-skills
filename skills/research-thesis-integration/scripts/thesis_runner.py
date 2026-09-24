#!/usr/bin/env python3
"""research-thesis-integration 段8 驱动：元素卡片提取 + 契约校验。

运行模型：opencode-go 供应商 deepseek-v4-flash（用户机制 2026-08-13）。
- API：OpenAI 兼容 `https://opencode.ai/zen/go/v1/chat/completions`
- key：`~/.local/share/opencode/auth.json` 的 `opencode-go` 条目
- 必须带浏览器 User-Agent 头（否则 Cloudflare 403）

子命令：
  validate  段8 输入验证（topics 齐备 + 每课题 deepened/screening 1:1 + evidence.csv）
  cards     元素卡片提取（每课题一个调用，全并行，严格输入隔离；--topics 支持雾区增量）
  check     契约校验（cards 1:1/四段/RE 只在本课题 screening 内；三产物字段齐、RE 在
            evidence.csv 内；rounds 编号连续、雾区快照逐轮非增且终态清空）

用法：
  python thesis_runner.py validate --project <工作目录> --slug <slug>
  python thesis_runner.py cards    --project <工作目录> --slug <slug> [--topics t1,t2] [--workers N] [--dry]
  python thesis_runner.py check    --project <工作目录> --slug <slug>
"""

import argparse
import concurrent.futures
import csv
import json
import os
import re
import sys
import time
import urllib.request

API = os.environ.get("OPENCODE_GO_API", "https://opencode.ai/zen/go/v1/chat/completions")
MODEL = os.environ.get("THESIS_MODEL", "deepseek-v4-flash")
AUTH = os.path.expanduser(r"~\.local\share\opencode\auth.json")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAX_CONCURRENCY = 100
RE_PATTERN = re.compile(r"\[RE(\d+)\]|(?:^|\s)RE(\d+)(?=[^\d]|$)")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "Chrome/131.0 Safari/537.36")
CARD_SECTIONS = ["## 核心元素", "## 方案要点", "## 参考文献设计", "## 可合并点"]
FOG_HEADER = re.compile(r"## 雾区清单（本轮末，(\d+) 项）")


def load_key(auth_path=AUTH):
    if os.environ.get("OPENCODE_GO_KEY"):
        return os.environ["OPENCODE_GO_KEY"]
    d = json.load(open(auth_path, encoding="utf-8"))
    return d["opencode-go"]["key"]


def read_text(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def read_prompt(name):
    return read_text(os.path.join(SKILL_DIR, "prompts", name))


def read_re_ids(text):
    return {m.group(1) or m.group(2) for m in RE_PATTERN.finditer(text)}


def read_csv_re_ids(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return {re.sub(r"[^0-9]", "", r.get("编号", "")) for r in csv.DictReader(f)}


def call_llm(key, messages, max_retries=3, max_tokens=8000):
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
            choice = data["choices"][0]
            return choice["message"]["content"], choice.get("finish_reason")
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(10 * (attempt + 1))


def topic_slugs(topics_dir):
    """topics/ 下课题 MD 的 slug（文件名去 .md，排除清单文件与子目录）。"""
    return sorted(f[:-3] for f in os.listdir(topics_dir)
                  if f.endswith(".md") and not f.startswith("_"))


def paths(args):
    base = os.path.join(args.project, "directions", args.slug)
    return {
        "topics": os.path.join(base, "topics"),
        "evidence": os.path.join(base, "search", "evidence.csv"),
        "thesis": os.path.join(base, "thesis"),
        "cards": os.path.join(base, "thesis", "cards"),
        "rounds": os.path.join(base, "thesis", "rounds"),
    }


# ── validate ─────────────────────────────────────────────────────

def validate_basics(p, print_errors=True):
    issues = []
    if not os.path.isdir(p["topics"]):
        issues.append("缺 topics/（段5 产物缺失，先跑 research-topic-building）")
        return issues
    slugs = topic_slugs(p["topics"])
    if not slugs:
        issues.append("topics/ 下无课题 MD（段5 产物缺失，先跑 research-topic-building）")
    if not os.path.exists(p["evidence"]):
        issues.append("缺 directions/<slug>/search/evidence.csv（方向证据 CSV，段5.2 产物）")
    for s in slugs:
        d = os.path.join(p["topics"], s)
        for f in ("deepened.md", "screening.md"):
            if not os.path.exists(os.path.join(d, f)):
                issues.append(f"{s} 缺 {f}（段6 产物缺失，先跑 research-scheme-deepening）")
    if print_errors:
        for i in issues:
            print(f"[FAIL] {i}")
    return issues


def cmd_validate(args):
    p = paths(args)
    issues = validate_basics(p)
    if issues:
        return 1
    print(f"validate: topics={len(topic_slugs(p['topics']))} evidence={p['evidence']} 齐备")
    return 0


# ── cards ────────────────────────────────────────────────────────

def build_cards_prompt(template, title, slug, deepened_text, screening_text, out_md):
    prompt = template.replace("{TOPIC_TITLE}", title)
    prompt = prompt.replace("{TOPIC_SLUG}", slug)
    prompt = prompt.replace("{DEEPENED_TEXT}", deepened_text)
    prompt = prompt.replace("{SCREENING_TEXT}", screening_text)
    prompt = prompt.replace("{OUTPUT_MD_PATH}", out_md)
    return prompt


def repair_illegal_re(key, content, legit_ids):
    """非法编号修复：要求重写整张卡片（≤2 轮），编号只允许本课题 screening.md 内。

    防御：重写结果为空或缺段时保留原内容（宁可 ⚠️ 标记，也不把好卡片清空）。
    """
    for _ in range(2):
        illegal = sorted(read_re_ids(content) - legit_ids, key=int)
        if not illegal:
            return content, False
        sample = sorted(legit_ids, key=int)[:300]
        prompt = (
            "你的元素卡片里以下论文编号不在本课题 screening.md 内（可能捏造或串课题）：\n"
            f"{', '.join('[RE' + r + ']' for r in illegal)}\n\n"
            f"本课题 screening.md 内的合法编号（前 300 个）如下：\n"
            f"{', '.join('[RE' + r + ']' for r in sample)}\n\n"
            "请重写整张元素卡片全文：把非法编号改为正确编号（对应内容不变）或删除该表述；"
            "其余内容保持原样。直接输出修正后的完整卡片（含四个 ## 段，即 "
            "## 核心元素 / ## 方案要点 / ## 参考文献设计 / ## 可合并点），不要输出其他说明。")
        cont, _ = call_llm(key, [
            {"role": "user", "content": "你是科研专家，正在修正课题元素卡片。"},
            {"role": "user", "content": prompt},
        ])
        if cont and all(s in cont for s in CARD_SECTIONS):
            content = cont
    remaining = sorted(read_re_ids(content) - legit_ids, key=int)
    return content, bool(remaining)


def run_cards_one(key, slug, p, dry=False):
    topics_dir = p["topics"]
    topic_path = os.path.join(topics_dir, slug + ".md")
    deepened_path = os.path.join(topics_dir, slug, "deepened.md")
    screening_path = os.path.join(topics_dir, slug, "screening.md")
    out_md = os.path.join(p["cards"], slug + ".md")
    title = read_text(topic_path).splitlines()[0].lstrip("# ").strip()
    deepened_text = read_text(deepened_path)
    screening_text = read_text(screening_path)
    template = read_prompt("01-element-cards.md")
    prompt = build_cards_prompt(template, title, slug, deepened_text, screening_text, out_md)
    if dry:
        print(f"[dry] {slug} deepened={len(deepened_text)} screening={len(screening_text)} "
              f"prompt_chars={len(prompt)}")
        return "ok"
    key = load_key()
    content, finish = call_llm(key, [{"role": "user", "content": prompt}])
    rounds = 1
    while finish == "length" or any(s not in content for s in CARD_SECTIONS):
        if rounds >= 3:
            break
        cont, finish = call_llm(key, [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": content[-4000:]},
            {"role": "user", "content":
             "你的输出不完整（可能被截断）。请从被截断的位置继续完成剩余段落"
             "（## 核心元素 / ## 方案要点 / ## 参考文献设计 / ## 可合并点 四段齐全），"
             "不要重复已输出的内容。"},
        ])
        content = content + "\n" + cont
        rounds += 1
    legit = read_re_ids(screening_text)
    if content:
        content, has_illegal = repair_illegal_re(key, content, legit)
    else:
        has_illegal = False
        print(f"[WARN] {slug} 首轮输出为空（重跑 cards --topics {slug} 重试）")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(content)
    flag = " ⚠️非法编号残留" if has_illegal else ""
    print(f"[done] {slug} out_chars={len(content)} rounds={rounds}{flag}")
    return "ok"


def cmd_cards(args):
    p = paths(args)
    issues = validate_basics(p)
    if issues:
        return 1
    slugs = args.topics.split(",") if args.topics else topic_slugs(p["topics"])
    for s in slugs:
        if s not in topic_slugs(p["topics"]):
            print(f"错误：{s} 不在 topics/ 下")
            return 1
    workers = min(max(args.workers, 1), MAX_CONCURRENCY, len(slugs))
    print(f"cards: topics={len(slugs)} workers={workers}（严格输入隔离：一课题一调用）")
    key = None if args.dry else load_key()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(run_cards_one, key, s, p, args.dry): s for s in slugs}
        for fut in concurrent.futures.as_completed(futures):
            s = futures[fut]
            try:
                fut.result()
            except Exception as e:
                print(f"[FAIL] {s}: {e}")
    return 0


# ── check ────────────────────────────────────────────────────────

def fog_snapshot(md_text):
    idx = md_text.find("## 雾区清单")
    if idx == -1:
        return None
    tail = md_text[idx:]
    header = tail.splitlines()[0]
    m = FOG_HEADER.match(header)
    declared = int(m.group(1)) if m else None
    count = len(re.findall(r"^\s*-\s*FG-\d+", tail, re.M))
    return declared, count


def check_card(issues, slug, p, valid_re):
    card = os.path.join(p["cards"], slug + ".md")
    if not os.path.exists(card):
        issues.append(f"cards/ 缺 {slug}.md（先跑 cards）")
        return
    text = read_text(card)
    for sec in CARD_SECTIONS:
        if sec not in text:
            issues.append(f"{slug}.md 缺段 {sec}")
    if "⚠️" in text:
        issues.append(f"{slug}.md 含 ⚠️ 非法编号残留")
    screening = read_text(os.path.join(p["topics"], slug, "screening.md"))
    screening_re = read_re_ids(screening)
    out = sorted(read_re_ids(text) - screening_re, key=int)
    if out:
        issues.append(f"{slug}.md 引用 screening 外编号 [RE" + "],[RE".join(out) + "]")
    outside = sorted(screening_re - valid_re, key=int)
    if outside:
        issues.append(f"{slug}/screening.md 含证据集外编号 [RE" + "],[RE".join(outside) + "]")


def check_thesis_file(issues, name, p, valid_re, required_headers, extra_checks=None):
    path = os.path.join(p["thesis"], name)
    if not os.path.exists(path):
        issues.append(f"缺 thesis/{name}（先起草三产物）")
        return
    text = read_text(path)
    for h in required_headers:
        if h not in text:
            issues.append(f"{name} 缺字段 {h}")
    out = sorted(read_re_ids(text) - valid_re, key=int)
    if out:
        issues.append(f"{name} 引用证据集外编号 [RE" + "],[RE".join(out) + "]")
    if extra_checks:
        extra_checks(text, issues)


def cmd_check(args):
    p = paths(args)
    issues = validate_basics(p)
    if not os.path.isdir(p["topics"]):
        print("；".join(issues))
        return 1
    slugs = topic_slugs(p["topics"])
    valid_re = read_csv_re_ids(p["evidence"])

    # cards 1:1 + 段齐全 + RE 合法
    if not os.path.isdir(p["cards"]):
        issues.append("缺 thesis/cards/（先跑 cards）")
    else:
        for s in slugs:
            check_card(issues, s, p, valid_re)
        stray = {x[:-3] for x in os.listdir(p["cards"]) if x.endswith(".md")}
        for x in sorted(stray - set(slugs)):
            issues.append(f"cards/ 多余文件 {x}.md")

    # 三产物字段 + RE 合法
    check_thesis_file(issues, "thesis_argument.md", p, valid_re,
                      ["## 候选总标题", "## 核心论点/研究主线"])
    check_thesis_file(issues, "thesis_story.md", p, valid_re,
                      ["## 选定主线", "## 论文故事"],
                      lambda t, i: [i.append("thesis_story.md 缺课题来源标注（课题：<slug>）")
                                    for _ in [0] if "（课题：" not in t])
    check_thesis_file(issues, "thesis_structure.md", p, valid_re,
                      ["## 章级结构", "## 章间逻辑"],
                      lambda t, i: [i.append("thesis_structure.md 缺章↔课题映射（↔）")
                                    for _ in [0] if "↔" not in t])

    # rounds 连续 + 雾区快照非增 + 终态清空
    if not os.path.isdir(p["rounds"]):
        issues.append("缺 thesis/rounds/（讨论轮次未落盘）")
    else:
        files = sorted(f for f in os.listdir(p["rounds"]) if re.match(r"round_\d+\.md$", f))
        nums = [int(re.search(r"(\d+)", f).group(1)) for f in files]
        if nums != list(range(1, len(nums) + 1)):
            issues.append(f"rounds 编号不连续（现有：{nums or '无'}）")
        fog_sizes = []
        for f in files:
            text = read_text(os.path.join(p["rounds"], f))
            for h in ("## 用户原话", "## 判读", "## 动作"):
                if h not in text:
                    issues.append(f"{f} 缺段 {h}")
            snap = fog_snapshot(text)
            if snap is None:
                issues.append(f"{f} 缺雾区清单快照（## 雾区清单（本轮末，M 项））")
            else:
                declared, count = snap
                if declared is None:
                    issues.append(f"{f} 雾区清单头格式错（需带本轮末项数）")
                elif declared != count:
                    issues.append(f"{f} 雾区头声明 {declared} 项 ≠ 实际 {count} 项")
                fog_sizes.append(count)
        if fog_sizes:
            if any(b > a for a, b in zip(fog_sizes, fog_sizes[1:])):
                issues.append("雾区清单逐轮增加（违反减雾：应非增）")
            if fog_sizes[-1] != 0:
                issues.append(f"雾区未清空（末轮 {fog_sizes[-1]} 项）")

    if issues:
        print(f"[FAIL] {len(issues)} 个问题：")
        for i in issues:
            print("  - " + i)
        return 1
    print(f"check: 全部通过（topics={len(slugs)} cards 1:1、三产物字段齐、RE 库内实测、"
          f"rounds 连续、雾区清空）")
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="段8 论文故事整合驱动（deepseek-v4-flash）")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "cards", "check"):
        p = sub.add_parser(name)
        p.add_argument("--project", required=True)
        p.add_argument("--slug", required=True)
        if name == "cards":
            p.add_argument("--topics", default=None, help="逗号分隔课题 slug；缺省 = topics/ 全部")
            p.add_argument("--workers", type=int, default=MAX_CONCURRENCY)
            p.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    fn = {"validate": cmd_validate, "cards": cmd_cards, "check": cmd_check}
    sys.exit(fn[args.cmd](args))


if __name__ == "__main__":
    main()
