# 📸 截图添加指南

本文档说明如何为 README.md 添加截图，使其更加生动美观。

## 推荐截图内容

### 1. Swagger API 文档截图
位置：访问 http://localhost:8000/docs

建议截图：
- API 接口列表全景
- 单个接口的详细说明
- Try it out 功能演示

文件名：`docs/images/swagger-ui.png`

### 2. 查询结果示例
展示一次完整的查询过程和结果

文件名：`docs/images/query-example.png`

### 3. 文档上传界面
展示文档上传的过程

文件名：`docs/images/upload-demo.png`

### 4. 任务状态追踪
展示异步任务的状态变化

文件名：`docs/images/task-status.png`

### 5. 租户管理界面
展示租户统计和管理功能

文件名：`docs/images/tenant-management.png`

### 6. 性能监控
展示系统性能指标

文件名：`docs/images/performance-metrics.png`

## 截图制作步骤

### 步骤 1: 创建图片目录

```bash
mkdir -p docs/images
```

### 步骤 2: 启动服务并访问

```bash
# 启动服务
docker compose up -d

# 访问 API 文档
open http://localhost:8000/docs
```

### 步骤 3: 截图并保存

使用截图工具（macOS: Cmd+Shift+4, Windows: Win+Shift+S）

保存到 `docs/images/` 目录。

### 步骤 4: 在 README.md 中引用

在 README.md 对应位置添加：

```markdown
## 📸 界面预览

### Swagger API 文档

<div align="center">
  <img src="docs/images/swagger-ui.png" alt="Swagger UI" width="800">
  <p><i>完整的 RESTful API 文档</i></p>
</div>

### 查询示例

<div align="center">
  <img src="docs/images/query-example.png" alt="Query Example" width="800">
  <p><i>智能问答演示</i></p>
</div>

### 文档上传

<div align="center">
  <img src="docs/images/upload-demo.png" alt="Upload Demo" width="800">
  <p><i>多文件批量上传</i></p>
</div>
```

## 推荐添加位置

在 README.md 中建议在以下位置添加截图：

### 位置 1: 项目简介后
```markdown
## 📖 项目简介
...

## 📸 界面预览

<div align="center">
  <img src="docs/images/hero-banner.png" alt="RAG API" width="800">
</div>
```

### 位置 2: 快速开始前
```markdown
## 📸 系统界面

### Swagger API 文档
...

## 🚀 快速开始
```

### 位置 3: API 文档章节
```markdown
## 📚 API 文档

### 界面展示

<div align="center">
  <img src="docs/images/swagger-ui.png" alt="Swagger UI" width="800">
</div>

### 核心接口
```

## 图片优化建议

### 1. 尺寸优化
```bash
# 使用 ImageMagick 压缩图片
convert input.png -resize 1600x -quality 85 output.png

# 或使用在线工具
# https://tinypng.com/
# https://compressor.io/
```

### 2. 推荐尺寸
- 宽度：1200-1600px
- 格式：PNG（界面截图）或 JPG（照片）
- 文件大小：< 500KB

### 3. 添加水印（可选）
```bash
# 使用 ImageMagick 添加水印
convert input.png -pointsize 36 -fill white -gravity southeast \
  -annotate +10+10 'RAG API' output.png
```

## 替代方案：使用 GIF 动图

对于需要展示操作流程的场景，推荐使用 GIF 动图：

### 制作工具
- macOS: **Kap** (https://getkap.co/)
- Windows: **ScreenToGif** (https://www.screentogif.com/)
- Linux: **Peek** (https://github.com/phw/peek)

### 推荐 GIF 内容
1. 完整的文档上传-查询流程
2. 批量上传多个文件
3. 实时查看任务状态变化
4. 多租户切换演示

### GIF 优化
```bash
# 使用 gifsicle 优化 GIF
gifsicle -O3 --colors 256 input.gif -o output.gif
```

## 在线图表工具

除了截图，还可以使用在线工具生成图表：

### 架构图
- **Excalidraw**: https://excalidraw.com/
- **draw.io**: https://app.diagrams.net/
- **Whimsical**: https://whimsical.com/

### Logo 设计
- **Canva**: https://www.canva.com/
- **Figma**: https://www.figma.com/
- **Looka**: https://looka.com/

### 图标资源
- **Iconify**: https://iconify.design/
- **Font Awesome**: https://fontawesome.com/
- **Feather Icons**: https://feathericons.com/

## 添加 Banner

可以创建一个精美的 Banner 放在 README 顶部：

```markdown
<div align="center">
  <img src="docs/images/banner.png" alt="RAG API Banner" width="100%">
  
  <h1>🚀 RAG API</h1>
  <p>多租户多模态文档智能检索系统</p>
</div>
```

### Banner 设计建议
- 尺寸：1200x400px
- 包含：项目名称、Slogan、主要特性图标
- 风格：简洁、专业、现代化
- 颜色：与项目主题一致

## 示例代码截图

对于代码示例，可以使用 Carbon 生成美观的代码截图：

**Carbon**: https://carbon.now.sh/

配置建议：
- Theme: Night Owl
- Font: Fira Code
- Window Style: Sharp
- Padding: 32px

## README 完整示例

将以下内容添加到 README.md 的合适位置：

```markdown
---

## 📸 系统界面

<div align="center">

### Swagger API 文档

<img src="docs/images/swagger-ui.png" alt="Swagger UI" width="800">

*功能完整的 RESTful API 交互式文档*

---

### 智能问答演示

<img src="docs/images/query-example.png" alt="Query Example" width="800">

*基于知识图谱的混合检索，准确理解用户意图*

---

### 批量文档上传

<img src="docs/images/batch-upload.gif" alt="Batch Upload" width="800">

*一次最多上传 100 个文件，异步处理，实时追踪*

---

### 租户管理面板

<img src="docs/images/tenant-management.png" alt="Tenant Management" width="800">

*完整的多租户隔离，数据安全有保障*

</div>

---
```

## 提交图片到 Git

```bash
# 添加图片目录
git add docs/images/

# 提交
git commit -m "docs: 添加系统界面截图"

# 推送
git push origin main
```

## 注意事项

1. ⚠️ **文件大小**：单个图片不要超过 1MB
2. ⚠️ **命名规范**：使用小写字母和连字符，如 `swagger-ui.png`
3. ⚠️ **版权**：确保图片没有版权问题
4. ⚠️ **敏感信息**：截图中不要包含 API 密钥等敏感信息
5. ⚠️ **分辨率**：使用高清截图（2x Retina 显示器截图最佳）

## 快速生成模板截图

可以使用以下脚本批量生成占位图：

```bash
#!/bin/bash
# 生成占位图

mkdir -p docs/images

# 使用 ImageMagick 生成占位图
convert -size 1600x900 xc:gray -pointsize 72 -fill white \
  -gravity center -annotate +0+0 'Swagger UI\nScreenshot Here' \
  docs/images/swagger-ui.png

convert -size 1600x900 xc:gray -pointsize 72 -fill white \
  -gravity center -annotate +0+0 'Query Example\nScreenshot Here' \
  docs/images/query-example.png

echo "✅ 占位图已生成到 docs/images/"
echo "请替换为实际的截图"
```

---

**准备好截图后，运行：**

```bash
git add docs/images/
git commit -m "docs: 添加系统界面截图"
git push origin main
```

这样 README.md 就会显示你的截图了！✨

