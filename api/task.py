"""
任务状态查询路由（支持多租户隔离 + Lazy Evaluation）
"""

from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Depends, Query

from src.logger import logger
from src.tenant_deps import get_tenant_id
from .task_store import get_task, update_task, get_tenant_tasks
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


@router.get("/tasks")
async def list_tasks(
    tenant_id: str = Depends(get_tenant_id),
    status: Optional[Literal["pending", "processing", "completed", "failed"]] = None,
    page: int = Query(1, ge=1, le=10000, description="页码（从 1 开始）"),
    page_size: int = Query(50, ge=1, le=100, description="每页数量（最多 100）"),
    sort_by: Literal["created_at", "updated_at", "status"] = Query("created_at"),
    sort_order: Literal["asc", "desc"] = Query("desc")
):
    """
    获取租户的任务列表（支持分页、过滤、排序）

    **功能**：
    - ✅ 分页：page, page_size
    - ✅ 过滤：status (pending/processing/completed/failed)
    - ✅ 排序：sort_by (created_at/updated_at/status), sort_order (asc/desc)

    **注意**：
    - 当前在内存中分页，如果任务量 >10000，性能会下降
    - 建议未来在存储层实现分页

    **示例请求**：
    - GET /tasks?tenant_id=tenant_a&page=1&page_size=20
    - GET /tasks?tenant_id=tenant_a&status=completed&sort_by=updated_at&sort_order=desc

    **示例响应**：
    ```json
    {
        "tasks": [
            {
                "task_id": "xxx",
                "tenant_id": "tenant_a",
                "status": "completed",
                "doc_id": "doc_001",
                "filename": "test.pdf",
                "created_at": "2025-10-14T20:00:00",
                "updated_at": "2025-10-14T20:02:30"
            }
        ],
        "pagination": {
            "total": 100,
            "page": 1,
            "page_size": 20,
            "total_pages": 5,
            "has_next": true,
            "has_prev": false
        }
    }
    ```
    """
    try:
        # 获取所有任务
        tasks_dict = get_tenant_tasks(tenant_id)

        # 如果没有任务，返回空列表
        if not tasks_dict:
            return {
                "tasks": [],
                "pagination": {
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False
                }
            }

        tasks_list = list(tasks_dict.values())

        # 过滤状态
        if status:
            tasks_list = [t for t in tasks_list if t.status.value == status]

        # 排序
        reverse = (sort_order == "desc")
        tasks_list.sort(
            key=lambda t: getattr(t, sort_by, 0) or 0,
            reverse=reverse
        )

        # 分页
        total = len(tasks_list)
        start = (page - 1) * page_size
        end = start + page_size
        tasks_page = tasks_list[start:end]

        # 转换为 dict（确保可序列化）
        tasks_data = []
        for t in tasks_page:
            if hasattr(t, 'dict'):
                tasks_data.append(t.dict())
            else:
                # 手动转换为字典
                task_dict = {
                    "task_id": t.task_id,
                    "tenant_id": t.tenant_id,
                    "status": t.status.value,
                    "doc_id": t.doc_id,
                    "filename": t.filename,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at
                }
                if hasattr(t, 'result') and t.result:
                    task_dict["result"] = t.result
                if hasattr(t, 'error') and t.error:
                    task_dict["error"] = t.error
                tasks_data.append(task_dict)

        return {
            "tasks": tasks_data,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": end < total,
                "has_prev": page > 1
            }
        }

    except Exception as e:
        logger.error(f"Failed to list tasks for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve tasks"
        )
