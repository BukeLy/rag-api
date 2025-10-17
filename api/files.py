"""
文件访问端点
在 8000 端口提供临时文件下载服务，支持远程 MinerU API
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

from src.file_url_service import get_file_service
from src.logger import logger

router = APIRouter()


@router.get("/files/{file_id}/{filename}")
async def serve_file(file_id: str, filename: str):
    """
    提供文件下载服务
    
    用于远程 MinerU API 访问本地文件，所有访问都通过 8000 端口
    """
    file_service = get_file_service()
    file_path = file_service.get_file_path(file_id)
    
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"File not found: file_id={file_id}, filename={filename}")
        raise HTTPException(status_code=404, detail="File not found")
    
    # 记录访问日志
    logger.info(f"Serving file: {filename} (file_id: {file_id})")
    
    return FileResponse(
        file_path, 
        filename=filename,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Allow-Origin": "*"
        }
    )
