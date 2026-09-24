import csv
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import check_validation as cv

FIX = Path(__file__).parent / "fixtures"


def write_re_db(path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["编号", "标题", "DOI", "EID"])
        w.writeheader()
        w.writerow({
            "编号": "[RE257]",
            "标题": "Capacitance loss and ESR evolution of metallized film capacitors under repetitive pulses",
            "DOI": "10.1109/example.2024.0001",
            "EID": "2-s2.0-85000000001",
        })


def write_mini_project(root, build=True):
    p = Path(root)
    slug = "mfc"
    (p / "reports").mkdir(parents=True)
    (p / "directions" / slug / "topics" / "obj1").mkdir(parents=True)
    (p / "directions" / slug / "thesis" / "plan").mkdir(parents=True)
    write_re_db(p / "reports" / "literature_db.csv")
    (p / "directions" / slug / "direction.md").write_text("# 方向契约\n", encoding="utf-8")
    (p / "directions" / slug / "topics" / "obj1.md").write_text(
        "# 课题 obj1\n\n核心问题\n", encoding="utf-8")
    (p / "directions" / slug / "thesis" / "plan" / "constraints.md").write_text(
        "# constraints\n\nC-001 频率 ≤20 Hz\n", encoding="utf-8")

    v = p / "directions" / slug / "validation"
    for d in ["obj1/mve_steps", "scopus_runs/ACU-001/round_01", "knowledge_base"]:
        (v / d).mkdir(parents=True, exist_ok=True)
    (v / "selection.md").write_text(
        "# 验证对象选择（Step 0）\n\n> 用户原话：选 obj1，A+B 全部步骤。\n\n"
        "## 对象清单\n\n- **对象 1**：obj1 ｜ 9.7 细化范围：路径 A 全部步骤 + 路径 B 全部步骤\n",
        encoding="utf-8")
    (v / "metadata.json").write_text(json.dumps({
        "skill": "research-validation",
        "project": str(p), "slug": slug, "objects": ["obj1"],
        "last_step": "check", "loop_round": 1, "gate3_pending": False,
    }, ensure_ascii=False), encoding="utf-8")
    (v / "obj1" / "research_design.md").write_text(
        "# 研究设计\n\n已读 constraints.md。\n\n# 第一部分 研究基本盘——问题与假说\n\n核心问题。\n\n"
        "# 第二部分 核心实验方案——从设计到执行\n\n步骤一 [RE257]。\n", encoding="utf-8")
    (v / "obj1" / "mve_paths.md").write_text(
        "# MVE\n\n路径 A：问题-假设验证路径\n核心假设：X。G：>1；N-G：<1。"
        "低配替代：用现有设备。路径 B：方案-假设验证路径\n核心假设：Y。"
        "G：>2；N-G：<2。低配替代：简化组。\n\n两路径互补说明 + 成功/失败行动路径。\n",
        encoding="utf-8")
    (v / "meta_analysis.md").write_text(
        "# 元分析\n\n阶段1：测量。ACU-001 停机测量（来源对象：obj1）。任务依赖图 + 并行可能。关键路径：ACU-001。\n",
        encoding="utf-8")
    (v / "search_strategies.md").write_text(
        "# 检索策略\n\n## ACU-001 停机测量\n\n- 锚点实体：film capacitor\n"
        '- 组合策略菜单：\n  - 策略一：精准打击 检索式：`TITLE-ABS-KEY("film capacitor" AND "esr")`\n'
        '  - 策略二：实现优先（默认起手） 检索式：`TITLE-ABS-KEY("film capacitor" AND "esr" AND "protocol")`\n'
        '  - 策略三：双核探索 检索式：`TITLE-ABS-KEY("film capacitor" AND "esr")`\n',
        encoding="utf-8")
    (v / "acu_index.json").write_text(json.dumps({
        "ACU-001": {"name": "停机测量", "stage": "阶段1", "source_objects": ["obj1"],
                    "query": 'TITLE-ABS-KEY("film capacitor" AND "esr" AND "protocol")',
                    "default_strategy": "②实现优先"}
    }, ensure_ascii=False), encoding="utf-8")
    shutil.copy(FIX / "mini_scopus_raw.json",
                v / "scopus_runs/ACU-001/round_01/results_raw.json")
    shutil.copy(FIX / "mini_verdict.md",
                v / "scopus_runs/ACU-001/round_01/verdict.md")
    (v / "loop_state.json").write_text(json.dumps({
        "version": 1, "round": 1, "max_rounds": 10,
        "acus": {"ACU-001": {"query": "q", "status": "covered", "merged_into": None,
                              "pass_round": 1, "consecutive_fails": 0,
                              "last_total_results": 2}},
        "skipped_acus": [], "gate_history": []}, ensure_ascii=False), encoding="utf-8")
    (v / "per_ACU_summary.json").write_text(json.dumps({
        "ACU-001": {"source_objects": ["obj1"], "rounds_run": [1], "fail_rounds": [],
                    "consecutive_fails": 0, "pass_round": 1, "status": "covered",
                    "merged_into": None, "queries": ["q"]}
    }, ensure_ascii=False), encoding="utf-8")
    (v / "retrieval_report.md").write_text("# retrieval_report\n\nACU-001 PASS。\n", encoding="utf-8")
    (v / "gate_3_decisions.md").write_text("# gate_3_decisions\n\n（本轮未触发）\n", encoding="utf-8")
    shutil.copy(FIX / "mini_kb.txt", v / "knowledge_base" / "obj1.txt")
    (v / "reproducibility_filter.md").write_text(
        "# 复现筛选（9.6）\n\n| 文献编号 | 来源 ACU | 可复现的关键步骤与参数 | 可直接整合至我方案的具体步骤 |\n"
        "| --- | --- | --- | --- |\n"
        "| XE001 [RE257] | ACU-001 | 每 1000 发测一次 C/ESR | 整合为路径 A 步骤 1 |\n",
        encoding="utf-8")
    (v / "reproducibility_index.json").write_text(json.dumps({
        "covered_acus": ["ACU-001"],
        "entries": [{"xe": "XE001", "re": "[RE257]", "eid": "2-s2.0-85000000001",
                     "doi": "10.1109/example.2024.0001",
                     "title": "Capacitance loss and ESR evolution of metallized film capacitors under repetitive pulses",
                     "source_acus": ["ACU-001"], "objects": ["obj1"]}]
    }, ensure_ascii=False), encoding="utf-8")
    (v / "obj1" / "mve_steps" / "steps_manifest.json").write_text(json.dumps({
        "object": "obj1", "scope": "A+B all steps",
        "steps": [{"path": "A", "step_no": 1, "file": "A_step_01.md",
                   "source_acus": ["ACU-001"], "skipped": False}]
    }, ensure_ascii=False), encoding="utf-8")
    (v / "obj1" / "mve_steps" / "A_step_01.md").write_text(
        "# A_step_01\n\n1. 步骤定位\n2. 优化目标\n3. 【主方案】MVE核心路径 用 [RE257] 与 XE001。\n"
        "4. 【备选战略】\n5. 战略选择建议\n6. 对资源清单的影响\n7. 验证与检查点 (Go/No-Go Criteria)：阈值为 3。\n",
        encoding="utf-8")
    (v / "obj1" / "mve_step_detail.md").write_text(
        "# mve_step_detail\n\n" + (v / "obj1" / "mve_steps" / "A_step_01.md").read_text(encoding="utf-8"),
        encoding="utf-8")
    return p, slug, v


def test_check_validation_pass(tmp_path):
    p, slug, v = write_mini_project(tmp_path)
    cv.issues.clear()
    rc = cv.main_argv(["--validation", str(v), "--project", str(p), "--slug", slug])
    assert rc == 0, "\n".join(cv.issues)


def test_check_validation_fails_on_missing_verdict(tmp_path):
    p, slug, v = write_mini_project(tmp_path)
    (v / "scopus_runs/ACU-001/round_01/verdict.md").unlink()
    cv.issues.clear()
    rc = cv.main_argv(["--validation", str(v), "--project", str(p), "--slug", slug])
    assert rc == 1
    assert any("verdict" in i for i in cv.issues)


def test_check_validation_fails_on_query_with_re(tmp_path):
    p, slug, v = write_mini_project(tmp_path)
    idx = json.loads((v / "acu_index.json").read_text(encoding="utf-8"))
    idx["ACU-001"]["query"] = 'TITLE-ABS-KEY("film capacitor" AND "esr") AND NOT TITLE(RE257)'
    (v / "acu_index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    cv.issues.clear()
    rc = cv.main_argv(["--validation", str(v), "--project", str(p), "--slug", slug])
    assert rc == 1
    assert any("RE" in i and "query" in i for i in cv.issues)
