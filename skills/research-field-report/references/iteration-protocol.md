# Subagent 验证协议

步2 subagent 的输入/输出/判定标准。判门评审按 [统一评审配置](review-agents.md) 使用宿主轻量模型、关闭 thinking，只读不写。

## 输入

- `round_N/results_raw.json`
- `iteration_log.json`（含 pass_criteria）
- 用户主题（一句话）

## 判定

读前20篇（已按 author 升序），逐篇判 title+abstract 与用户主题是否直接相关：

```
PASS: totalResults ≥ min_total AND 前20相关 ≥ min_relevant
FAIL: 否则
```

默认阈值：total≥500、相关≥10、最多3轮。

相关性原则：保守（宁可判不相关）、容忍术语变体（LLM/large language model）、跨领域论文判不相关。

## 输出格式

写 `round_N/verdict.md`：

```markdown
# Round N Verdict

**Verdict: PASS / FAIL**

| 指标 | 实测 | 阈值 | 通过 |
|------|------|------|------|
| totalResults | N | ≥500 | ✓/✗ |
| 前20相关 | N | ≥10 | ✓/✗ |

## 优化建议（FAIL时）

1. **关键词**：具体修改
2. **字段限定**：加 AND NOT 等
3. **结构**：拆括号/重组

## Final Query（PASS时）

本轮 query 原样固定。
```

## 常见失败模式

| 现象 | 原因 | 调整 |
|------|------|------|
| total < 500 | 过严 | 减 AND、加同义词 OR |
| total > 1000 但相关 < 10 | 过宽 | 加 AND 限定、AND NOT 排噪音 |
| total < 100 | 过窄 | 放宽关键词、加通配符 |
| 前20混入其他领域 | 关键词偏了 | 加 AND NOT TITLE(...) 排除 |

## Refinement Sub-Prompt（步4用）

```
你是 query 优化助手。以下 query 被判定 FAIL：

Query: {query}
主题: {user_topic}
失败: totalResults={total}，前20相关={relevant}

前20篇明细（标了相关/不相关）：
{entries}

任务：
1. 分析哪些片段导致不相关
2. 1-3条具体修改（关键词/字段/结构）
3. 输出完整优化后 query（必须可直接运行，禁止占位符）

Scopus 语法：TITLE-ABS-KEY(...)、AND/OR/AND NOT、通配符*。
```
