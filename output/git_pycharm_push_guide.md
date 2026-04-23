# PyCharm 手动推送 GitHub 仓库笔记

本文以当前项目为例：

- 本地项目目录：`D:\py\project`
- GitHub 仓库：`https://github.com/bao-an123456/math_modeling.git`
- 当前分支：`main`
- 建议提交的核心文件：
  - `code/solve_problem1.py`
  - `output/*.md`
  - `.gitignore`

## 1. 为什么要写 `.gitignore`

`.gitignore` 用来告诉 Git：哪些文件不应该进入版本库。

常见应该忽略的内容：

- PyCharm 配置目录：`.idea/`
- Python 缓存：`__pycache__/`、`*.pyc`
- 虚拟环境：`.venv/`、`venv/`
- 原始数据或大文件：`data/`
- 程序运行结果：`results/`
- 生成的表格和图表：`*.csv`、`*.xlsx`、`*.pdf`

但是，`.gitignore` 不应该随便忽略所有源码文件。比如新的 `.py` 文件将来可能也需要提交，所以更稳妥的做法是：

- 忽略缓存、数据、结果、生成物。
- 保留真正需要版本管理的代码和 Markdown 笔记。
- 如果某个源码文件明确只是临时脚本，再单独写入 `.gitignore`。

当前项目的 `.gitignore` 规则保留了 `output/*.md`，同时忽略 `output` 里的 CSV、Excel 等生成结果。

注意：`.gitignore` 只会自动影响“还没有被 Git 跟踪”的文件。如果某个文件已经 commit 过，再写进 `.gitignore` 也不会自动取消跟踪，需要执行：

```powershell
git rm --cached 文件路径
```

## 2. 在 PyCharm 中确认项目已经启用 Git

打开 PyCharm 后，确认打开的是：

```text
D:\py\project
```

如果右上角或底部能看到 Git 分支，例如 `main`，说明项目已经启用 Git。

如果没有启用：

1. 点击菜单 `VCS`。
2. 选择 `Enable Version Control Integration...`。
3. 选择 `Git`。
4. 点击确认。

当前项目已经有 `.git`，所以不需要重新初始化。

## 3. 配置 GitHub 远程仓库

在 PyCharm 中操作：

1. 打开菜单 `Git`。
2. 选择 `Manage Remotes...` 或 `Remotes...`。
3. 点击 `+` 添加远程仓库。
4. Name 填：

```text
origin
```

5. URL 填：

```text
https://github.com/bao-an123456/math_modeling.git
```

6. 点击 `OK`。

如果提示 `origin already exists`，说明远程仓库已经存在，不要重复添加。可以选中原来的 `origin`，点击编辑，把 URL 改成正确地址。

命令行等价操作是：

```powershell
git remote add origin https://github.com/bao-an123456/math_modeling.git
```

如果 `origin` 已经存在，改用：

```powershell
git remote set-url origin https://github.com/bao-an123456/math_modeling.git
```

## 4. 检查要提交的文件

PyCharm 左侧或底部打开 `Commit` 工具窗口。

你会看到文件分组，例如：

- Changes
- Unversioned Files
- Ignored Files

建议本次提交选择：

```text
.gitignore
code/solve_problem1.py
output/problem1_model_notes.md
output/git_pycharm_push_guide.md
```

不要提交这些内容：

```text
.idea/
__pycache__/
data/
results/
output/*.csv
output/*.xlsx
code/traffic_bar_chart.pdf
```

如果 `.gitignore` 生效，这些文件通常会出现在 Ignored Files 里，或者不再出现在待提交列表中。

## 5. 在 PyCharm 中提交 Commit

操作步骤：

1. 打开 `Commit` 工具窗口。
2. 勾选要提交的文件。
3. 填写提交说明，例如：

```text
Add problem 1 solution notes and git guide
```

4. 点击 `Commit`。

如果你想提交后立刻推送，也可以点 `Commit and Push...`。

建议初学时先点 `Commit`，确认本地提交成功后，再单独执行 Push，这样更容易理解流程。

## 6. 在 PyCharm 中推送 Push

提交完成后：

1. 打开菜单 `Git`。
2. 点击 `Push...`。
3. 确认推送方向是：

```text
main -> origin/main
```

4. 点击 `Push`。

如果是第一次推送，PyCharm 可能会要求登录 GitHub。按提示用浏览器登录即可。

GitHub 现在通常不支持账号密码直接推送。如果要求输入密码，需要使用 Personal Access Token，或者使用 PyCharm / Git Credential Manager 的浏览器登录。

命令行等价操作是：

```powershell
git push -u origin main
```

以后已经建立跟踪关系后，可以直接：

```powershell
git push
```

## 7. 推送后在 GitHub 检查

打开仓库页面：

```text
https://github.com/bao-an123456/math_modeling
```

检查是否能看到：

```text
code/solve_problem1.py
output/problem1_model_notes.md
output/git_pycharm_push_guide.md
.gitignore
```

如果 GitHub 页面没有更新，先确认 PyCharm 里是否真的执行了 Push，而不只是 Commit。

## 8. 常见提示和错误

### LF will be replaced by CRLF

这不是错误，只是 Windows 下的换行符提示。通常不影响提交和推送。

### remote origin already exists

说明已经配置过 `origin`。不要再次添加，直接编辑 URL。

命令行修复：

```powershell
git remote set-url origin https://github.com/bao-an123456/math_modeling.git
```

### src refspec main does not match any

常见原因：

- 本地还没有 commit。
- 当前分支不叫 `main`。

先提交，再确认分支名。

```powershell
git branch --show-current
git status
```

### authentication failed

说明 GitHub 登录失败。

解决方法：

- 在 PyCharm 里重新登录 GitHub。
- 或使用浏览器授权。
- 或使用 GitHub Personal Access Token。

### rejected because remote contains work

说明 GitHub 远程仓库里已经有本地没有的提交，比如创建仓库时添加了 `README.md`。

通常先拉取：

```powershell
git pull --rebase origin main
```

解决冲突后再推送：

```powershell
git push
```

## 9. 推荐练习流程

以后每次做完一小部分工作，可以按这个顺序练：

1. 修改代码或笔记。
2. 看 PyCharm 的 `Commit` 窗口。
3. 确认 `.gitignore` 已经隐藏不该提交的文件。
4. 只勾选真正要提交的文件。
5. 写清楚 commit message。
6. 点击 `Commit`。
7. 点击 `Git -> Push...`。
8. 去 GitHub 网页检查结果。

核心理解：

- `Commit` 是提交到本地 Git 仓库。
- `Push` 是把本地提交上传到 GitHub。
- `.gitignore` 是减少误提交，不是代替你判断哪些文件该提交。
