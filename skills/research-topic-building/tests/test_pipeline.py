import argparse
import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import aggregate_analysis as agg  # noqa: E402
import check_topics as ct  # noqa: E402
import split_batches as sb  # noqa: E402

EVIDENCE_COLS = ["编号", "来源库", "标题", "作者（IEEE）", "来源名称", "文献类型", "是否综述",
                 "卷", "期", "页码", "出版年", "出版月", "DOI", "ISSN", "出版社", "会议名",
                 "摘要", "作者关键词", "被引次数", "EID", "原文链接", "子问题标签", "来源检索式"]
GLOBAL_COLS = ["编号", "来源库", "标题", "作者（IEEE）", "来源名称", "文献类型", "是否综述",
               "卷", "期", "页码", "出版年", "出版月", "DOI", "ISSN", "出版社", "会议名",
               "摘要", "作者关键词", "被引次数", "EID", "原文链接"]


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


def make_global_db(path):
    rows = [{"编号": f"[RE{i:03d}]", "标题": f"G{i}", "摘要": "g", "EID": f"ge-{i}"}
            for i in range(1, 6)]
    write_csv(path, GLOBAL_COLS, rows)
    return rows


def make_batch_md(path, batch_no, re_range):
    rows = "\n".join(f"| [RE{i:03d}] | 方法 {i} | 指标 {i} | 创新与局限 {i} | 启发 {i} |"
                     for i in re_range)
    content = f"""# 批次分析报告（batch_{batch_no:03d}）

## 进阶分析矩阵
| 论文编号 | 关键研究方法与材料 | 核心性能指标 (量化) | 创新性与局限性分析 | 对我课题的启发点 |
| --- | --- | --- | --- | --- |
{rows}

## 综合报告

### 研究趋势总结
趋势内容。

### 研究空白识别
空白内容。

### 课题提案
#### 提案 1：示例标题
- 立论依据：[RE{re_range[0]:03d}]
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def make_topic(path, name, re_ref):
    content = f"""# {name}

> 策略：meta ｜ 来源：reports/report_1_meta_analysis.md 第 1 个提案

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
- 来源报告：reports/report_1_meta_analysis.md（第 1 个提案）
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


@pytest.fixture()
def project(tmp_path):
    ev = tmp_path / "directions" / "slug" / "search" / "evidence.csv"
    analysis = tmp_path / "directions" / "slug" / "analysis"
    topics = tmp_path / "directions" / "slug" / "topics"
    db = tmp_path / "reports" / "literature_db.csv"
    make_evidence(ev)
    make_global_db(db)
    os.makedirs(analysis, exist_ok=True)
    os.makedirs(topics, exist_ok=True)
    return {"ev": str(ev), "analysis": str(analysis), "topics": str(topics), "db": str(db)}


# ── split_batches ──────────────────────────────────────────────

