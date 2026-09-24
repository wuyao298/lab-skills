#!/usr/bin/env python3
"""research-scheme-deepening 段6 驱动：6.1 强相关文献筛选 + 6.2 深化方案。

运行模型：opencode-go 供应商 deepseek-v4-flash（用户机制 2026-08-13）。
- API：OpenAI 兼容 `https://opencode.ai/zen/go/v1/chat/completions`
- key：`~/.local/share/opencode/auth.json` 的 `opencode-go` 条目
- 必须带浏览器 User-Agent 头（否则 Cloudflare 403）

子命令：
  screen   6.1 分批筛选（课题 × 批次全并行，并发上限 100，严格输入隔离）
  merge    合并各批次筛选表 → topics/<课题>/screening.md
  check    校验筛选产物（1:1 批次、RE 只在本批内、无重复、合并一致）
  deepen   6.2 深化方案（每课题一个调用，全并行，输入 = 课题 MD + screening.md）

用法：
  python deepening_runner.py screen --project <工作目录> --slug <slug> [--topics t1,t2] [--workers 100] [--split] [--dry]
  python deepening_runner.py merge  --project <工作目录> --slug <slug> [--topics t1,t2]
  python deepening_runner.py check  --project <工作目录> --slug <slug> [--topics t1,t2]
  python deepening_runner.py deepen --project <工作目录> --slug <slug> [--topics t1,t2] [--workers 100] [--dry]
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
MODEL = os.environ.get("DEEPENING_MODEL", "deepseek-v4-flash")
AUTH = os.path.expanduser(r"~\.local\share\opencode\auth.json")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAX_CONCURRENCY = 100
RE_PATTERN = re.compile(r"\[RE(\d+)\]|(?:^|\s)RE(\d+)(?=\s|\||$|，|,|\.|：|:)")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "Chrome/131.0 Safari/537.36")
BATCH_COLUMNS = ["编号", "标题", "摘要"]
TABLE_HEADERS = ["论文编号", "相关性类别", "关键研究方法与材料",
                 "核心性能指标 (量化)", "创新性与局限性分析", "对我课题的启发点"]


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


def read_batch_csv(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_csv_ids(path):
    return {re.sub(r"[^0-9]", "", r["编号"]) for r in read_batch_csv(path)}


def topic_slugs(topics_dir):
    """topics/ 下课题 MD 的 slug（文件名去 .md，排除清单文件与子目录）。"""
    slugs = []
    for f in sorted(os.listdir(topics_dir)):
        if f.endswith(".md") and not f.startswith("_"):
            slugs.append(f[:-3])
    return slugs


def collect_batch_files(analysis_dir):
    return sorted(f for f in os.listdir(analysis_dir)
                  if re.match(r"batch_\d{3}\.csv$", f))


def call_llm(key, messages, max_retries=3, max_tokens=None):
    # 默认 max_tokens 走环境变量 DEEPENING_MAX_TOKENS（缺省 16000，对齐 m2_runner_v2.py 实战值，
    # 适配 deepseek-chat 端点；opencode-go 端点 40000 反复 finish=length）。
    if max_tokens is None:
        max_tokens = int(os.environ.get("DEEPENING_MAX_TOKENS", "16000"))
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


# ── 6.1 screen ─────────────────────────────────────────────────

def build_screen_prompt(template, topic_text, rows, batch_csv, out_md, batch_name):
    prompt = template.replace("{TOPIC_TEXT}", topic_text)
    prompt = prompt.replace("{BATCH_CSV_PATH}", batch_csv)
    prompt = prompt.replace("{BATCH_NAME}", batch_name)
    prompt = prompt.replace("{OUTPUT_MD_PATH}", out_md)
    lines = [f"{r['编号']} | {r['标题']} | {r['摘要']}" for r in rows]
    return prompt + "\n\n## 本批次文献（编号 | 标题 | 摘要）\n\n" + "\n".join(lines)


def extract_table_rows(md_text):
    """取「## 筛选表」段（到下一个 ## 为止）的表格行；返回 [(编号, 行文本)]。"""
    seg = md_text
    idx = md_text.find("## 筛选表")
    if idx != -1:
        rest = md_text[idx + len("## 筛选表"):]
        end = rest.find("\n## ")
        seg = rest if end == -1 else rest[:end]
    rows = []
    for line in seg.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0].startswith("论文编号") or set(cells[0]) == {"-"}:
            continue
        re_id = cells[0]
        m = RE_PATTERN.search(re_id)
        if not m:
            continue
        rows.append((m.group(1) or m.group(2), "| " + " | ".join(cells) + " |"))
    return rows


