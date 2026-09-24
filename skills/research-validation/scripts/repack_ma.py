#!/usr/bin/env python3
"""段 9 9.3 后处理：把 meta_analysis.md 中按「**ACU [N.M]:**」格式写的 ACU 段切出，
重写为契约要求的 search_strategies.md（每 ACU 一段：锚点实体/关键词模块/三策略）
+ acu_index.json（默认起手 = 策略二·实现优先 的检索式）。

策略：
  - 按 `#### ACU [N.M]:` 段头切（出现 1 次即视为该 ACU 完整定义）
  - 若模型有「续写」，后段覆盖前段
  - 编号映射：ACU [N.M] → ACU-XXX（按全局出现顺序，三位零填充）
"""
import json
import os
import re
import sys

ACU_HEADER = re.compile(r"^#{2,4}\s*ACU\s*\[(\d+)\.(\d+)\][：:]\s*(.+?)\s*$", re.MULTILINE)
ALT_ACU_HEADER = re.compile(r"^\*\*ACU\s*\[(\d+)\.(\d+)\][：:]\s*(.+?)\*\*\s*$", re.MULTILINE)
QUERIED = re.compile(r"检索式[：:]?\s*[`']?(TITLE-ABS-KEY\([^`]+\))[`']?")
ANCHOR = re.compile(r"锚点实体[：:]\s*(.+?)$", re.MULTILINE)


def parse_meta(text: str) -> dict:
    """扫描全文，按 ACU [N.M] 切段（保留最后一次出现的内容）。"""
    # 先找所有 `#### ACU [N.M]:` 头
    headers = []
    for m in re.finditer(r"^#{2,4}\s*ACU\s*\[(\d+)\.(\d+)\][：:]\s*([^\n]+)$", text, re.MULTILINE):
        headers.append((m.start(), int(m.group(1)), int(m.group(2)), m.group(3).strip(), m.end()))
    if not headers:
        # fallback：**ACU [N.M]:** 行（meta_analysis.md 早段用这种）
        for m in re.finditer(r"^\*\*ACU\s*\[(\d+)\.(\d+)\][：:]\s*([^\n]+?)\*\*\s*$", text, re.MULTILINE):
            headers.append((m.start(), int(m.group(1)), int(m.group(2)), m.group(3).strip(), m.end()))

    headers.sort()
    # 去重（保留最后一个）
    last_by_key = {}
    for h in headers:
        _, stage, sub, name, end = h
        last_by_key[(stage, sub)] = (h, name)

    sections = []
    for key, (h, name) in sorted(last_by_key.items(), key=lambda x: x[1][0][0]):
        pos, stage, sub, _, end = h
        # 找段尾：下一个 `#### ACU` 或 `### 阶段` 或 `---`
        rest = text[end:]
        end_match = re.search(r"^#{2,4}\s*ACU\s*\[\d+\.\d+\]|^###\s*阶段|^---|^####\s*ACU\s*\[\d+\.\d+\]|^##\s*第三步|^##\s*第四步", rest, re.MULTILINE)
        if end_match:
            section_text = rest[:end_match.start()].rstrip()
        else:
            section_text = rest.rstrip()
        sections.append({
            "stage": stage,
            "sub": sub,
            "name": name,
            "text": section_text,
        })
    return sections


def build_search_strategies_md(sections: list, source_objects: list) -> str:
    """按 ACU 编号顺序生成 search_strategies.md。"""
    out = ["# 检索式策略（按 ACU）\n",
           "> 默认起手 = 策略二·实现优先；每 ACU 含锚点实体 / 关键词模块 / 三策略菜单。\n",
           f"> 来源对象：{', '.join(source_objects)}\n\n"]
    for i, sec in enumerate(sections, start=1):
        acu_id = f"ACU-{i:03d}"
        name = sec["name"]
        out.append(f"## {acu_id} {name}\n\n")
        out.append(f"- 锚点实体：{extract_anchor(sec['text'])}\n")
        # 找关键词模块
        kw_match = re.search(r"关键词模块定义[：:](.*?)(?=组合策略菜单|组合检索式说明|$)", sec["text"], re.DOTALL)
        if kw_match:
            out.append(f"- 关键词模块定义：\n\n{kw_match.group(1).strip()}\n\n")
        # 找三策略
        strat_match = re.search(r"组合策略菜单[：:](.*?)(?=组合检索式说明|---|$)", sec["text"], re.DOTALL)
        if strat_match:
            out.append(f"- 组合策略菜单：\n\n{strat_match.group(1).strip()}\n\n")
        out.append("---\n\n")
    return "".join(out)


def extract_anchor(text: str) -> str:
    """从 ACU 文本中提取第一个「锚点实体」行。"""
    m = re.search(r"锚点实体[：:]\s*([^\n]+)", text)
    if m:
        return m.group(1).strip()
    return "（未显式给出）"


def build_acu_index(sections: list, source_objects: list) -> dict:
    """按 ACU 编号顺序生成 acu_index.json，默认起手 = 策略二·实现优先。"""
    out = {}
    for i, sec in enumerate(sections, start=1):
        acu_id = f"ACU-{i:03d}"
        # 抓策略二下的检索式
        # 找到「策略二：」与「策略三：」之间的所有 TITLE-ABS-KEY
        strat2 = re.search(r"策略二[：:].*?(?=策略三|---|\Z)", sec["text"], re.DOTALL)
        query = ""
        if strat2:
            m = QUERIED.search(strat2.group(0))
            if m:
                query = m.group(1)
        out[acu_id] = {
            "name": sec["name"],
            "stage": f"阶段 [{sec['stage']}]",
            "source_objects": source_objects,
            "query": query,
            "default_strategy": "②实现优先"
        }
    return out


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    proj = sys.argv[1].rstrip("\\/")
    slug = sys.argv[2]
    object_slug = sys.argv[3]
    ma_path = os.path.join(proj, "directions", slug, "validation", "meta_analysis.md")
    out_dir = os.path.join(proj, "directions", slug, "validation")
    text = open(ma_path, encoding="utf-8").read()
    sections = parse_meta(text)
    if not sections:
        print("[repack] no ACU sections found in meta_analysis.md")
        sys.exit(1)
    print(f"[repack] parsed {len(sections)} ACU sections: {[(s['stage'], s['sub'], s['name']) for s in sections]}")
    ss_md = build_search_strategies_md(sections, [object_slug])
    with open(os.path.join(out_dir, "search_strategies.md"), "w", encoding="utf-8") as f:
        f.write(ss_md)
    acu = build_acu_index(sections, [object_slug])
    with open(os.path.join(out_dir, "acu_index.json"), "w", encoding="utf-8") as f:
        json.dump(acu, f, ensure_ascii=False, indent=2)
    print(f"[repack] wrote search_strategies.md and acu_index.json ({len(acu)} ACU entries)")


if __name__ == "__main__":
    main()
