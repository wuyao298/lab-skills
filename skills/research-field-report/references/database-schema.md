# 数据库契约：21 列 schema + meta.json（research-field-report）

> 定稿：#6（CSV schema）+ 执行修订（2026-08-12）。构建由 `scripts/build_database.py build` 强制执行。

## literature_db.csv（21 列）

| # | 列名 | 来源 | 规则 |
|---|---|---|---|
| 1 | 编号 | 模块字段 | `[RE001]` 起递增（coverDate 倒序后编号），人读索引，EID 为主键 |
| 2 | 来源库 | 模块字段 | 固定 `Scopus` |
| 3 | 标题 | `dc:title` | 原样 |
| 4 | 作者（IEEE） | `dc:creator` 派生 | 仅第一作者（Scopus search API 返回格式）；`'Qin S.'` → `'S. Qin'`；`'Andreeva N.A.'` → `'N. A. Andreeva'`；复姓 `'Albéndiz García A.'` → `'A. Albéndiz García'`；去中文字符；缺失 → `[Unknown]` |
| 5 | 来源名称 | `prism:publicationName` | 期刊/会议名原样 |
| 6 | 文献类型 | `subtypeDescription` | 如 Article / Review / Conference Paper |
| 7 | 是否综述 | `subtype` 派生 | `re`/`sh` → 是；其余 → 否（**综述口径**，见下） |
| 8 | 卷 | `prism:volume` | 缺失填空 |
| 9 | 期 | `prism:issueIdentifier` | 缺失填空 |
| 10 | 页码 | `prism:pageRange` | 缺失填空 |
| 11 | 出版年 | `prism:coverDate` 派生 | 取前 4 位 |
| 12 | 出版月 | `prism:coverDate` 派生 | IEEE 缩写（Jan. Feb. Mar. Apr. May Jun. Jul. Aug. Sep. Oct. Nov. Dec.，May 无句点） |
| 13 | DOI | `prism:doi` | 原样，不转小写 |
| 14 | ISSN | `prism:issn` / `prism:eIssn` | 任一 |
| 15 | 出版社 | — | **留空**（search API 不返回） |
| 16 | 会议名 | `subtypeDescription` 派生 | 文献类型以 `Conference` 开头时镜像该值，否则空 |
| 17 | 摘要 | `dc:description`（兼容 `abstract`） | 原样（含 HTML 标签），缺失填空 |
| 18 | 作者关键词 | `authkeywords` | 单条/数组均可；`; ` → `|` 归一化 |
| 19 | 被引次数 | `citedby-count` | 字符串 → int，缺失为 0 |
| 20 | EID | `eid` | Scopus 库内唯一键 |
| 21 | 原文链接 | `prism:url` | 原样 |

## 编码与排序

- 编码：全部 CSV 用 `utf-8-sig`（Excel 兼容）
- 排序：`prism:coverDate` 倒序（数字序，非月份字母序）；缺失日期排最后
- 全量导出后按 `eid → DOI → title` 去重（`scopus_search.py merge`）

## meta.json 字段

| 字段 | 说明 |
|---|---|
| `review_count` | 综述口径（re+sh）条数 |
| `total_count` | 全库条数 |
| `build_date` | 建库日期 YYYY-MM-DD |
| `query` | 最终检索式全文 |
| `source_db` | `Scopus` |
| `review_subtype_criteria` | `subtype in {re, sh} (Review / Short Survey); cr excluded as conference proceedings records (user decision 2026-08-12)` |
| `csv_columns` | `21` |

## 综述口径（re+sh）

- 综述 = `subtype` 为 `re`（Review）或 `sh`（Short Survey）
- **`cr` 排除**：实测 `cr` 全是会议 proceedings 记录（"The proceedings contain N papers..."），非综述论文（用户决策 2026-08-12，修订自 re/sh/cr）

## 报告输入（split 产物，防上下文污染）

| 文件 | 内容 | 消费方 |
|---|---|---|
| `review_subset.csv` | 综述口径行（21 列完整） | 存档/复核 |
| `report_input_review.csv` | 综述子集 5 列：标题,摘要,出版年,来源名称,作者关键词 | 报告 1-4 subagent（**唯一**输入） |
| `report_input_full_metadata.csv` | 全库 5 列：标题,出版年,来源名称,作者关键词,文献类型（**无摘要**） | 报告 5 subagent（**唯一**输入） |

> 以上文件与 5 份报告同放工作目录 **`reports/`（产出目录，交付集中）**；检索原始数据（round_1_raw / batches / final_raw）留工作目录根（中间产物）。