def repair_illegal_re(key, content, rows, batch_ids):
    """非法编号修复：喂回非法行 + 本批合法编号，要求重输出（≤2 轮）。"""
    for _ in range(2):
        found = dict(extract_table_rows(content))
        illegal = [rid for rid in found if rid not in batch_ids]
        if not illegal:
            return content, False
        legit = sorted(batch_ids)
        prompt = (
            "你输出的筛选表里以下论文编号不在本批次 CSV 中（可能捏造或串批）：\n"
            f"{', '.join('[RE' + r + ']' for r in sorted(illegal))}\n\n"
            "本批次合法编号如下：\n"
            f"{', '.join('[RE' + r + ']' for r in legit)}\n\n"
            "请只输出这些非法行的修正版（若该编号实际对应某合法论文，请改用正确编号并保留分析内容；"
            "若确为误判，则不要输出该行）。格式 = 与筛选表一致的表格行：\n"
            "| [REXXX] | 相关性类别 | 关键研究方法与材料 | 核心性能指标 (量化) | 创新性与局限性分析 | 对我课题的启发点 |\n"
            "不要输出表格头或其他任何内容。")
        cont, _ = call_llm(key, [
            {"role": "user", "content": "你是科研专家，正在修正文献筛选表。"},
            {"role": "user", "content": prompt},
        ])
        fixed = "\n".join(row for _, row in extract_table_rows(cont))
        if fixed:
            for rid in illegal:
                content = re.sub(r"\|[^|\n]*\[RE" + re.escape(rid) + r"[^|\n]*\|",
                                 "| ~~非法行（编号 " + rid + " 不在本批，已移除）~~ |", content)
            content += "\n" + fixed
    remaining = [rid for rid, _ in extract_table_rows(content) if rid not in batch_ids]
    return content, bool(remaining)


def run_screen_one(key, topic, batch_no, project, slug, dry=False):
    analysis = os.path.join(project, "directions", slug, "analysis")
    batch_csv = os.path.join(analysis, f"batch_{batch_no:03d}.csv")
    topic_path = os.path.join(project, "directions", slug, "topics", topic + ".md")
    out_dir = os.path.join(project, "directions", slug, "topics", topic, "screening_batches")
    os.makedirs(out_dir, exist_ok=True)
    out_md = os.path.join(out_dir, f"batch_{batch_no:03d}.md")
    topic_text = read_text(topic_path)
    rows = read_batch_csv(batch_csv)
    template = read_prompt("01-screening.md")
    prompt = build_screen_prompt(template, topic_text, rows, batch_csv, out_md,
                                 f"batch_{batch_no:03d}")
    if dry:
        print(f"[dry] {topic} batch_{batch_no:03d} rows={len(rows)} prompt_chars={len(prompt)}")
        return "ok"
    key = load_key()
    content, finish = call_llm(key, [{"role": "user", "content": prompt}])
    rounds = 1
    while finish == "length" or "## 筛选表" not in content:
        if rounds >= 3:
            break
        cont, finish = call_llm(key, [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": content[-6000:]},
            {"role": "user", "content":
             "你的输出不完整（可能被截断）。请从上一段被截断的位置继续：完成剩余的筛选表行"
             "（论文编号带方括号 [REXXX] 原样、只含本批次编号），然后收尾。不要重复已输出的内容。"},
        ])
        content = content + "\n" + cont
        rounds += 1
    content, has_illegal = repair_illegal_re(key, content, rows, read_csv_ids(batch_csv))
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(content)
    n = len(extract_table_rows(content))
    flag = " ⚠️非法编号残留" if has_illegal else ""
    print(f"[done] {topic} batch_{batch_no:03d} rows_in={len(rows)} related={n} "
          f"rounds={rounds}{flag}")
    return "ok"


