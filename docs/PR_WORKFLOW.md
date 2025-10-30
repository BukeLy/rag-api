# Pull Request 工作流程

## 概述

本项目采用基于 Pull Request 的开发流程，所有新功能和 Bug 修复都通过 PR 合并到 `main` 分支。

## 分支策略

- **`main` 分支**：唯一的主分支，包含最新的稳定代码
- **功能分支**：临时分支，用于开发新功能或修复 Bug
- **PR 合并**：所有代码变更通过 GitHub Pull Request 审查后合并

## 开发流程

### 1. 准备工作

确保本地 `main` 分支是最新的：

```bash
git checkout main
git pull origin main
```

### 2. 创建功能分支

根据开发任务类型，使用合适的分支命名：

```bash
# 新功能
git checkout -b feature/功能描述

# Bug 修复
git checkout -b fix/bug描述

# 文档更新
git checkout -b docs/文档描述

# 性能优化
git checkout -b perf/优化描述

# 重构
git checkout -b refactor/重构描述
```

**分支命名规范：**
- 使用小写字母和连字符
- 使用描述性的名称
- 示例：
  - `feature/add-user-authentication`
  - `fix/memory-leak-in-parser`
  - `docs/update-api-documentation`
  - `perf/optimize-query-performance`

### 3. 开发和提交

在功能分支上进行开发，频繁提交：

```bash
# 查看修改
git status
git diff

# 添加修改
git add .

# 提交（使用规范的 commit message）
git commit -m "feat: 添加用户认证功能"
```

**Commit Message 规范：**

```
<type>: <subject>

[optional body]

[optional footer]
```

**Type 类型：**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构（不改变功能）
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例：**

```bash
# 简单提交
git commit -m "feat: 添加多租户支持"

# 详细提交
git commit -m "fix: 修复批量任务查询 Bug

- 修改 get_batch_status 函数以支持多租户数据结构
- 从单层循环改为双层循环遍历
- 添加详细的代码注释

Closes #123"
```

### 4. 推送到远端

```bash
# 首次推送
git push origin feature/your-feature-name

# 后续推送
git push
```

### 5. 创建 Pull Request

在 GitHub 上创建 PR：

1. 访问 https://github.com/BukeLy/rag-api
2. 点击 "Pull requests" → "New pull request"
3. 选择 `base: main` ← `compare: feature/your-feature-name`
4. 填写 PR 标题和描述
5. 添加相关标签（如 `enhancement`, `bug`, `documentation`）
6. 指定审查者（如果有团队成员）
7. 点击 "Create pull request"

**PR 描述模板：**

```markdown
## 变更说明

简要描述此 PR 的目的和实现方式。

## 变更类型

- [ ] 新功能 (Feature)
- [ ] Bug 修复 (Bug Fix)
- [ ] 文档更新 (Documentation)
- [ ] 性能优化 (Performance)
- [ ] 重构 (Refactoring)
- [ ] 其他 (Other)

## 测试

描述如何测试这些变更：

- [ ] 本地测试通过
- [ ] 添加了单元测试
- [ ] 手动测试步骤：
  1. ...
  2. ...

## 相关 Issue

Closes #issue_number (如果有)

## 截图/日志

（如果适用）粘贴相关截图或日志输出

## 检查清单

- [ ] 代码遵循项目规范
- [ ] 添加了必要的文档
- [ ] 没有引入新的 linter 错误
- [ ] 所有测试通过
- [ ] 更新了 CLAUDE.md（如果架构有变化）
```

### 6. 代码审查

等待代码审查（如果是个人项目可跳过）：

- 响应审查者的评论和建议
- 根据反馈进行修改

```bash
# 在功能分支上继续修改
git add .
git commit -m "fix: 根据审查意见调整代码"
git push
```

### 7. 合并 PR

PR 审查通过后合并到 `main`：

**在 GitHub 上：**
1. 点击 "Merge pull request"
2. 选择合并方式：
   - **Merge commit**：保留完整的提交历史（推荐）
   - **Squash and merge**：将多个提交合并为一个（适合小功能）
   - **Rebase and merge**：线性历史（适合简单变更）
3. 点击 "Confirm merge"
4. 删除远端功能分支（GitHub 会提示）

**在本地：**

