"""
查询路由
"""

import logging
from fastapi import APIRouter, HTTPException

from src.rag import get_rag_instance
from .models import QueryRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query")
async def query_rag(request: QueryRequest):
    """
    查询 RAG 系统
    
    支持的模式：
    - local: 仅本地搜索
    - global: 仅全局搜索
    - hybrid: 混合搜索
    - mix: 混合模式（默认）
    """
    rag_instance = get_rag_instance()
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG service is not ready.")
    
    try:
        answer = await rag_instance.aquery(request.query, mode=request.mode)
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Error during query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