def cmd_screen(args):
    topics_dir = os.path.join(args.project, "directions", args.slug, "topics")
    analysis = os.path.join(args.project, "directions", args.slug, "analysis")
    batch_files = collect_batch_files(analysis)
    if not batch_files:
        if not args.split:
            print("错误：directions/<slug>/analysis/ 无 batch_NNN.csv（段5.3 分割产物）。"
                  "先跑 research-topic-building 的 split_batches.py，或加 --split 自动分割。")
            return 1
        evidence = os.path.join(args.project, "directions", args.slug, "search", "evidence.csv")
        os.makedirs(analysis, exist_ok=True)
        cmd_split(evidence, analysis)
        batch_files = collect_batch_files(analysis)
    slugs = args.topics.split(",") if args.topics else topic_slugs(topics_dir)
    if not slugs:
        print("错误：topics/ 下无课题 MD（段5 产物缺失）。")
        return 1
    tasks = [(t, n) for t in slugs for n in range(1, len(batch_files) + 1)]
    if args.only:
        tasks = [t for t in tasks if t[1] == args.only]
    workers = min(max(args.workers, 1), MAX_CONCURRENCY, len(tasks))
    print(f"screen: topics={slugs} batches=1-{len(batch_files)} tasks={len(tasks)} workers={workers}")
    key = None if args.dry else load_key()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(run_screen_one, key, t, n, args.project, args.slug, args.dry):
                   (t, n) for t, n in tasks}
        for fut in concurrent.futures.as_completed(futures):
            t, n = futures[fut]
            try:
                fut.result()
            except Exception as e:
                print(f"[FAIL] {t} batch_{n:03d}: {e}")
    return 0


