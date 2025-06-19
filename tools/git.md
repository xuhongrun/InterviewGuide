### **Git**
Git 是一个**分布式版本控制系统**，由 Linus Torvalds 于 2005 年为管理 Linux 内核开发而创建。它通过跟踪文件变化、记录历史版本和协调多人协作，解决了代码管理的核心问题：
- 📝 **版本回溯**：随时回退到任意历史版本
- 👥 **团队协作**：多人并行开发同一项目
- 🔒 **代码安全**：完整保存所有修改记录
- 🔄 **分支管理**：支持非线性开发流程

> 与 SVN 等集中式系统不同，Git 每个开发者都有完整的仓库副本，实现离线操作和高可靠性

---

### **核心概念**
| 概念 | 说明 | 图示 |
| --- | --- | --- |
| **仓库 (Repository)** | 存储项目历史记录和元数据的数据库 | 📦 `.git` 隐藏目录 |
| **工作区 (Working Directory)** | 用户直接编辑的本地文件 | 💻 你的项目文件夹 |
| **暂存区 (Staging Area)** | 准备提交的文件临时存储区 | 📥 `git add` 后存放的位置 |
| **提交 (Commit)** | 带唯一 ID 的版本快照 | 🔖 `commit d3b0738...` |
| **分支 (Branch)** | 基于特定提交的可移动指针 | 🌿 `main`/`feature` |
| **HEAD** | 当前工作位置的指针 | 👆 指向分支最新提交 |
| **远程仓库 (Remote)** | 共享代码的中心服务器 | ☁️ GitHub/GitLab |

---

### **基础操作**
| 命令 | 参数 | 说明 |
| --- | --- | --- |
| `git init` | `--bare` | 创建裸仓库（无工作目录） |
| `git clone` | `[url]` | 克隆仓库 |
|  | `--depth [n]` | 浅克隆（只获取最近 n 次提交） |
|  | `-b [分支名]` | 克隆指定分支 |
| `git add` | `[文件路径]` | 添加特定文件 |
|  | `.` | 添加所有修改文件 |
|  | `-p` 或 `--patch` | 交互式选择添加改动 |
| `git commit` | `-m "[消息]"` | 提交并添加消息 |
|  | `-a` | 自动添加所有已跟踪文件改动 |
|  | `--amend` | 修改最后一次提交 |
| `git status` | `-s` 或 `--short` | 精简模式输出 |
|  | `-b` | 显示分支信息 |
| `git diff` |  | 显示未暂存的改动 |
|  | `--staged` | 显示暂存区与最新提交的差异 |
|  | `HEAD~[n]` | 与第 n 次前提交比较 |

---

### **分支管理**
| 命令 | 参数 | 说明 |
| --- | --- | --- |
| `git branch` |  | 列出本地分支 |
|  | `-a` | 列出所有分支（含远程） |
|  | `-r` | 列出远程分支 |
|  | `-d [分支名]` | 删除分支（安全模式） |
|  | `-D [分支名]` | 强制删除分支 |
| `git checkout` | `[分支名]` | 切换分支 |
|  | `-b [新分支名]` | 创建并切换分支 |
|  | `-- [文件路径]` | 丢弃文件修改 |
| `git merge` | `[分支名]` | 合并分支 |
|  | `--no-ff` | 禁用快进合并 |
|  | `--abort` | 终止合并冲突 |

---

### **远程协作**
| 命令 | 参数 | 说明 |
| --- | --- | --- |
| `git pull` |  | 拉取并合并 |
|  | `--rebase` | 使用变基代替合并 |
| `git push` |  | 推送到远程 |
|  | `-u origin [分支名]` | 首次推送并建立追踪 |
|  | `--force` 或 `-f` | 强制推送（慎用！） |
|  | `--tags` | 推送所有标签 |
| `git fetch` | `[远程名]` | 获取特定远程更新 |
|  | `--prune` | 清除已删除的远程分支 |
| `git remote` | `-v` | 显示远程仓库地址 |
|  | `add [名称] [url]` | 添加远程仓库 |
|  | `rename [旧名] [新名]` | 重命名远程 |

