"""
任务存储和状态管理

注意：这是内存存储，重启后数据会丢失。
生产环境建议使用 Redis 或数据库。
"""

import os
import asyncio
from typing import Dict
from .models import TaskInfo

# 任务存储（内存字典）
TASK_STORE: Dict[str, TaskInfo] = {}

# 并发控制信号量（从环境变量读取）
# 限制同时处理的文档数量（防止 MinerU 并发导致 OOM）
DOCUMENT_PROCESSING_CONCURRENCY = int(os.getenv("DOCUMENT_PROCESSING_CONCURRENCY", "1"))
DOCUMENT_PROCESSING_SEMAPHORE = asyncio.Semaphore(DOCUMENT_PROCESSING_CONCURRENCY)


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

