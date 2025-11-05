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
        """创建 LLM 函数（支持租户配置覆盖）"""
        # 从配置中提取参数（支持租户覆盖）
        model = llm_config.get("model", self.ark_model)
        api_key = llm_config.get("api_key", self.ark_api_key)
        base_url = llm_config.get("base_url", self.ark_base_url)

        def llm_model_func(prompt, **kwargs):
            kwargs['enable_cot'] = False
            if 'system_prompt' not in kwargs:
                kwargs['system_prompt'] = self.default_system_prompt
            return openai_complete_if_cache(
                model, prompt,
                api_key=api_key,
                base_url=base_url,
                **kwargs
            )
        return llm_model_func

    def _create_embedding_func(self, embedding_config: Dict):
        """创建 Embedding 函数（支持租户配置覆盖）"""
        # 从配置中提取参数（支持租户覆盖）
        model = embedding_config.get("model", self.sf_embedding_model)
        api_key = embedding_config.get("api_key", self.sf_api_key)
        base_url = embedding_config.get("base_url", self.sf_base_url)
        embedding_dim = embedding_config.get("dim", config.embedding.dim)

        return EmbeddingFunc(
            embedding_dim=embedding_dim,
            func=lambda texts: openai_embed(
                texts,
                model=model,
                api_key=api_key,
                base_url=base_url
            ),
        )

    def _create_rerank_func(self, rerank_config: Dict):
        """创建 Rerank 函数（支持租户配置覆盖）"""
        # 从配置中提取参数（支持租户覆盖）
        model = rerank_config.get("model", self.rerank_model)
        api_key = rerank_config.get("api_key", self.sf_api_key)
        base_url = rerank_config.get("base_url", self.sf_base_url)

        if not model:
            return None

        try:
            from lightrag.rerank import cohere_rerank
            from functools import partial

            return partial(
                cohere_rerank,
                model=model,
                api_key=api_key,
                base_url=f"{base_url}/rerank"
            )
        except ImportError:
            logger.warning("lightrag.rerank not available")
            return None

    def _create_vision_model_func(self, llm_config: Dict):
        """创建 Vision Model 函数（支持租户配置覆盖）"""
        import aiohttp

        # 从配置中提取参数（支持租户覆盖）
        model = llm_config.get("model", self.ark_model)
        api_key = llm_config.get("api_key", self.ark_api_key)
        base_url = llm_config.get("base_url", self.ark_base_url)
        vlm_timeout = llm_config.get("vlm_timeout", self.vlm_timeout)

        async def seed_vision_model_func(prompt: str, image_data: str, system_prompt: str) -> str:
            """
            使用 VLM 理解图片内容

            Args:
                prompt: 主要提示词（如"请描述这张图片"）
                image_data: base64 编码的图片数据
                system_prompt: 系统提示词

            Returns:
                str: 图片描述文本
            """
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
        llm_func = self._create_llm_func(merged_config["llm"])
        embedding_func = self._create_embedding_func(merged_config["embedding"])
        rerank_func = self._create_rerank_func(merged_config["rerank"])
        vision_func = self._create_vision_model_func(merged_config["llm"])  # 🆕 创建 VLM 函数

        # 准备存储配置
        storage_kwargs = {}
        if self.use_external_storage:
            # 直接传递配置值，支持所有存储类型（Redis, Qdrant, Memgraph, PostgreSQL, Neo4j 等）
            storage_kwargs["kv_storage"] = self.kv_storage
            storage_kwargs["vector_storage"] = self.vector_storage
            storage_kwargs["graph_storage"] = self.graph_storage
            logger.info(f"[{tenant_id}] Using external storage: KV={self.kv_storage}, Vector={self.vector_storage}, Graph={self.graph_storage}")

        # 创建 LightRAG 实例（使用 workspace 隔离）
        instance = LightRAG(
            working_dir="./rag_local_storage",  # 共享工作目录
            workspace=tenant_id,  # 关键：使用 tenant_id 作为 workspace
            llm_model_func=llm_func,
            embedding_func=embedding_func,
            llm_model_max_async=self.max_async,
            **storage_kwargs
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
