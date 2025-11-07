"""
查询路由（多租户 LightRAG 知识图谱访问）
"""

import os
import re
import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Optional

from src.logger import logger
from src.config import config  # 使用集中配置管理
from src.tenant_deps import get_tenant_id
from src.multi_tenant import get_tenant_lightrag
from .models import QueryRequest, QueryResponse

# 导入 LightRAG 查询参数
try:
    from lightrag import QueryParam
except ImportError:
    # 如果导入失败，创建一个简单的替代类
    class QueryParam:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

router = APIRouter()

# 从配置管理类读取查询优化参数
DEFAULT_TOP_K = config.lightrag_query.top_k
DEFAULT_CHUNK_TOP_K = config.lightrag_query.chunk_top_k


def strip_think_tags(text: str) -> str:
    """Remove <think>...</think> markers from LLM output."""
    if not text:
        return text
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


@router.post("/query", response_model=QueryResponse)
async def query_rag(
    request: QueryRequest,
    tenant_id: str = Depends(get_tenant_id)
) -> QueryResponse:
    """
    查询 RAG 系统（多租户隔离，直接访问 LightRAG 知识图谱）

    **v2.0 新特性**：
    - ✨ **对话历史支持**：通过 `conversation_history` 实现多轮对话
    - ✨ **自定义提示词**：通过 `user_prompt` 定制回答风格
    - ✨ **响应格式控制**：支持 paragraph/list/json 格式
    - ✨ **关键词提取**：通过 `hl_keywords`/`ll_keywords` 精准检索
    - ✨ **Token 限制**：精细控制输出长度
    - ✨ **调试模式**：`only_need_context=true` 仅返回上下文

    **多租户支持**：
    - 🔒 **租户隔离**：每个租户的数据完全隔离
    - 🎯 **必填参数**：`?tenant_id=your_tenant_id`
    - ⚡ **共享资源**：LLM/Embedding 函数共享，节省资源

    **查询模式**：
    - `naive`: 向量检索（**最快**，推荐日常使用，15-20秒）
    - `local`: 局部知识图谱（适合精确查询）
    - `global`: 全局知识图谱（完整，但较慢）
    - `hybrid`: 混合模式
    - `mix`: 全功能混合（慢，但结果最全面）

    **性能优化**：
    - `top_k=20`（从默认 60 减少）
    - `chunk_top_k=10`（从默认 20 减少）
    - `max_async=8`（从 4 提升，优化实体合并）
    - `enable_rerank=True`（提升相关性，增加 2-3秒）
    """
    # 获取租户专属的 LightRAG 实例
    lightrag = await get_tenant_lightrag(tenant_id)
    if not lightrag:
        raise HTTPException(
            status_code=503,
            detail=f"LightRAG is not ready for tenant: {tenant_id}"
        )

    try:
        # 直接使用 LightRAG 查询（绕过 RAGAnything 解析器）
        from lightrag import QueryParam

        # 构建查询参数（包含 v2.0 新增参数）
        query_param_kwargs = {
            "mode": request.mode,
            "top_k": DEFAULT_TOP_K,
            "chunk_top_k": DEFAULT_CHUNK_TOP_K,
            "enable_rerank": True,
            "only_need_context": request.only_need_context,
        }

        # 添加高级参数（如果提供）
        if request.response_type:
            query_param_kwargs["response_type"] = request.response_type

        if request.hl_keywords:
            query_param_kwargs["hl_keywords"] = request.hl_keywords

        if request.ll_keywords:
            query_param_kwargs["ll_keywords"] = request.ll_keywords

        if request.max_entity_tokens:
            query_param_kwargs["max_entity_tokens"] = request.max_entity_tokens

        if request.max_relation_tokens:
            query_param_kwargs["max_relation_tokens"] = request.max_relation_tokens

        if request.max_total_tokens:
            query_param_kwargs["max_total_tokens"] = request.max_total_tokens

        if request.user_prompt:
            query_param_kwargs["user_prompt"] = request.user_prompt

        if request.conversation_history:
            query_param_kwargs["conversation_history"] = request.conversation_history

        # 创建 QueryParam
        query_param = QueryParam(**query_param_kwargs)

        # 执行查询
        answer = await lightrag.aquery(
            request.query,
            param=query_param
        )

        # 检查查询是否成功
        if answer is None:
            error_msg = "Query failed: LLM API returned no response. Please check your API configuration and quota."
            logger.error(f"[Tenant {tenant_id}] {error_msg} (query: {request.query[:50]}...)")
            return {"answer": error_msg}

        # 清理 LLM 输出中的 think 标签
        answer = strip_think_tags(answer)

        logger.info(f"[Tenant {tenant_id}] Query successful: {request.query[:50]}... (mode: {request.mode})")
        return {"answer": answer}

    except Exception as e:
        logger.error(f"[Tenant {tenant_id}] Error during query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def query_stream(
    request: QueryRequest,
    tenant_id: str = Depends(get_tenant_id)
):
    """
    流式查询 RAG 系统（SSE 格式，实时推送结果）

    **新特性**：
    - ⚡ **实时输出**：查询结果逐步推送，用户体验更好
    - 📡 **SSE 格式**：标准 Server-Sent Events 格式
    - 🔄 **支持所有高级参数**：与 `/query` 端点功能一致
    - 🔒 **多租户隔离**：每个租户的数据完全隔离

    **使用场景**：
    - 长时间查询（需要实时反馈）
    - 聊天界面（逐字输出）
    - 需要取消长时间查询的场景

    **客户端使用示例**：
    ```javascript
    const eventSource = new EventSource('/query/stream?tenant_id=xxx');

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.done) {
            console.log('查询完成');
            eventSource.close();
        } else {
            console.log('收到数据块:', data.chunk);
        }
    };

    eventSource.onerror = (error) => {
        console.error('连接错误:', error);
        eventSource.close();
    };
    ```

    **Python 客户端示例**：
    ```python
    import requests
    import json

    response = requests.post(
        "http://api.com/query/stream?tenant_id=xxx",
        json={"query": "什么是 AI？", "mode": "naive"},
        stream=True
    )

    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                data = json.loads(line_str[6:])  # 去除 "data: " 前缀
                if data.get('done'):
                    break
                print(data.get('chunk'), end='', flush=True)
    ```
    """
    # 获取租户专属的 LightRAG 实例
    lightrag = await get_tenant_lightrag(tenant_id)
    if not lightrag:
        raise HTTPException(
            status_code=503,
            detail=f"LightRAG is not ready for tenant: {tenant_id}"
        )

    async def generate():
        """异步生成器：流式输出查询结果"""
        try:
            # 构建查询参数（与 /query 端点相同）
            from lightrag import QueryParam

            query_param_kwargs = {
                "mode": request.mode,
                "top_k": DEFAULT_TOP_K,
                "chunk_top_k": DEFAULT_CHUNK_TOP_K,
                "enable_rerank": True,
                "only_need_context": request.only_need_context,
            }

            # 添加高级参数
            if request.response_type:
                query_param_kwargs["response_type"] = request.response_type
            if request.hl_keywords:
                query_param_kwargs["hl_keywords"] = request.hl_keywords
            if request.ll_keywords:
                query_param_kwargs["ll_keywords"] = request.ll_keywords
            if request.max_entity_tokens:
                query_param_kwargs["max_entity_tokens"] = request.max_entity_tokens
            if request.max_relation_tokens:
                query_param_kwargs["max_relation_tokens"] = request.max_relation_tokens
            if request.max_total_tokens:
                query_param_kwargs["max_total_tokens"] = request.max_total_tokens
            if request.user_prompt:
                query_param_kwargs["user_prompt"] = request.user_prompt
            if request.conversation_history:
                query_param_kwargs["conversation_history"] = request.conversation_history

            query_param = QueryParam(**query_param_kwargs)

            # 检查 LightRAG 是否支持流式查询
            if hasattr(lightrag, 'aquery_stream'):
                # 使用 LightRAG 的原生流式 API
                async for chunk in lightrag.aquery_stream(request.query, param=query_param):
                    cleaned_chunk = strip_think_tags(chunk)
                    if cleaned_chunk:
                        yield f"data: {json.dumps({'chunk': cleaned_chunk, 'done': False})}\n\n"
            else:
                # Fallback：一次性获取全部结果然后分块发送
                logger.warning(f"[Tenant {tenant_id}] LightRAG does not support streaming, using fallback mode")
                answer = await lightrag.aquery(request.query, param=query_param)

                # 检查查询是否成功
                if answer is None:
                    error_msg = "Query failed: LLM API returned no response. Please check your API configuration and quota."
                    logger.error(f"[Tenant {tenant_id}] {error_msg} (query: {request.query[:50]}...)")
                    yield f"data: {json.dumps({'chunk': error_msg, 'done': False})}\n\n"
                else:
                    answer = strip_think_tags(answer)

                    # 将结果分块发送（模拟流式输出）
                    chunk_size = 50  # 每块 50 个字符
                    for i in range(0, len(answer), chunk_size):
                        chunk = answer[i:i + chunk_size]
                        yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"

            # 发送完成标记
            yield f"data: {json.dumps({'done': True})}\n\n"

            logger.info(f"[Tenant {tenant_id}] Stream query successful: {request.query[:50]}... (mode: {request.mode})")

        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error during stream query: {e}", exc_info=True)
            # 发送错误信息
            error_data = {
                "error": str(e),
                "done": True
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )
