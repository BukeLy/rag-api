"""
API 数据模型
"""

from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"        # 排队中
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"    # 完成
    FAILED = "failed"          # 失败


class TaskInfo(BaseModel):
    """任务信息模型"""
    task_id: str
    status: TaskStatus
    doc_id: str
    filename: str
    created_at: str
    updated_at: str
    error: Optional[str] = None
    result: Optional[Dict] = None


class QueryRequest(BaseModel):
    """查询请求模型"""
    query: str
    mode: str = "mix"