---

### **撤销与回退**
| 命令 | 参数 | 说明 |
| --- | --- | --- |
| `git restore` | `[文件路径]` | 丢弃工作区修改 |
|  | `--staged [文件路径]` | 取消暂存 |
|  | `--source=[commit] [文件]` | 从指定提交恢复 |
| `git reset` | `--soft HEAD~[n]` | 回退提交但保留修改在暂存区 |
|  | `--mixed HEAD~[n]` | 默认：回退提交并取消暂存 |
|  | `--hard HEAD~[n]` | 彻底回退（慎用！） |
| `git revert` | `[commit-id]` | 创建撤销提交 |
|  | `--no-commit` | 撤销但不自动提交 |

---

### **日志与追溯**
| 命令 | 参数 | 说明 |
| --- | --- | --- |
| `git log` | `--oneline` | 简洁单行显示 |
|  | `-p` | 显示差异内容 |
|  | `--graph` | 图形化分支结构 |
|  | `--since="1 week ago"` | 时间范围筛选 |
|  | `-[n]` | 显示最近 n 条记录 |
| `git blame` | `-L [start],[end]` | 查看指定行范围 |
|  | `-C` | 追踪文件移动历史 |
| `git show` | `[commit-id]` | 显示提交详情 |
|  | `[commit-id]:[文件]` | 查看提交中的文件 |

---

### **高级操作**
| 命令 | 参数 | 说明 |
| --- | --- | --- |
| `git rebase` | `[分支名]` | 变基当前分支 |
|  | `-i HEAD~[n]` | 交互式变基 |
| `git stash` | `save "[消息]"` | 暂存修改 |
|  | `list` | 查看暂存列表 |
|  | `pop` | 恢复最新暂存 |
|  | `apply stash@\{[n]\}` | 恢复指定暂存 |
| `git tag` | `[标签名]` | 创建轻量标签 |
|  | `-a [标签名] -m "[消息]"` | 创建附注标签 |
|  | `-d [标签名]` | 删除标签 |

---

### **配置与帮助**
```bash
# 全局配置
git config --global user.name "Your Name"
git config --global user.email "email@example.com"
git config --global core.editor "code --wait"  # 设置VS Code为编辑器

# 查看配置
git config --list

# 获取帮助
git help [命令]      # 打开手册
git [命令] --help   # 查看帮助
```

---

### 常见场景示例
1. **首次推送本地项目到远程**：
    ```bash
    git init
    git add .
    git commit -m "Initial commit"
    git remote add origin <远程仓库URL>
    git push -u origin main
    ```
2. **解决合并冲突**：
    - 执行 `git pull` 后出现冲突
    - 手动编辑冲突文件（搜索 `<<<<<<<` 标记）
    - 删除冲突标记并保存 → `git add <file>` → `git commit`

3. **撤回已推送的提交**：
    ```bash
    git revert <commit-id>   # 生成反向提交
    git push                 # 推送撤销操作
    ```
    > ⚠️ 注意：强制推送 (`git push -f`) 会覆盖远程历史，团队协作中慎用！

### **典型工作流**
```bash
# 1. 修复bug工作流
git checkout -b hotfix      # 创建分支
git commit -m "Fix bug"     # 提交修复
git checkout main           # 切回主分支
git merge --no-ff hotfix    # 合并修复
git branch -d hotfix        # 删除分支

# 2. 交互式变基（整理提交）
git rebase -i HEAD~3        # 编辑最近3个提交
# 弹出编辑器：squash/fixup/reword等操作

# 3. 恢复误删文件
git checkout HEAD^ -- [文件路径]  # 从上一版本恢复
```

> 💡 **参数组合技巧**：
> ```bash
> # 查看简洁日志（带分支图）
> git log --oneline --graph -10
>
> # 查找包含关键字的提交
> git log -S "functionName" --source --all
>
> # 批量删除已合并分支
> git branch --merged | egrep -v "main|\*" | xargs git branch -d
> ```
