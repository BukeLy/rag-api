"""
任务状态查询路由（支持多租户隔离 + Lazy Evaluation）
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends

from src.logger import logger
from src.tenant_deps import get_tenant_id
from .task_store import get_task, update_task
from .models import TaskStatus, TaskInfo

router = APIRouter()


@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    tenant_id: str = Depends(get_tenant_id)
):
    """
    查询任务处理状态（支持多租户隔离 + Lazy Evaluation）

    **多租户支持**：
    - 🔒 **租户隔离**：只能查询本租户的任务
    - 🎯 **必填参数**：`?tenant_id=your_tenant_id`

    **Lazy Evaluation**：
    - 如果任务状态为 PROCESSING，实时查询 LightRAG 状态
    - 如果 LightRAG 已完成，更新任务为 COMPLETED 并缓存
    - 如果 LightRAG 已失败，更新任务为 FAILED 并缓存
    - 如果 LightRAG 仍在处理，保持 PROCESSING（不缓存）

    状态说明：
    - pending: 排队等待处理
    - processing: 正在处理中（包括文档解析和 LightRAG 后台处理）
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
            "filename": "test.pdf",
            "chunks_count": 42
        }
    }
    """
    task_info = get_task(task_id, tenant_id)

    if not task_info:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found for tenant {tenant_id}"
        )

    # Lazy evaluation: only query LightRAG for PROCESSING tasks
    if task_info.status == TaskStatus.PROCESSING:
        task_info = await sync_task_with_lightrag(task_info, tenant_id)

    return task_info


async def sync_task_with_lightrag(task: TaskInfo, tenant_id: str) -> TaskInfo:
    """
    Sync task status with LightRAG doc_status (lazy evaluation)

    Only called when task.status == PROCESSING

    Query LightRAG to check if document processing is complete:
    - If doc_status == "processed" → update task to COMPLETED and cache
    - If doc_status == "failed" → update task to FAILED and cache
    - If doc_status == "processing" → keep task as PROCESSING (don't cache)

    Args:
        task: Task object with status == PROCESSING
        tenant_id: Tenant ID

    Returns:
        Updated task object (may still be PROCESSING if LightRAG hasn't finished)
    """
    try:
        # Get LightRAG instance for this tenant
        from src.multi_tenant import get_tenant_lightrag
        lightrag = await get_tenant_lightrag(tenant_id)

        if not lightrag:
            logger.warning(
                f"[Task {task.task_id}] [Tenant {tenant_id}] "
                f"LightRAG instance not available, cannot sync status"
            )
            return task

        # Query LightRAG doc_status for this document
        doc_data = await lightrag.doc_status.get_by_id(task.doc_id)

        if not doc_data:
            # Document not found in LightRAG (shouldn't happen after successful submission)
            logger.warning(
                f"[Task {task.task_id}] [Tenant {tenant_id}] "
                f"Document '{task.doc_id}' not found in LightRAG doc_status"
            )
            return task

        doc_status = doc_data.get("status")

        if doc_status == "processed":
            # ✅ LightRAG processing completed → update task to COMPLETED
            chunks_count = doc_data.get("chunks_count", 0)
            created_at = doc_data.get("created_at")

            logger.info(
                f"[Task {task.task_id}] [Tenant {tenant_id}] "
                f"LightRAG processing completed (doc_id={task.doc_id}, chunks={chunks_count})"
            )

            update_task(
                task.task_id, tenant_id,
                status=TaskStatus.COMPLETED,
                updated_at=datetime.now().isoformat(),
                result={
                    "message": "Document processed successfully",
                    "doc_id": task.doc_id,
                    "filename": task.filename,
                    "chunks_count": chunks_count,
                    "created_at": created_at
                }
            )

            # Update local task object
            task.status = TaskStatus.COMPLETED
            task.updated_at = datetime.now().isoformat()
            task.result = {
                "message": "Document processed successfully",
                "doc_id": task.doc_id,
                "filename": task.filename,
                "chunks_count": chunks_count,
                "created_at": created_at
            }

        elif doc_status == "failed":
            # ❌ LightRAG processing failed → update task to FAILED
            error_msg = doc_data.get("error_msg", "Unknown error")

            logger.warning(
                f"[Task {task.task_id}] [Tenant {tenant_id}] "
                f"LightRAG processing failed (doc_id={task.doc_id}, error={error_msg})"
            )

            update_task(
                task.task_id, tenant_id,
                status=TaskStatus.FAILED,
                updated_at=datetime.now().isoformat(),
                error=f"LightRAG processing failed: {error_msg}"
            )

            # Update local task object
            task.status = TaskStatus.FAILED
            task.updated_at = datetime.now().isoformat()
            task.error = f"LightRAG processing failed: {error_msg}"

        else:
            # 🔄 Still processing (pending/processing/preprocessed)
            logger.debug(
                f"[Task {task.task_id}] [Tenant {tenant_id}] "
                f"LightRAG still processing (doc_id={task.doc_id}, doc_status={doc_status})"
            )
            # Keep task as PROCESSING, don't update cache

    except Exception as e:
        # Query failed, don't update task status
        logger.error(
            f"[Task {task.task_id}] [Tenant {tenant_id}] "
            f"Failed to sync with LightRAG: {e}",
            exc_info=True
        )

    return task
