import logging
import os
import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel

# 导入 RAG 相关模块
from src.rag import lifespan, get_rag_instance

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI 应用 ---

app = FastAPI(lifespan=lifespan)

# --- API 端点 ---

class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"

@app.post("/insert")
async def insert_document(doc_id: str, file: UploadFile = File(...)):
    """
    上传文件并处理。支持 PDF、DOCX、图片等多模态文件。
    """
    rag_instance = get_rag_instance()
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG service is not ready.")
    
    # 保存上传的文件到临时位置
    temp_file_path = f"/tmp/{doc_id}_{file.filename}"
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Processing uploaded file: {temp_file_path} (original: {file.filename}) for doc_id: {doc_id}")
        
        # 使用 RAG-Anything 处理上传的文件 (支持 PDF, DOCX, PNG, JPG 等)
        # 注意: process_document_complete 不返回值，如果处理失败会抛出异常
        await rag_instance.process_document_complete(file_path=temp_file_path, output_dir="./output")
        
        logger.info(f"Document processed successfully: {file.filename}")
        return {"message": "Document processed successfully", "doc_id": doc_id, "filename": file.filename}

    except Exception as e:
        logger.error(f"Error during document insertion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 确保临时文件总是被删除
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Cleaned up temporary file: {temp_file_path}")


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