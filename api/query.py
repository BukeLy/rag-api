"""
查询路由（直接访问 LightRAG 知识图谱）
"""

import os
import logging
from fastapi import APIRouter, HTTPException
from typing import Optional

from src.rag import get_lightrag_instance
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
    查询 RAG 系统（直接访问 LightRAG 知识图谱，绕过解析器）
    
    **架构优势**：
    - ⚡ **直接访问 LightRAG**：绕过解析器，性能提升
    - 🎯 **适合 95% 文本查询**：大多数查询不需要多模态能力
    - 💾 **资源占用更低**：无 MinerU/Docling 解析器开销
    - ⚠️ **解决并发冲突**：读写分离，查询不受文档插入影响
    
    **查询模式**：
    - `naive`: 向量检索（**最快**，推荐日常使用，15-20秒）
    - `local`: 局部知识图谱（适合精确查询）
    - `global`: 全局知识图谱（完整，但较慢）
    - `hybrid`: 混合模式
    - `mix`: 全功能混合（慢，但结果最全面）
    
    **性能优化**：
    - `top_k=20`（从默认 60 减少）
    - `chunk_top_k=10`（从默认 20 减少）
    - `max_async=8`（从 4 提升，优化实体合并）
    - `enable_rerank=True`（提升相关性，增加 2-3秒）
    """
    lightrag = get_lightrag_instance()
    if not lightrag:
        raise HTTPException(status_code=503, detail="LightRAG is not ready.")
    
    try:
        # 直接使用 LightRAG 查询（绕过 RAGAnything 解析器）
        from lightrag import QueryParam
        
        query_param = QueryParam(
            mode=request.mode,
            top_k=DEFAULT_TOP_K,  # 从环境变量 TOP_K 读取（默认 20）
            chunk_top_k=DEFAULT_CHUNK_TOP_K,  # 从环境变量 CHUNK_TOP_K 读取（默认 10）
            enable_rerank=True,  # 启用 rerank 提升检索相关性（如果配置了 RERANK_MODEL）
        )
        
        answer = await lightrag.aquery(
            request.query,
            param=query_param
        )
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Error during query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

