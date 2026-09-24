import argparse
import csv
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_evidence_db as bed  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
GLOBAL_DB = os.path.join(FIXTURES, "mini_literature_db.csv")
FINAL_1 = os.path.join(FIXTURES, "final_raw.json")
FINAL_2 = os.path.join(FIXTURES, "final_raw_second.json")


@pytest.fixture()
def workdir(tmp_path):
    out = tmp_path / "directions" / "test-slug" / "search"
    ctx = tmp_path / "project_context.json"
    db = tmp_path / "literature_db.csv"
    shutil.copyfile(GLOBAL_DB, db)
    return {"out": str(out), "ctx": str(ctx), "db": str(db), "root": str(tmp_path)}


def read_rows(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def run_append(workdir, final, label, query, weak=False):
    args = argparse.Namespace(final=final, label=label, query=query,
                              db=workdir["db"], out=workdir["out"],
                              context=workdir["ctx"], weak=weak)
    return bed.cmd_append(args)


def run_self_check(workdir):
    args = argparse.Namespace(dir=workdir["out"], db=workdir["db"], context=workdir["ctx"])
    return bed.cmd_self_check(args)


def test_append_builds_23_column_evidence_csv(workdir):
    run_append(workdir, FINAL_1, "失效演化-重频脉冲", "TITLE-ABS-KEY(test)")
    rows = read_rows(os.path.join(workdir["out"], "evidence.csv"))
    with open(os.path.join(workdir["out"], "evidence.csv"), "r", encoding="utf-8-sig") as f:
        fieldnames = csv.DictReader(f).fieldnames
    assert fieldnames == bed.COLUMNS
    assert len(fieldnames) == 23
    assert len(rows) == 4


def test_append_reuses_global_re_and_continues_sequence(workdir):
    run_append(workdir, FINAL_1, "失效演化-重频脉冲", "Q1")
    rows = read_rows(os.path.join(workdir["out"], "evidence.csv"))
    by_eid = {r["EID"]: r for r in rows}
    assert by_eid["eid-global-2"]["编号"] == "[RE002]"
    assert by_eid["eid-global-4"]["编号"] == "[RE004]"
    assert by_eid["eid-new-1"]["编号"] == "[RE006]"
    assert by_eid["eid-new-2"]["编号"] == "[RE007]"


def test_append_fills_label_and_query_columns(workdir):
    run_append(workdir, FINAL_1, "失效演化-重频脉冲", "TITLE-ABS-KEY(rep-rate)")
    rows = read_rows(os.path.join(workdir["out"], "evidence.csv"))
    assert all(r["子问题标签"] == "失效演化-重频脉冲" for r in rows)
    assert all(r["来源检索式"] == "TITLE-ABS-KEY(rep-rate)" for r in rows)


def test_append_writes_meta_json(workdir):
    run_append(workdir, FINAL_1, "失效演化-重频脉冲", "Q1", weak=True)
    meta = json.load(open(os.path.join(workdir["out"], "meta.json"), "r", encoding="utf-8"))
    assert meta["evidence_rows"] == 4
    s = meta["searches"][0]
    assert s["label"] == "失效演化-重频脉冲"
    assert s["found"] == 5
    assert s["reused"] == 2
    assert s["added"] == 2
    assert s["skipped_dup"] == 1
    assert s["weak_evidence"] is True


def test_second_append_dedups_and_continues_re(workdir):
    run_append(workdir, FINAL_1, "标签A", "Q1")
    run_append(workdir, FINAL_2, "标签B", "Q2")
    rows = read_rows(os.path.join(workdir["out"], "evidence.csv"))
    assert len(rows) == 6
    by_eid = {r["EID"]: r for r in rows}
    assert by_eid["eid-new-3"]["编号"] == "[RE008]"
    assert by_eid["eid-new-4"]["编号"] == "[RE009]"
    assert by_eid["eid-new-1"]["子问题标签"] == "标签A"
    meta = json.load(open(os.path.join(workdir["out"], "meta.json"), "r", encoding="utf-8"))
    assert meta["evidence_rows"] == 6
    assert len(meta["searches"]) == 2


def test_append_updates_project_context(workdir):
    run_append(workdir, FINAL_1, "标签A", "Q1")
    ctx = json.load(open(workdir["ctx"], "r", encoding="utf-8"))
    assert ctx["last_issued_re"] == 7
    assert ctx["segment"] == 5
    assert ctx["re_index"]["[RE006]"].endswith("evidence.csv")
    assert ctx["re_index"]["[RE007]"].endswith("evidence.csv")
    assert ctx["re_index"]["[RE002]"].endswith("literature_db.csv")
    slug_cfg = ctx["directions"]["test-slug"]
    assert slug_cfg["evidence_csv"].endswith("evidence.csv")


def test_self_check_pass(workdir):
    run_append(workdir, FINAL_1, "标签A", "Q1")
    assert run_self_check(workdir) == 0


def test_self_check_fails_on_duplicate_re(workdir):
    run_append(workdir, FINAL_1, "标签A", "Q1")
    ev = os.path.join(workdir["out"], "evidence.csv")
    rows = read_rows(ev)
    rows[1]["编号"] = rows[0]["编号"]
    with open(ev, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=bed.COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    assert run_self_check(workdir) == 1


def test_self_check_fails_on_new_re_below_global_max(workdir):
    run_append(workdir, FINAL_1, "标签A", "Q1")
    ev = os.path.join(workdir["out"], "evidence.csv")
    rows = read_rows(ev)
    for r in rows:
        if r["编号"] == "[RE006]":
            r["编号"] = "[RE003]"
    with open(ev, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=bed.COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    assert run_self_check(workdir) == 1


def test_entries_without_eid_skipped(workdir):
    run_append(workdir, FINAL_1, "标签A", "Q1")
    rows = read_rows(os.path.join(workdir["out"], "evidence.csv"))
    assert all(r["EID"] for r in rows)


def test_skill_structure():
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(skill_dir, "SKILL.md"), encoding="utf-8") as f:
        skill = f.read()
    assert skill.startswith("---")
    assert "name: research-subtopic-retrieval" in skill
    assert "description:" in skill
    for step in ("Step 0", "Step 1", "Step 2", "Step 3", "Step 4"):
        assert step in skill
    assert "prompts/01-entity-decomposition.md" in skill
    assert "prompts/02-search-iteration.md" in skill
    assert "references/iteration-protocol.md" in skill
    assert "references/evidence-csv-contract.md" in skill
    for f in ("prompts/01-entity-decomposition.md", "prompts/02-search-iteration.md",
              "references/iteration-protocol.md", "references/evidence-csv-contract.md",
              "scripts/build_evidence_db.py", "scripts/fetch_scopus.py",
              "scripts/scopus_search.py"):
        assert os.path.exists(os.path.join(skill_dir, f)), f
