"""
多租户 LightRAG 实例管理器

支持基于 workspace 的租户隔离，使用 LRU 缓存管理实例池。
"""

import os
from functools import lru_cache
from typing import Dict, Optional
from contextlib import asynccontextmanager
from lightrag import LightRAG
from lightrag.utils import EmbeddingFunc
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from src.logger import logger
from src.config import config  # 使用集中配置管理
from src.rate_limiter import get_rate_limiter  # 导入速率限制器

# 模型调用 Future 超时（秒）= rate limiter 等待 + API 调用 + 缓冲
# 从环境变量读取，默认 90 秒
MODEL_CALL_TIMEOUT = float(os.getenv("MODEL_CALL_TIMEOUT", "90"))


class MultiTenantRAGManager:
    """
    多租户 RAG 实例管理器

    特性：
    - 基于 workspace 的租户隔离
    - LRU 缓存管理实例池（最多缓存 N 个租户）
    - 共享 LLM/Embedding 函数
    - 自动清理不活跃租户实例
    """

    def __init__(
        self,
        max_instances: int = 50,  # 最多缓存 50 个租户实例
        default_system_prompt: str = "You are a helpful assistant. Provide direct answers without showing your reasoning process.",
    ):
        self.max_instances = max_instances
        self.default_system_prompt = default_system_prompt

        # 租户实例缓存：tenant_id -> LightRAG
        self._instances: Dict[str, LightRAG] = {}

        # 共享配置（从集中配置管理读取）
        self.ark_api_key = config.llm.api_key
        self.ark_base_url = config.llm.base_url
        self.ark_model = config.llm.model

        self.sf_api_key = config.embedding.api_key
        self.sf_base_url = config.embedding.base_url
        self.sf_embedding_model = config.embedding.model

        self.rerank_model = config.rerank.model

        # 性能配置
        self.top_k = config.lightrag_query.top_k
        self.chunk_top_k = config.lightrag_query.chunk_top_k
        self.max_async = config.llm.max_async
        self.vlm_timeout = config.llm.vlm_timeout

        # 存储配置
        self.use_external_storage = config.storage.use_external
        self.kv_storage = config.storage.kv_storage
        self.vector_storage = config.storage.vector_storage
        self.graph_storage = config.storage.graph_storage

        logger.info(f"MultiTenantRAGManager initialized (max_instances={max_instances})")

    def _create_llm_func(self, llm_config: Dict):
        """创建 LLM 函数（支持租户配置覆盖 + 速率限制）

        Tenant Configuration Scope:
        - ✅ Can configure: api_key, model, base_url, RateLimiter params (max_async, RPM, TPM)
        - ❌ Cannot configure: LightRAG's llm_model_max_async (always uses RateLimiter's value)

        Returns:
            tuple: (llm_func, actual_max_concurrent) - 函数和实际并发数
        """
        import asyncio

        # 从配置中提取参数（支持租户覆盖）
        model = llm_config.get("model", self.ark_model)
        api_key = llm_config.get("api_key", self.ark_api_key)
        base_url = llm_config.get("base_url", self.ark_base_url)

        # 获取 RateLimiter 参数（租户可配置）
        # 注意：这里的 max_async 是 RateLimiter 的并发控制，不是 LightRAG 的
        requests_per_minute = llm_config.get("requests_per_minute", config.llm.requests_per_minute)
        tokens_per_minute = llm_config.get("tokens_per_minute", config.llm.tokens_per_minute)
        max_concurrent = llm_config.get("max_async", None)  # RateLimiter 的并发数（可选）

        # 创建速率限制器（会自动计算 max_concurrent，除非显式提供）
        rate_limiter = get_rate_limiter(
            service="llm",
            max_concurrent=max_concurrent,  # 租户的 RateLimiter 配置
            requests_per_minute=requests_per_minute,
            tokens_per_minute=tokens_per_minute
        )

        # 获取 rate_limiter 实际使用的并发数（将用于 LightRAG）
        actual_max_concurrent = rate_limiter.max_concurrent

        def llm_model_func(prompt, **kwargs):
            # 估算 tokens（简单估算：字符数 / 3）
            estimated_tokens = len(prompt) // 3 + 500  # 输入 + 预估输出

            # 在同步函数中运行异步速率限制
            async def _call_with_rate_limit():
                # 🔒 CRITICAL: Must acquire semaphore first to limit concurrency
                async with rate_limiter.semaphore:
                    # Then acquire rate limit permission
                    await rate_limiter.rate_limiter.acquire(estimated_tokens)

                    # Finally call the API
                    kwargs['enable_cot'] = False
                    if 'system_prompt' not in kwargs:
                        kwargs['system_prompt'] = self.default_system_prompt
                    return openai_complete_if_cache(
                        model, prompt,
                        api_key=api_key,
                        base_url=base_url,
                    )

            # 如果已在事件循环中，使用 create_task
            # 处理同步/异步调用 - 修复死锁问题
            # 使用线程池执行器避免 asyncio.run_coroutine_threadsafe 的死锁
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _call_with_rate_limit())
                # 超时 = 60s (rate limiter最大等待) + 30s (API调用+缓冲)
                return future.result(timeout=MODEL_CALL_TIMEOUT)

        return llm_model_func, actual_max_concurrent

    def _create_embedding_func(self, embedding_config: Dict):
        """创建 Embedding 函数（支持租户配置覆盖 + 速率限制）"""
        import asyncio

        # 从配置中提取参数（支持租户覆盖）
        model = embedding_config.get("model", self.sf_embedding_model)
        api_key = embedding_config.get("api_key", self.sf_api_key)
        base_url = embedding_config.get("base_url", self.sf_base_url)
        embedding_dim = embedding_config.get("dim", config.embedding.dim)

        # 获取速率限制器
        requests_per_minute = embedding_config.get("requests_per_minute", config.embedding.requests_per_minute)
        tokens_per_minute = embedding_config.get("tokens_per_minute", config.embedding.tokens_per_minute)
        max_concurrent = embedding_config.get("max_async", config.embedding.max_async)

        rate_limiter = get_rate_limiter(
            service="embedding",
            max_concurrent=max_concurrent,
            requests_per_minute=requests_per_minute,
            tokens_per_minute=tokens_per_minute
        )

        # 获取 rate_limiter 实际使用的并发数（将用于 LightRAG）
        actual_max_concurrent = rate_limiter.max_concurrent

        def embedding_func_with_rate_limit(texts):
            # 估算 tokens（所有文本的总字符数 / 3）
            total_chars = sum(len(text) for text in texts)
            estimated_tokens = total_chars // 3

            async def _call_with_rate_limit():
                # 🔒 CRITICAL: Must acquire semaphore first to limit concurrency
                async with rate_limiter.semaphore:
                    # Then acquire rate limit permission
                    await rate_limiter.rate_limiter.acquire(estimated_tokens)

                    # Finally call the API
                    return openai_embed(
                        texts,
                        model=model,
                        api_key=api_key,
                        base_url=base_url
                    )

            # 处理同步/异步调用 - 修复死锁问题
            # 使用线程池执行器避免 asyncio.run_coroutine_threadsafe 的死锁
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _call_with_rate_limit())
                # 超时 = 60s (rate limiter最大等待) + 30s (API调用+缓冲)
                return future.result(timeout=MODEL_CALL_TIMEOUT)

        return EmbeddingFunc(
            embedding_dim=embedding_dim,
            func=embedding_func_with_rate_limit,
        ), actual_max_concurrent

    def _create_rerank_func(self, rerank_config: Dict):
        """创建 Rerank 函数（支持租户配置覆盖 + 速率限制）"""
        import asyncio

        # 从配置中提取参数（支持租户覆盖）
        model = rerank_config.get("model", self.rerank_model)
        api_key = rerank_config.get("api_key", self.sf_api_key)
        base_url = rerank_config.get("base_url", self.sf_base_url)

        if not model:
            return None

        try:
            from lightrag.rerank import cohere_rerank

            # 获取速率限制器
            requests_per_minute = rerank_config.get("requests_per_minute", config.rerank.requests_per_minute)
            tokens_per_minute = rerank_config.get("tokens_per_minute", config.rerank.tokens_per_minute)
            max_concurrent = rerank_config.get("max_async", config.rerank.max_async)

            rate_limiter = get_rate_limiter(
                service="rerank",
                max_concurrent=max_concurrent,
                requests_per_minute=requests_per_minute,
                tokens_per_minute=tokens_per_minute
            )

            def rerank_func_with_rate_limit(query, documents, top_n=None, **kwargs):
                # 接受 **kwargs 以兼容 LightRAG 可能传递的其他参数
                # 估算 tokens（查询 + 所有文档的字符数 / 3）
                total_chars = len(query) + sum(len(doc) for doc in documents)
                estimated_tokens = total_chars // 3

                async def _call_with_rate_limit():
                    # 🔒 CRITICAL: Must acquire semaphore first to limit concurrency
                    async with rate_limiter.semaphore:
                        # Then acquire rate limit permission
                        await rate_limiter.rate_limiter.acquire(estimated_tokens)

                        # Finally call the API
                        return cohere_rerank(
                            query=query,
                            documents=documents,
                            top_n=top_n,
                            model=model,
                            api_key=api_key,
                            base_url=f"{base_url}/rerank"
                        )

                # 处理同步/异步调用 - 修复死锁问题
                # 使用线程池执行器避免 asyncio.run_coroutine_threadsafe 的死锁
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(asyncio.run, _call_with_rate_limit())
                    # 超时 = 60s (rate limiter最大等待) + 30s (API调用+缓冲)
                    return future.result(timeout=MODEL_CALL_TIMEOUT)

            return rerank_func_with_rate_limit

        except ImportError:
            logger.warning("lightrag.rerank not available")
            return None

    def _create_vision_model_func(self, llm_config: Dict):
        """创建 Vision Model 函数（支持租户配置覆盖 + 速率限制）"""
        import aiohttp

        # 从配置中提取参数（支持租户覆盖）
        model = llm_config.get("model", self.ark_model)
        api_key = llm_config.get("api_key", self.ark_api_key)
        base_url = llm_config.get("base_url", self.ark_base_url)
        vlm_timeout = llm_config.get("vlm_timeout", self.vlm_timeout)

        # 获取速率限制器（VLM 使用 LLM 的限制）
        requests_per_minute = llm_config.get("requests_per_minute", config.llm.requests_per_minute)
        tokens_per_minute = llm_config.get("tokens_per_minute", config.llm.tokens_per_minute)
        max_concurrent = llm_config.get("max_async", config.llm.max_async)

        rate_limiter = get_rate_limiter(
            service="llm",  # VLM 共享 LLM 的速率限制
            max_concurrent=max_concurrent,
            requests_per_minute=requests_per_minute,
            tokens_per_minute=tokens_per_minute
        )

        async def seed_vision_model_func(prompt: str, image_data: str, system_prompt: str) -> str:
            """
            使用 VLM 理解图片内容（带速率限制）

            Args:
                prompt: 主要提示词（如"请描述这张图片"）
                image_data: base64 编码的图片数据
                system_prompt: 系统提示词

            Returns:
                str: 图片描述文本
            """
            # 估算 tokens（提示词 + 图片约 200 tokens + 输出 500）
            estimated_tokens = len(prompt) // 3 + 200 + 500

            # 🔒 CRITICAL: Must acquire semaphore first to limit concurrency
            async with rate_limiter.semaphore:
                # Then acquire rate limit permission
                await rate_limiter.rate_limiter.acquire(estimated_tokens)

                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{image_data}"}
                                }
                            ]
                        }
                    ],
                    "max_tokens": 500,
                    "temperature": 0.1
                }

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{base_url}/chat/completions",
                            json=payload,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=vlm_timeout)
                        ) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                logger.error(f"VLM API error ({response.status}): {error_text}")
                                raise Exception(f"VLM API error: {error_text}")

                            result = await response.json()
                            content = result["choices"][0]["message"]["content"]
                            logger.debug(f"VLM response: {content[:100]}...")
                            return content
                except Exception as e:
                    logger.error(f"Failed to call VLM API: {e}")
                    raise

        return seed_vision_model_func

    async def get_instance(self, tenant_id: str) -> LightRAG:
        """
        获取指定租户的 LightRAG 实例（懒加载）

        Args:
            tenant_id: 租户 ID（作为 workspace）

        Returns:
            LightRAG: 该租户的 LightRAG 实例
        """
        # 验证 tenant_id
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError(f"Invalid tenant_id: {tenant_id}")

        # 检查缓存
        if tenant_id in self._instances:
            logger.debug(f"Reusing cached instance for tenant: {tenant_id}")
            return self._instances[tenant_id]

        # 检查实例数量限制
        if len(self._instances) >= self.max_instances:
            # 清理最旧的实例（简单 FIFO 策略）
            oldest_tenant = next(iter(self._instances))
            logger.info(f"Instance pool full, removing oldest tenant: {oldest_tenant}")
            del self._instances[oldest_tenant]

        # 创建新实例
        logger.info(f"Creating new LightRAG instance for tenant: {tenant_id}")
        instance = await self._create_instance(tenant_id)
        self._instances[tenant_id] = instance

        return instance

    async def _create_instance(self, tenant_id: str) -> LightRAG:
        """
        为指定租户创建新的 LightRAG 实例

        Args:
            tenant_id: 租户 ID

        Returns:
            LightRAG: 新创建的实例
        """
        # 🆕 加载租户配置并与全局配置合并
        from src.tenant_config import get_tenant_config_manager
        config_manager = get_tenant_config_manager()
        tenant_config = config_manager.get(tenant_id)
        merged_config = config_manager.merge_with_global(tenant_config)

        # 记录配置来源
        if tenant_config:
            logger.info(f"[{tenant_id}] Using tenant-specific config")
        else:
            logger.debug(f"[{tenant_id}] Using global config (no tenant config found)")

        # 准备租户专属函数（使用合并后的配置）
        llm_func, llm_max_concurrent = self._create_llm_func(merged_config["llm"])
        embedding_func, embedding_max_concurrent = self._create_embedding_func(merged_config["embedding"])
        rerank_func = self._create_rerank_func(merged_config["rerank"])
        vision_func = self._create_vision_model_func(merged_config["llm"])  # 🆕 创建 VLM 函数

        # 准备存储配置
        storage_kwargs = {}
        if self.use_external_storage:
            # 直接传递配置值，支持所有存储类型（Redis, Qdrant, Memgraph, PostgreSQL, Neo4j 等）
            storage_kwargs["kv_storage"] = self.kv_storage
            storage_kwargs["vector_storage"] = self.vector_storage
            storage_kwargs["graph_storage"] = self.graph_storage
            storage_kwargs["doc_status_storage"] = "RedisDocStatusStorage"  # 🆕 使用 Redis 存储 doc_status
            logger.info(f"[{tenant_id}] Using external storage: KV={self.kv_storage}, Vector={self.vector_storage}, Graph={self.graph_storage}, DocStatus=RedisDocStatusStorage")

        # 创建 LightRAG 实例
        # CRITICAL: llm_model_max_async & embedding_func_max_async MUST match RateLimiter's concurrent value
        # This ensures LightRAG's worker pool doesn't bypass rate limiting
        instance = LightRAG(
            working_dir="./rag_local_storage",  # 共享工作目录
            workspace=tenant_id,  # 关键：使用 tenant_id 作为 workspace
            llm_model_func=llm_func,
            embedding_func=embedding_func,
            llm_model_max_async=llm_max_concurrent,  # 🔒 Force use RateLimiter's value (not tenant-controllable)
            embedding_func_max_async=embedding_max_concurrent,  # 🔒 Force use RateLimiter's value
            **storage_kwargs
        )

        logger.info(
            f"[{tenant_id}] LightRAG instance created: "
            f"LLM workers={llm_max_concurrent}, Embedding workers={embedding_max_concurrent} "
            f"(enforced by RateLimiter, tenant cannot override)"
        )

        # 初始化存储
        await instance.initialize_storages()

        # 初始化 Pipeline Status（多租户模式必需）
        from lightrag.kg.shared_storage import initialize_pipeline_status
        await initialize_pipeline_status()

        # 配置 Rerank（如果启用）
        if rerank_func:
            instance.rerank_model_func = rerank_func

        # 🆕 附加 Vision Model 函数（供 RAG-Anything 使用）
        instance.vision_model_func = vision_func

        logger.info(f"✓ LightRAG instance created for tenant: {tenant_id} (workspace={tenant_id}, VLM enabled)")
        return instance

    def remove_instance(self, tenant_id: str) -> bool:
        """
        手动移除指定租户的实例（释放内存）

        Args:
            tenant_id: 租户 ID

        Returns:
            bool: 是否成功移除
        """
        if tenant_id in self._instances:
            del self._instances[tenant_id]
            logger.info(f"Removed instance for tenant: {tenant_id}")
            return True
        return False

    def get_stats(self) -> dict:
        """获取实例池统计信息"""
        return {
            "total_instances": len(self._instances),
            "max_instances": self.max_instances,
            "tenants": list(self._instances.keys())
        }


# 全局单例管理器
_manager: Optional[MultiTenantRAGManager] = None


def get_multi_tenant_manager() -> MultiTenantRAGManager:
    """获取全局多租户管理器（单例）"""
    global _manager
    if _manager is None:
        _manager = MultiTenantRAGManager()
    return _manager


async def get_tenant_lightrag(tenant_id: str) -> LightRAG:
    """
    便捷函数：获取指定租户的 LightRAG 实例

    Args:
        tenant_id: 租户 ID

    Returns:
        LightRAG: 该租户的实例
    """
    manager = get_multi_tenant_manager()
    return await manager.get_instance(tenant_id)