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
    title="RAG API",
    description="多模态 RAG 系统 API - 支持文档处理和智能查询",
    version="1.0.0",
    lifespan=lifespan
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
