import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import evidence  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "mini_literature_db.csv")


def test_load_assigns_columns():
    df = evidence.load(FIXTURE)
    assert list(df.columns) == evidence.COLUMNS
    assert len(df) == 3


def test_search_keyword_hits():
    df = evidence.load(FIXTURE)
    buf = io.StringIO()
    sys.stdout = buf
    evidence.search(df, ["self-healing"], limit=12)
    sys.stdout = sys.__stdout__
    out = buf.getvalue()
    assert "self-healing : 2 hits" in out
    assert "[RE001]" in out
    assert "[RE003]" in out
    assert "[RE002]" not in out


def test_search_case_insensitive():
    df = evidence.load(FIXTURE)
    buf = io.StringIO()
    sys.stdout = buf
    evidence.search(df, ["SELF-HEALING"], limit=12)
    sys.stdout = sys.__stdout__
    assert "SELF-HEALING : 2 hits" in buf.getvalue()


def test_search_no_match():
    df = evidence.load(FIXTURE)
    buf = io.StringIO()
    sys.stdout = buf
    evidence.search(df, ["radiation"], limit=12)
    sys.stdout = sys.__stdout__
    assert "radiation : 0 hits" in buf.getvalue()


def test_search_limit():
    df = evidence.load(FIXTURE)
    buf = io.StringIO()
    sys.stdout = buf
    evidence.search(df, ["capacitor"], limit=1)
    sys.stdout = sys.__stdout__
    lines = [l for l in buf.getvalue().splitlines() if l.startswith("[RE")]
    assert len(lines) == 1
