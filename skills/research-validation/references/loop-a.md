# LOOP A 与闸门3

## Step 4：检索 → 原生 agent 分级 → 收取

主 agent 是唯一编排者。脚本负责 Scopus 检索、任务文件、校验和共享状态；分级交给宿主提供的原生子 agent。Codex、Claude Code、OpenCode 或其他宿主都用同一文件协议，无需在脚本里配置模型 API。没有子 agent 工具时，主 agent 逐任务执行相同提示词。

`<runner>` = 本技能 `scripts/loop_a_runner.py` 的绝对路径；`<validation>` = 项目 `directions/<slug>/validation/` 的绝对路径。

1. **恢复/准备。** 执行 `python <runner> prepare --validation <validation> --workers 4 [--env-file <外置env>]`。`--workers` 只控制 Scopus 并发，1..100，按配额调整；子 agent 并发由宿主可用槽位决定。`--dry` 只读计划，不联网、不读密钥、不改轮次。
2. **分派。** 按 [子 agent 配置](execution.md#子-agent-配置) 选择轻量模型、关闭 thinking，再读命令返回的 `ready` 列表。每个任务只把 `prompt_file` 交给一个 worker，指定它只写对应 `result_file`。输入含 ep4-A 原文、本 ACU 所有 `source_objects` 的 MVE、该轮 ≤25 条真实条目。每篇按 H1/H2/H3、M1/M2、排除标准判断；输出契约见 [产物契约](artifact-contracts.md)。同一任务同时只派一个 worker。
3. **有结果即收取。** 运行 `python <runner> collect --validation <validation>`。只接收 task_id 匹配、逐篇覆盖、级别合法的结果，机械生成四列 `verdict.md`。无需等所有 worker 才收取已完成任务；仍在运行的任务不重复分派。格式错误只退回该 worker，附上 `errors` 的具体原因；连续两次修复无效时由主 agent 检查输入，不无限续写。
4. **判断出口。** `pending>0` 留在本轮；检索错误时重跑 prepare 只补错误任务，已有有效任务不重查。全部任务有效后 `phase=complete` 才推进全局 round。`gate3_pending=true` 先走 Step 5；否则仍有 open ACU 才开始下一轮，全部 ended 才进入9.6。即使零命中且 `ready=[]`，也执行 collect 完成本轮。

`status --validation <validation>` 只读状态；优先用宿主的任务完成通知/等待工具，避免高频轮询。`round` 是 prepare 的兼容别名，只准备任务，不再直接调用模型。旧 `--project/--slug` 可用，`--object` 仅兼容参数；上下文始终由 ACU 的来源对象决定。

### 完成与错误边界

- **PASS** = 完整有效结果中≥1篇高；**FAIL** = 完整有效结果中0篇高（含真实 totalResults=0）。级别不必三类都出现。网络超时、401/429、agent 中断、非法 EID/缺行属于执行错误，不增加科研失败计数。
- Scopus 固定首页 `count=25, sort=relevance, view=COMPLETE`；同一轮完全相同 query 共用一次真实检索，ACU 分别分级；跨轮不缓存。响应 query 不一致、非零结果缺条目会报错，不能使用旧 raw 冒充成功。
- covered / skipped / merged 不派任务。当前 query 以 loop_state 为准（缺失才用 acu_index 初始化），不会用陈旧索引覆盖用户的闸门决议。
- worker 只写独占结果文件；主进程用写锁、原子替换和恢复日志更新 loop_state、per_ACU、metadata、retrieval_report。collect 可重复执行，不重复增加轮次或失败计数。
- 待完成轮中不改 query/MVE/来源对象或共享状态。输入摘要或 task_id 不匹配时拒收旧结果，先核对修改来源。正常改 query 在闸门决议之后，下一轮生成新任务。

**完成：** 全部 ACU 为 covered/skipped/merged；或所有触发 ACU 已批量进入闸门3。全局仍限10轮；第10轮未决时不自动开第11轮。

## Step 5：闸门3（批量）

触发 = 某 ACU 连续两轮真实 FAIL，或第10轮仍未达标。先收齐当前轮有效结果，再把所有触发 ACU 一起呈现。可运行 `build_gate3_material.py --validation <validation>` 生成机械材料；第10轮但失败计数不足2的 ACU 用重复的 `--acu <id>` 显式纳入。

主 agent 用 `prompts/05-gate3-refine.md` 原文加每 ACU 材料，原生分派 query 建议任务。输入含当前 query、totalResults、前20条题录摘要、verdict 摘要、三策略菜单、合并候选与跳过风险。建议不直接改当前 query；所有决定引用用户真实答复：

- **a 改 query**：接受建议/手改/全新；更新 loop_state 当前 query 与 acu_index，失败计数清零。
- **b 合并**：源 ACU 标 merged、写 merged_into；目标/新 ACU 的来源对象与必要锚点同步，失败计数清零；已 covered 目标如果研究输入改变，须明确重新验证。
- **c 跳过**：标 skipped 并记 skipped_acus；保留对应 MVE 步骤，9.7 标「实现锚点缺失」。
- **d 重写策略**：更新锚点/模块/策略和 acu_index，经用户确认后更新当前 query，失败计数清零。

主 agent 串行同步 loop_state、per_ACU、metadata；用户原话与决议追加到 gate_3_decisions.md。未全部裁决保留 gate3_pending，不进入9.6。第10轮仍需 a/b/d 时，先明确新的验证周期/归档范围，不能静默重置或突破当前10轮上限。

**完成：** 无未决 ACU，才进入知识库构建；已确认事项不重复询问。
