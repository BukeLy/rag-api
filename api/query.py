"""
查询路由
"""

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
        # 使用优化参数直接查询
        answer = await rag_instance.aquery(
            request.query,
            mode=request.mode,
            top_k=20,  # 从默认 60 减少到 20（减少 66% 的检索量）
            chunk_top_k=10,  # 从默认 20 减少到 10
            enable_rerank=True,  # 启用 rerank 提升检索相关性（如果配置了 RERANK_MODEL）
            # 如果需要更快的响应，可以进一步减少：
            # top_k=10,
            # chunk_top_k=5,
        )
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Error during query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

