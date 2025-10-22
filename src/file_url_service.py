"""
文件 URL 服务
在 8000 端口提供临时文件访问，支持远程 MinerU API 集成
"""

import os
import shutil
import uuid
import asyncio
import threading
from typing import Optional
from pathlib import Path
from datetime import datetime, timedelta

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
        """清理过期文件（基于创建时间自动删除）"""
        current_time = datetime.now()
        cleanup_count = 0
        freed_bytes = 0
        
        files_to_remove = []
        
        # 检查所有文件的创建时间
        for file_id, file_path in list(self.file_mapping.items()):
            if os.path.exists(file_path):
                try:
                    # 获取文件创建时间
                    file_ctime = datetime.fromtimestamp(os.path.getctime(file_path))
                    file_age = current_time - file_ctime
                    
                    # 如果超过指定时间，标记为待删除
                    if file_age > timedelta(hours=max_age_hours):
                        file_size = os.path.getsize(file_path)
                        files_to_remove.append((file_id, file_path, file_size))
                        freed_bytes += file_size
                        cleanup_count += 1
                except (OSError, ValueError) as e:
                    logger.warning(f"Failed to check file age for {file_id}: {e}")
        
        # 执行删除
        for file_id, file_path, file_size in files_to_remove:
            try:
                os.remove(file_path)
                del self.file_mapping[file_id]
                logger.info(f"Cleaned up old file: {file_id} (size: {file_size} bytes, age: {(current_time - datetime.fromtimestamp(os.path.getctime(file_path))).total_seconds() / 3600:.1f}h)")
            except OSError as e:
                logger.warning(f"Failed to cleanup file {file_id}: {e}")
        
        if cleanup_count > 0:
            logger.info(f"File cleanup completed: removed {cleanup_count} files, freed {freed_bytes / (1024 * 1024):.2f} MB")
    
    def start_cleanup_task(self, interval_seconds: int = 3600, max_age_hours: int = 24):
        """启动后台定时清理任务
        
        Args:
            interval_seconds: 清理间隔（秒），默认每小时清理一次
            max_age_hours: 文件保留时间（小时），默认 24 小时
        """
        def cleanup_loop():
            while True:
                try:
                    asyncio.run(asyncio.sleep(interval_seconds))
                    self.cleanup_old_files(max_age_hours=max_age_hours)
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}")
                except asyncio.CancelledError:
                    logger.info("Cleanup task cancelled")
                    break
        
        # 使用后台线程执行定时清理
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.name = "FileCleanupThread"
        cleanup_thread.start()
        logger.info(f"File cleanup task started: interval={interval_seconds}s, max_age={max_age_hours}h")
    
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
