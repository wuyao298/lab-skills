#!/usr/bin/env python3
"""research-topic-building 批量分析驱动：batch_NNN.csv → batch_NNN.md（段5.4 Step 2）。

运行模型：opencode-go 供应商 deepseek-v4-flash（用户机制 2026-08-13）。
- API：OpenAI 兼容 `https://opencode.ai/zen/go/v1/chat/completions`
- key：`~/.local/share/opencode/auth.json` 的 `opencode-go` 条目
- 必须带浏览器 User-Agent 头（否则 Cloudflare 403）

机制：
- 并发上限 100，缺省 workers = min(批数, 100)，尽可能大并发
- 输出截断/缺「## 综合报告」段 → 自动续写（≤3 轮）
- 矩阵覆盖核对：缺行 → 自动把缺失篇目（编号+标题+摘要）喂回补行，补行插入「## 进阶分析矩阵」段内
  （不得追加到文件尾）；修复 ≤2 轮
- 失败重试：网络异常退避重试 3 次

用法：
  python batch_analysis_runner.py --project <工作目录> --slug <slug> \
      --focus "方向核心焦点(用+连接3-4个关键词)" \
      [--from 1] [--to N] [--workers 100] [--only N] [--dry]
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
MODEL = os.environ.get("BATCH_MODEL", "deepseek-v4-flash")
AUTH = os.path.expanduser(r"~\.local\share\opencode\auth.json")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAX_CONCURRENCY = 100
RE_PATTERN = re.compile(r"\[RE(\d+)\]|(?:^|\s)RE(\d+)(?=\s|\||$|，|,|\.|：|:)")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "Chrome/131.0 Safari/537.36")


def load_key(auth_path=AUTH):
    if os.environ.get("OPENCODE_GO_KEY"):
        return os.environ["OPENCODE_GO_KEY"]
    d = json.load(open(auth_path, encoding="utf-8"))
    return d["opencode-go"]["key"]


def read_prompt_template():
    with open(os.path.join(SKILL_DIR, "prompts", "01-batch-analysis.md"), encoding="utf-8") as f:
        return f.read()


def read_batch(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_prompt(template, batch_rows, focus, batch_csv_path, out_md_path, batch_name):
    prompt = template.replace("{DIRECTION_FOCUS}", focus)
    prompt = prompt.replace("{BATCH_CSV_PATH}", batch_csv_path)
    prompt = prompt.replace("{BATCH_NAME}", batch_name)
    prompt = prompt.replace("{OUTPUT_MD_PATH}", out_md_path)
    lines = [f"{r['编号']} | {r['标题']} | {r['摘要']}" for r in batch_rows]
    return prompt + "\n\n## 本批次文献（编号 | 标题 | 摘要）\n\n" + "\n".join(lines)


def call_llm(key, messages, max_retries=3, max_tokens=40000):
    payload = {"model": MODEL, "messages": messages, "max_tokens": max_tokens}
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(API, data=body, headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + key,
                "User-Agent": USER_AGENT,
            })
            with urllib.request.urlopen(req, timeout=900) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]
            return choice["message"]["content"], choice.get("finish_reason")
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(10 * (attempt + 1))


def matrix_re_ids(text):
    ids = set()
    for m in RE_PATTERN.finditer(text):
        ids.add(m.group(1) or m.group(2))
    return ids


def csv_id_map(rows):
    return {re.sub(r"[^0-9]", "", r["编号"]): r for r in rows}


def insert_rows_before_section(md_text, rows_block):
    """把补行插入「## 进阶分析矩阵」段内（综合报告段之前）；无该段则追加文末。"""
    idx = md_text.find("## 综合报告")
    if idx == -1:
        return md_text + "\n" + rows_block
    return md_text[:idx] + rows_block.rstrip() + "\n\n" + md_text[idx:]


