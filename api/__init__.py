"""
API 路由模块
"""

from fastapi import APIRouter

# 创建主路由器
api_router = APIRouter()

# 导入子路由
from .insert import router as insert_router
from .query import router as query_router
from .task import router as task_router
from .files import router as files_router

# 注册子路由
api_router.include_router(insert_router, tags=["Document Processing"])
api_router.include_router(query_router, tags=["Query"])
api_router.include_router(task_router, tags=["Task Management"])
api_router.include_router(files_router, tags=["File Service"])

