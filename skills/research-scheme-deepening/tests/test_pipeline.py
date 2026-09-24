import argparse
import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import deepening_runner as dr  # noqa: E402

EVIDENCE_COLS = ["编号", "来源库", "标题", "作者（IEEE）", "来源名称", "文献类型", "是否综述",
                 "卷", "期", "页码", "出版年", "出版月", "DOI", "ISSN", "出版社", "会议名",
                 "摘要", "作者关键词", "被引次数", "EID", "原文链接", "子问题标签", "来源检索式"]


def write_csv(path, cols, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})


def make_evidence(path, n=120, start_re=740):
    rows = []
    for i in range(n):
        rows.append({"编号": f"[RE{start_re + i:03d}]", "标题": f"Paper {i + 1}",
                     "摘要": f"Abstract {i + 1}", "EID": f"eid-{i + 1}",
                     "子问题标签": "test", "来源检索式": "Q"})
    write_csv(path, EVIDENCE_COLS, rows)
    return rows


def make_topic(path, name, re_ref):
    content = f"""# {name}

> 策略：entry ｜ 来源：reports/report_2_feasible_entry.md 第 1 个提案

## 论文标题
{name}

## 核心科学问题
一句话。

## 研究设计与技术路线
1. 步骤一

## 预期创新性与价值
新颖之处。

## 立论依据（[{re_ref}]）
基于共识交叉点，依据 [{re_ref}]。

## 来源标注
- 来源报告：reports/report_2_feasible_entry.md（第 1 个提案）
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def make_screening_batch(path, batch_no, re_range, illegal=None):
    rows = "\n".join(
        f"| [RE{i:03d}] | A | 方法 {i} | 指标 {i} | 创新与局限 {i} | 启发 {i} |"
        for i in re_range)
    if illegal:
        rows += "\n" + "\n".join(
            f"| [RE{i}] | B | 方法 | 指标 | 局限 | 启发 |" for i in illegal)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = f"""# 筛选报告（batch_{batch_no:03d}）

## 筛选表
| 论文编号 | 相关性类别 | 关键研究方法与材料 | 核心性能指标 (量化) | 创新性与局限性分析 | 对我课题的启发点 |
| --- | --- | --- | --- | --- | --- |
{rows}

## 其他说明
无关内容，合并时应被丢弃。
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


@pytest.fixture()
def project(tmp_path):
    root = tmp_path
    ev = root / "directions" / "slug" / "search" / "evidence.csv"
    analysis = root / "directions" / "slug" / "analysis"
    topics = root / "directions" / "slug" / "topics"
    make_evidence(ev)
    os.makedirs(analysis, exist_ok=True)
    os.makedirs(topics, exist_ok=True)
    dr.cmd_split(str(ev), str(analysis))
    return {"root": str(root), "ev": str(ev), "analysis": str(analysis),
            "topics": str(topics)}


# ── split（内嵌，段5.3 先例） ───────────────────────────────────

def test_split_120_into_3_batches(project):
    files = dr.collect_batch_files(project["analysis"])
    assert files == ["batch_001.csv", "batch_002.csv", "batch_003.csv"]
    sizes = []
    for f in files:
        with open(os.path.join(project["analysis"], f), "r", encoding="utf-8-sig") as fh:
            sizes.append(len(list(csv.DictReader(fh))))
    assert sizes == [50, 50, 20]


# ── screen 提示词构建 ───────────────────────────────────────────

def test_build_screen_prompt_fills_placeholders(project):
    template = ("课题={TOPIC_TEXT} 批次={BATCH_NAME} 输入={BATCH_CSV_PATH} 输出={OUTPUT_MD_PATH}")
    rows = [{"编号": "[RE740]", "标题": "T1", "摘要": "A1"},
            {"编号": "[RE741]", "标题": "T2", "摘要": "A2"}]
    prompt = dr.build_screen_prompt(template, "课题全文", rows, "in.csv", "out.md", "batch_001")
    assert "课题=课题全文" in prompt
    assert "批次=batch_001" in prompt
    assert "输入=in.csv" in prompt
    assert "输出=out.md" in prompt
    assert "[RE740] | T1 | A1" in prompt
    assert "[RE741] | T2 | A2" in prompt


# ── 筛选表解析 ──────────────────────────────────────────────────

def test_extract_table_rows_only_section():
    md = """## 筛选表
| 论文编号 | 相关性类别 | 关键研究方法与材料 | 核心性能指标 (量化) | 创新性与局限性分析 | 对我课题的启发点 |
| --- | --- | --- | --- | --- | --- |
| [RE740] | A | 方法 | 指标 | 局限 | 启发 |
| [RE741] | AB | 方法 | 指标 | 局限 | 启发 |

## 其他说明
| [RE999] | 不应被收进 |
"""
    rows = dr.extract_table_rows(md)
    assert rows == [("740", "| [RE740] | A | 方法 | 指标 | 局限 | 启发 |"),
                    ("741", "| [RE741] | AB | 方法 | 指标 | 局限 | 启发 |")]


def test_extract_table_rows_no_section_falls_back_to_all():
    md = "| [RE740] | A | x |\n| [RE741] | B | y |"
    assert [rid for rid, _ in dr.extract_table_rows(md)] == ["740", "741"]


# ── merge / check ───────────────────────────────────────────────

