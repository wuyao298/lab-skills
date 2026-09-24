import argparse
import csv
import os
import shutil
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import thesis_runner as tr  # noqa: E402

EVIDENCE_COLS = ["编号", "来源库", "标题", "作者（IEEE）", "来源名称", "文献类型", "是否综述",
                 "卷", "期", "页码", "出版年", "出版月", "DOI", "ISSN", "出版社", "会议名",
                 "摘要", "作者关键词", "被引次数", "EID", "原文链接", "子问题标签", "来源检索式"]

# 沙箱下 pytest 的 tmp_path 与 tempfile.mkdtemp（mode 0o700）建出的目录会被
# 施加限制性 ACL 导致后续不可写，改用普通 os.makedirs（.scratch 内、uuid 命名）。
SCRATCH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "..", "..", "..", ".scratch")


def tmp_dir(prefix):
    d = os.path.join(SCRATCH, prefix + "-" + uuid.uuid4().hex)
    os.makedirs(d, exist_ok=True)
    return d


def write_csv(path, cols, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})


def make_evidence(path, n=10):
    rows = []
    for i in range(1, n + 1):
        rows.append({"编号": f"[RE{i:03d}]", "标题": f"Paper {i}",
                     "摘要": f"Abstract {i}", "出版年": str(2020 + i % 6),
                     "是否综述": "否", "来源名称": "JTest"})
    write_csv(path, EVIDENCE_COLS, rows)


def make_topic_md(path, name, re_ref):
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
依据 [{re_ref}]。
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def make_deepened(path, name, re_ids):
    refs = "、".join(f"[{r}]" for r in re_ids)
    content = f"""# {name}

## 相对课题 MD 的修改摘要
依据 {refs} 做了**重大修改**。

## 论文标题
{name}

## 核心科学问题
精炼后的问题。

## 研究设计与技术路线
1. 优化步骤（依据 {refs}）

## 预期创新性与价值
升级表述。

## 立论依据（[REXXX]）
{refs}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def make_screening(path, name, re_ids):
    rows = "\n".join(
        f"| [{r}] | A | 方法 | 指标 | 创新与局限 | 启发 |" for r in re_ids)
    content = f"""# 强相关文献筛选表（{name}）

> 课题：topics/x.md ｜ 论文池：evidence.csv

## batch_001（源 screening_batches/batch_001.md）
| 论文编号 | 相关性类别 | 关键研究方法与材料 | 核心性能指标 (量化) | 创新性与局限性分析 | 对我课题的启发点 |
| --- | --- | --- | --- | --- | --- |
{rows}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def make_card(path, name, re_ids, sections=None):
    sections = sections or ["## 核心元素", "## 方案要点", "## 参考文献设计", "## 可合并点"]
    refs = "、".join(f"[{r}]" for r in re_ids)
    content = f"# 元素卡片：{name}\n\n"
    for sec in sections:
        content += f"{sec}\n内容（{refs}）。\n\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def make_round(path, n, fog_items):
    fog_lines = "\n".join(f"- {fg}" for fg in fog_items)
    content = f"""# Round {n}（2026-08-14）

## 用户原话
- R{n}Q1（…）：用户裁决。

## 判读
- (a) 确认合并。

## 动作
1. 落盘合并裁决。

## 雾区清单（本轮末，{len(fog_items)} 项）
{fog_lines}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


@pytest.fixture()
def project():
    root = tmp_dir("thesis-test")
    slug_dir = os.path.join(root, "directions", "slug")
    ev = os.path.join(slug_dir, "search", "evidence.csv")
    topics = os.path.join(slug_dir, "topics")
    make_evidence(ev)
    for slug, re_ids in (("entry-01-alpha", ["RE001", "RE002"]),
                         ("meta-01-beta", ["RE003", "RE004"])):
        os.makedirs(os.path.join(topics, slug), exist_ok=True)
        make_topic_md(os.path.join(topics, f"{slug}.md"), f"Topic {slug}", re_ids[0])
        make_deepened(os.path.join(topics, slug, "deepened.md"), f"Topic {slug}", re_ids)
        make_screening(os.path.join(topics, slug, "screening.md"), f"Topic {slug}", re_ids)
    yield {"root": root, "slug_dir": slug_dir, "topics": topics, "ev": ev}
    shutil.rmtree(root, ignore_errors=True)


def ns(root, slug, **kw):
    d = {"project": root, "slug": slug}
    d.update(kw)
    return argparse.Namespace(**d)


def make_full_thesis(project):
    slug_dir = project["slug_dir"]
    cards = os.path.join(slug_dir, "thesis", "cards")
    rounds = os.path.join(slug_dir, "thesis", "rounds")
    thesis = os.path.join(slug_dir, "thesis")
    os.makedirs(cards, exist_ok=True)
    os.makedirs(rounds, exist_ok=True)
    make_card(os.path.join(cards, "entry-01-alpha.md"), "Topic entry-01-alpha",
              ["RE001", "RE002"])
    make_card(os.path.join(cards, "meta-01-beta.md"), "Topic meta-01-beta",
              ["RE003", "RE004"])
    with open(os.path.join(thesis, "thesis_argument.md"), "w", encoding="utf-8") as f:
        f.write("""# 论文总标题与核心论点（候选）

