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

        # 共享配置（从环境变量读取）
        self.ark_api_key = os.getenv("ARK_API_KEY")
        self.ark_base_url = os.getenv("ARK_BASE_URL")
        self.ark_model = os.getenv("ARK_MODEL", "seed-1-6-250615")

        self.sf_api_key = os.getenv("SF_API_KEY")
        self.sf_base_url = os.getenv("SF_BASE_URL")
        self.sf_embedding_model = os.getenv("SF_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")

        self.rerank_model = os.getenv("RERANK_MODEL", "")

        # 性能配置
        self.top_k = int(os.getenv("TOP_K", "20"))
        self.chunk_top_k = int(os.getenv("CHUNK_TOP_K", "10"))
        self.max_async = int(os.getenv("MAX_ASYNC", "8"))

        # 存储配置
        self.use_external_storage = os.getenv("USE_EXTERNAL_STORAGE", "false").lower() == "true"
        self.kv_storage = os.getenv("KV_STORAGE", "JsonKVStorage")
        self.vector_storage = os.getenv("VECTOR_STORAGE", "NanoVectorDB")
        self.graph_storage = os.getenv("GRAPH_STORAGE", "NetworkXStorage")

        logger.info(f"MultiTenantRAGManager initialized (max_instances={max_instances})")

    def _create_llm_func(self):
        """创建共享的 LLM 函数"""
        def llm_model_func(prompt, **kwargs):
            kwargs['enable_cot'] = False
            if 'system_prompt' not in kwargs:
                kwargs['system_prompt'] = self.default_system_prompt
            return openai_complete_if_cache(
                self.ark_model, prompt,
                api_key=self.ark_api_key,
                base_url=self.ark_base_url,
                **kwargs
            )
        return llm_model_func

    def _create_embedding_func(self):
        """创建共享的 Embedding 函数"""
        # 从环境变量读取维度，避免硬编码
        embedding_dim = int(os.getenv("EMBEDDING_DIM", "1024"))

        return EmbeddingFunc(
            embedding_dim=embedding_dim,
            func=lambda texts: openai_embed(
                texts,
                model=self.sf_embedding_model,
                api_key=self.sf_api_key,
                base_url=self.sf_base_url
            ),
        )

    def _create_rerank_func(self):
        """创建共享的 Rerank 函数（如果配置）"""
        if not self.rerank_model:
            return None

        try:
            from lightrag.rerank import cohere_rerank
            from functools import partial

            return partial(
                cohere_rerank,
                model=self.rerank_model,
                api_key=self.sf_api_key,
                base_url=f"{self.sf_base_url}/rerank"
            )
        except ImportError:
            logger.warning("lightrag.rerank not available")
            return None

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
        # 准备共享函数
        llm_func = self._create_llm_func()
        embedding_func = self._create_embedding_func()
        rerank_func = self._create_rerank_func()

        # 准备存储配置
        storage_kwargs = {}
        if self.use_external_storage:
            if self.kv_storage == "RedisKVStorage":
                storage_kwargs["kv_storage"] = "RedisKVStorage"
            if self.vector_storage == "PGVectorStorage":
                storage_kwargs["vector_storage"] = "PGVectorStorage"
            if self.graph_storage == "Neo4JStorage":
                storage_kwargs["graph_storage"] = "Neo4JStorage"

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

        logger.info(f"✓ LightRAG instance created for tenant: {tenant_id} (workspace={tenant_id})")
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
