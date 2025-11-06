"""
任务存储和状态管理（支持多租户隔离）

支持内存存储和 Redis 存储两种模式：
- memory: 内存存储，重启后数据会丢失（默认）
- redis: Redis 持久化存储，支持容器重启和实例重建后恢复

环境变量配置：
- TASK_STORE_STORAGE: 存储类型（memory/redis）
"""

import os
import asyncio
import json
from typing import Dict, Optional

try:
    import redis
except ImportError:
    redis = None

from src.logger import logger
from .models import TaskInfo


# ===== 内部类：存储实现 =====

class _MemoryStore:
    """内存存储实现（原有逻辑）"""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, TaskInfo]] = {}
        self.batches: Dict[str, Dict[str, Dict]] = {}

    def get_task(self, tenant_id: str, task_id: str) -> Optional[TaskInfo]:
        return self.tasks.get(tenant_id, {}).get(task_id)

    def create_task(self, tenant_id: str, task_info: TaskInfo) -> None:
        if tenant_id not in self.tasks:
            self.tasks[tenant_id] = {}
        self.tasks[tenant_id][task_info.task_id] = task_info
        logger.debug(f"Task created: {task_info.task_id} for tenant: {tenant_id}")

    def update_task(self, tenant_id: str, task_id: str, **kwargs) -> None:
        if tenant_id in self.tasks and task_id in self.tasks[tenant_id]:
            for key, value in kwargs.items():
                setattr(self.tasks[tenant_id][task_id], key, value)
            logger.debug(f"Task updated: {task_id} for tenant: {tenant_id}")

    def delete_task(self, tenant_id: str, task_id: str) -> bool:
        if tenant_id in self.tasks and task_id in self.tasks[tenant_id]:
            del self.tasks[tenant_id][task_id]
            logger.debug(f"Task deleted: {task_id} for tenant: {tenant_id}")
            return True
        return False

    def get_tenant_tasks(self, tenant_id: str) -> Dict[str, TaskInfo]:
        return self.tasks.get(tenant_id, {})

    # 批量任务方法
    def create_batch(self, tenant_id: str, batch_id: str, task_ids: list, created_at: str):
        if tenant_id not in self.batches:
            self.batches[tenant_id] = {}
        self.batches[tenant_id][batch_id] = {
            "task_ids": task_ids,
            "total": len(task_ids),
            "created_at": created_at
        }
        logger.debug(f"Batch created: {batch_id} for tenant: {tenant_id} ({len(task_ids)} tasks)")

    def get_batch(self, tenant_id: str, batch_id: str) -> Optional[Dict]:
        return self.batches.get(tenant_id, {}).get(batch_id)

    def delete_batch(self, tenant_id: str, batch_id: str) -> bool:
        if tenant_id in self.batches and batch_id in self.batches[tenant_id]:
            del self.batches[tenant_id][batch_id]
            logger.debug(f"Batch deleted: {batch_id} for tenant: {tenant_id}")
            return True
        return False


