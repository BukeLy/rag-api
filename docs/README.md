# 📚 文档导航

本目录包含 RAG API 项目的所有文档。

## 📖 公开文档（GitHub）

以下文档会同步到 GitHub，对所有用户可见：

### 核心文档

| 文档 | 描述 | 适用人群 |
|------|------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构设计文档 | 开发者、架构师 |
| [USAGE.md](USAGE.md) | 完整的 API 使用指南 | 所有用户 |
| [DEPLOY_MODES.md](DEPLOY_MODES.md) | 部署模式说明（生产/开发） | 运维人员、开发者 |
| [DEPLOYMENT_EXTERNAL_STORAGE.md](DEPLOYMENT_EXTERNAL_STORAGE.md) | 外部存储配置指南 | 运维人员 |

### 开发文档

| 文档 | 描述 | 适用人群 |
|------|------|---------|
| [PR_WORKFLOW.md](PR_WORKFLOW.md) | Pull Request 工作流程 | 贡献者、开发者 |

---

## 🔒 内部文档（仅本地）

以下文档包含内部实现细节、优化策略和测试数据，**不会**推送到 GitHub：

### 技术实现文档

| 文档 | 描述 | 用途 |
|------|------|------|
| `LIGHTRAG_IMPLEMENTATION_GUIDE.md` | LightRAG 详细实现指南 | 内部开发参考 |
| `MINERU_REMOTE_API.md` | MinerU 远程 API 文档 | 内部集成文档 |
| `OPTIMIZATION_GUIDE.md` | 性能优化指南 | 内部优化参考 |
| [deepseek-ocr-complete.md](deepseek-ocr-complete.md) | DeepSeek-OCR 完整研究报告 | DS-OCR 集成测试和评估 |
| [smart-parser-selection-v2.md](smart-parser-selection-v2.md) | 智能 Parser 选择方案 v2.0 | DS-OCR + MinerU + Docling 智能选择 |
| [parser-selection-upgrade-v1-to-v2.md](parser-selection-upgrade-v1-to-v2.md) | Parser 选择方案升级报告 | v1.0 → v2.0 升级详情 |

### 迁移文档

| 文档 | 描述 | 用途 |
|------|------|------|
| `PRODUCTION_MIGRATION_GUIDE.md` | 生产环境迁移详细指南 | 内部运维文档 |
| `PRODUCTION_MIGRATION_QUICKSTART.md` | 快速迁移指南 | 内部运维文档 |

### 测试报告

位于 `../performance_reports/` 目录：

- `performance_analysis_20251023.md` - 性能分析报告
- `upgrade_comparison_20251023.md` - 升级对比测试
- `local_mode_performance_analysis.md` - 本地模式性能分析
- `perf_report_*.txt` - 性能测试原始数据

**说明**：这些报告包含测试过程中的失败案例、性能问题分析等内部信息，仅供团队内部参考。

---

## 📝 文档维护

### 添加新文档

#### 公开文档
1. 在 `docs/` 目录创建新文档
2. 确保内容适合公开展示
3. 更新本 README.md 的文档列表
4. 提交到 Git 并推送

```bash
git add docs/your-new-doc.md docs/README.md
git commit -m "docs: 添加新文档"
git push origin main
```

#### 内部文档
1. 在 `docs/` 目录创建新文档
2. 将文件名添加到 `.gitignore`
3. **不要**提交到 Git

```bash
# 编辑 .gitignore，添加：
# docs/YOUR_INTERNAL_DOC.md

# 确认不会被追踪
git status  # 不应该看到该文件
```

### 将公开文档改为内部文档

```bash
# 1. 从 Git 中移除（保留本地文件）
git rm --cached docs/YOUR_DOC.md

# 2. 添加到 .gitignore
echo "docs/YOUR_DOC.md" >> .gitignore

# 3. 提交更改
git add .gitignore
git commit -m "chore: 将 YOUR_DOC.md 改为内部文档"
git push origin main
```

### 将内部文档改为公开文档

```bash
# 1. 从 .gitignore 中移除该行

# 2. 添加到 Git
git add docs/YOUR_DOC.md
git commit -m "docs: 公开 YOUR_DOC.md"
git push origin main
```

---

## 🔍 快速查找

### 我想了解...

**如何使用 API？**
→ 查看 [USAGE.md](USAGE.md)

**系统是如何设计的？**
→ 查看 [ARCHITECTURE.md](ARCHITECTURE.md)

**如何部署服务？**
→ 查看 [DEPLOY_MODES.md](DEPLOY_MODES.md) 和 [DEPLOYMENT_EXTERNAL_STORAGE.md](DEPLOYMENT_EXTERNAL_STORAGE.md)

**如何贡献代码？**
→ 查看 [PR_WORKFLOW.md](PR_WORKFLOW.md)

**性能优化建议？**（内部）
→ 查看 `OPTIMIZATION_GUIDE.md`

**LightRAG 实现细节？**（内部）
→ 查看 `LIGHTRAG_IMPLEMENTATION_GUIDE.md`

**生产环境迁移？**（内部）
→ 查看 `PRODUCTION_MIGRATION_GUIDE.md`

---

## 📊 文档统计

### 公开文档
- 总计：**5 个文档**
- 总字数：约 **18,000 字**
- 主要语言：中文

### 内部文档
- 总计：**5 个技术文档 + 测试报告**
- 总字数：约 **60,000 字**
- 主要语言：中文

---

## 🤝 贡献文档

欢迎改进文档！

### 文档质量标准

公开文档应该：
- ✅ 清晰易懂，面向目标用户
- ✅ 包含实用的代码示例
- ✅ 保持更新，与代码同步
- ✅ 使用正确的 Markdown 格式
- ✅ 添加必要的图片和图表
- ✅ 不包含敏感信息（API 密钥、内部策略等）

### 文档风格指南

1. **标题层次**：使用正确的 Markdown 标题层级（#, ##, ###）
2. **代码块**：使用语法高亮（```bash, ```python 等）
3. **表格**：用于对比和列表
4. **列表**：有序列表用于步骤，无序列表用于要点
5. **链接**：使用相对路径引用其他文档
6. **图片**：放在 `docs/images/` 目录

---

## 📧 联系我们

对文档有疑问或建议？

- **GitHub Issues**: [提交问题](https://github.com/BukeLy/rag-api/issues)
- **Email**: buledream233@gmail.com

---

**最后更新**: 2025-10-30

