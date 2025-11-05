"""
API 路由模块（多租户支持）
"""

from fastapi import APIRouter

# 创建主路由器
api_router = APIRouter()

# 导入子路由
from .insert import router as insert_router
from .query import router as query_router
from .task import router as task_router
from .files import router as files_router
from .monitor import router as monitor_router
from .tenant import router as tenant_router  # 租户管理路由
from .tenant_config import router as tenant_config_router  # 租户配置管理路由

# 注册子路由
api_router.include_router(insert_router, tags=["Document Processing"])
api_router.include_router(query_router, tags=["Query"])
api_router.include_router(task_router, tags=["Task Management"])
api_router.include_router(files_router, tags=["File Service"])
api_router.include_router(monitor_router, tags=["Performance Monitoring"])
api_router.include_router(tenant_router)  # 租户管理（已在 tenant.py 中定义 tags）
api_router.include_router(tenant_config_router)  # 租户配置管理（已在 tenant_config.py 中定义 tags）

