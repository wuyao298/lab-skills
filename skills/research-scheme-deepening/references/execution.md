# 执行说明

## 命令（先解析绝对路径）

- 筛选：`python scripts/deepening_runner.py screen --project <项目> --slug <slug> [--topics t1,t2] [--workers 100] [--split] [--dry] [--only N]`
- 合并：`python scripts/deepening_runner.py merge --project <项目> --slug <slug> [--topics t1,t2]`
- 检查：`python scripts/deepening_runner.py check --project <项目> --slug <slug> [--topics t1,t2]`
- 深化：`python scripts/deepening_runner.py deepen --project <项目> --slug <slug> [--topics t1,t2] [--workers 100] [--dry]`

默认全量课题；--topics 用于显式限定或修复重跑，--only 用于单批试跑。--split 在缺批次时重新切分，使用前先确保 `<项目>/directions/<slug>/analysis/` 目录存在；当前 runner 会先枚举目录，再处理自动切分。
--dry 只产生试跑材料，不调用模型，不算完成筛选/深化。
模型与 auth 约定见 deepening_runner.py 头注释，缺省 workers=min(任务数,100)。 这是执行器的 API 缺省；筛选判断、契约检验与复验等评审子 agent 按 [统一评审配置](review-agents.md) 选择轻量模型、关闭 thinking，核对实际运行参数后再执行。

## check 的边界

check 可用于筛选后的检查，因此不强制每课题已有 deepened.md；其 RE 检查覆盖方向批次集合，并不代替逐课题 screening 子集核验。交付前另查 deepened 文件齐备、五要素、修改摘要、加粗和逐课题 RE 子集。
保留 topics/<课题>/screening_batches/；screening.md 为合并论文集，deepened.md 为最终方案；原 topics/<课题>.md 只读。
