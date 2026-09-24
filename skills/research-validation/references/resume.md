# 恢复与续跑

先读 metadata、loop_state 和 `loop_a_runner.py status --validation <validation>`。last_step 和文件存在只是线索，按产物契约校验后决定跳过。

- **有活动轮**（phase=prepared）：沿用 task_id 和原轮次；prepare 只补检索错误，collect 接收已写结果。用宿主任务状态识别还在运行的 worker，避免重复派发；会话丢失且 worker 已终止时，只重派仍缺结果的任务。covered/skipped/merged 和失败计数保留。
- **有 transaction.json**（recovery_needed=true）：下一次 prepare/collect 在写锁内重放上次提交，再继续；无需重新调用 agent。
- **当前轮完成且 gate3_pending**：先批量呈现已有闸门材料和用户决议；a/b/d 才允许清失败计数。不要把网络/格式错误伪装成科研 FAIL 来触发闸门。
- **旧项目没有 loop_a/active.json**：已完整提交的历史轮原样保留，从下一轮 prepare。若下一轮目录已有旧 raw/verdict，脚本明确拒绝覆盖；主 agent 先依据当时 query、来源对象和完整性核对它，补齐旧轮状态后继续。不能仅凭文件存在认领为新版已完成任务。
- **任务生成后输入被改**：脚本拒收陈旧结果。先核对当前输入与活动轮快照，恢复误改或完成旧轮后的正式裁决；不要伪造 task_id 或按表格位置替换论文标识。
- **9.7**：按每对象 steps_manifest 找缺口，只补缺格；其余已校验产物不重跑。

具体命令、字段与退出码见 [执行说明](execution.md) 和 [产物契约](artifact-contracts.md)。本技能不要求固定分支或自动提交。