def cmd_split(evidence, analysis, size=50):
    with open(evidence, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for i in range(0, len(rows), size):
        chunk = rows[i:i + size]
        path = os.path.join(analysis, f"batch_{i // size + 1:03d}.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=BATCH_COLUMNS)
            w.writeheader()
            for r in chunk:
                w.writerow({"编号": r.get("编号", ""), "标题": r.get("标题", ""),
                            "摘要": r.get("摘要", "")})


# ── 6.1 merge ───────────────────────────────────────────────────

def cmd_merge(args):
    topics_dir = os.path.join(args.project, "directions", args.slug, "topics")
    analysis = os.path.join(args.project, "directions", args.slug, "analysis")
    batch_files = collect_batch_files(analysis)
    total_papers = sum(len(read_batch_csv(os.path.join(analysis, f))) for f in batch_files)
    slugs = args.topics.split(",") if args.topics else topic_slugs(topics_dir)
    for slug in slugs:
        topic_path = os.path.join(topics_dir, slug + ".md")
        title = read_text(topic_path).splitlines()[0].lstrip("# ").strip()
        sb_dir = os.path.join(topics_dir, slug, "screening_batches")
        out = os.path.join(topics_dir, slug, "screening.md")
        parts = [
            f"# 强相关文献筛选表（{title}）\n",
            f"> 课题：topics/{slug}.md ｜ 论文池：directions/{args.slug}/search/evidence.csv"
            f"（{total_papers} 篇，{len(batch_files)} 批）｜ 合并自 screening_batches/\n",
            "> 相关性判定：A 理论支持 / B 技术路线支持 / C 关键资源与基准支持 / "
            "D 问题剖析与前瞻支持（至少一类 = 直接相关）\n",
        ]
        n_related = 0
        for f in batch_files:
            md_path = os.path.join(sb_dir, f.replace(".csv", ".md"))
            if not os.path.exists(md_path):
                print(f"[WARN] {slug} 缺 {os.path.basename(md_path)}，跳过该批")
                continue
            rows = extract_table_rows(read_text(md_path))
            n_related += len(rows)
            parts.append(f"\n## {f[:-4]}（源 screening_batches/{f[:-4]}.md）\n")
            parts.append("| " + " | ".join(TABLE_HEADERS) + " |")
            parts.append("| " + " | ".join(["---"] * len(TABLE_HEADERS)) + " |")
            parts.extend(row for _, row in rows)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(parts) + "\n")
        print(f"[merge] {slug} related={n_related} → {out}")
    return 0


# ── 6.1 check ───────────────────────────────────────────────────

def cmd_check(args):
    topics_dir = os.path.join(args.project, "directions", args.slug, "topics")
    analysis = os.path.join(args.project, "directions", args.slug, "analysis")
    batch_files = collect_batch_files(analysis)
    valid_re = set()
    for f in batch_files:
        valid_re |= read_csv_ids(os.path.join(analysis, f))
    slugs = args.topics.split(",") if args.topics else topic_slugs(topics_dir)
    ok = True
    for slug in slugs:
        sb_dir = os.path.join(topics_dir, slug, "screening_batches")
        issues = []
        if not os.path.isdir(sb_dir):
            issues.append("缺 screening_batches/")
        else:
            for f in batch_files:
                md_path = os.path.join(sb_dir, f.replace(".csv", ".md"))
                if not os.path.exists(md_path):
                    issues.append(f"缺 {f[:-4]}.md")
                    continue
                batch_ids = read_csv_ids(os.path.join(analysis, f))
                rows = extract_table_rows(read_text(md_path))
                seen = {}
                for rid, _ in rows:
                    if rid not in batch_ids:
                        issues.append(f"{f[:-4]}.md 含批次外编号 [RE{rid}]")
                    seen[rid] = seen.get(rid, 0) + 1
                for rid, c in seen.items():
                    if c > 1:
                        issues.append(f"{f[:-4]}.md 重复行 [RE{rid}] ×{c}")
            stray = {x[:-3] for x in os.listdir(sb_dir) if x.endswith(".md")}
            expected = {f[:-4] for f in batch_files}
            for x in sorted(stray - expected):
                issues.append(f"多余文件 {x}.md")
        merged = os.path.join(topics_dir, slug, "screening.md")
        if not os.path.exists(merged):
            issues.append("缺 screening.md（先跑 merge）")
        else:
            mrows = extract_table_rows(read_text(merged))
            mset = [rid for rid, _ in mrows]
            for rid, c in [(rid, mset.count(rid)) for rid in sorted(set(mset))]:
                if c > 1:
                    issues.append(f"screening.md 重复行 [RE{rid}] ×{c}")
            batch_rows = {}
            for f in batch_files:
                p = os.path.join(sb_dir, f.replace(".csv", ".md"))
                if os.path.exists(p):
                    batch_rows.update(dict(extract_table_rows(read_text(p))))
            if set(batch_rows) != set(mset):
                issues.append("screening.md 与分批表行集不一致")
        deepened = os.path.join(topics_dir, slug, "deepened.md")
        if os.path.exists(deepened):
            dtext = read_text(deepened)
            if "修改摘要" not in dtext:
                issues.append("deepened.md 缺「相对课题 MD 的修改摘要」段")
            if "**" not in dtext:
                issues.append("deepened.md 无加粗修改标记")
            d_bad = sorted({rid for rid, _ in
                            [(m.group(1) or m.group(2), "") for m in
                             RE_PATTERN.finditer(dtext)]} - valid_re, key=int)
            if d_bad:
                issues.append("deepened.md 引用证据集外编号 [RE"
                              + "],[RE".join(d_bad) + "]")
        if issues:
            ok = False
            print(f"[FAIL] {slug}: " + "；".join(issues))
        else:
            print(f"[ok] {slug}")
    return 0 if ok else 1


# ── 6.2 deepen ──────────────────────────────────────────────────

def build_deepen_prompt(template, topic_text, screening_text, screening_path, out_md):
    prompt = template.replace("{TOPIC_TEXT}", topic_text)
    prompt = prompt.replace("{SCREENING_PATH}", screening_path)
    prompt = prompt.replace("{SCREENING_SUMMARY}", screening_text)
    prompt = prompt.replace("{OUTPUT_MD_PATH}", out_md)
    return prompt


def run_deepen_one(key, topic, project, slug, dry=False):
    topics_dir = os.path.join(project, "directions", slug, "topics")
    topic_path = os.path.join(topics_dir, topic + ".md")
    screening_path = os.path.join(topics_dir, topic, "screening.md")
    out_md = os.path.join(topics_dir, topic, "deepened.md")
    if not os.path.exists(screening_path):
        print(f"[SKIP] {topic} 缺 screening.md（先跑 screen + merge）")
        return "skip"
    topic_text = read_text(topic_path)
    screening_text = read_text(screening_path)
    template = read_prompt("02-deepening.md")
    prompt = build_deepen_prompt(template, topic_text, screening_text, screening_path, out_md)
    if dry:
        print(f"[dry] {topic} screening_chars={len(screening_text)} prompt_chars={len(prompt)}")
        return "ok"
    key = load_key()
    content, finish = call_llm(key, [{"role": "user", "content": prompt}])
    rounds = 1
    while finish == "length" or "修改摘要" not in content:
        if rounds >= 3:
            break
        cont, finish = call_llm(key, [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": content[-6000:]},
            {"role": "user", "content":
             "你的输出不完整（可能被截断）。请继续完成进化版方案（含「相对课题 MD 的修改摘要」段、"
             "五要素完整、修改处加粗），不要重复已输出的内容。"},
        ])
        content = content + "\n" + cont
        rounds += 1
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[done] {topic} out_chars={len(content)} rounds={rounds}")
    return "ok"


def cmd_deepen(args):
    topics_dir = os.path.join(args.project, "directions", args.slug, "topics")
    slugs = args.topics.split(",") if args.topics else topic_slugs(topics_dir)
    workers = min(max(args.workers, 1), MAX_CONCURRENCY, len(slugs))
    print(f"deepen: topics={len(slugs)} workers={workers}")
    key = None if args.dry else load_key()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(run_deepen_one, key, t, args.project, args.slug, args.dry): t
                   for t in slugs}
        for fut in concurrent.futures.as_completed(futures):
            t = futures[fut]
            try:
                fut.result()
            except Exception as e:
                print(f"[FAIL] {t}: {e}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="段6 方案前置深化驱动（deepseek-v4-flash）")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("screen", "merge", "check", "deepen"):
        p = sub.add_parser(name)
        p.add_argument("--project", required=True)
        p.add_argument("--slug", required=True)
        p.add_argument("--topics", default=None, help="逗号分隔课题 slug；缺省 = topics/ 全部")
        if name == "screen":
            p.add_argument("--workers", type=int, default=MAX_CONCURRENCY)
            p.add_argument("--split", action="store_true", help="缺批次文件时按证据 CSV 重新分割")
            p.add_argument("--only", type=int, default=None, help="只跑指定批次号")
            p.add_argument("--dry", action="store_true")
        elif name == "deepen":
            p.add_argument("--workers", type=int, default=MAX_CONCURRENCY)
            p.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    fn = {"screen": cmd_screen, "merge": cmd_merge, "check": cmd_check, "deepen": cmd_deepen}
    sys.exit(fn[args.cmd](args))


if __name__ == "__main__":
    main()
