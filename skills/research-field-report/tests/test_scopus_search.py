#!/usr/bin/env python3
"""scopus-search 工具链单元测试（不依赖真实 Scopus API，全 mock 数据）"""
import json, os, sys, tempfile, shutil

# Windows encoding fix
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from scopus_search import (
    parse_response, by_author_top_n, merge_batches, write_final_raw,
    init_iteration_log, append_round,
    decide_next_step, record_force_pass,
    _first_author_lastname, _entry_dedup_key
)

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}  — {detail}")


# ── Mock 数据工厂 ──────────────────────────────────────────────

def make_mock_response(total: int, entries: list, start_index: int = 0) -> dict:
    """构造 mock Scopus 响应。"""
    return {
        "search-results": {
            "opensearch:totalResults": str(total),
            "opensearch:startIndex": str(start_index),
            "opensearch:itemsPerPage": str(len(entries)),
            "entry": entries
        }
    }


def make_entry(eid: str, title: str, first_author: str, doi: str = "",
               cite_count: str = "0") -> dict:
    return {
        "eid": eid,
        "dc:title": title,
        "dc:creator": [{"$": first_author}],
        "prism:coverDate": "2024-01-01",
        "prism:publicationName": "Nature",
        "prism:doi": doi,
        "citedby-count": cite_count,
        "subtypeDescription": "Review",
        "authkeywords": "ai; survey",
        "abstract": "Mock abstract for " + title
    }


# ── 测试1: parse_response ────────────────────────────────────
print("\n📋 测试1: parse_response")

tmp = tempfile.mkdtemp()
raw_path = os.path.join(tmp, "round_1_results_raw.json")
mock_resp = make_mock_response(
    total=1234,
    entries=[make_entry("eid1", "Title A", "Adams J."), make_entry("eid2", "Title B", "Brown K.")]
)
with open(raw_path, "w", encoding="utf-8") as f:
    json.dump(mock_resp, f)

parsed = parse_response(raw_path)
check("totalResults 正确解析为 int", parsed["total_results"] == 1234,
      f"实际: {parsed['total_results']}")
check("entries 数正确", len(parsed["entries"]) == 2)
check("start_index 正确", parsed["start_index"] == 0)

# 无效响应
bad_path = os.path.join(tmp, "bad.json")
with open(bad_path, "w", encoding="utf-8") as f:
    json.dump({"foo": "bar"}, f)
try:
    parse_response(bad_path)
    check("无效响应应抛错", False, "未抛异常")
except ValueError as e:
    check("无效响应应抛错", True)


# ── 测试2: by_author_top_n + _first_author_lastname ──────────
print("\n📋 测试2: by_author_top_n 排序")

entries = [
    make_entry("e1", "Zebra paper", "Zebra Z."),
    make_entry("e2", "Apple paper", "Adams A."),
    make_entry("e3", "Mango paper", "Mango M."),
]
parsed = {"entries": entries}
top_20 = by_author_top_n(parsed, 20)
check("返回 3 篇", len(top_20) == 3)
check("第一篇是 Adams（字母序最早）", "Adams" in top_20[0]["dc:creator"][0]["$"])
check("最后一篇是 Zebra", "Zebra" in top_20[-1]["dc:creator"][0]["$"])

# 仅取前 2
top_2 = by_author_top_n(parsed, 2)
check("仅取前 2 篇", len(top_2) == 2)

# 缺失作者的兜底排序
no_author = [make_entry("x", "T", "")]
parsed_no = {"entries": no_author}
try:
    by_author_top_n(parsed_no, 1)
    check("缺失作者不崩溃", True)
except Exception as e:
    check("缺失作者不崩溃", False, str(e))


# ── 测试3: merge_batches 去重 ────────────────────────────────
print("\n📋 测试3: merge_batches")

batch1 = os.path.join(tmp, "b1.json")
batch2 = os.path.join(tmp, "b2.json")
output = os.path.join(tmp, "final_raw.json")

# b1 含 eid1 + eid3
b1_entries = [
    make_entry("eid1", "Paper 1", "Adams A.", doi="10.1000/aaa"),
    make_entry("eid3", "Paper 3", "Chen W.", doi="10.1000/ccc"),
]
with open(batch1, "w", encoding="utf-8") as f:
    json.dump(make_mock_response(100, b1_entries), f)

# b2 含 eid1 (重复) + eid2 (新)
b2_entries = [
    make_entry("eid1", "Paper 1 (dup)", "Adams A.", doi="10.1000/aaa"),
    make_entry("eid2", "Paper 2", "Brown K.", doi="10.1000/bbb"),
]
with open(batch2, "w", encoding="utf-8") as f:
    json.dump(make_mock_response(100, b2_entries), f)

merge_batches(output, [batch1, batch2])
with open(output, "r", encoding="utf-8") as f:
    final = json.load(f)

check("合并后共 3 条（去重 1 条）", final["meta"]["total_entries"] == 3,
      f"实际: {final['meta']['total_entries']}")
check("原始 4 条 - 去重后 3 条 = 1 条去重",
      final["meta"]["raw_total_before_dedup"] == 4)
check("meta.batch_count = 2", final["meta"]["batch_count"] == 2)
check("按作者姓字母序排：第一篇是 Adams", "Adams" in final["entries"][0]["dc:creator"][0]["$"])

# 来源不存在的批次
merge_batches(os.path.join(tmp, "x.json"), ["nonexistent.json"])
check("缺失批次不崩溃", os.path.exists(os.path.join(tmp, "x.json")))


