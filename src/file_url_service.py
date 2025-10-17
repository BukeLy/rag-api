"""
文件 URL 服务
在 8000 端口提供临时文件访问，支持远程 MinerU API 集成
"""

import os
import shutil
import uuid
from typing import Optional
from pathlib import Path

from src.logger import logger


class FileURLService:
    """轻量级文件 URL 服务，在 8000 端口提供临时文件访问"""
    
    def __init__(self, base_url: str = "http://localhost:8000", 
                 temp_dir: str = "/tmp/rag-files"):
        self.base_url = base_url
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)
        self.file_mapping = {}  # file_id -> file_path
        logger.info(f"FileURLService initialized: {base_url}, temp_dir: {temp_dir}")
    
    async def register_file(self, file_path: str, filename: str) -> str:
        """注册文件并返回访问 URL（8000 端口）"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found: {file_path}")
        
        file_id = str(uuid.uuid4())
        safe_filename = self._sanitize_filename(filename)
        target_path = os.path.join(self.temp_dir, f"{file_id}_{safe_filename}")
        
        # 复制文件到服务目录
        shutil.copy2(file_path, target_path)
        self.file_mapping[file_id] = target_path
        
        # 使用 8000 端口的 URL
        file_url = f"{self.base_url}/files/{file_id}/{safe_filename}"
        logger.info(f"File registered: {filename} -> {file_url}")
        
        return file_url
    
    def get_file_path(self, file_id: str) -> Optional[str]:
        """根据文件 ID 获取本地路径"""
        return self.file_mapping.get(file_id)
    
    def cleanup_file(self, file_id: str):
        """清理单个文件"""
        file_path = self.file_mapping.get(file_id)
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                del self.file_mapping[file_id]
                logger.info(f"Cleaned up file: {file_id}")
            except OSError as e:
                logger.warning(f"Failed to cleanup file {file_id}: {e}")
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """清理过期文件（TODO: 实现基于时间的清理）"""
        # 目前先简单实现，后续可以添加基于文件创建时间的清理逻辑
        logger.info("File cleanup triggered (placeholder implementation)")
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，确保 URL 安全"""
        # 移除路径分隔符和特殊字符
        safe_name = os.path.basename(filename)
        safe_name = safe_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c in ['_', '-', '.'])
        return safe_name or "file"


# 全局文件服务实例
global_file_service = None


def get_file_service():
    """获取文件服务实例"""
    global global_file_service
    if global_file_service is None:
        base_url = os.getenv("FILE_SERVICE_BASE_URL", "http://localhost:8000")
        global_file_service = FileURLService(base_url)
    return global_file_service
