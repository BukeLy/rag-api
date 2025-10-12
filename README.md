# RAG API

基于 RAG-Anything 和 LightRAG 的多模态文档检索增强生成 API。

## ⚡ 快速开始

### 一键部署（3 分钟）

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd rag-api

# 2. 配置环境变量
cp env.example .env
nano .env  # 填入你的 API 密钥

# 3. 启动服务
docker compose up -d

# 4. 验证
curl http://localhost:8000/
```

**访问 API 文档：** http://localhost:8000/docs

---

## 📦 服务器部署（自动化）

在全新的 Linux 服务器上运行：

```bash
chmod +x deploy.sh
./deploy.sh
```

脚本会自动安装 Docker、配置环境、启动服务。

**推荐配置（测试环境）：**
- 实例类型: 计算型 c7（阿里云/腾讯云）
- 配置: 2 核 4GB + 40GB SSD
- 价格: ¥105/月

---

## 🔧 本地开发

```bash
# 安装依赖
uv sync

# 启动服务
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 📝 API 使用

### 上传文档
```bash
curl -X POST "http://localhost:8000/insert?doc_id=doc1" \
  -F "file=@document.pdf"
```

### 查询
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "文档讲了什么？", "mode": "mix"}'
```

## 🛠️ 维护命令

```bash
./scripts/monitor.sh  # 监控服务状态
./scripts/backup.sh   # 备份数据
./scripts/update.sh   # 更新部署

docker compose logs -f              # 查看日志
docker compose restart              # 重启服务
uv run python scripts/test_api.py   # 测试 API
```

## 📂 项目结构

```
rag-api/
├── main.py              # FastAPI 应用
├── src/rag.py           # RAG 实例管理
├── deploy.sh            # 一键部署脚本
├── docker-compose.yml   # Docker 配置
├── scripts/             # 维护脚本（监控/备份/更新）
└── docs/                # 文档
    ├── USAGE.md         # 详细使用文档
    └── IMPROVEMENTS.md  # 技术改进说明
```

## ⚠️ 常见问题

**Q: 服务启动失败？**
```bash
docker compose logs  # 查看错误日志
```

**Q: multimodal_processed 错误？**
```bash
rm -rf ./rag_local_storage  # 清理旧数据
```

**Q: 上传文件返回 400？**
- 支持格式: PDF, DOCX, PNG, JPG
- 最大 100MB

详见 [使用文档](docs/USAGE.md)

---

**技术栈:** FastAPI · RAG-Anything · LightRAG · Docker

© 2025
