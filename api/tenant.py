"""
租户管理路由
"""

from fastapi import APIRouter, Depends

from src.logger import logger
from src.tenant_deps import get_tenant_id
from src.multi_tenant import get_multi_tenant_manager
from .task_store import get_tenant_tasks

router = APIRouter(prefix="/tenants", tags=["Tenant Management"])


@router.get("/stats")
async def get_tenant_stats(tenant_id: str = Depends(get_tenant_id)):
    """
    获取当前租户的统计信息

    **返回信息**：
    - 租户ID
    - 任务统计（总数、已完成、失败、处理中）
    - 实例状态（是否已缓存）

    示例响应：
    ```json
    {
        "tenant_id": "tenant_a",
        "tasks": {
            "total": 10,
            "completed": 7,
            "failed": 1,
            "processing": 2,
            "pending": 0
        },
        "instance_cached": true
    }
    ```
    """
    # 获取租户任务统计
    tenant_tasks = get_tenant_tasks(tenant_id)

    total = len(tenant_tasks)
    completed = sum(1 for t in tenant_tasks.values() if t.status == "completed")
    failed = sum(1 for t in tenant_tasks.values() if t.status == "failed")
    processing = sum(1 for t in tenant_tasks.values() if t.status == "processing")
    pending = sum(1 for t in tenant_tasks.values() if t.status == "pending")

    # 检查实例是否已缓存
    manager = get_multi_tenant_manager()
    instance_cached = tenant_id in manager._instances

    return {
        "tenant_id": tenant_id,
        "tasks": {
            "total": total,
            "completed": completed,
            "failed": failed,
            "processing": processing,
            "pending": pending
        },
        "instance_cached": instance_cached
    }


@router.delete("/cache")
async def clear_tenant_cache(tenant_id: str = Depends(get_tenant_id)):
    """
    清理当前租户的实例缓存（释放内存）

    **使用场景**：
    - 租户长时间不活跃，手动释放内存
    - 租户数据已迁移/删除

    **注意**：
    - 下次查询时会重新创建实例（有3秒延迟）
    - 不影响已存储的数据

    示例响应：
    ```json
    {
        "tenant_id": "tenant_a",
        "message": "Tenant cache cleared successfully"
    }
    ```
    """
    manager = get_multi_tenant_manager()
    removed = manager.remove_instance(tenant_id)

    if removed:
        logger.info(f"Tenant cache cleared: {tenant_id}")
        return {
            "tenant_id": tenant_id,
            "message": "Tenant cache cleared successfully"
        }
    else:
        return {
            "tenant_id": tenant_id,
            "message": "Tenant instance was not cached"
        }


@router.get("/pool/stats")
async def get_pool_stats():
    """
    获取实例池统计信息（管理员接口）

    **返回信息**：
    - 当前实例数量
    - 最大实例数量
    - 所有活跃租户列表

    **注意**：
    - 此接口不需要 tenant_id 参数
    - 未来可添加管理员鉴权

    示例响应：
    ```json
    {
        "total_instances": 5,
        "max_instances": 50,
        "tenants": ["tenant_a", "tenant_b", "tenant_c", "tenant_d", "tenant_e"]
    }
    ```
    """
    manager = get_multi_tenant_manager()
    stats = manager.get_stats()

    logger.info(f"Pool stats requested: {stats['total_instances']} instances")
    return stats
