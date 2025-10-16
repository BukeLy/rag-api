"""
文档插入路由
"""

import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Query
from typing import Optional

from src.logger import logger
from src.rag import get_rag_instance, select_parser_by_file
from .models import TaskStatus, TaskInfo
from .task_store import TASK_STORE, DOCUMENT_PROCESSING_SEMAPHORE

# 导入 RAG-Anything 异常类型
try:
    from raganything.parser import MineruExecutionError
except ImportError:
    class MineruExecutionError(Exception):
        pass

router = APIRouter()


async def process_document_task(task_id: str, doc_id: str, temp_file_path: str, original_filename: str, parser: str = "auto"):
    """
    后台异步处理文档
    
    Args:
        task_id: 任务ID
        doc_id: 文档ID
        temp_file_path: 临时文件路径
        original_filename: 原始文件名
        parser: 解析器类型 ("mineru" / "docling" / "auto")
    """
    try:
        # 更新任务状态为处理中
        TASK_STORE[task_id].status = TaskStatus.PROCESSING
        TASK_STORE[task_id].updated_at = datetime.now().isoformat()
        logger.info(f"[Task {task_id}] Started processing: {original_filename} (parser: {parser})")
        
        # 根据 parser 参数获取对应的 RAG 实例
        rag_instance = get_rag_instance(parser=parser)
        if not rag_instance:
            raise Exception(f"RAG service ({parser}) is not ready")
        
        # 检查是否为纯文本文件，使用轻量级直接插入
        file_ext = Path(original_filename).suffix.lower()
        if file_ext in ['.txt', '.md', '.markdown']:
            logger.info(f"[Task {task_id}] Detected text file, using lightweight direct insertion")
            
            # 直接读取文本内容
            with open(temp_file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            if not text_content or len(text_content.strip()) == 0:
                raise ValueError(f"Empty text file: {original_filename}")
            
            # 直接插入到 LightRAG（轻量级，无需解析）
            await rag_instance.lightrag.ainsert(text_content)
            logger.info(f"[Task {task_id}] Text content inserted directly to LightRAG ({len(text_content)} characters)")
        else:
            # 非文本文件，需要使用解析器
            mineru_mode = os.getenv("MINERU_MODE", "local")
            
            # 根据 MinerU 模式选择处理策略
            # 注意：当前仅支持本地模式，远程模式需要实现文件 URL 上传
            async with DOCUMENT_PROCESSING_SEMAPHORE:
                logger.info(f"[Task {task_id}] Acquired processing lock for: {original_filename} (mode: {mineru_mode}, parser: {parser})")
                
                # TODO: 远程 MinerU 优化
                # 如果 mineru_mode == "remote" 且 parser == "mineru":
                #   1. 将文件上传到临时存储（S3/OSS）或本地临时 HTTP 服务
                #   2. 获取可访问的 URL
                #   3. 使用 src.mineru_client.MinerUClient 调用远程 API
                #   4. 批量处理多个文件（充分利用 API 性能）
                #   5. 下载 markdown 结果并插入 LightRAG
                # 优势：
                #   - 无本地资源消耗（无需 GPU、无需模型下载）
                #   - 并发数可提升到 10+（由远程 API 限流控制）
                #   - 支持批量识别（单次 API 调用处理多文件）
                
                # 当前：使用 RAG-Anything 本地解析
                await rag_instance.process_document_complete(file_path=temp_file_path, output_dir="./output")
                logger.info(f"[Task {task_id}] Document parsed using {parser} parser (mode: {mineru_mode})")
        
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
async def insert_document(
    doc_id: str, 
    file: UploadFile = File(...), 
    background_tasks: BackgroundTasks = None,
    parser: Optional[str] = Query(
        default="auto",
        description="解析器选择: 'mineru'(强大多模态), 'docling'(快速轻量), 'auto'(智能选择)"
    )
):
    """
    上传文件并异步处理。立即返回 task_id，客户端可通过 /task/{task_id} 查询处理状态。
    
    **文件类型处理策略：**
    - **纯文本 (.txt, .md)**: 直接插入 LightRAG，轻量快速，无需解析器
    - **图片 (.jpg, .png)**: 使用 MinerU（OCR 能力强）
    - **PDF/Office 小文件 (< 500KB)**: 使用 Docling（快速）
    - **PDF/Office 大文件 (> 500KB)**: 使用 MinerU（强大多模态）
    
    **解析器参数（仅对非文本文件生效）：**
    - `auto`: 自动选择（推荐）
    - `mineru`: 强大的多模态解析器（内存占用大）
    - `docling`: 轻量级解析器（内存占用小）
    
    返回 202 Accepted 表示任务已接受，正在处理中。
    """
    # 验证 parser 参数
    if parser not in ["mineru", "docling", "auto"]:
        raise HTTPException(status_code=400, detail=f"Invalid parser: {parser}. Must be 'mineru', 'docling', or 'auto'.")
    
    rag_instance = get_rag_instance(parser if parser != "auto" else "mineru")
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
        
        # 智能选择解析器
        selected_parser = parser
        if parser == "auto":
            selected_parser = select_parser_by_file(original_filename, file_size)
            logger.info(f"Auto-selected parser for {original_filename} ({file_size} bytes): {selected_parser}")
        
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
        
        # 添加后台任务（传递选择的解析器）
        background_tasks.add_task(
            process_document_task,
            task_id=task_id,
            doc_id=doc_id,
            temp_file_path=temp_file_path,
            original_filename=original_filename,
            parser=selected_parser  # 传递选择的解析器
        )
        
        logger.info(f"[Task {task_id}] Created task for file: {original_filename} (size: {file_size} bytes, doc_id: {doc_id}, parser: {selected_parser})")
        
        # 立即返回 202 + task_id
        return {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "message": "Document upload accepted. Processing in background.",
            "doc_id": doc_id,
            "filename": original_filename,
            "parser": selected_parser,  # 告知用户使用的解析器
            "file_size": file_size
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