# ── 测试4: write_final_raw ────────────────────────────────────
print("\n📋 测试4: write_final_raw")

output2 = os.path.join(tmp, "final2.json")
entries2 = [make_entry("e5", "X", "X Y."), make_entry("e6", "Y", "Y Z.")]
write_final_raw(output2, entries2, ["b1.json"])
with open(output2, "r", encoding="utf-8") as f:
    data = json.load(f)
check("final 文件 entries 数为 2", len(data["entries"]) == 2)
check("meta.schema = raw_scopus", data["meta"]["schema"] == "raw_scopus")


# ── 测试5: _entry_dedup_key 多级回退 ────────────────────────
print("\n📋 测试5: _entry_dedup_key")

e_with_eid = make_entry("s2-eid", "T", "X Y.")
check("eid 优先作 key", _entry_dedup_key(e_with_eid) == "eid:s2-eid")

e_with_doi = make_entry("", "T", "X Y.", doi="10.1000/ddd")
check("无 eid 用 doi", _entry_dedup_key(e_with_doi) == "doi:10.1000/ddd")

e_no_id = make_entry("", "T", "X Y.", doi="")
check("都缺用 title", _entry_dedup_key(e_no_id).startswith("title:"))


# ── 测试6: init_iteration_log + append_round ─────────────────
print("\n📋 测试6: iteration_log")

log_dir = os.path.join(tmp, "iteration_test")
os.makedirs(log_dir, exist_ok=True)
log = init_iteration_log(
    output_dir=log_dir,
    original_query='TITLE-ABS-KEY("agent")',
    topic_slug="test_topic",
    year_range="2021-2026",
    min_total=500,
    min_relevant=10,
    max_iterations=3
)
log_path = os.path.join(log_dir, "iteration_log.json")

check("log 含 original_query", log["original_query"] == 'TITLE-ABS-KEY("agent")')
check("pass_criteria.min_total = 500", log["pass_criteria"]["min_total"] == 500)
check("pass_criteria.min_relevant = 10", log["pass_criteria"]["min_relevant"] == 10)
check("force_pass_history 初始为空", log["force_pass_history"] == [])
check("rounds 初始为空", log["rounds"] == [])

append_round(log_path, round_num=1, query='Q1', total_results=1234,
             verdict="PASS", relevant_count=14)
with open(log_path, "r", encoding="utf-8") as f:
    updated = json.load(f)
check("append_round 添加了 1 条", len(updated["rounds"]) == 1)
check("round 1 verdict 正确", updated["rounds"][0]["verdict"] == "PASS")


# ── 测试7: Skill 文件完整性 ──────────────────────────────────
print("\n📋 测试7: Skill 文件结构")

skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
check("SKILL.md 存在", os.path.exists(os.path.join(skill_dir, "SKILL.md")))

with open(os.path.join(skill_dir, "SKILL.md"), encoding="utf-8") as f:
    skill = f.read()
check("frontmatter 完整", skill.startswith("---") and "description:" in skill.split("---")[1])
# 结构检查适配 research-field-report SKILL.md（步骤为 Step 0..8，非独立 scopus-search 的"第 N 步"）
check("包含 Step 0", "Step 0" in skill)
check("包含 Step 1（检索式）", "Step 1" in skill)
check("包含 Step 2（建库门/验证）", "Step 2" in skill)
check("包含 Step 3（全量导出）", "Step 3" in skill)
check("包含 subagent 协议引用",
      "references/iteration-protocol.md" in skill)
check("包含 API 文档引用",
      "references/scopus-api.md" in skill)

check("references/scopus-api.md 存在",
      os.path.exists(os.path.join(skill_dir, "references", "scopus-api.md")))
check("references/iteration-protocol.md 存在",
      os.path.exists(os.path.join(skill_dir, "references", "iteration-protocol.md")))


# ── 测试8: decide_next_step 迭代决策 ────────────────────────
print("\n📋 测试8: decide_next_step")

# PASS 在任何轮都直接进入 fetch
check("Round 1 PASS → pass_and_fetch",
      decide_next_step(1, "PASS", {"max_iterations": 3}) == "pass_and_fetch")

check("Round 2 PASS → pass_and_fetch",
      decide_next_step(2, "PASS", {"max_iterations": 3}) == "pass_and_fetch")

# FAIL + 未达上限 → refine
check("Round 1 FAIL (未达限) → refine_and_retry",
      decide_next_step(1, "FAIL", {"max_iterations": 3}) == "refine_and_retry")

check("Round 2 FAIL (未达限) → refine_and_retry",
      decide_next_step(2, "FAIL", {"max_iterations": 3}) == "refine_and_retry")

# FAIL + 达到上限 → force_pass
check("Round 3 FAIL (达限) → force_pass_and_fetch",
      decide_next_step(3, "FAIL", {"max_iterations": 3}) == "force_pass_and_fetch")

# pass_criteria 缺省
check("无 pass_criteria 默认 max=3",
      decide_next_step(4, "FAIL", None) == "force_pass_and_fetch")


# ── 清理 + 结果 ───────────────────────────────────────────────
shutil.rmtree(tmp)

print(f"\n{'='*50}")
print(f"  通过: {passed}  |  失败: {failed}  |  总计: {passed+failed}")
print(f"{'='*50}")
if failed > 0:
    sys.exit(1)
