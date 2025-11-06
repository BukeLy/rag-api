"""
文档管理路由
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from src.multi_tenant import get_tenant_lightrag
from src.tenant_deps import get_tenant_id
from src.logger import logger
from .models import DocumentStatusResponse, DeletionTaskInfo
from .task_store import (
    create_deletion_task,
    get_deletion_task,
    update_deletion_task,
    delete_task
)
from datetime import datetime

router = APIRouter(prefix="", tags=["Document Management"])


# ============ GET 文档状态 ============

@router.get("/documents/status")
async def get_document_status(
    doc_id: str = Query(..., description="文档 ID"),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    查询文档处理状态

    **多租户支持**:
    - 必填参数: `?tenant_id=your_tenant_id&doc_id=xxx`
    - 自动隔离: 只能查询本租户的文档

    **状态说明**:
    - pending: 排队中
    - processing: 处理中
    - preprocessed: 预处理完成
    - processed: 完全处理完成
    - failed: 失败

    **返回示例**:
    ```json
    {
        "doc_id": "doc-abc123",
        "status": "processed",
        "file_path": "research_paper.pdf",
        "created_at": "2025-11-06T10:00:00",
        "updated_at": "2025-11-06T10:05:00",
        "content_summary": "This paper discusses...",
        "content_length": 5000,
        "chunks_count": 15
    }
    ```
    """
    # 获取租户的 LightRAG 实例
    lightrag_instance = await get_tenant_lightrag(tenant_id)

    # 调用 LightRAG 内部方法（方案 1：原生 API）
    doc_data = await lightrag_instance.doc_status.get_by_id(doc_id)

    if not doc_data:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found in tenant {tenant_id}"
        )

    # 添加 doc_id 字段
    doc_data["doc_id"] = doc_id

    # 计算 chunks 数量
    if "chunks_list" in doc_data:
        doc_data["chunks_count"] = len(doc_data["chunks_list"])

    return DocumentStatusResponse(**doc_data)


# ============ DELETE 删除文档 ============

async def execute_document_deletion(
    task_id: str,
    tenant_id: str,
    doc_id: str
):
    """
    后台异步删除文档
    """
    try:
        # 1. 更新任务状态为 deleting
        update_deletion_task(
            task_id,
            tenant_id,
            status="deleting",
            updated_at=datetime.now().isoformat()
        )

        logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Started deleting document: {doc_id}")

        # 2. 获取租户的 LightRAG 实例
        lightrag_instance = await get_tenant_lightrag(tenant_id)

        # 3. 调用 LightRAG 原生删除方法
        await lightrag_instance.adelete_by_doc_id(doc_id)

        # 4. 删除对应的插入任务记录（如果存在）
        try:
            delete_task(task_id=doc_id, tenant_id=tenant_id)
        except:
            pass  # 任务记录可能不存在，忽略错误

        # 5. 记录审计日志（INFO 级别）
        logger.info(
            f"[Audit] Document deleted: tenant={tenant_id}, doc_id={doc_id}, "
            f"timestamp={datetime.now().isoformat()}"
        )

        # 6. 更新任务状态为 completed
        update_deletion_task(
            task_id,
            tenant_id,
            status="completed",
            updated_at=datetime.now().isoformat()
        )

        logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Document deleted successfully: {doc_id}")

    except Exception as e:
        logger.error(f"[Task {task_id}] [Tenant {tenant_id}] Failed to delete document: {e}", exc_info=True)
        update_deletion_task(
            task_id,
            tenant_id,
            status="failed",
            updated_at=datetime.now().isoformat(),
            error=str(e)
        )


@router.delete("/documents", status_code=202)
async def delete_document(
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id),
    doc_id: str = Query(..., description="文档 ID")
):
    """
    删除指定租户的指定文档（异步）

    **参数**：
    - tenant_id: 租户 ID（必填查询参数）
    - doc_id: 文档 ID（必填查询参数）

    **返回** (202 Accepted)：
    - task_id: 删除任务 ID
    - status_url: 任务状态查询 URL

    **错误**：
    - 400: 文档正在删除中（"the doc is deleting"）

    **示例**：
    ```bash
    DELETE /documents?tenant_id=siraya&doc_id=research_paper_001
    ```
    """

    # 1. 检查是否已有正在进行的删除任务
    existing_task = get_deletion_task(tenant_id, doc_id)
    if existing_task:
        raise HTTPException(status_code=400, detail="the doc is deleting")

    # 2. 创建删除任务
    task_id = create_deletion_task(tenant_id, doc_id)

    # 3. 在后台执行删除
    background_tasks.add_task(
        execute_document_deletion,
        task_id=task_id,
        tenant_id=tenant_id,
        doc_id=doc_id
    )

    # 4. 立即返回任务信息（202 Accepted）
    return {
        "task_id": task_id,
        "message": "Document deletion started",
        "status_url": f"/task/{task_id}",
        "doc_id": doc_id,
        "tenant_id": tenant_id
    }
