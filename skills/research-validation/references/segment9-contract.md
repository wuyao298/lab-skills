# 段9 完整验证契约（#16 定稿要点）

> 本文件是本技能可独立执行的验证契约，覆盖流程边界、人工决策点、输入输出与校验要求。

## 定位

- 段9 做：研究设计 → MVE → 元分析+检索式 → LOOP A → 闸门3 → 复现筛选 → 逐步骤 MVE 细化。
- 段9 不做：实验执行、实验结果分析、回写 `thesis/plan/`、论文写作。
- 段9 不依赖段8 故事；验证范围由用户入口指定；验证结果不改故事骨架。

## 输入

| 输入 | 必须 | 用途 |
|---|---|---|
| `directions/<slug>/direction.md` | 是 | 方向边界与术语契约 |
| `topics/<课题 slug>.md` + `topics/<课题 slug>/deepened.md` + `topics/<课题 slug>/screening.md` | 是 | 验证对象候选池；研究设计/约束来源 |
| `thesis/plan/chapter_*_workpackage.md` | 否（有则优先） | 直接复用，不重跑 ep1 |
| `thesis/plan/constraints.md` | 否（有则强制读） | 信息误差约束 |
| `thesis/references/thesis_references.csv` | 否 | RE 元数据查询 |
| 全局库 / 方向证据 CSV / `project_context.json` | 是（按需） | RE 合法性、EID 去重、双标注 |
| Scopus API key（环境变量/.env） | 是 | LOOP A 检索；密钥永不入库 |

## 人工点（仅两个）

1. **Step 0 入口选择**：用户指定 1..N 个验证对象 + 每个对象 9.7 细化范围。
2. **闸门3**：LOOP A 连续失败 ACU 批量裁决（改 query / 合并 / 跳过 / 重写策略）。

其余全部自动。9.1/9.2 无 MVE pin；9.3/9.4/9.6/9.7 无人工确认点。

## 关键决策（按步骤）

- **9.1**：优先复用 `thesis/plan/chapter_*_workpackage.md`，只写指针不复制正文；工作包 `【待补】` 必须在 selection.md 补齐或显式声明沿用 deepened 默认，否则不入本轮。constraints.md 强制读。
- **9.2**：ep2-promptB 双路径（A 问题-假设验证 / B 方案-假设验证）；G/NG 可量化、低配替代必选；全自动直通 9.3。
- **9.3**：多对象 = 一次全局元分析（单对象退化）；ACU 全局唯一编号、每 ACU 标来源对象；锚点实体必须来自方案原文；**RE 编号不入检索式**；起手策略 = ②实现优先（资源锚点模块）。
- **9.4**：仅 Scopus 直连 REST；`count=25`、`sort=relevance`、`view=COMPLETE`；不加 year/doctype/来源库；每轮每 ACU 只拉首页 25 条；totalResults=0 记 FAIL。verdict 用 ep4-A 原文，**高/中/建议排除**（高 = H1 参数优化 / H2 参数-结果直接关联 / H3 详尽方案宣告；中 = M1 核心方法明确 / M2 方法改进声明）。**PASS = ≥1 篇高；FAIL = 0 篇高**；中/排除不计覆盖。全局 ≤10 轮，只重跑 open ACU。
- **9.5**：单 ACU 连续 2 轮 FAIL → 闸门3；第 10 轮仍有未达标 ACU → 全部强制上桌；批量逐 ACU 四选一：a 改 query / b 合并 / c 跳过 / d 重写策略。a/b/d 清失败计数；c 不删 MVE 步骤，9.7 标「实现锚点缺失」。
- **9.6**：只收 covered ACU 首个 PASS 轮全部「高」；EID → DOI → 标题去重；跨 ACU 记 `来源 ACU`；XE 本地唯一编号；已 RE 文献双标注；不新签全局 RE、不追加证据 CSV；按对象切分 knowledge_base。
- **9.7**：默认 A+B 全部步骤；`(对象 × 路径 × 步骤)` 全并行、严格输入隔离；ep4-B 七段结构；skip 步骤照常细化并标风险；合并为 `<object>/mve_step_detail.md`。

## 目录根

`directions/<slug>/validation/`（与 `thesis/`、`topics/` 平级）。文件集见 [执行说明](execution.md) 的文件布局；校验清单见本文件 §13。
