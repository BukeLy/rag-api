"""
RAG API - 主应用入口

这是一个基于 FastAPI 的 RAG (检索增强生成) API 服务。
支持多模态文档处理（PDF、DOCX、图片等）和异步任务处理。
"""

from fastapi import FastAPI

# 导入统一日志系统
from src.logger import logger

# 导入 RAG 相关模块
from src.rag import lifespan

# 导入 API 路由
from api import api_router

# --- FastAPI 应用 ---

app = FastAPI(
    title="RAG API - 多租户多模态知识图谱系统",
    description="""
    ## 🚀 多租户多模态 RAG 系统 API

    基于 **LightRAG** 和 **RAG-Anything** 构建的企业级检索增强生成系统。

    ### ✨ 核心特性

    - **🔒 多租户隔离**: 每个租户拥有独立的知识图谱空间，数据完全隔离
    - **🎨 多模态支持**: 处理 PDF、DOCX、图片等多种文档格式
    - **⚡ 高性能查询**: 优化后的查询性能，首次查询 ~15秒，后续查询 6-11秒
    - **📊 知识图谱**: 自动构建实体关系图谱，支持 5 种查询模式
    - **🔄 异步处理**: 后台任务处理，支持批量文档上传
    - **💾 外部存储**: 支持 Redis、PostgreSQL、Neo4j 外部存储

    ### 📋 快速开始

    1. **上传文档**: 使用 `/insert` 端点上传文档（需提供 `tenant_id`）
    2. **查询知识**: 使用 `/query` 端点查询知识图谱
    3. **查看任务**: 使用 `/task/{task_id}` 查看处理状态

    ### 🏗️ 架构说明

    - **实例池管理**: LRU 缓存，最多 50 个租户实例
    - **共享资源**: LLM/Embedding 函数在租户间共享
    - **解析器选择**: 自动选择最佳解析器（MinerU/Docling）
    - **直接查询**: 查询直接访问 LightRAG，绕过解析器开销

    ### 📞 联系方式

    - GitHub: [rag-api](https://github.com/your-org/rag-api)
    - 文档: 查看项目 `docs/` 目录
    """,
    version="1.0.0",
    lifespan=lifespan,
    contact={
        "name": "RAG API Team",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=[
        {
            "name": "Health Check",
            "description": "系统健康检查端点"
        },
        {
            "name": "Document Processing",
            "description": "文档上传和处理接口（支持多租户隔离）"
        },
        {
            "name": "Query",
            "description": "知识图谱查询接口（支持多种查询模式）"
        },
        {
            "name": "Task Management",
            "description": "异步任务状态查询"
        },
        {
            "name": "Tenant Management",
            "description": "租户管理和统计信息"
        },
        {
            "name": "File Service",
            "description": "临时文件下载服务（用于远程 MinerU）"
        },
        {
            "name": "Performance Monitoring",
            "description": "系统性能监控和指标收集"
        }
    ]
)

# 注册 API 路由
app.include_router(api_router)

# 健康检查端点
@app.get("/", tags=["Health Check"])
def health_check():
    """
    健康检查接口
    
    返回 API 运行状态
    """
    return {
        "status": "running",
        "service": "RAG API",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
