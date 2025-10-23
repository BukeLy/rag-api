"""
API 数据模型
"""

from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"        # 排队中
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"    # 完成
    FAILED = "failed"          # 失败


class TaskInfo(BaseModel):
    """
    任务信息模型

    记录文档处理任务的完整生命周期信息
    """
    task_id: str = Field(
        ...,
        description="任务唯一标识符",
        example="550e8400-e29b-41d4-a716-446655440000"
    )
    status: TaskStatus = Field(
        ...,
        description="任务当前状态（pending/processing/completed/failed）",
        example="completed"
    )
    doc_id: str = Field(
        ...,
        description="文档唯一标识符",
        example="research_paper_001"
    )
    filename: str = Field(
        ...,
        description="原始文件名",
        example="AI研究报告.pdf"
    )
    created_at: str = Field(
        ...,
        description="任务创建时间（ISO 8601 格式）",
        example="2025-10-24T14:30:00"
    )
    updated_at: str = Field(
        ...,
        description="任务最后更新时间（ISO 8601 格式）",
        example="2025-10-24T14:32:15"
    )
    error: Optional[str] = Field(
        None,
        description="错误信息（仅在 failed 状态时存在）",
        example="Unsupported file format: .xyz"
    )
    result: Optional[Dict] = Field(
        None,
        description="处理结果详情（仅在 completed 状态时存在）",
        example={
            "message": "Document processed successfully",
            "doc_id": "research_paper_001",
            "filename": "AI研究报告.pdf",
            "entities_extracted": 45,
            "relations_extracted": 78
        }
    )

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "doc_id": "research_paper_001",
                "filename": "AI研究报告.pdf",
                "created_at": "2025-10-24T14:30:00",
                "updated_at": "2025-10-24T14:32:15",
                "result": {
                    "message": "Document processed successfully",
                    "doc_id": "research_paper_001",
                    "filename": "AI研究报告.pdf"
                }
            }
        }


class QueryRequest(BaseModel):
    """
    查询请求模型

    用于向 RAG 系统提交查询请求
    """
    query: str = Field(
        ...,
        description="查询问题（自然语言）",
        example="什么是人工智能？它有哪些应用场景？",
        min_length=1,
        max_length=2000
    )
    mode: str = Field(
        default="naive",
        description="""查询模式：
- `naive`: 向量检索（最快，推荐日常使用，15-20秒）
- `local`: 局部知识图谱（适合精确查询）
- `global`: 全局知识图谱（完整，但较慢）
- `hybrid`: 混合模式（结合 local 和 global）
- `mix`: 全功能混合（最慢，但结果最全面）
""",
        example="naive",
        pattern="^(naive|local|global|hybrid|mix)$"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "什么是人工智能？它有哪些应用场景？",
                "mode": "naive"
            }
        }


class QueryResponse(BaseModel):
    """
    查询响应模型

    包含 AI 生成的答案和引用来源
    """
    answer: str = Field(
        ...,
        description="AI 生成的答案（Markdown 格式，包含引用来源）",
        example="""人工智能（AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。

主要应用场景包括：
- 自然语言处理
- 计算机视觉
- 推荐系统
- 自动驾驶

### References
- [1] AI研究报告.pdf
- [2] 深度学习基础.docx
"""
    )

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "人工智能（AI）是计算机科学的一个分支...\n\n### References\n- [1] AI研究报告.pdf"
            }
        }


class TenantStats(BaseModel):
    """
    租户统计信息模型
    """
    tenant_id: str = Field(..., description="租户唯一标识符", example="tenant_a")
    tasks: Dict = Field(
        ...,
        description="任务统计信息",
        example={
            "total": 10,
            "completed": 8,
            "failed": 1,
            "processing": 1,
            "pending": 0
        }
    )
    instance_cached: bool = Field(
        ...,
        description="租户实例是否已缓存",
        example=True
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant_a",
                "tasks": {
                    "total": 10,
                    "completed": 8,
                    "failed": 1,
                    "processing": 1,
                    "pending": 0
                },
                "instance_cached": True
            }
        }

