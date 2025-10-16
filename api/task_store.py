"""
任务存储和状态管理

注意：这是内存存储，重启后数据会丢失。
生产环境建议使用 Redis 或数据库。
"""

import os
import asyncio
from typing import Dict

from src.logger import logger
from .models import TaskInfo

# 任务存储（内存字典）
TASK_STORE: Dict[str, TaskInfo] = {}

# 并发控制信号量（动态配置，根据 MinerU 模式）
# 读取 MinerU 模式
mineru_mode = os.getenv("MINERU_MODE", "local")

if mineru_mode == "remote":
    # 远程模式：允许高并发（远程服务器处理，不占用本地资源）
    # 由 MinerU API 的限流配置控制，而非本地 Semaphore
    DEFAULT_CONCURRENCY = 10  # 高并发，充分利用远程 API
    logger.info(f"📡 MinerU Remote Mode: 允许高并发处理（并发数: {DEFAULT_CONCURRENCY}）")
else:
    # 本地模式：限制并发（防止本地 OOM）
    DEFAULT_CONCURRENCY = 1  # 严格限制，避免多个本地 MinerU 进程
    logger.info(f"💻 MinerU Local Mode: 限制并发处理（并发数: {DEFAULT_CONCURRENCY}）")

DOCUMENT_PROCESSING_CONCURRENCY = int(
    os.getenv("DOCUMENT_PROCESSING_CONCURRENCY", str(DEFAULT_CONCURRENCY))
)
DOCUMENT_PROCESSING_SEMAPHORE = asyncio.Semaphore(DOCUMENT_PROCESSING_CONCURRENCY)

# 输出配置信息
logger.info(f"⚙️  Document Processing: mode={mineru_mode}, concurrency={DOCUMENT_PROCESSING_CONCURRENCY}")


def get_task(task_id: str) -> TaskInfo:
    """获取任务信息"""
    return TASK_STORE.get(task_id)


def create_task(task_info: TaskInfo) -> None:
    """创建任务"""
    TASK_STORE[task_info.task_id] = task_info


def update_task(task_id: str, **kwargs) -> None:
    """更新任务信息"""
    if task_id in TASK_STORE:
        for key, value in kwargs.items():
            setattr(TASK_STORE[task_id], key, value)


def delete_task(task_id: str) -> bool:
    """删除任务"""
    if task_id in TASK_STORE:
        del TASK_STORE[task_id]
        return True
    return False

