#!/usr/bin/env python3
"""段 9 9.7 输入准备：为每个 (对象 × 路径 × 步骤) 生成一份自包含提示词文件。

每份文件 = `prompts/06-mve-detail.md` 原文 + 该步骤专属输入（严格输入隔离）：
  - 知识库1：本对象 XE 知识库（按该步骤 source_acus 切片）
  - 知识库2：核心参考文献 RE 材料（按该路径/步骤实际引用的 RE 切片）
  - 最短验证路径：mve_paths.md 中该路径全文
  - 研究设计：research_design.md（对象自生成版）
  - 本次需要优化的内容：该步骤原文

用法：
  python build_step_prompts.py --validation <vroot> --object <slug>
输出：
  <vroot>/<object>/mve_steps/_prompts/<path>_step_NN.prompt.md
  <vroot>/<object>/mve_steps/steps_manifest.json
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)

SEVEN = """## 输出结构（硬性要求，七段齐全，标题原样）

**1. 步骤定位**
**2. 优化目标**
**3. 【主方案】MVE核心路径**
**4. 【备选战略】**
**5. 战略选择建议**
**6. 对资源清单的影响**
**7. 验证与检查点 (Go/No-Go Criteria)**

引用规则（违反即作废）：
- 知识库引用只允许 `XE001..` 形式（必须来自下面「知识库1」的条目），RE 引用只允许 `[REXXX]` 形式（必须来自下面「知识库2」）。
- 禁止编造 XE/RE 编号、文献标题、参数；知识库没有的，按提示词「情况三」三段式写并声明核实要求。
- Go/No-Go 必须可量化（阈值 + 判据 + 失败后动作）。
- 输出为完整 markdown 正文，不要前言寒暄，不要额外表格以外的解释性前缀。
"""


def split_paths(mve_text):
    """按 `## 路径 A` / `## 路径 B` 切出两段。"""
    out = {}
    m = re.search(r"^##\s*路径\s*A(.*?)(?=^##\s*路径\s*B|\Z)", mve_text, re.DOTALL | re.MULTILINE)
    if m:
        out["A"] = m.group(0).strip()
    m = re.search(r"^##\s*路径\s*B(.*?)(?=^##\s*路径\s*A\s*与\s*路径\s*B|\Z)", mve_text, re.DOTALL | re.MULTILINE)
    if m:
        out["B"] = m.group(0).strip()
    return out


def steps_of(path_text):
    """抽 `**步骤 N：<name>**` 及其正文。"""
    steps = []
    for m in re.finditer(r"^\*\*步骤\s*(\d+)[：:]\s*(.+?)\*\*\s*$", path_text, re.MULTILINE):
        start = m.end()
        nxt = re.search(r"^\*\*步骤\s*\d+[：:]|^####\s|^###\s", path_text[start:], re.MULTILINE)
        body = path_text[start:start + nxt.start()] if nxt else path_text[start:]
        steps.append({"no": int(m.group(1)), "name": m.group(2).strip(), "body": body.strip()})
    return steps


def slice_kb(kb_text, acus):
    """知识库按 `=== XEXXX ... ===` 条目切，保留 source ACU 与 acus 有交集的条目。"""
    blocks = re.split(r"(?m)^(?====\s*XE\d)", kb_text)
    head = blocks[0]
    kept = []
    for b in blocks[1:]:
        m = re.search(r"来源 ACU[：:]\s*(.+)", b)
        src = m.group(1) if m else ""
        if not acus or any(a in src for a in acus):
            kept.append(b)
    return head + "".join(kept), len(kept)


def slice_re(re_text, cited):
    blocks = re.split(r"(?m)^(?=##\s*\[RE)", re_text)
    head = blocks[0]
    kept = []
    for b in blocks[1:]:
        m = re.match(r"##\s*\[RE(\d+)\]", b)
        if m and int(m.group(1)) in cited:
            kept.append(b)
    return head + "".join(kept), len(kept)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validation", required=True)
    ap.add_argument("--object", required=True)
    ap.add_argument("--manifest", default=None, help="自定义 steps_manifest.json（默认用对象内已存在的）")
    args = ap.parse_args()

    vroot = os.path.abspath(args.validation)
    obj = args.object
    odir = os.path.join(vroot, obj)
    sdir = os.path.join(odir, "mve_steps")
    pdir = os.path.join(sdir, "_prompts")
    os.makedirs(pdir, exist_ok=True)

    mve_text = open(os.path.join(odir, "mve_paths.md"), encoding="utf-8").read()
    rd_text = open(os.path.join(odir, "research_design.md"), encoding="utf-8").read()
    kb_path = os.path.join(vroot, "knowledge_base", f"{obj}.txt")
    kb_text = open(kb_path, encoding="utf-8").read() if os.path.isfile(kb_path) else ""
    re_path = os.path.join(odir, "re_material.md")
    re_text = open(re_path, encoding="utf-8").read() if os.path.isfile(re_path) else ""
    prompt06 = open(os.path.join(SKILL_DIR, "prompts", "06-mve-detail.md"), encoding="utf-8").read()

    man_path = args.manifest or os.path.join(sdir, "steps_manifest.json")
    manifest = json.load(open(man_path, encoding="utf-8")) if os.path.isfile(man_path) else None
    loop_state = {}
    ls_path = os.path.join(vroot, "loop_state.json")
    if os.path.isfile(ls_path):
        loop_state = json.load(open(ls_path, encoding="utf-8")).get("acus", {})
    paths = split_paths(mve_text)
    built = []
    for path_key in ("A", "B"):
        steps = steps_of(paths.get(path_key, ""))
        for st in steps:
            entry = None
            if manifest:
                entry = next((s for s in manifest["steps"]
                              if s["path"] == path_key and s["step_no"] == st["no"]), None)
            acus = (entry or {}).get("source_acus") or []
            st_status = {a: (loop_state.get(a, {}).get("status") or "unknown") for a in acus}
            covered = [a for a, s in st_status.items() if s == "covered"]
            gap = [a for a, s in st_status.items() if s != "covered"]
            skipped = bool(acus) and not covered
            kb_slice, n_kb = slice_kb(kb_text, acus)
            cited = {int(x) for x in re.findall(r"\[RE(\d+)\]", st["body"] + paths[path_key])}
            # RE 材料：每步都给全量（对象级 31 条左右），保证 B 路径步骤也有 RE 可引；
            # cited 只用于统计与提示。
            re_slice, n_re = re_text, len(re.findall(r"(?m)^##\s*\[RE\d+\]", re_text))

            step_file = f"{path_key}_step_{st['no']:02d}.md"
            out = [prompt06, "\n\n---\n\n", "**【指定知识库】**\n\n",
                   f"**知识库1（XE 高文献知识库，本步骤相关 {n_kb} 条）**：\n\n", kb_slice,
                   "\n\n**知识库2（核心参考文献 RE，本路径/步骤引用 "
                   f"{n_re} 条）**：\n\n", re_slice,
                   "\n\n**【最短验证路径】**\n\n", paths.get(path_key, ""),
                   "\n\n**【研究设计（对象自生成 ep1）】**\n\n", rd_text,
                   "\n\n**【本次需要优化的内容】**\n\n",
                   f"步骤 {st['no']}：{st['name']}\n\n{st['body']}\n\n",
                   "**【输出路径】**\n\n",
                   f"`{os.path.join(sdir, step_file)}`\n\n",
                   SEVEN]
            if skipped:
                out.append("\n**本步骤特别声明**：本步骤对应的实现锚点 ACU（"
                           + "、".join(acus) + "）在闸门3 被跳过/未覆盖，"
                           "必须显式标注「实现锚点缺失」，参数只能按通用实践给出并写明核实要求。\n")
            elif gap:
                out.append("\n**本步骤特别声明**：本步骤的部分实现锚点 ACU（"
                           + "、".join(f"{a}({st_status[a]})" for a in gap)
                           + "）在闸门3 被跳过/未覆盖；涉及这些锚点的环节请显式标注「实现锚点缺失」，"
                             "参数按通用实践给出并写明核实要求；其余环节照常用知识库 XE 引用。\n")
            text = "".join(out)
            fp = os.path.join(pdir, f"{path_key}_step_{st['no']:02d}.prompt.md")
            open(fp, "w", encoding="utf-8").write(text)
            built.append({"path": path_key, "step_no": st["no"], "name": st["name"],
                          "file": f"{path_key}_step_{st['no']:02d}.md",
                          "prompt_file": os.path.relpath(fp, vroot).replace("\\", "/"),
                          "source_acus": acus, "skipped": skipped,
                          "kb_entries": n_kb, "re_entries": n_re})
            print(f"  built {path_key}_step_{st['no']:02d}: {st['name']} "
                  f"(kb={n_kb}, re={n_re}, skipped={skipped}, {len(text)} chars)")

    new_manifest = {
        "object": obj,
        "scope": "A+B all steps",
        "source": "mve_paths.md（路径 A / 路径 B 各步骤）",
        "steps": [{"path": b["path"], "step_no": b["step_no"], "file": b["file"],
                   "name": b["name"], "source_acus": b["source_acus"],
                   "skipped": b["skipped"], "prompt_file": b["prompt_file"]} for b in built],
    }
    with open(os.path.join(sdir, "steps_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False, indent=2)
    print(f"[done] {len(built)} prompts -> {pdir}")
    print(f"[done] manifest -> {os.path.join(sdir, 'steps_manifest.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
