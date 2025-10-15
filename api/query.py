"""
查询路由
"""

import os
import logging
from fastapi import APIRouter, HTTPException
from typing import Optional

from src.rag import get_rag_instance
from .models import QueryRequest

# 导入 LightRAG 查询参数
try:
    from lightrag import QueryParam
except ImportError:
    # 如果导入失败，创建一个简单的替代类
    class QueryParam:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

logger = logging.getLogger(__name__)
router = APIRouter()

# 从环境变量读取查询优化参数
DEFAULT_TOP_K = int(os.getenv("TOP_K", "20"))
DEFAULT_CHUNK_TOP_K = int(os.getenv("CHUNK_TOP_K", "10"))


@router.post("/query")
async def query_rag(request: QueryRequest):
    """
    查询 RAG 系统
    
    **查询模式**：
    - `local`: 局部知识图谱（快速，适合精确查询）
    - `global`: 全局知识图谱（完整，但较慢）
    - `naive`: 向量检索（**最快**，推荐日常使用）
    - `hybrid`: 混合模式
    - `mix`: 全功能混合（慢，但结果最全面）
    
    **性能优化配置**：
    - 减少了 `top_k` 从 60 → 20（减少检索量）
    - 减少了 `chunk_top_k` 从 20 → 10
    - **启用了 `enable_rerank`**（需配置 `RERANK_MODEL` 环境变量）
    - Rerank 会提升检索相关性，但会增加约 2-3 秒响应时间
    """
    rag_instance = get_rag_instance()
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG service is not ready.")
    
    try:
        # 使用优化参数直接查询（从环境变量读取，可在 .env 中调整）
        answer = await rag_instance.aquery(
            request.query,
            mode=request.mode,
            top_k=DEFAULT_TOP_K,  # 从环境变量 TOP_K 读取（默认 20）
            chunk_top_k=DEFAULT_CHUNK_TOP_K,  # 从环境变量 CHUNK_TOP_K 读取（默认 10）
            enable_rerank=True,  # 启用 rerank 提升检索相关性（如果配置了 RERANK_MODEL）
        )
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Error during query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

