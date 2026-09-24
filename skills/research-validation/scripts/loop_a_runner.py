#!/usr/bin/env python3
"""LOOP A coordinator: prepare → native host-agent workers → collect/status.

prepare (round alias) fetches the first Scopus page and exports isolated tasks.
collect validates worker JSON and commits shared state once; status is read-only.
Contexts come from each ACU's source_objects, never one global --object.
The API helpers below remain only for historical repair scripts that import L;
normal LOOP A commands neither load a model key nor call a model endpoint.
"""
import argparse
import json
import os
import re
import subprocess
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


def write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


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
            {"role": "user", "content": "你的输出不完整（可能被截断）。请继续完成剩余内容，不要重复。"},
        ])
        content = content + "\n" + cont
        rounds += 1
    return content, rounds


def fetch_scopus(query, out_path):
    """调 fetch_scopus.py 子进程。"""
    env = os.environ.copy()
    env["SCOPUS_API_KEY"] = os.environ.get("SCOPUS_API_KEY", "")
    if not env["SCOPUS_API_KEY"]:
        raise RuntimeError("SCOPUS_API_KEY not set in env")
    result = subprocess.run(
        [sys.executable, os.path.join(SKILL_DIR, "scripts", "fetch_scopus.py"),
         "search", "--query", query, "--out", out_path],
        env=env, capture_output=True, text=True, timeout=180
    )
    return result.returncode, result.stdout, result.stderr


def format_entries_for_verdict(results_path, max_entries=25):
    """读 results_raw.json，把 ≤25 条 entry 格式化成「序号 | 标题 | 摘要 | 年份 | 期刊 | EID」"""
    data = json.load(open(results_path, encoding="utf-8"))
    entries = (data.get("search-results") or {}).get("entry") or []
    lines = []
    for i, e in enumerate(entries[:max_entries], start=1):
        title = (e.get("dc:title") or "").strip()
        abstract = ""
        if "abstract" in e and e["abstract"]:
            abstract = (e["abstract"].get("abstract") or "").strip()
        year = (e.get("prism:coverDate") or "")[:4]
        journal = (e.get("prism:publicationName") or "").strip()
        eid = e.get("eid") or ""
        lines.append(f"{i} | {title} | {abstract} | {year} | {journal} | EID:{eid}")
    return "\n".join(lines), len(entries)


def run_verdict(acu_id, mve_text, scopus_entries_text, key):
    """调 ep4-A verdict prompt，对 ≤25 条 Scopus 条目分级。"""
    template = read_text(os.path.join(SKILL_DIR, "prompts", "04-loop-a-verdict.md"))
    # 模板里有占位符（待确认）；如果没有，就末尾追加
    prompt = template
    for placeholder in ["{SCOPUS_ENTRIES}", "{INPUT_ENTRIES}"]:
        prompt = prompt.replace(placeholder, scopus_entries_text)
    for placeholder in ["{MVE_TEXT}", "{MVE_PATHS}", "{MVE_CONTEXT}"]:
        prompt = prompt.replace(placeholder, mve_text)
    prompt = prompt.replace("{ACU_ID}", acu_id)
    if "{INPUT_NOTE}" in prompt:
        prompt = prompt.replace("{INPUT_NOTE}", scopus_entries_text)
    else:
        prompt += f"\n\n## ACU：{acu_id}\n\n## MVE 路径上下文\n\n{mve_text}\n\n## Scopus 条目（序号 | 标题 | 摘要 | 年份 | 期刊 | EID）\n\n{scopus_entries_text}"
    prompt += "\n\n输出适配：逐条覆盖全部输入；仅用以下四列表头，级别为高/中/建议排除之一。\n" \
              "| 论文标识 | 级别 | 可复现的关键步骤与参数 | 可直接整合至我方案的具体步骤 |\n"
    content, rounds = run_with_continuation(
        key, prompt,
        must_contain=["| 论文标识 | 级别 | 可复现的关键步骤与参数 | 可直接整合至我方案的具体步骤 |"]
    )
    return content, rounds


