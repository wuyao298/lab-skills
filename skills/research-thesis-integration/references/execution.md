# 执行说明

## 命令（先解析绝对路径）

- 输入检查：`python scripts/thesis_runner.py validate --project <项目> --slug <slug>`
- 全量卡片：`python scripts/thesis_runner.py cards --project <项目> --slug <slug>`
- 增量卡片：`python scripts/thesis_runner.py cards --project <项目> --slug <slug> --topics <涉及课题slug,…>`
- 最终检查：`python scripts/thesis_runner.py check --project <项目> --slug <slug>`
- 引用复核：`python scripts/evidence.py --re <编号…> --db <项目>/directions/<slug>/search/evidence.csv`

模型与 auth 约定见 thesis_runner.py 头注释。 这是执行器的 API 缺省；筛选判断、契约检验与复验等评审子 agent 按 [统一评审配置](review-agents.md) 选择轻量模型、关闭 thinking，核对实际运行参数后再执行。卡片保留在 thesis/cards/<课题>.md；讨论保留在 thesis/rounds/round_N.md；最终文件为 thesis_argument.md、thesis_story.md、thesis_structure.md。
check 包括 cards 四段、逐课题 RE 子集、三产物字段、rounds 连续、雾区逐轮非增及终态清空；与讨论出现的新雾区有冲突时保留真实快照，报告冲突，不能改写用户记录以通过检查。