```bash
# 切换回 main 分支
git checkout main

# 拉取最新代码
git pull origin main

# 删除本地功能分支
git branch -d feature/your-feature-name
```

### 8. 部署到测试服务器

合并后部署到测试服务器：

```bash
# 快速部署
ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205 "cd ~/rag-api && git pull origin main"

# 或完整部署（如果修改了依赖或配置）
ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205
cd ~/rag-api
git pull origin main
docker compose -f docker-compose.dev.yml restart
```

## 常见场景

### 场景 1：功能分支过期

如果在开发过程中 `main` 分支有新的提交：

```bash
# 在功能分支上
git checkout feature/your-feature-name

# 拉取最新的 main 分支
git fetch origin main

# 变基到最新的 main
git rebase origin/main

# 如果有冲突，解决后：
git add .
git rebase --continue

# 强制推送（因为改写了历史）
git push --force-with-lease
```

### 场景 2：修改最后一次提交

```bash
# 修改文件
git add .

# 修正最后一次提交
git commit --amend

# 强制推送
git push --force-with-lease
```

### 场景 3：合并多个提交

```bash
# 交互式变基（合并最近 3 个提交）
git rebase -i HEAD~3

# 在编辑器中，将后续提交从 pick 改为 squash
# 保存并退出

# 强制推送
git push --force-with-lease
```

### 场景 4：撤销提交

```bash
# 撤销最后一次提交（保留修改）
git reset --soft HEAD~1

# 撤销最后一次提交（丢弃修改）
git reset --hard HEAD~1

# 强制推送
git push --force-with-lease
```

### 场景 5：同步远端删除的分支

```bash
# 清理本地已删除的远端分支引用
git fetch --prune

# 查看所有分支（包括远端）
git branch -a
```

## 最佳实践

### 1. 保持功能分支专注

- 一个分支只做一件事
- 避免在功能分支上混合多个不相关的改动

### 2. 频繁提交

- 小步提交，每个提交都是一个逻辑单元
- 便于回滚和查找问题

### 3. 及时同步

- 定期从 `main` 分支同步最新代码
- 减少合并冲突

### 4. 写清晰的 PR 描述

- 说明"为什么"而不只是"做了什么"
- 提供测试步骤和相关上下文

### 5. 自我审查

- 提交 PR 前自己先审查一遍代码
- 确保没有调试代码、日志输出等

### 6. 及时清理

- PR 合并后立即删除功能分支
- 保持分支列表整洁

### 7. 使用 Draft PR

- 开发中的 PR 可以标记为 Draft
- 完成后再转为 Ready for review

## Git 命令速查

```bash
# 查看状态
git status

# 查看分支
git branch -a

# 创建并切换分支
git checkout -b feature/name

# 切换分支
git checkout branch-name

# 拉取最新代码
git pull origin main

# 添加修改
git add .
git add file.txt

# 提交
git commit -m "message"

# 推送
git push origin branch-name

# 删除本地分支
git branch -d branch-name

# 删除远端分支
git push origin --delete branch-name

# 查看提交历史
git log --oneline -10

# 查看远端仓库
git remote -v

# 同步远端分支列表
git fetch --prune
```

## 故障排查

### 问题 1：推送被拒绝

```bash
# 错误：Updates were rejected because the remote contains work...
# 解决：先拉取远端代码
git pull --rebase origin feature/name
git push
```

### 问题 2：合并冲突

```bash
# 1. 查看冲突文件
git status

# 2. 手动解决冲突（编辑文件）

# 3. 标记为已解决
git add conflicted-file.txt

# 4. 继续变基/合并
git rebase --continue
# 或
git merge --continue
```

### 问题 3：误提交到 main

```bash
# 1. 创建功能分支保存当前工作
git branch feature/save-work

# 2. 重置 main 到远端状态
git checkout main
git reset --hard origin/main

# 3. 切换到功能分支继续工作
git checkout feature/save-work
```

### 问题 4：忘记基于最新 main 创建分支

```bash
# 在功能分支上变基到最新 main
git fetch origin main
git rebase origin/main
```

## 相关文档

- [部署模式说明](./DEPLOY_MODES.md)
- [架构文档](./ARCHITECTURE.md)
- [使用指南](./USAGE.md)

## 更新历史

- **v1.0** (2025-10-30)
  - 初始版本
  - 从 dev 分支策略迁移到 PR 工作流程