class _RedisStore:
    """Redis 存储实现（带自动降级）"""

    # TTL 配置（秒）
    TTL_COMPLETED = 24 * 60 * 60      # 24小时
    TTL_FAILED = 24 * 60 * 60         # 24小时
    TTL_PENDING = 6 * 60 * 60         # 6小时

    def __init__(self, redis_uri: str):
        if redis is None:
            logger.error("redis-py is not installed. Falling back to memory storage.")
            self.fallback = _MemoryStore()
            self.redis = None
            return

        try:
            self.redis = redis.from_url(redis_uri, decode_responses=True)
            self.redis.ping()
            self.fallback = None
            logger.info("✅ TaskStore: Redis connection successful")
        except Exception as e:
            logger.warning(f"⚠️  TaskStore: Redis unavailable, falling back to memory storage: {e}")
            self.fallback = _MemoryStore()
            self.redis = None

    def _get_ttl(self, status: str) -> Optional[int]:
        """根据任务状态返回 TTL"""
        if status == "completed":
            return self.TTL_COMPLETED
        elif status == "failed":
            return self.TTL_FAILED
        elif status in ["pending", "processing"]:
            return self.TTL_PENDING
        return None

    def get_task(self, tenant_id: str, task_id: str) -> Optional[TaskInfo]:
        if self.fallback:
            return self.fallback.get_task(tenant_id, task_id)

        key = f"task:{tenant_id}:{task_id}"
        task_json = self.redis.get(key)
        if task_json:
            return TaskInfo(**json.loads(task_json))
        return None

    def create_task(self, tenant_id: str, task_info: TaskInfo) -> None:
        if self.fallback:
            return self.fallback.create_task(tenant_id, task_info)

        key = f"task:{tenant_id}:{task_info.task_id}"
        task_json = task_info.model_dump_json()

        # 设置 TTL
        ttl = self._get_ttl(task_info.status)
        if ttl:
            self.redis.setex(key, ttl, task_json)
        else:
            self.redis.set(key, task_json)

        # 添加到租户索引
        self.redis.sadd(f"tenant:tasks:{tenant_id}", task_info.task_id)
        logger.debug(f"Task created: {task_info.task_id} for tenant: {tenant_id}")

    def update_task(self, tenant_id: str, task_id: str, **kwargs) -> None:
        if self.fallback:
            return self.fallback.update_task(tenant_id, task_id, **kwargs)

        # 读取 → 更新 → 写回
        task = self.get_task(tenant_id, task_id)
        if task:
            for key, value in kwargs.items():
                setattr(task, key, value)

            # 重新写入（可能更新 TTL）
            key = f"task:{tenant_id}:{task_id}"
            task_json = task.model_dump_json()
            ttl = self._get_ttl(task.status)
            if ttl:
                self.redis.setex(key, ttl, task_json)
            else:
                self.redis.set(key, task_json)
            logger.debug(f"Task updated: {task_id} for tenant: {tenant_id}")

    def delete_task(self, tenant_id: str, task_id: str) -> bool:
        if self.fallback:
            return self.fallback.delete_task(tenant_id, task_id)

        key = f"task:{tenant_id}:{task_id}"
        deleted = self.redis.delete(key)
        self.redis.srem(f"tenant:tasks:{tenant_id}", task_id)
        if deleted > 0:
            logger.debug(f"Task deleted: {task_id} for tenant: {tenant_id}")
        return deleted > 0

    def get_tenant_tasks(self, tenant_id: str) -> Dict[str, TaskInfo]:
        if self.fallback:
            return self.fallback.get_tenant_tasks(tenant_id)

        # 从索引获取所有 task_ids
        task_ids = self.redis.smembers(f"tenant:tasks:{tenant_id}")

        # 使用 pipeline 批量读取
        tasks = {}
        if task_ids:
            pipeline = self.redis.pipeline()
            for task_id in task_ids:
                pipeline.get(f"task:{tenant_id}:{task_id}")
            results = pipeline.execute()

            for task_id, task_json in zip(task_ids, results):
                if task_json:
                    tasks[task_id] = TaskInfo(**json.loads(task_json))

        return tasks

    # 批量任务方法
    def create_batch(self, tenant_id: str, batch_id: str, task_ids: list, created_at: str):
        if self.fallback:
            return self.fallback.create_batch(tenant_id, batch_id, task_ids, created_at)

        key = f"batch:{tenant_id}:{batch_id}"
        batch_data = {
            "task_ids": task_ids,
            "total": len(task_ids),
            "created_at": created_at
        }
        self.redis.set(key, json.dumps(batch_data))
        self.redis.sadd(f"tenant:batches:{tenant_id}", batch_id)
        logger.debug(f"Batch created: {batch_id} for tenant: {tenant_id} ({len(task_ids)} tasks)")

    def get_batch(self, tenant_id: str, batch_id: str) -> Optional[Dict]:
        if self.fallback:
            return self.fallback.get_batch(tenant_id, batch_id)

        key = f"batch:{tenant_id}:{batch_id}"
        batch_json = self.redis.get(key)
        if batch_json:
            return json.loads(batch_json)
        return None

    def delete_batch(self, tenant_id: str, batch_id: str) -> bool:
        if self.fallback:
            return self.fallback.delete_batch(tenant_id, batch_id)

        key = f"batch:{tenant_id}:{batch_id}"
        deleted = self.redis.delete(key)
        self.redis.srem(f"tenant:batches:{tenant_id}", batch_id)
        if deleted > 0:
            logger.debug(f"Batch deleted: {batch_id} for tenant: {tenant_id}")
        return deleted > 0


# ===== 初始化存储 Backend =====

storage_type = os.getenv("TASK_STORE_STORAGE", "memory")

if storage_type == "redis":
    try:
        from src.config import config
        _store = _RedisStore(config.storage.redis_uri)
        logger.info(f"📦 TaskStore initialized: Redis mode")
    except Exception as e:
        logger.error(f"Failed to initialize Redis store: {e}, falling back to memory")
        _store = _MemoryStore()
        logger.info(f"📦 TaskStore initialized: Memory mode (fallback)")
else:
    _store = _MemoryStore()
    logger.info(f"📦 TaskStore initialized: Memory mode")


# ===== 并发控制信号量（动态配置，根据 MinerU 模式）=====

mineru_mode = os.getenv("MINERU_MODE", "local")

if mineru_mode == "remote":
    # 远程模式：允许高并发（远程服务器处理，不占用本地资源）
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

