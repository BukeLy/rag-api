"""
任务状态查询路由（支持多租户隔离）
"""

from fastapi import APIRouter, HTTPException, Depends

from src.logger import logger
from src.tenant_deps import get_tenant_id
from .task_store import get_task

router = APIRouter()


@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    tenant_id: str = Depends(get_tenant_id)
):
    """
    查询任务处理状态（支持多租户隔离）

    **多租户支持**：
    - 🔒 **租户隔离**：只能查询本租户的任务
    - 🎯 **必填参数**：`?tenant_id=your_tenant_id`

    状态说明：
    - pending: 排队等待处理
    - processing: 正在处理中
    - completed: 处理完成（result 字段包含处理结果）
    - failed: 处理失败（error 字段包含错误信息）

    示例响应：
    {
        "task_id": "xxx",
        "tenant_id": "tenant_a",
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
    task_info = get_task(task_id, tenant_id)

    if not task_info:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found for tenant {tenant_id}"
        )

    return task_info

