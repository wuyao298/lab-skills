# check_validation.py 补丁记录（2026-09-09）

> 原则：契约文档 `本技能 references/segment9-contract.md` 与
> `references/artifact-contracts.md` 不改；只修校验脚本里与契约 schema 不一致的实现 bug，
> 每条补丁都在此登记，便于复现与回滚。

## P1 · `per_ACU.rounds_run` 形态容错

- 位置：`check_step4()`「scopus_runs 轮次与 per_ACU.rounds_run 不一致」判定。
- 问题：契约 schema 规定 `rounds_run` 是**已跑轮数**（int，如 `2`），原实现写
  `sorted(rounds) == sorted(pa.get("rounds_run") or [])`，对 int 调用 `sorted()` 会
  `TypeError`，脚本直接崩。
- 修复：int 形态要求 `max(rounds) == rounds_run`；list 形态仍按集合比较。

## P2 · RE 双标注按数值比较

- 位置：`check_step6()`「命中已签发 RE… 但未双标注」判定。
- 问题：`load_re_maps()` 返回 `int` RE 编号，而 `reproducibility_index.json` 的 `re`
  字段保留零填充原文（如 `[RE073]`）。原实现用 `str(expected_re) in re_tags`
  比较 `"73"` 与 `["073"]`，永远为假 → 3 条已正确双标注的条目被误判失败。
- 修复：两侧都转成整数集合比较。

## P3 · 归档批次排除

- 位置：`check_step0()` 对象清单解析。
- 问题：共享 `validation/` 只有一套 `acu_index.json` / `knowledge_base/` /
  `reproducibility_index.json`。`obs-01`（2026-09-08 已完成、check_passed=true）与
  `entry-01-topic-01` 两批次 ACU 编号体系冲突：obs-01 的 XE 条目 `source_acus` 含
  已不存在的 ACU-012，且其 ACU-001..011 与 entry-01 同名不同义。两批次同时纳入校验
  范围必然互斥失败。
- 修复：`metadata.json` 增加 `archived_objects` 列表；`check_step0` 从对象清单中剔除
  归档对象，其 9.1/9.2/9.7 产物不再要求存在。obs-01 的原始证据与全部产物完整保留在
  `validation/_archive/obs-01/`（含 9.6 与 README 说明）。

## 新增脚本（不改原 runner）

| 脚本 | 用途 |
|---|---|
| `refetch_round.py` | 单个 ACU 指定轮次重新检索 + 重判（修陈旧 raw） |
| `stub_zero_rounds.py` | totalResults=0 的轮次补空表 verdict（原 runner 不写） |
| `strict_verdict.py` | 按契约四列表头强制重出 verdict（H1/H2/H3 口径 + 位置修复） |
| `strict_regrade.py` | 用 check_validation 的判定口径重算 loop/per_ACU 状态 |
| `build_gate3_material.py` | 闸门3 机械材料（query/total/前20/verdict统计/策略菜单/合并候选） |
| `gate3_suggest.py` | ep3-prompt2 批量检索式优化建议 |
| `build_step_prompts.py` | 9.7 每步自包含提示词（严格输入隔离 + 知识库切片） |
| `merge_step_detail.py` | 9.7 分步文件合并为 `mve_step_detail.md` |
