# 方向证据 CSV 契约 + project_context.json（research-subtopic-retrieval）

> 定稿：#12（段5 定稿 v2，2026-08-13）。构建由 `scripts/build_evidence_db.py append` 强制执行。

## evidence.csv（23 列 = 21 列同构 + 2 附加列）

前 21 列与全局库 `reports/literature_db.csv` **完全同构**（列名、顺序、编码、规则均同，见 research-field-report `references/database-schema.md`）。附加：

| # | 列名 | 规则 |
|---|---|---|
| 22 | 子问题标签 | 该行由哪个子问题检索带入；取值 = 检索策略文档中该组合的子问题标签（≤12 字） |
| 23 | 来源检索式 | 带入该行的 Scopus 检索式全文（按子问题标签逐次记录的检索式清单） |

规则：

- 编码 `utf-8-sig`；排序 = coverDate 倒序（与全局库一致）
- **EID 去重**：同一 EID 只保留一行；已在全局库的 EID → 复用其 [REXXX] 编号（全局唯一）；已在证据 CSV 的 EID → 不重复追加
- **RE 续签**：新文献从 `project_context.json` 的 `last_issued_re` 续签（全局序列延续）；证据 CSV 内 RE 只增不改、不重排（跨运行稳定）
- **不并入全局库**：全局 `reports/literature_db.csv` 建库后冻结，证据 CSV 独立落盘
- 证据薄弱（某组合 3 轮迭代仍不达标）→ 该组合的行照常追加，`meta.json` 标 `weak_evidence=true`，不设行级列

## search/meta.json 字段

| 字段 | 说明 |
|---|---|
| `direction` | 方向 slug |
| `searches` | 逐组合记录数组：`label` / `query` / `date` / `found`（检索命中数）/ `reused`（复用全局 RE 行数）/ `added`（新签 RE 行数）/ `gate_rounds`（判门轮次）/ `weak_evidence`（bool） |
| `evidence_rows` | 证据 CSV 当前总行数 |

## project_context.json（项目根，跨段状态机）

| 字段 | 说明 |
|---|---|
| `project` | 工作目录名，如 `research_20260812_mfc` |
| `segment` | 当前最远已执行段号 |
| `directions` | `<slug>` → `{"direction_md": 路径, "evidence_csv": 路径}` |
| `last_issued_re` | 全局最后签发 RE 序号（初始 = 全局库最大号，新文献签发后更新） |
| `re_index` | `[REXXX]` → 所在文件路径（全局库行 → `reports/literature_db.csv`；证据行 → 对应 `directions/<slug>/search/evidence.csv`） |
| `topics` | 课题文件指针（**段6 起**写入；段5 为空对象） |

维护规则：由 `build_evidence_db.py append` 自动更新；跨 skill 只读引用，不手工编辑。

共享写入由主 agent 按执行清单串行 append；每次显式传 --context，跨方向共用编号游标时同样串行。全项目 last_issued_re 是已签发编号上界，不要求等于当前方向最大 RE。