def grade_pass(verdict_text: str) -> bool:
    """PASS = verdict 含 ≥1 个「高」行（容忍 3 列 + 优先级段 或 4 列表）。"""
    high_count = 0
    for line in verdict_text.splitlines():
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
        # 优先级 1: 第 2 列 = "高"（4 列表）
        if len(cells) >= 2 and cells[1] == "高":
            high_count += 1
            continue
        # 优先级 2: 4 列表（含 优先级/理由 列）→ 任何 cell 含 "高" 或 "高优先"
        if any(("高" == c.strip() or "高优先级" in c) for c in cells):
            high_count += 1
            continue
    return high_count > 0


def process_one(acu_id, query, round_n, mve_text, key, base_dir, dry=False):
    """一个 ACU 一轮：fetch_scopus + verdict + 状态更新。"""
    run_dir = os.path.join(base_dir, "scopus_runs", acu_id, f"round_{round_n:02d}")
    raw_path = os.path.join(run_dir, "results_raw.json")
    verdict_path = os.path.join(run_dir, "verdict.md")

    if dry:
        return {"acu": acu_id, "round": round_n, "dry": True}

    # 1. fetch scopus
    rc, out, err = fetch_scopus(query, raw_path)
    if rc != 0 and not os.path.exists(raw_path):
        return {"acu": acu_id, "round": round_n, "error": f"scopus fetch failed: rc={rc}, err={err[:200]}"}
    # 读 totalResults
    data = json.load(open(raw_path, encoding="utf-8"))
    total = int((data.get("search-results") or {}).get("opensearch:totalResults", 0) or 0)
    n_entries = len((data.get("search-results") or {}).get("entry") or [])

    if total == 0:
        return {"acu": acu_id, "round": round_n, "totalResults": 0, "pass": False}

    # 2. verdict
    entries_text, n_kept = format_entries_for_verdict(raw_path)
    verdict_text, verdict_rounds = run_verdict(acu_id, mve_text, entries_text, key)
    write_text(verdict_path, verdict_text)
    passed = grade_pass(verdict_text)
    return {
        "acu": acu_id, "round": round_n, "totalResults": total, "entries": n_entries,
        "verdict_rounds": verdict_rounds, "pass": passed
    }


def validation_root(args):
    if args.validation:
        return os.path.abspath(args.validation)
    if args.project and args.slug:
        return os.path.abspath(os.path.join(args.project, "directions", args.slug, "validation"))
    raise ValueError("use --validation or both --project and --slug")


def cmd_round(args):
    """Compatibility entry point: round now PREPARES native-agent tasks only."""
    import loop_a_tasks as tasks
    return tasks.prepare(validation_root(args), workers=args.workers,
                         env_file=args.env_file, dry=args.dry)


def main(argv=None):
    import loop_a_tasks as tasks
    ap = argparse.ArgumentParser(description="LOOP A native-agent task coordinator; no model API required")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "round", "collect", "status"):
        p = sub.add_parser(name, help="round is an alias for prepare" if name == "round" else None)
        p.add_argument("--validation")
        p.add_argument("--project")
        p.add_argument("--slug")
        if name in ("prepare", "round"):
            p.add_argument("--object", help="legacy argument; contexts come from acu_index.source_objects")
            p.add_argument("--workers", type=int, default=4, help="Scopus request concurrency, 1..100")
            p.add_argument("--env-file")
            p.add_argument("--dry", action="store_true", help="read-only plan, no credentials/network/writes")
    args = ap.parse_args(argv)
    try:
        root = validation_root(args)
        if args.cmd in ("prepare", "round"):
            result = cmd_round(args)
        elif args.cmd == "collect":
            result = tasks.collect(root)
        else:
            result = tasks.status(root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("errors"):
            return 2
        return 3 if result.get("gate3_pending") else 0
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