def test_split_120_into_3_batches(project):
    assert sb.cmd_split(argparse.Namespace(evidence=project["ev"], out=project["analysis"])) == 0
    files = sb.collect_batch_files(project["analysis"])
    assert files == ["batch_001.csv", "batch_002.csv", "batch_003.csv"]
    sizes = []
    for f in files:
        with open(os.path.join(project["analysis"], f), "r", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        sizes.append(len(rows))
    assert sizes == [50, 50, 20]


def test_split_batches_keep_three_columns(project):
    sb.cmd_split(argparse.Namespace(evidence=project["ev"], out=project["analysis"]))
    with open(os.path.join(project["analysis"], "batch_001.csv"), "r", encoding="utf-8-sig") as fh:
        fieldnames = csv.DictReader(fh).fieldnames
    assert fieldnames == sb.BATCH_COLUMNS


def test_split_self_check_pass(project):
    sb.cmd_split(argparse.Namespace(evidence=project["ev"], out=project["analysis"]))
    assert sb.cmd_self_check(argparse.Namespace(dir=project["analysis"],
                                                evidence=project["ev"])) == 0


def test_split_self_check_fails_on_gap(project):
    sb.cmd_split(argparse.Namespace(evidence=project["ev"], out=project["analysis"]))
    p = os.path.join(project["analysis"], "batch_002.csv")
    with open(p, "r", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    rows = rows[1:]  # 删一行 → 证据集缺 1 行
    write_csv(p, sb.BATCH_COLUMNS, rows)
    assert sb.cmd_self_check(argparse.Namespace(dir=project["analysis"],
                                                evidence=project["ev"])) == 1


# ── aggregate_analysis ─────────────────────────────────────────

def test_merge_creates_literature_analysis(project):
    sb.cmd_split(argparse.Namespace(evidence=project["ev"], out=project["analysis"]))
    make_batch_md(os.path.join(project["analysis"], "batch_001.md"), 1, range(740, 790))
    make_batch_md(os.path.join(project["analysis"], "batch_002.md"), 2, range(790, 840))
    make_batch_md(os.path.join(project["analysis"], "batch_003.md"), 3, range(840, 860))
    assert agg.cmd_merge(argparse.Namespace(dir=project["analysis"])) == 0
    with open(os.path.join(project["analysis"], "literature_analysis.md"), encoding="utf-8") as fh:
        la = fh.read()
    assert "（源 batch_001.md）" in la
    assert "（源 batch_002.md）" in la
    assert "（源 batch_003.md）" in la
    assert "综合报告" not in la.split("## batch_001")[1].split("## batch_002")[0]
    assert "[RE739]" not in la  # 矩阵只收本批编号


def test_aggregate_check_pass(project):
    sb.cmd_split(argparse.Namespace(evidence=project["ev"], out=project["analysis"]))
    make_batch_md(os.path.join(project["analysis"], "batch_001.md"), 1, range(740, 790))
    make_batch_md(os.path.join(project["analysis"], "batch_002.md"), 2, range(790, 840))
    make_batch_md(os.path.join(project["analysis"], "batch_003.md"), 3, range(840, 860))
    agg.cmd_merge(argparse.Namespace(dir=project["analysis"]))
    assert agg.cmd_check(argparse.Namespace(dir=project["analysis"])) == 0


def test_aggregate_check_fails_on_missing_matrix_row(project):
    sb.cmd_split(argparse.Namespace(evidence=project["ev"], out=project["analysis"]))
    make_batch_md(os.path.join(project["analysis"], "batch_001.md"), 1, range(740, 789))
    make_batch_md(os.path.join(project["analysis"], "batch_002.md"), 2, range(790, 840))
    make_batch_md(os.path.join(project["analysis"], "batch_003.md"), 3, range(840, 860))
    assert agg.cmd_check(argparse.Namespace(dir=project["analysis"])) == 1


# ── check_topics ───────────────────────────────────────────────

def test_topics_check_pass(project):
    for i in range(1, 7):
        make_topic(os.path.join(project["topics"], f"meta-0{i}-topic-alpha.md"), f"Meta Topic {i}", "RE740")
    with open(os.path.join(project["topics"], "_extraction_manifest.md"), "w", encoding="utf-8") as f:
        f.write("# 提取清单\n")
    assert ct.cmd_check(argparse.Namespace(dir=project["topics"], evidence=project["ev"],
                                           db=project["db"])) == 0


def test_topics_check_rejects_unknown_re(project):
    make_topic(os.path.join(project["topics"], "meta-01-topic-alpha.md"), "T1", "RE999")
    for i in range(2, 7):
        make_topic(os.path.join(project["topics"], f"meta-0{i}-topic-alpha.md"), f"T{i}", "RE740")
    with open(os.path.join(project["topics"], "_extraction_manifest.md"), "w", encoding="utf-8") as f:
        f.write("# 提取清单\n")
    assert ct.cmd_check(argparse.Namespace(dir=project["topics"], evidence=project["ev"],
                                           db=project["db"])) == 1


def test_topics_check_rejects_global_db_re_when_valid(project):
    # 全局库编号（RE001）也是合法引用（证据 CSV 行可复用全局 RE）
    make_topic(os.path.join(project["topics"], "meta-01-topic-alpha.md"), "T1", "RE001")
    for i in range(2, 7):
        make_topic(os.path.join(project["topics"], f"meta-0{i}-topic-alpha.md"), f"T{i}", "RE740")
    with open(os.path.join(project["topics"], "_extraction_manifest.md"), "w", encoding="utf-8") as f:
        f.write("# 提取清单\n")
    assert ct.cmd_check(argparse.Namespace(dir=project["topics"], evidence=project["ev"],
                                           db=project["db"])) == 0


def test_topics_check_rejects_noncontiguous_nn(project):
    for i in (1, 3, 4, 5, 6, 7):
        make_topic(os.path.join(project["topics"], f"meta-0{i}-topic-alpha.md"), f"T{i}", "RE740")
    with open(os.path.join(project["topics"], "_extraction_manifest.md"), "w", encoding="utf-8") as f:
        f.write("# 提取清单\n")
    assert ct.cmd_check(argparse.Namespace(dir=project["topics"], evidence=project["ev"],
                                           db=project["db"])) == 1


def test_topics_check_rejects_bad_filename(project):
    make_topic(os.path.join(project["topics"], "meta-01-topic-alpha.md"), "T1", "RE740")
    make_topic(os.path.join(project["topics"], "meta-02.md"), "T2", "RE740")  # 缺短标题
    for i in range(3, 7):
        make_topic(os.path.join(project["topics"], f"meta-0{i}-topic-alpha.md"), f"T{i}", "RE740")
    with open(os.path.join(project["topics"], "_extraction_manifest.md"), "w", encoding="utf-8") as f:
        f.write("# 提取清单\n")
    assert ct.cmd_check(argparse.Namespace(dir=project["topics"], evidence=project["ev"],
                                           db=project["db"])) == 1


def test_topics_check_accepts_single_strategy(project):
    make_topic(os.path.join(project["topics"], "single-01-paper-next.md"), "S1", "RE740")
    with open(os.path.join(project["topics"], "_extraction_manifest.md"), "w", encoding="utf-8") as f:
        f.write("# 提取清单\n")
    assert ct.cmd_check(argparse.Namespace(dir=project["topics"], evidence=project["ev"],
                                           db=project["db"])) == 0


# ── batch_analysis_runner 纯函数 ───────────────────────────────

def test_runner_build_prompt_fills_placeholders(tmp_path):
    import batch_analysis_runner as runner
    template = "焦点={DIRECTION_FOCUS} 批次={BATCH_NAME} 输入={BATCH_CSV_PATH} 输出={OUTPUT_MD_PATH}"
    rows = [{"编号": "[RE740]", "标题": "T1", "摘要": "A1"},
            {"编号": "[RE741]", "标题": "T2", "摘要": "A2"}]
    prompt = runner.build_prompt(template, rows, "A+B+C", "in.csv", "out.md", "batch_001")
    assert "焦点=A+B+C" in prompt
    assert "批次=batch_001" in prompt
    assert "输入=in.csv" in prompt
    assert "输出=out.md" in prompt
    assert "[RE740] | T1 | A1" in prompt
    assert "[RE741] | T2 | A2" in prompt


def test_runner_matrix_re_ids_accepts_both_formats():
    import batch_analysis_runner as runner
    text = "| [RE740] | x |\n| RE741 | y |\n正文 RE742 也计入"
    assert runner.matrix_re_ids(text) == {"740", "741", "742"}


def test_runner_insert_rows_before_section():
    import batch_analysis_runner as runner
    md = "## 进阶分析矩阵\n| [RE740] |\n\n## 综合报告\n正文"
    out = runner.insert_rows_before_section(md, "| [RE741] | 补行 |")
    assert out.index("补行") < out.index("## 综合报告")
    assert "## 进阶分析矩阵" in out


def test_runner_insert_rows_appends_when_no_section():
    import batch_analysis_runner as runner
    md = "## 进阶分析矩阵\n| [RE740] |\n\n（无综合报告段）"
    out = runner.insert_rows_before_section(md, "| [RE741] |")
    assert out.endswith("| [RE741] |")


# ── Skill 文件结构 ──────────────────────────────────────────────

def test_skill_structure():
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(skill_dir, "SKILL.md"), encoding="utf-8") as f:
        skill = f.read()
    assert skill.startswith("---")
    assert "name: research-topic-building" in skill
    assert "description:" in skill
    for step in ("Step 0", "Step 1", "Step 2", "Step 3", "Step 4", "Step 5", "Step 6", "Step 7"):
        assert step in skill
    for f in ("prompts/01-batch-analysis.md", "prompts/02-meta-analysis.md",
              "prompts/03-feasible-entry.md", "prompts/04-structured-innovation.md",
              "prompts/05-single-paper.md", "prompts/06-topic-extraction.md",
              "references/batch-analysis-contract.md", "references/report-contracts.md",
              "references/topic-md-contract.md",
              "scripts/split_batches.py", "scripts/aggregate_analysis.py",
              "scripts/check_topics.py", "scripts/batch_analysis_runner.py"):
        assert os.path.exists(os.path.join(skill_dir, f)), f
