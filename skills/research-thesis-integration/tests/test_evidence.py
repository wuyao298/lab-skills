import csv
import io
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import evidence  # noqa: E402

EVIDENCE_COLS = ["编号", "来源库", "标题", "作者（IEEE）", "来源名称", "文献类型", "是否综述",
                 "卷", "期", "页码", "出版年", "出版月", "DOI", "ISSN", "出版社", "会议名",
                 "摘要", "作者关键词", "被引次数", "EID", "原文链接", "子问题标签", "来源检索式"]

# 沙箱下 tmp_path / mkdtemp（mode 0o700）建出的目录会被施加限制性 ACL，改用普通 os.makedirs。
SCRATCH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "..", "..", "..", ".scratch")


@pytest.fixture()
def db():
    path = os.path.join(SCRATCH, "evidence-test-" + uuid.uuid4().hex)
    os.makedirs(path, exist_ok=True)
    db_path = os.path.join(path, "evidence.csv")
    rows = [
        {"编号": "[RE001]", "标题": "Self-healing metallized film capacitor",
         "摘要": "Pulse aging of metallized polypropylene capacitors.",
         "作者关键词": "self-healing | pulse", "来源名称": "JPhysD", "出版年": "2026",
         "是否综述": "否"},
        {"编号": "[RE002]", "标题": "Lifetime model of power capacitors",
         "摘要": "Accelerated lifetime testing under repetitive pulses.",
         "作者关键词": "lifetime | aging | self-healing events", "来源名称": "IEEE TPS",
         "出版年": "2025", "是否综述": "是"},
        {"编号": "[RE003]", "标题": "Termination failure analysis",
         "摘要": "Sprayed end contact degradation.",
         "作者关键词": "termination | failure", "来源名称": "IEEE TDEI", "出版年": "2024",
         "是否综述": "否"},
    ]
    with open(db_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EVIDENCE_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in EVIDENCE_COLS})
    return db_path


def run_main(argv):
    buf = io.StringIO()
    sys.stdout = buf
    sys.argv = ["evidence.py"] + argv
    evidence.main()
    sys.stdout = sys.__stdout__
    return buf.getvalue()


def test_search_keyword_hits(db):
    out = run_main(["self-healing", "--db", db])
    assert "self-healing : 2 hits" in out
    assert "[RE001]" in out
    assert "[RE002]" in out
    assert "[RE003]" not in out


def test_search_case_insensitive(db):
    out = run_main(["SELF-HEALING", "--db", db])
    assert "SELF-HEALING : 2 hits" in out


def test_search_no_match(db):
    out = run_main(["radiation", "--db", db])
    assert "radiation : 0 hits" in out


def test_lookup_hit(db):
    out = run_main(["--re", "RE002", "--db", db])
    assert "=== [RE002] : 1 hits ===" in out
    assert "IEEE TPS" in out


def test_lookup_miss(db):
    out = run_main(["--re", "RE999", "--db", db])
    assert "=== [RE999] : 0 hits ===" in out
    assert "未命中" in out


def test_lookup_multiple(db):
    out = run_main(["--re", "RE001", "RE003", "--db", db])
    assert "[RE001] | 2026" in out
    assert "[RE003] | 2024" in out
