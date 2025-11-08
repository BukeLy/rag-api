"""
API 数据模型
"""

from enum import Enum
from typing import Dict, Optional, List
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"        # 排队中
    PROCESSING = "processing"  # 处理中
    DELETING = "deleting"      # 删除中
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
    查询请求模型（增强版，对齐 LightRAG 官方 API）

    支持基础查询和高级参数，提供更精细的控制能力
    """
    # ===== 基础参数 =====
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

    # ===== 高级参数（v2.0 新增）=====
    conversation_history: Optional[List[Dict]] = Field(
        None,
        description="""对话历史（支持多轮对话）

格式示例：
```json
[
  {"role": "user", "content": "什么是 AI？"},
  {"role": "assistant", "content": "AI 是人工智能..."},
  {"role": "user", "content": "它有哪些应用？"}
]
```
""",
        example=[
            {"role": "user", "content": "什么是人工智能？"},
            {"role": "assistant", "content": "人工智能是计算机科学的一个分支..."}
        ]
    )

    user_prompt: Optional[str] = Field(
        None,
        description="自定义提示词（覆盖默认系统提示词）",
        example="请以专家的口吻回答，并提供具体案例",
        max_length=1000
    )

    response_type: Optional[str] = Field(
        "paragraph",
        description="""响应格式类型：
- `paragraph`: 段落格式（默认，适合阅读）
- `list`: 列表格式（结构化输出）
- `json`: JSON 格式（结构化数据）
""",
        example="paragraph",
        pattern="^(paragraph|list|json)$"
    )

    only_need_context: bool = Field(
        False,
        description="是否仅返回上下文（不生成 AI 回答），适合调试和自定义生成",
        example=False
    )

    only_need_prompt: bool = Field(
        False,
        description="是否仅返回最终提示词（用于调试，查看发送给 LLM 的完整提示）",
        example=False
    )

    # ===== 关键词提取 =====
    hl_keywords: Optional[List[str]] = Field(
        None,
        description="高级关键词（High-Level Keywords），用于指定重要的检索关键词",
        example=["人工智能", "深度学习"],
        max_length=10
    )

    ll_keywords: Optional[List[str]] = Field(
        None,
        description="低级关键词（Low-Level Keywords），用于指定次要的检索关键词",
        example=["神经网络", "算法"],
        max_length=20
    )

    # ===== Token 限制 =====
    max_entity_tokens: Optional[int] = Field(
        None,
        description="实体上下文最大 token 数（用于控制输出长度）",
        example=2000,
        gt=0,
        le=10000
    )

    max_relation_tokens: Optional[int] = Field(
        None,
        description="关系上下文最大 token 数（用于控制输出长度）",
        example=2000,
        gt=0,
        le=10000
    )

    max_total_tokens: Optional[int] = Field(
        None,
        description="总上下文最大 token 数（用于控制整体输出长度）",
        example=4000,
        gt=0,
        le=20000
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "什么是人工智能？它有哪些应用场景？",
                "mode": "naive",
                "response_type": "paragraph",
                "only_need_context": False
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


class DeletionTaskInfo(BaseModel):
    """
    文档删除任务模型

    记录文档删除任务的完整生命周期信息
    """
    task_id: str = Field(
        ...,
        description="删除任务唯一标识符",
        example="deletion_abc123"
    )
    tenant_id: str = Field(
        ...,
        description="租户唯一标识符",
        example="siraya"
    )
    doc_id: str = Field(
        ...,
        description="文档唯一标识符",
        example="research_paper_001"
    )
    status: str = Field(
        ...,
        description="任务当前状态（pending/deleting/completed/failed）",
        example="deleting"
    )
    created_at: str = Field(
        ...,
        description="任务创建时间（ISO 8601 格式）",
        example="2025-11-06T10:00:00Z"
    )
    updated_at: str = Field(
        ...,
        description="任务最后更新时间（ISO 8601 格式）",
        example="2025-11-06T10:00:02Z"
    )
    error: Optional[str] = Field(
        None,
        description="错误信息（仅在 failed 状态时存在）",
        example="Document not found"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "deletion_abc123",
                "tenant_id": "siraya",
                "doc_id": "research_paper_001",
                "status": "deleting",
                "created_at": "2025-11-06T10:00:00Z",
                "updated_at": "2025-11-06T10:00:02Z"
            }
        }


class DocumentStatusResponse(BaseModel):
    """
    文档状态响应模型

    返回文档在 LightRAG 中的处理状态和元数据
    """
    doc_id: str = Field(
        ...,
        description="文档唯一标识符",
        example="doc-abc123"
    )
    status: str = Field(
        ...,
        description="文档处理状态（pending/processing/preprocessed/processed/failed）",
        example="processed"
    )
    file_path: str = Field(
        ...,
        description="文件路径",
        example="research_paper.pdf"
    )
    created_at: str = Field(
        ...,
        description="创建时间（ISO 8601 格式）",
        example="2025-11-06T10:00:00+00:00"
    )
    updated_at: str = Field(
        ...,
        description="更新时间（ISO 8601 格式）",
        example="2025-11-06T10:05:00+00:00"
    )
    content_summary: str = Field(
        ...,
        description="内容摘要（前 100 字符）",
        example="This paper discusses machine learning..."
    )
    content_length: int = Field(
        ...,
        description="内容总长度（字符数）",
        example=5000
    )
    chunks_count: Optional[int] = Field(
        None,
        description="切片数量",
        example=15
    )
    error_msg: Optional[str] = Field(
        None,
        description="错误信息（仅 failed 状态时存在）",
        example="Parsing failed: invalid format"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "doc_id": "doc-abc123",
                "status": "processed",
                "file_path": "research_paper.pdf",
                "created_at": "2025-11-06T10:00:00+00:00",
                "updated_at": "2025-11-06T10:05:00+00:00",
                "content_summary": "This paper discusses machine learning...",
                "content_length": 5000,
                "chunks_count": 15
            }
        }

