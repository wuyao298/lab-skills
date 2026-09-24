import csv
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_knowledge_base as bkb

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def write_db(path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["编号", "标题", "DOI", "EID"])
        w.writeheader()
        w.writerow({
            "编号": "[RE257]",
            "标题": "Capacitance loss and ESR evolution of metallized film capacitors under repetitive pulses",
            "DOI": "10.1109/example.2024.0001",
            "EID": "2-s2.0-85000000001",
        })


def make_validation(tmp_path):
    v = tmp_path / "validation"
    for d in ["scopus_runs/ACU-001/round_01", "knowledge_base"]:
        (v / d).mkdir(parents=True)
    shutil.copy(os.path.join(FIX, "mini_scopus_raw.json"),
                v / "scopus_runs/ACU-001/round_01/results_raw.json")
    shutil.copy(os.path.join(FIX, "mini_verdict.md"),
                v / "scopus_runs/ACU-001/round_01/verdict.md")
    (v / "acu_index.json").write_text(json.dumps({
        "ACU-001": {"name": "停机测量", "stage": "阶段1",
                    "source_objects": ["obj1"],
                    "query": "TITLE-ABS-KEY(film capacitor AND esr)",
                    "default_strategy": "②实现优先"}
    }, ensure_ascii=False), encoding="utf-8")
    (v / "loop_state.json").write_text(json.dumps({
        "round": 1, "max_rounds": 10,
        "acus": {"ACU-001": {"status": "covered", "pass_round": 1}},
        "skipped_acus": [], "gate_history": []}, ensure_ascii=False), encoding="utf-8")
    (v / "per_ACU_summary.json").write_text(json.dumps({
        "ACU-001": {"rounds_run": [1], "status": "covered", "pass_round": 1}
    }, ensure_ascii=False), encoding="utf-8")
    return v


def test_build_knowledge_base(tmp_path):
    v = make_validation(tmp_path)
    db = tmp_path / "literature_db.csv"
    write_db(db)
    rc = bkb.main_argv(["--validation", str(v), "--db", str(db)])
    assert rc == 0

    filt = (v / "reproducibility_filter.md").read_text(encoding="utf-8")
    assert "XE001" in filt and "[RE257]" in filt and "ACU-001" in filt
    assert "85000000002" not in filt

    kb = (v / "knowledge_base/obj1.txt").read_text(encoding="utf-8")
    assert "=== XE001 [RE257] ===" in kb
    assert "Capacitance loss" in kb

    idx = json.loads((v / "reproducibility_index.json").read_text(encoding="utf-8"))
    assert idx["entries"][0]["xe"] == "XE001"
    assert idx["entries"][0]["source_acus"] == ["ACU-001"]
    assert idx["entries"][0]["objects"] == ["obj1"]


def test_parse_verdict_only_high():
    rows = bkb.parse_verdict(open(os.path.join(FIX, "mini_verdict.md"), encoding="utf-8").read())
    assert len(rows) == 1
    assert rows[0][0] == "EID:2-s2.0-85000000001"
    assert rows[0][1] == "高"