## 候选总标题
1. 候选标题一 — 定位

## 核心论点/研究主线
一段统领性陈述（依据 [RE001]、[RE003]）。

## 用户选定
选定总标题与主线。
""")
    with open(os.path.join(thesis, "thesis_story.md"), "w", encoding="utf-8") as f:
        f.write("""# 论文级整合方案

## 选定主线
选定主线。

## 论文故事
段落叙事（课题：entry-01-alpha）依据 [RE001]；（课题：meta-01-beta）依据 [RE003]。

## 支撑层
支撑声明。
""")
    with open(os.path.join(thesis, "thesis_structure.md"), "w", encoding="utf-8") as f:
        f.write("""# 章级结构

## 章级结构
| 章 | 名称 | 内容范围 | 对应课题/实验（课题 slug ↔ 实验单元） | 证据群 [REXXX] |
| --- | --- | --- | --- | --- |
| 第1章 | 绪论 | 背景 | entry-01-alpha ↔ 实验A | [RE001] |

## 章间逻辑
第1章 → 第2章 递进。
""")
    make_round(os.path.join(rounds, "round_1.md"), 1, ["FG-01：问题A — 影响 — 待决",
                                                       "FG-02：问题B — 影响 — 待决"])
    make_round(os.path.join(rounds, "round_2.md"), 2, ["FG-02：问题B — 影响 — 已收窄"])
    make_round(os.path.join(rounds, "round_3.md"), 3, [])


# ── validate ─────────────────────────────────────────────────────

def test_validate_ok(project):
    assert tr.cmd_validate(ns(project["root"], "slug")) == 0


def test_validate_missing_deepened(project):
    os.remove(os.path.join(project["topics"], "entry-01-alpha", "deepened.md"))
    assert tr.cmd_validate(ns(project["root"], "slug")) == 1


def test_validate_missing_evidence(project):
    os.remove(project["ev"])
    assert tr.cmd_validate(ns(project["root"], "slug")) == 1


# ── cards 提示词构建 ──────────────────────────────────────────────

def test_build_cards_prompt_fills_placeholders():
    template = ("标题={TOPIC_TITLE} slug={TOPIC_SLUG} 深={DEEPENED_TEXT} "
                "筛={SCREENING_TEXT} 输出={OUTPUT_MD_PATH}")
    prompt = tr.build_cards_prompt(template, "T", "entry-01-alpha", "D", "S", "out.md")
    assert "标题=T" in prompt
    assert "slug=entry-01-alpha" in prompt
    assert "深=D" in prompt
    assert "筛=S" in prompt
    assert "输出=out.md" in prompt


# ── RE 提取 / 雾区解析 ───────────────────────────────────────────

def test_read_re_ids():
    assert tr.read_re_ids("依据 [RE001] 与 RE002。") == {"001", "002"}


def test_fog_snapshot_parses():
    md = "## 雾区清单（本轮末，2 项）\n- FG-01：A — B — C\n- FG-02：D — E — F\n"
    assert tr.fog_snapshot(md) == (2, 2)


def test_fog_snapshot_header_mismatch():
    md = "## 雾区清单（本轮末，3 项）\n- FG-01：A — B — C\n"
    assert tr.fog_snapshot(md) == (3, 1)


def test_fog_snapshot_missing():
    assert tr.fog_snapshot("## 用户原话\n无雾区") is None


# ── check 全链路 ─────────────────────────────────────────────────

def test_check_pass_full(project):
    make_full_thesis(project)
    assert tr.cmd_check(ns(project["root"], "slug")) == 0


def test_check_fail_card_re_outside_screening(project):
    make_full_thesis(project)
    card = os.path.join(project["slug_dir"], "thesis", "cards", "entry-01-alpha.md")
    with open(card, "r", encoding="utf-8") as f:
        content = f.read()
    with open(card, "w", encoding="utf-8") as f:
        f.write(content.replace("[RE001]", "[RE999]"))
    assert tr.cmd_check(ns(project["root"], "slug")) == 1


def test_check_fail_card_missing_section(project):
    make_full_thesis(project)
    card = os.path.join(project["slug_dir"], "thesis", "cards", "meta-01-beta.md")
    with open(card, "r", encoding="utf-8") as f:
        content = f.read()
    with open(card, "w", encoding="utf-8") as f:
        f.write(content.replace("## 可合并点", ""))
    assert tr.cmd_check(ns(project["root"], "slug")) == 1


def test_check_fail_card_stray_file(project):
    make_full_thesis(project)
    stray = os.path.join(project["slug_dir"], "thesis", "cards", "extra-99-x.md")
    make_card(stray, "Extra", ["RE001"])
    assert tr.cmd_check(ns(project["root"], "slug")) == 1


def test_check_fail_thesis_re_outside_evidence(project):
    make_full_thesis(project)
    arg = os.path.join(project["slug_dir"], "thesis", "thesis_argument.md")
    with open(arg, "r", encoding="utf-8") as f:
        content = f.read()
    with open(arg, "w", encoding="utf-8") as f:
        f.write(content.replace("[RE001]", "[RE999]"))
    assert tr.cmd_check(ns(project["root"], "slug")) == 1


def test_check_fail_story_missing_source_annotation(project):
    make_full_thesis(project)
    story = os.path.join(project["slug_dir"], "thesis", "thesis_story.md")
    with open(story, "r", encoding="utf-8") as f:
        content = f.read()
    with open(story, "w", encoding="utf-8") as f:
        f.write(content.replace("（课题：entry-01-alpha）", "").replace("（课题：meta-01-beta）", ""))
    assert tr.cmd_check(ns(project["root"], "slug")) == 1


def test_check_fail_structure_missing_mapping(project):
    make_full_thesis(project)
    struct = os.path.join(project["slug_dir"], "thesis", "thesis_structure.md")
    with open(struct, "r", encoding="utf-8") as f:
        content = f.read()
    with open(struct, "w", encoding="utf-8") as f:
        f.write(content.replace("↔", "-"))
    assert tr.cmd_check(ns(project["root"], "slug")) == 1


def test_check_fail_rounds_gap(project):
    make_full_thesis(project)
    rounds = os.path.join(project["slug_dir"], "thesis", "rounds")
    os.remove(os.path.join(rounds, "round_2.md"))
    assert tr.cmd_check(ns(project["root"], "slug")) == 1


def test_check_fail_fog_increasing(project):
    make_full_thesis(project)
    rounds = os.path.join(project["slug_dir"], "thesis", "rounds")
    make_round(os.path.join(rounds, "round_2.md"), 2, ["FG-01：A — B — 待决",
                                                        "FG-02：B — B — 待决",
                                                        "FG-03：C — B — 待决"])
    assert tr.cmd_check(ns(project["root"], "slug")) == 1


def test_check_fail_fog_not_cleared(project):
    make_full_thesis(project)
    rounds = os.path.join(project["slug_dir"], "thesis", "rounds")
    make_round(os.path.join(rounds, "round_3.md"), 3, ["FG-02：B — B — 待决"])
    assert tr.cmd_check(ns(project["root"], "slug")) == 1


def test_check_fail_round_missing_fog_snapshot(project):
    make_full_thesis(project)
    rounds = os.path.join(project["slug_dir"], "thesis", "rounds")
    with open(os.path.join(rounds, "round_2.md"), "r", encoding="utf-8") as f:
        content = f.read()
    with open(os.path.join(rounds, "round_2.md"), "w", encoding="utf-8") as f:
        f.write(content.replace("## 雾区清单（本轮末，1 项）\n", ""))
    assert tr.cmd_check(ns(project["root"], "slug")) == 1


# ── 课题 slug 收集 ───────────────────────────────────────────────

def test_topic_slugs_skips_subdirs_and_manifest(project):
    os.makedirs(os.path.join(project["topics"], "entry-01-alpha"), exist_ok=True)
    with open(os.path.join(project["topics"], "_extraction_manifest.md"), "w",
              encoding="utf-8") as f:
        f.write("# 清单\n")
    assert tr.topic_slugs(project["topics"]) == ["entry-01-alpha", "meta-01-beta"]


# ── Skill 文件结构 ───────────────────────────────────────────────

def test_skill_structure():
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(skill_dir, "SKILL.md"), encoding="utf-8") as f:
        skill = f.read()
    assert skill.startswith("---")
    assert "name: research-thesis-integration" in skill
    assert "description:" in skill
    for step in ("Step 0", "Step 1", "Step 2", "Step 3", "Step 4", "Step 5"):
        assert step in skill
    for f in ("prompts/01-element-cards.md", "prompts/02-proposal-round.md",
              "prompts/03-argument-draft.md", "prompts/04-story-draft.md",
              "prompts/05-structure-draft.md",
              "references/discussion-rules.md", "references/thesis-contract.md",
              "scripts/thesis_runner.py", "scripts/evidence.py"):
        assert os.path.exists(os.path.join(skill_dir, f)), f
