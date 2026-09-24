#!/usr/bin/env python3
"""段 9 9.7 合并：按 steps_manifest.json 顺序把分步文件合并为 mve_step_detail.md。

用法：python merge_step_detail.py --validation <vroot> --object <slug>
"""
import argparse
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validation", required=True)
    ap.add_argument("--object", required=True)
    args = ap.parse_args()
    vroot = os.path.abspath(args.validation)
    obj = args.object
    sdir = os.path.join(vroot, obj, "mve_steps")
    man = json.load(open(os.path.join(sdir, "steps_manifest.json"), encoding="utf-8"))

    out = [f"# MVE 逐步骤细化（9.7）· {obj}", "",
           f"> 范围：{man.get('scope')}（{len(man['steps'])} 步）",
           f"> 合并自 `{obj}/mve_steps/`；每步保留 ep4-B 七段结构。",
           f"> 引用：XE = 本对象知识库 `knowledge_base/{obj}.txt`；RE = 全局库/方向证据集。", ""]
    missing, total_headers = [], 0
    for st in man["steps"]:
        fp = os.path.join(sdir, st["file"])
        out += ["---", "", f"# {st['path']} 路径 · 步骤 {st['step_no']:02d}：{st.get('name', '')}", ""]
        if not os.path.isfile(fp):
            missing.append(st["file"])
            out += [f"> **[缺失]** 分步文件 `{st['file']}` 不存在。", ""]
            continue
        text = open(fp, encoding="utf-8").read().strip()
        total_headers += text.count("步骤定位")
        out += [text, ""]

    detail = os.path.join(vroot, obj, "mve_step_detail.md")
    open(detail, "w", encoding="utf-8").write("\n".join(out))
    print(f"[merge] {len(man['steps'])} steps, missing={missing}, 步骤定位 hits={total_headers}")
    print(f"[merge] -> {detail}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
