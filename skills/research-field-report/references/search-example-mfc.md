# MFC 建库示例：领域参数的完整参照（research-field-report）

> 2026-08-12 真实跑通（research_20260812_mfc/）。领域内容参数化的参照——换领域时替换变体/语义群/排除词，其余照抄。
> ⚠️ 目录契约：该次真实执行时文献库文件落在工作目录根（`literature_db.csv`/`meta.json`/报告输入直接放根目录），
> 已修订为与 5 份报告同放 **`reports/`（产出目录）**——本节列文件名，实际路径以 execution.md 文件布局为准。

## 领域输入（参数化字段）

| 参数 | MFC 值 |
|---|---|
| 领域名 | 金属化薄膜电容器（metallized film capacitor） |
| 命名变体 | metallized / metallised / metalized film capacitor*；self-healing capacitor*；metallized/metallised polypropylene capacitor* |
| 语义群 | `("film capacitor*") AND (metalliz* OR metallis* OR "self-healing")` |
| 排除词（TITLE 级） | supercapacitor* OR electrolytic OR ceramic OR battery OR "solar cell" |

## 最终检索式（1 轮通过，未迭代）

```
TITLE-ABS-KEY(("metallized film capacitor*" OR "metallised film capacitor*" OR "metalized film capacitor*" OR "self-healing capacitor*" OR "metallized polypropylene capacitor*" OR "metallised polypropylene capacitor*") OR (("film capacitor*") AND (metalliz* OR metallis* OR "self-healing"))) AND NOT TITLE(supercapacitor* OR electrolytic OR ceramic OR battery OR "solar cell")
```

- 不加 year / doctype（全时段建库）
- 命名变体用引号短语 + 截词符 `*`；排除词限定在 TITLE 字段

## 建库门结果

- totalResults = 741（≥500 ✅）
- 时间倒序前 20 篇相关 18/20（≥50% ✅）
- 全量导出 30 批 → 合并去重（eid）→ final_raw.json **739 篇**（2 条跨批重复）
- 全程无 429（若出现：等 15s+ 重试，见 fetch_scopus.py 内置退避）

## 数据库

- literature_db.csv 21 列，739 行；卷 497/739、期 395/739、页 739/739；出版社列留空
- meta.json：review_count=14 / total_count=739 / csv_columns=21
- 摘要键兼容解析（dc:description / abstract）：733/739 有摘要

## 综述口径（re+sh）

- 14 篇 = 13 Review + 1 Short Survey；subtypeDescription 显示 12 篇 cr（Conference Review）全部排除

## 5 份报告要点（验收记录）

- 报告 1-4 只喂 14 篇综述子集；报告 5 喂 739 全库 metadata + JCR 表
- grep 校验零污染：全库统计仅出现在 field_landscape.md
- 关键事实：IEEE TDEI 59 篇为第一阵地；材料顶刊（AM/AFM/JMCA/CEJ）2022 起第二增长极；综述子集 2002-2017 空白、2025 单年 4 篇峰值；全库峰值 2024（85 篇）
- 五个前沿方向 D1-D5（field_landscape.md）：自愈概率-寿命一体化模型（基础）、声电阻抗融合在线健康管理+ML RUL（基础）、原子尺度自愈模拟（中期）、辐射-电-热多应力寿命模型（中期）、新型高温介质器件级验证（高阶）

## 期刊分层（报告 5 维度）

- `references/journal-jcr-ranking.json`（16KB 静态 JCR 分层表，冻结自 D:\research_agent\docs\）
- 分层信号：IEEE TDEI（T1/Q2 量级）第一阵地；材料顶刊第二增长极；中文电工期刊（高电压技术 27 篇等）工程线
