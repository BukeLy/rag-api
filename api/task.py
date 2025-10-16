"""
任务状态查询路由
"""

from fastapi import APIRouter, HTTPException

from src.logger import logger
from .task_store import TASK_STORE

router = APIRouter()


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务处理状态
    
    状态说明：
    - pending: 排队等待处理
    - processing: 正在处理中
    - completed: 处理完成（result 字段包含处理结果）
    - failed: 处理失败（error 字段包含错误信息）
    
    示例响应：
    {
        "task_id": "xxx",
        "status": "completed",
        "doc_id": "doc_001",
        "filename": "test.pdf",
        "created_at": "2025-10-14T20:00:00",
        "updated_at": "2025-10-14T20:02:30",
        "result": {
            "message": "Document processed successfully",
            "doc_id": "doc_001",
            "filename": "test.pdf"
        }
    }
    """
    if task_id not in TASK_STORE:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    task_info = TASK_STORE[task_id]
    return task_info

