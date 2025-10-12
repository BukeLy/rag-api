import logging
import os
import shutil
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel

# 导入 RAG 相关模块
from src.rag import lifespan, get_rag_instance

# 导入 RAG-Anything 异常类型
try:
    from raganything.parser import MineruExecutionError
except ImportError:
    # 如果导入失败，定义一个占位类
    class MineruExecutionError(Exception):
        pass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI 应用 ---

app = FastAPI(lifespan=lifespan)

# --- API 端点 ---

class QueryRequest(BaseModel):
    query: str
    mode: str = "mix"

@app.post("/insert")
async def insert_document(doc_id: str, file: UploadFile = File(...)):
    """
    上传文件并处理。支持 PDF、DOCX、图片等多模态文件。
    """
    rag_instance = get_rag_instance()
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG service is not ready.")
    
    # 保留原始文件名（仅用于日志）
    original_filename = file.filename
    
    # 安全地提取文件扩展名
    # 1. 只取最后的文件名部分（避免路径遍历）
    # 2. 验证扩展名是否合法（只包含字母数字和点）
    if original_filename:
        basename = os.path.basename(original_filename)  # 只取文件名，去掉路径
        file_extension = Path(basename).suffix.lower()  # 提取扩展名并转小写
        # 验证扩展名格式（只允许 .字母数字）
        if file_extension and not file_extension[1:].replace('_', '').replace('-', '').isalnum():
            file_extension = ""  # 非法扩展名，忽略
    else:
        file_extension = ""
    
    # 使用 UUID 生成安全的临时文件名，避免路径遍历攻击
    safe_filename = f"{uuid.uuid4()}{file_extension}"
    temp_file_path = f"/tmp/{safe_filename}"
    
    try:
        # 保存上传的文件到临时位置
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 验证文件大小（空文件检查）
        file_size = os.path.getsize(temp_file_path)
        if file_size == 0:
            raise ValueError(f"Empty file: {original_filename}")
        
        # 可选：限制文件大小（例如最大 100MB）
        max_file_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_file_size:
            raise ValueError(f"File too large: {original_filename} ({file_size} bytes, max: {max_file_size} bytes)")
        
        logger.info(f"Processing uploaded file: {original_filename} (saved as: {safe_filename}, size: {file_size} bytes) for doc_id: {doc_id}")
        
        # 使用 RAG-Anything 处理上传的文件 (支持 PDF, DOCX, PNG, JPG 等)
        # 注意: process_document_complete 在失败时会抛出异常
        await rag_instance.process_document_complete(file_path=temp_file_path, output_dir="./output")
        
        logger.info(f"Document processed successfully: {original_filename}")
        return {
            "message": "Document processed successfully", 
            "doc_id": doc_id, 
            "filename": original_filename
        }

    except ValueError as e:
        # 捕获 RAG-Anything 的验证错误（如文件格式不支持、解析失败等）
        logger.error(f"Validation error during document processing: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid document: {str(e)}")
    
    except MineruExecutionError as e:
        # 捕获 MinerU 解析错误（不支持的文件格式等）
        error_msg = str(e)
        logger.error(f"MinerU parsing error: {error_msg}", exc_info=True)
        
        # 判断是否为不支持的文件格式
        if "Unknown file suffix" in error_msg or "Unsupported" in error_msg:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {original_filename}")
        else:
            raise HTTPException(status_code=500, detail=f"Document parsing failed: {original_filename}")
    
    except OSError as e:
        # 捕获文件系统相关错误（磁盘满、权限问题等）
        logger.error(f"File system error during document processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="File system error occurred")
    
    except Exception as e:
        # 捕获其他未预期的错误
        logger.error(f"Unexpected error during document insertion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    finally:
        # 确保临时文件总是被删除
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Cleaned up temporary file: {safe_filename}")
            except OSError as e:
                logger.warning(f"Failed to clean up temporary file {safe_filename}: {e}")


@app.post("/query")
async def query_rag(request: QueryRequest):
    rag_instance = get_rag_instance()
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG service is not ready.")
    try:
        answer = await rag_instance.aquery(request.query, mode=request.mode)
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Error during query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    return {"status": "RAG API is running"}