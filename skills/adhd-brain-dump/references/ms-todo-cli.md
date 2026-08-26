# Microsoft To Do CLI 参考（microsoft-todo-cli）

## 概览

- Python 包 `microsoft-todo-cli`（PyPI），命令名 `todo`。**默认已安装**（不要用 `mstodo`/`ms365todo`，那是另外两个无关 CLI）。
- 运行前必须设置 `$env:PYTHONIOENCODING="utf-8"`（PowerShell）或 `PYTHONIOENCODING=utf-8`（bash），否则中文/emoji 输出触发 GBK 编码错误。

## 定位与安装

```powershell
# 1) 尝试 PATH 中的 todo
$todo = (Get-Command todo -ErrorAction SilentlyContinue).Source
# 2) 否则在 pip 用户安装目录中查找
if (-not $todo) { $todo = (Get-Item "$env:APPDATA\Python\Python3*\Scripts\todo.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName }
# 均无 → 安装
if (-not $todo) { pip install microsoft-todo-cli; $todo = (Get-Item "$env:APPDATA\Python\Python3*\Scripts\todo.exe").FullName }
```

前置检查：`$env:PYTHONIOENCODING="utf-8"; & $todo lists` 返回清单列表即认证可用。

### 认证排障（CLI 已知 OAuth bug）

配置与凭据位于 `~/.config/microsoft-todo-cli/`（`keys.yml`、`token.json`，**绝不打印内容**）。首次使用需按官方指南注册 Azure 应用并完成 OAuth：<https://github.com/underwear/microsoft-todo-cli/blob/main/docs/setup-api.md>

两个已实测的 bug 及绕法：

1. **token 交换失败（AADSTS7000215）**：CLI 的 `fetch_token` 把 client 凭据放在 HTTP Basic Auth，Azure 拒绝。绕法：手动向 `https://login.microsoftonline.com/common/oauth2/v2.0/token` 发 `grant_type=authorization_code` 的 **form body** 请求（client_id/secret 放 body）。
2. **token.json 格式**：必须为 UTF-8 无 BOM 且含 `expires_at`（`time.time() + expires_in`），否则 CLI 静默回退到重新认证。用 Python `json.dump` 写入。

token 过期重新认证时，CLI 的交互式 `input()` 提示无法在非交互 shell 中驱动：让用户在浏览器完成授权后把 redirect URL 喂给同一运行进程，或重复上述手动 body 交换。

## 常用命令

```powershell
todo lists -j                                  # 所有清单（JSON，含精确 emoji 名）
todo t -l "📞 紧急且重要"                       # 列出清单内任务及子任务
todo new "标题" -l "列表" -N "备注" -d 2026-08-27 -I -S "步骤1" -S "步骤2" -j
todo show "标题" -l "列表"                      # 查看单个任务详情
todo update "标题" -l "列表" -d 2026-08-28 -j   # 修改（标题/日期/重要等）
todo complete "标题" -l "列表"                  # 完成任务
todo new-step "标题" -l "列表" "新步骤名"       # 追加子任务
```

`new` 完整参数：`-l 列表`、`-N 备注`、`-d 日期(YYYY-MM-DD)`、`-I 重要`、`-S 步骤（可重复）`、`-r 提醒`、`-R 重复`、`-L 链接`、`-j JSON输出`。

## 已知坑（全部实测验证）

1. **截止日期 -1 天 bug**：CLI 把本地午夜转 UTC 存储，`-d 2026-08-26` 显示为 25.08。**补偿：传入目标日期 +1 天**（要 8/26 显示就传 8/27）。
2. **控制台中文显示乱码不影响实际写入**，验证以 `todo show` 内容为准。
3. **emoji 清单名**：PowerShell 直接传参可用；批量创建时优先用下面的 Python subprocess 模式（更稳）。
4. **重复导入**：创建前先 `todo t -l "列表"` 查已有任务标题，跳过已存在的，避免重复。

## 批量导入模式（推荐）

写临时 Python 脚本（放系统临时目录），subprocess 调用 todo.exe：

```python
# -*- coding: utf-8 -*-
import subprocess, os, glob

# 定位 todo 可执行文件（PATH → pip 用户目录）
todo = None
for cand in [os.path.join(os.environ["APPDATA"], "Python", f"Python3{m}", "Scripts", "todo.exe")
             for m in ("14", "13", "12", "11")]:
    if os.path.exists(cand):
        todo = cand
        break

def new(title, lst, note, due, important, steps):
    # due 传目标日期+1天，补偿 CLI 的 -1 天 bug
    cmd = [todo, "new", title, "-l", lst, "-N", note, "-d", due, "-j"]
    if important: cmd.append("-I")
    for s in steps: cmd += ["-S", s]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode == 0, (p.stderr or "")[:200]

TASKS = [
    {"list": "\U0001F4DE 紧急且重要", "title": "…", "note": "…",
     "due": "2026-08-27", "important": True, "steps": ["…", "…"]},
]
for t in TASKS:
    ok, err = new(t["title"], t["list"], t["note"], t["due"], t["important"], t["steps"])
    print(("OK " if ok else "FAIL ") + t["title"], err)
```

emoji 清单名在脚本里用 `\U0001F4DE`（📞）`\U0001F5A5`（🖥）等转义写法。

## 清单映射（四象限 → 默认清单）

| 象限 | 默认清单名 |
|---|---|
| 重要且紧急 | 📞 紧急且重要 |
| 紧急但不重要 | 🖥 紧急但不重要 |
| 不紧急但重要 | ✅ 不紧急但重要 |
| 不重要不紧急 / 杂项 | 任务 |

执行时先 `todo lists -j` 核对实际清单名（emoji 必须完全一致）；清单不存在时 `todo new-list "名称"` 创建，或退回「任务」清单。
