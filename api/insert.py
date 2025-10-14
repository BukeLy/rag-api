"""
文档插入路由
"""

import os
import shutil
import uuid
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks

from src.rag import get_rag_instance
from .models import TaskStatus, TaskInfo
from .task_store import TASK_STORE, DOCUMENT_PROCESSING_SEMAPHORE

# 导入 RAG-Anything 异常类型
try:
    from raganything.parser import MineruExecutionError
except ImportError:
    class MineruExecutionError(Exception):
        pass

logger = logging.getLogger(__name__)
router = APIRouter()


async def process_document_task(task_id: str, doc_id: str, temp_file_path: str, original_filename: str):
    """
    后台异步处理文档
    """
    try:
        # 更新任务状态为处理中
        TASK_STORE[task_id].status = TaskStatus.PROCESSING
        TASK_STORE[task_id].updated_at = datetime.now().isoformat()
        logger.info(f"[Task {task_id}] Started processing: {original_filename}")
        
        # 使用信号量限制并发处理（防止多个 MinerU 同时运行导致 OOM）
        async with DOCUMENT_PROCESSING_SEMAPHORE:
            logger.info(f"[Task {task_id}] Acquired processing lock for: {original_filename}")
            
            rag_instance = get_rag_instance()
            if not rag_instance:
                raise Exception("RAG service is not ready")
            
            # 使用 RAG-Anything 处理上传的文件
            await rag_instance.process_document_complete(file_path=temp_file_path, output_dir="./output")
        
        # 处理成功
        TASK_STORE[task_id].status = TaskStatus.COMPLETED
        TASK_STORE[task_id].updated_at = datetime.now().isoformat()
        TASK_STORE[task_id].result = {
            "message": "Document processed successfully",
            "doc_id": doc_id,
            "filename": original_filename
        }
        logger.info(f"[Task {task_id}] Completed successfully: {original_filename}")
        
    except ValueError as e:
        # 验证错误（客户端错误）
        TASK_STORE[task_id].status = TaskStatus.FAILED
        TASK_STORE[task_id].updated_at = datetime.now().isoformat()
        TASK_STORE[task_id].error = f"Validation error: {str(e)}"
        logger.error(f"[Task {task_id}] Validation error: {e}", exc_info=True)
        
    except MineruExecutionError as e:
        # MinerU 解析错误
        error_msg = str(e)
        TASK_STORE[task_id].status = TaskStatus.FAILED
        TASK_STORE[task_id].updated_at = datetime.now().isoformat()
        
        if "Unknown file suffix" in error_msg or "Unsupported" in error_msg:
            TASK_STORE[task_id].error = f"Unsupported file format: {original_filename}"
        else:
            TASK_STORE[task_id].error = f"Document parsing failed: {original_filename}"
        
        logger.error(f"[Task {task_id}] MinerU error: {error_msg}", exc_info=True)
        
    except OSError as e:
        # 文件系统错误
        TASK_STORE[task_id].status = TaskStatus.FAILED
        TASK_STORE[task_id].updated_at = datetime.now().isoformat()
        TASK_STORE[task_id].error = "File system error occurred"
        logger.error(f"[Task {task_id}] File system error: {e}", exc_info=True)
        
    except Exception as e:
        # 其他未预期的错误
        TASK_STORE[task_id].status = TaskStatus.FAILED
        TASK_STORE[task_id].updated_at = datetime.now().isoformat()
        TASK_STORE[task_id].error = f"Internal server error: {str(e)}"
        logger.error(f"[Task {task_id}] Unexpected error: {e}", exc_info=True)
        
    finally:
        # 确保临时文件总是被删除
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"[Task {task_id}] Cleaned up temporary file: {temp_file_path}")
            except OSError as e:
                logger.warning(f"[Task {task_id}] Failed to clean up temporary file: {e}")


@router.post("/insert", status_code=202)
async def insert_document(doc_id: str, file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """
    上传文件并异步处理。立即返回 task_id，客户端可通过 /task/{task_id} 查询处理状态。
    
    返回 202 Accepted 表示任务已接受，正在处理中。
    """
    rag_instance = get_rag_instance()
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG service is not ready.")
    
    # 保留原始文件名（仅用于日志）
    original_filename = file.filename or "unnamed_file"
    
    # 安全地提取文件扩展名
    if original_filename:
        basename = os.path.basename(original_filename)
        file_extension = Path(basename).suffix.lower()
        if file_extension and not file_extension[1:].replace('_', '').replace('-', '').isalnum():
            file_extension = ""
    else:
        file_extension = ""
    
    # 使用 UUID 生成安全的临时文件名
    safe_filename = f"{uuid.uuid4()}{file_extension}"
    temp_file_path = f"/tmp/{safe_filename}"
    
    try:
        # 保存上传的文件到临时位置
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 验证文件大小（空文件检查）
        file_size = os.path.getsize(temp_file_path)
        if file_size == 0:
            # 立即删除空文件
            os.remove(temp_file_path)
            raise HTTPException(status_code=400, detail=f"Empty file: {original_filename}")
        
        # 限制文件大小（例如最大 100MB）
        max_file_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_file_size:
            os.remove(temp_file_path)
            raise HTTPException(
                status_code=400, 
                detail=f"File too large: {original_filename} ({file_size} bytes, max: {max_file_size} bytes)"
            )
        
        # 生成任务 ID
        task_id = str(uuid.uuid4())
        current_time = datetime.now().isoformat()
        
        # 创建任务记录
        task_info = TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            doc_id=doc_id,
            filename=original_filename,
            created_at=current_time,
            updated_at=current_time
        )
        TASK_STORE[task_id] = task_info
        
        # 添加后台任务
        background_tasks.add_task(
            process_document_task,
            task_id=task_id,
            doc_id=doc_id,
            temp_file_path=temp_file_path,
            original_filename=original_filename
        )
        
        logger.info(f"[Task {task_id}] Created task for file: {original_filename} (size: {file_size} bytes, doc_id: {doc_id})")
        
        # 立即返回 202 + task_id
        return {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "message": "Document upload accepted. Processing in background.",
            "doc_id": doc_id,
            "filename": original_filename
        }
    
    except HTTPException:
        # 直接重新抛出 HTTP 异常
        raise
    
    except Exception as e:
        # 如果创建任务失败，清理临时文件
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass
        logger.error(f"Failed to create processing task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")