logger.info(f"⚙️  Document Processing: mode={mineru_mode}, concurrency={DOCUMENT_PROCESSING_CONCURRENCY}")


# ===== 公共接口（委托给 _store）=====

def get_task(task_id: str, tenant_id: str) -> TaskInfo:
    """
    获取指定租户的任务信息

    Args:
        task_id: 任务ID
        tenant_id: 租户ID

    Returns:
        TaskInfo: 任务信息，如果不存在则返回 None
    """
    return _store.get_task(tenant_id, task_id)


def create_task(task_info: TaskInfo, tenant_id: str) -> None:
    """
    为指定租户创建任务

    Args:
        task_info: 任务信息
        tenant_id: 租户ID
    """
    _store.create_task(tenant_id, task_info)


def update_task(task_id: str, tenant_id: str, **kwargs) -> None:
    """
    更新指定租户的任务信息

    Args:
        task_id: 任务ID
        tenant_id: 租户ID
        **kwargs: 要更新的字段
    """
    _store.update_task(tenant_id, task_id, **kwargs)


def delete_task(task_id: str, tenant_id: str) -> bool:
    """
    删除指定租户的任务

    Args:
        task_id: 任务ID
        tenant_id: 租户ID

    Returns:
        bool: 是否成功删除
    """
    return _store.delete_task(tenant_id, task_id)


def get_tenant_tasks(tenant_id: str) -> Dict[str, TaskInfo]:
    """
    获取指定租户的所有任务

    Args:
        tenant_id: 租户ID

    Returns:
        Dict[str, TaskInfo]: 租户的所有任务
    """
    return _store.get_tenant_tasks(tenant_id)


# ===== 批量任务管理函数 =====

def create_batch(batch_id: str, tenant_id: str, task_ids: list, created_at: str) -> None:
    """
    创建批量任务记录

    Args:
        batch_id: 批量任务ID
        tenant_id: 租户ID
        task_ids: 关联的任务ID列表
        created_at: 创建时间
    """
    _store.create_batch(tenant_id, batch_id, task_ids, created_at)


def get_batch(batch_id: str, tenant_id: str) -> Dict:
    """
    获取批量任务信息

    Args:
        batch_id: 批量任务ID
        tenant_id: 租户ID

    Returns:
        Dict: 批量任务信息（包含 task_ids、total、created_at），如果不存在则返回 None
    """
    return _store.get_batch(tenant_id, batch_id)


def delete_batch(batch_id: str, tenant_id: str) -> bool:
    """
    删除批量任务记录

    Args:
        batch_id: 批量任务ID
        tenant_id: 租户ID

    Returns:
        bool: 是否成功删除
    """
    return _store.delete_batch(tenant_id, batch_id)


# ===== 文档删除任务管理函数 =====

def create_deletion_task(tenant_id: str, doc_id: str) -> str:
    """
    创建删除任务

    Args:
        tenant_id: 租户ID
        doc_id: 文档ID

    Returns:
        str: 删除任务ID
    """
    import uuid
    from datetime import datetime
    from .models import DeletionTaskInfo

    task_id = f"deletion_{uuid.uuid4().hex[:8]}"

    # 注意：使用 dict() 而不是 DeletionTaskInfo 对象，因为任务存储使用字典
    task_data = {
        "task_id": task_id,
        "tenant_id": tenant_id,
        "doc_id": doc_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # 创建 TaskInfo 对象（因为 create_task 需要 TaskInfo 类型）
    # 注意：TaskInfo 模型需要 filename 字段，用 doc_id 代替
    task_info = TaskInfo(
        task_id=task_id,
        status="pending",
        doc_id=doc_id,
        filename=doc_id,  # 删除任务使用 doc_id 作为 filename
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )

    _store.create_task(tenant_id, task_info)
    return task_id


def get_deletion_task(tenant_id: str, doc_id: str):
    """
    查询是否有正在进行的删除任务

    Args:
        tenant_id: 租户ID
        doc_id: 文档ID

    Returns:
        TaskInfo: 如果存在正在删除的任务则返回任务信息，否则返回 None
    """
    tenant_tasks = get_tenant_tasks(tenant_id)
    for task in tenant_tasks.values():
        # TaskInfo 对象使用属性访问，不是字典
        # 检查 pending 和 deleting 状态，防止并发删除同一文档
        if (task.doc_id == doc_id and
            task.status in ["pending", "deleting"]):
            return task
    return None


def update_deletion_task(task_id: str, tenant_id: str, **kwargs) -> None:
    """
    更新删除任务状态

    Args:
        task_id: 任务ID
        tenant_id: 租户ID
        **kwargs: 要更新的字段
    """
    _store.update_task(tenant_id, task_id, **kwargs)
