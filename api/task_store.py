"""
任务存储和状态管理（支持多租户隔离）

注意：这是内存存储，重启后数据会丢失。
生产环境建议使用 Redis 或数据库。
"""

import os
import asyncio
from typing import Dict

from src.logger import logger
from .models import TaskInfo

# 任务存储（按租户隔离的嵌套字典）
# 结构: {tenant_id: {task_id: TaskInfo}}
TASK_STORE: Dict[str, Dict[str, TaskInfo]] = {}

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


def get_task(task_id: str, tenant_id: str) -> TaskInfo:
    """
    获取指定租户的任务信息

    Args:
        task_id: 任务ID
        tenant_id: 租户ID

    Returns:
        TaskInfo: 任务信息，如果不存在则返回 None
    """
    return TASK_STORE.get(tenant_id, {}).get(task_id)


def create_task(task_info: TaskInfo, tenant_id: str) -> None:
    """
    为指定租户创建任务

    Args:
        task_info: 任务信息
        tenant_id: 租户ID
    """
    if tenant_id not in TASK_STORE:
        TASK_STORE[tenant_id] = {}
    TASK_STORE[tenant_id][task_info.task_id] = task_info
    logger.debug(f"Task created: {task_info.task_id} for tenant: {tenant_id}")


def update_task(task_id: str, tenant_id: str, **kwargs) -> None:
    """
    更新指定租户的任务信息

    Args:
        task_id: 任务ID
        tenant_id: 租户ID
        **kwargs: 要更新的字段
    """
    if tenant_id in TASK_STORE and task_id in TASK_STORE[tenant_id]:
        for key, value in kwargs.items():
            setattr(TASK_STORE[tenant_id][task_id], key, value)
        logger.debug(f"Task updated: {task_id} for tenant: {tenant_id}")


def delete_task(task_id: str, tenant_id: str) -> bool:
    """
    删除指定租户的任务

    Args:
        task_id: 任务ID
        tenant_id: 租户ID

    Returns:
        bool: 是否成功删除
    """
    if tenant_id in TASK_STORE and task_id in TASK_STORE[tenant_id]:
        del TASK_STORE[tenant_id][task_id]
        logger.debug(f"Task deleted: {task_id} for tenant: {tenant_id}")
        return True
    return False


def get_tenant_tasks(tenant_id: str) -> Dict[str, TaskInfo]:
    """
    获取指定租户的所有任务

    Args:
        tenant_id: 租户ID

    Returns:
        Dict[str, TaskInfo]: 租户的所有任务
    """
    return TASK_STORE.get(tenant_id, {})

