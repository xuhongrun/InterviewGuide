`repo` 是 Google 为管理多个 Git 仓库而开发的工具，主要用于 Android 开源项目（AOSP）等大型项目。它通过清单文件（`manifest.xml`）统一管理多个 Git 仓库的依赖关系。以下是核心用法和常见命令：

---

### **一、安装 `repo`**
```bash
# Linux/macOS
curl https://storage.googleapis.com/git-repo-downloads/repo > ~/bin/repo
chmod a+x ~/bin/repo

# Windows (需先安装 Git 和 Python)
pip install git-repo
```

---

### **二、初始化仓库**
```bash
repo init -u <manifest仓库URL> -b <分支名>
```
- **示例** (初始化 AOSP 主分支)：
  `repo init -u https://android.googlesource.com/platform/manifest -b main`

---

### **三、常用命令**

常用 `repo` 命令与对应 git 命令对照表

| repo 命令 | 等效的 git 命令（单仓库场景） | 说明 |
| --- | --- | --- |
| `repo init -u <URL>` | `git init` + 清单配置 | 初始化仓库并配置清单 |
| `repo sync` | `git fetch --all && git merge` | 拉取远程更新并合并到本地 |
| `repo start <branch>` | `git checkout -b <branch>` | 创建并切换到新分支 |
| `repo status` | `git status` | 查看修改状态（汇总所有仓库） |
| `repo diff` | `git diff` | 查看代码差异（汇总所有仓库） |
| `repo upload` | `git push origin HEAD:refs/for/<br>` | 提交代码到评审系统（如 Gerrit） |
| `repo prune` | `git branch -d <merged-branch>` | 删除已合并的分支 |
| `repo abandon <branch>` | `git branch -D <branch>` | 强制删除分支 |
| `repo forall -c 'git log -1'` | 直接执行 `git log -1` | 在所有仓库执行指定 git 命令 |
| `repo checkout <branch>` | `git checkout <branch>` | 切换分支（需要清单支持） |
| `repo rebase` | `git rebase` | 变基操作（跨仓库批量处理） |

#### **关键区别说明**
1. **操作范围不同**
   - `git` 命令：仅针对**单个仓库**
   - `repo` 命令：默认操作**所有仓库**（可通过路径参数限定范围）

2. **清单文件依赖**
   `repo` 操作依赖 `.repo/manifests/` 中的 XML 清单文件定义仓库关系，例如：
   ```xml
   <!-- 示例：定义 kernel 仓库 -->
   <project
     path="kernel/linux"
     name="platform/kernel/linux"
     revision="android-14.0.0_r1" />
   ```

3. **批量操作优势**
   当需要跨 100+ 仓库执行操作时，`repo` 效率显著高于手动循环执行 `git` 命令：
   ```bash
   # 批量重置所有仓库（危险操作！）
   repo forall -c 'git reset --hard HEAD'

   # 批量查看未提交更改
   repo forall -c 'git status -s'
   ```

4. **工作流集成**
   `repo upload` 专为代码评审系统设计，比直接 `git push` 多了自动生成评审请求的功能。

> 💡 **经验提示**：在大型项目（如 Android 系统）中，组合使用 `repo` 和 `git` 更高效：
> - 用 `repo` 管理仓库组和全局操作
> - 用 `git` 在单个仓库内执行精细操作

---

### **四、配置清单文件**
- 默认清单路径：`.repo/manifests/default.xml`
- 自定义清单：
  `repo init -m custom_manifest.xml` （替换默认清单）
- 常用清单属性：
  ```xml
  <project path="目录名" name="仓库URL" revision="分支/标签" />
  ```

---

### **五、高级技巧**
- **部分同步**：
  `repo sync <project_path1> <project_path2>`（仅同步指定仓库）
- **跳过网络检查**：
  `repo sync -n`（仅更新元数据，不下载代码）
- **本地清单**：
  在 `.repo/local_manifests/` 添加 `local_manifest.xml` 可覆盖默认配置。

---

### **六、常见问题**
- **同步中断**：
重新运行 `repo sync` 或 `repo sync --fail-fast`。
- **网络问题**：
使用代理：`export HTTP_PROXY=http://<proxy_ip>:<port>`
- **磁盘空间不足**：
删除 `.repo/project-objects/` 中的缓存（谨慎操作！）

---

> 官方文档参考：[Android Repo 使用指南](https://source.android.com/docs/setup/develop/repo)
> 提示：结合 `git` 命令使用效果更佳（如 `git log`、`git branch` 等）。
