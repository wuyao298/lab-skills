# 强相关文献筛选契约（段6.1）

> 定稿：#13（段6 定稿：方案前置深化）。执行 = `scripts/deepening_runner.py screen / merge / check`。
> 输入 = 课题池（topics/ 全部课题 MD，课题间并行）+ 方向证据 CSV（`directions/<slug>/search/evidence.csv`，段5.2 产物）；分割 = 段5.3 先例（`directions/<slug>/analysis/batch_NNN.csv`，每批 50 篇，只留编号/标题/摘要；缺则按同规则重新分割）。

## 判定标准（提示词A，原文）

- 直接相关 = 满足 A 理论支持 / B 技术路线支持 / C 关键资源与基准支持 / D 问题剖析与前瞻支持 中**至少一类**
- 排除：仅领域相关；泛泛综述（除非满足 D 类）；场景相关但方法/理论/资源均无关

## screening_batches/batch_NNN.md（分批筛选输出）

由 subagent 按 `prompts/01-screening.md` 产出，段固定：

```
## 筛选表        → 表格：论文编号 | 相关性类别 | 关键研究方法与材料 | 核心性能指标 (量化) | 创新性与局限性分析 | 对我课题的启发点
```

铁律：

- 只含**直接相关**论文；不相关论文不输出行
- 论文编号 = 该批 CSV 内编号，带方括号原样（[REXXX]），**禁止批次外编号**（runner 脚本实测复核，非法行修复 ≤2 轮，仍非法则打 ⚠️ 标记并 check 失败）
- 相关性类别 = A/B/C/D，可多类连写（如 AB）
- 表格段 = 紧接 `## 筛选表` 标题之后的 Markdown 表格，直到下一个 `## ` 标题为止（merge 脚本按此段切取）

## screening.md（合并筛选表 = 该课题的论文集）

`deepening_runner.py merge` 自动产出（`topics/<课题 slug>/screening.md`）：

```markdown
# 强相关文献筛选表（<课题标题>）

> 课题：topics/<课题 slug>.md ｜ 论文池：directions/<slug>/search/evidence.csv（N 篇，B 批）｜ 合并自 screening_batches/
> 相关性判定：A 理论支持 / B 技术路线支持 / C 关键资源与基准支持 / D 问题剖析与前瞻支持（至少一类 = 直接相关）

## batch_001（源 screening_batches/batch_001.md）
| 论文编号 | 相关性类别 | … |

## batch_002（源 screening_batches/batch_002.md）
| 论文编号 | 相关性类别 | … |
```

- 只收「## 筛选表」表格段，不收批次文件其他内容
- `deepening_runner.py check` 校验（每课题）：screening_batches 与批次 CSV 一一对应；每行编号存在于对应批次 CSV（无外引、无捏造）；表内无重复行；screening.md 与分批表行集一致

## 目录

```
topics/<课题 slug>/
├── screening_batches/          # 分批筛选（中间产物，保留）
│   ├── batch_001.md … batch_NNN.md
├── screening.md                # 合并筛选表 = 该课题的论文集（6.2 输入）
└── deepened.md                 # 6.2 产物（见 deepened-contract.md）
```