def make_full_pipeline(project):
    make_topic(os.path.join(project["topics"], "entry-01-topic-alpha.md"),
               "Entry Topic 1", "RE740")
    for i, rng in enumerate([range(740, 790), range(790, 840), range(840, 860)], start=1):
        make_screening_batch(os.path.join(project["topics"], "entry-01-topic-alpha",
                                          "screening_batches", f"batch_{i:03d}.md"), i, rng)
    assert dr.cmd_merge(argparse.Namespace(project=project["root"], slug="slug",
                                           topics="entry-01-topic-alpha")) == 0
    return "entry-01-topic-alpha"


def test_merge_creates_screening(project):
    slug = make_full_pipeline(project)
    with open(os.path.join(project["topics"], slug, "screening.md"), encoding="utf-8") as fh:
        s = fh.read()
    assert s.startswith("# 强相关文献筛选表（Entry Topic 1）")
    assert "（120 篇，3 批）" in s
    assert "## batch_001（源 screening_batches/batch_001.md）" in s
    assert "| [RE740] | A |" in s
    assert "其他说明" not in s
    assert "[RE999]" not in s


def test_check_pass(project):
    slug = make_full_pipeline(project)
    assert dr.cmd_check(argparse.Namespace(project=project["root"], slug="slug",
                                           topics=slug)) == 0


def test_check_fails_on_out_of_batch_re(project):
    slug = make_full_pipeline(project)
    p = os.path.join(project["topics"], slug, "screening_batches", "batch_001.md")
    with open(p, "r", encoding="utf-8") as fh:
        content = fh.read()
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(content.replace("| [RE741]", "| [RE999]"))
    assert dr.cmd_check(argparse.Namespace(project=project["root"], slug="slug",
                                           topics=slug)) == 1


def test_check_fails_on_duplicate_row(project):
    slug = make_full_pipeline(project)
    p = os.path.join(project["topics"], slug, "screening_batches", "batch_001.md")
    with open(p, "r", encoding="utf-8") as fh:
        content = fh.read()
    dup = "| [RE740] | A | 方法 740 | 指标 740 | 创新与局限 740 | 启发 740 |"
    content = content.replace("| [RE740] | A | 方法 740 | 指标 740 | 创新与局限 740 | 启发 740 |",
                              dup + "\n" + dup, 1)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(content)
    assert dr.cmd_check(argparse.Namespace(project=project["root"], slug="slug",
                                           topics=slug)) == 1


def test_check_fails_on_missing_batch_md(project):
    make_topic(os.path.join(project["topics"], "entry-01-topic-alpha.md"),
               "Entry Topic 1", "RE740")
    # 不生成任何 screening_batches → 缺 3 个批次文件
    assert dr.cmd_check(argparse.Namespace(project=project["root"], slug="slug",
                                           topics="entry-01-topic-alpha")) == 1


def test_check_fails_on_deepened_re_outside_evidence(project):
    slug = make_full_pipeline(project)
    p = os.path.join(project["topics"], slug, "deepened.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("## 相对课题 MD 的修改摘要\n依据 [RE999]（捏造编号）与 [RE740]。\n**加粗**")
    assert dr.cmd_check(argparse.Namespace(project=project["root"], slug="slug",
                                           topics=slug)) == 1


def test_check_deepened_pass(project):
    slug = make_full_pipeline(project)
    p = os.path.join(project["topics"], slug, "deepened.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("## 相对课题 MD 的修改摘要\n依据 [RE740] 与 [RE841]。\n**加粗修改**")
    assert dr.cmd_check(argparse.Namespace(project=project["root"], slug="slug",
                                           topics=slug)) == 0


# ── deepen 提示词构建 ───────────────────────────────────────────

def test_build_deepen_prompt_fills_placeholders():
    template = ("课题={TOPIC_TEXT} 论文集={SCREENING_SUMMARY} 路径={SCREENING_PATH} "
                "输出={OUTPUT_MD_PATH}")
    prompt = dr.build_deepen_prompt(template, "课题全文", "筛选表全文", "screening.md", "deep.md")
    assert "课题=课题全文" in prompt
    assert "论文集=筛选表全文" in prompt
    assert "路径=screening.md" in prompt
    assert "输出=deep.md" in prompt


# ── 课题 slug 收集 ──────────────────────────────────────────────

def test_topic_slugs_skips_subdirs_and_manifest(project):
    make_topic(os.path.join(project["topics"], "entry-01-topic-alpha.md"), "T1", "RE740")
    make_topic(os.path.join(project["topics"], "meta-02-topic-beta.md"), "T2", "RE740")
    os.makedirs(os.path.join(project["topics"], "entry-01-topic-alpha"), exist_ok=True)
    with open(os.path.join(project["topics"], "_extraction_manifest.md"), "w",
              encoding="utf-8") as f:
        f.write("# 清单\n")
    assert dr.topic_slugs(project["topics"]) == ["entry-01-topic-alpha", "meta-02-topic-beta"]


# ── Skill 文件结构 ─────────────────────────────────────────────

def test_skill_structure():
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(skill_dir, "SKILL.md"), encoding="utf-8") as f:
        skill = f.read()
    assert skill.startswith("---")
    assert "name: research-scheme-deepening" in skill
    assert "description:" in skill
    for step in ("Step 0", "Step 1", "Step 2", "Step 3", "Step 4", "Step 5"):
        assert step in skill
    for f in ("prompts/01-screening.md", "prompts/02-deepening.md",
              "references/screening-contract.md", "references/deepened-contract.md",
              "scripts/deepening_runner.py"):
        assert os.path.exists(os.path.join(skill_dir, f)), f