def repair_missing(key, content, rows):
    """矩阵缺行修复：喂回缺失篇目，返回补行文本（≤2 轮内完成）。"""
    for _ in range(2):
        csv_ids = set(csv_id_map(rows))
        missing = sorted(csv_ids - matrix_re_ids(content), key=int)
        if not missing:
            return ""
        by_id = csv_id_map(rows)
        papers = "\n".join(
            f"{by_id[m]['编号']} | {by_id[m]['标题']} | {by_id[m]['摘要']}" for m in missing)
        prompt = (
            f"你之前对文献批次做了「进阶分析矩阵」，但遗漏了以下 {len(missing)} 篇：\n\n"
            f"{papers}\n\n"
            "请只输出这些缺失篇目的矩阵行，格式与已有矩阵一致：\n"
            "| [REXXX] | 关键研究方法与材料 | 核心性能指标(量化，含数值) | 创新性与局限性分析 | 对我课题的启发点 |\n"
            "每篇一行，编号带方括号原样，不要输出表格头或其他任何内容。")
        cont, _ = call_llm(key, [
            {"role": "user", "content": "你是科研分析师，正在补全文献批次分析矩阵。"},
            {"role": "user", "content": prompt},
        ])
        content = insert_rows_before_section(content, cont)
    return content


def run_one(batch_no, project, slug, focus, dry=False):
    analysis = os.path.join(project, "directions", slug, "analysis")
    batch_csv = os.path.join(analysis, f"batch_{batch_no:03d}.csv")
    out_md = os.path.join(analysis, f"batch_{batch_no:03d}.md")
    rows = read_batch(batch_csv)
    template = read_prompt_template()
    prompt = build_prompt(template, rows, focus, batch_csv, out_md, f"batch_{batch_no:03d}")
    if dry:
        print(f"[dry] batch_{batch_no:03d} rows={len(rows)} prompt_chars={len(prompt)}")
        return "ok"
    key = load_key()
    content, finish = call_llm(key, [{"role": "user", "content": prompt}])
    rounds = 1
    while finish == "length" or "## 综合报告" not in content:
        if rounds >= 3:
            break
        cont, finish = call_llm(key, [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": content[-6000:]},
            {"role": "user", "content":
             "你的输出不完整（可能被截断）。请从上一段被截断的位置继续：完成剩余的进阶分析矩阵行"
             "（每篇必现、编号带方括号 [REXXX] 原样），然后完成「## 综合报告」整段。"
             "不要重复已输出的内容，只输出剩余部分。"},
        ])
        content = content + "\n" + cont
        rounds += 1
    content = repair_missing(key, content, rows)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[done] batch_{batch_no:03d} rows={len(rows)} out_chars={len(content)} rounds={rounds}")
    return "ok"


def main():
    parser = argparse.ArgumentParser(description="段5.4 分批深度分析驱动（deepseek-v4-flash）")
    parser.add_argument("--project", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--focus", required=True)
    parser.add_argument("--from", dest="start", type=int, default=1)
    parser.add_argument("--to", type=int, default=None)
    parser.add_argument("--workers", type=int, default=MAX_CONCURRENCY)
    parser.add_argument("--only", type=int, default=None)
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()

    analysis = os.path.join(args.project, "directions", args.slug, "analysis")
    n_batches = len([f for f in os.listdir(analysis) if re.match(r"batch_\d{3}\.csv$", f)])
    end = args.to if args.to is not None else n_batches
    nos = range(args.start, end + 1)
    workers = min(max(args.workers, 1), MAX_CONCURRENCY, len(list(nos)))

    if args.only:
        run_one(args.only, args.project, args.slug, args.focus, dry=args.dry)
        return

    print(f"batches={list(nos)[0]}-{list(nos)[-1]} workers={workers}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(run_one, n, args.project, args.slug, args.focus, args.dry): n
                   for n in nos}
        for fut in concurrent.futures.as_completed(futures):
            n = futures[fut]
            try:
                fut.result()
            except Exception as e:
                print(f"[FAIL] batch_{n:03d}: {e}")


if __name__ == "__main__":
    main()
