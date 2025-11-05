"""
Configuration Management Module

Centralized configuration management using Pydantic Settings.
All environment variables are loaded and validated through this module.

重构日期: 2025-01-04
重构原因: 统一配置管理，从服务商导向改为功能导向命名
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


# ==================== LLM Configuration ====================

class LLMConfig(BaseSettings):
    """LLM Configuration"""

    api_key: str = Field(..., description="LLM API Key")
    base_url: str = Field(..., description="LLM API Base URL")
    model: str = Field(default="seed-1-6-250615", description="LLM Model Name")
    provider: str = Field(default="ark", description="LLM Provider (ark/openai/claude)")
    vlm_timeout: int = Field(default=120, description="VLM Image Understanding Timeout (seconds)")
    timeout: int = Field(default=60, description="General LLM Timeout (seconds)")
    max_async: int = Field(default=16, description="Maximum Concurrent LLM Requests")

    class Config:
        env_prefix = "LLM_"
        env_file = ".env"
        extra = "ignore"


# ==================== Embedding Configuration ====================

class EmbeddingConfig(BaseSettings):
    """Embedding Configuration"""

    api_key: str = Field(..., description="Embedding API Key")
    base_url: str = Field(..., description="Embedding API Base URL")
    model: str = Field(
        default="Qwen/Qwen3-Embedding-0.6B",
        description="Embedding Model Name"
    )
    dim: int = Field(
        default=1024,
        description="Embedding Dimension (Must match model output dimension!)"
    )
    provider: str = Field(
        default="siliconflow",
        description="Embedding Provider (siliconflow/openai)"
    )

    class Config:
        env_prefix = "EMBEDDING_"
        env_file = ".env"
        extra = "ignore"


# ==================== Rerank Configuration ====================

class RerankConfig(BaseSettings):
    """Rerank Configuration"""

    api_key: str = Field(..., description="Rerank API Key")
    base_url: str = Field(..., description="Rerank API Base URL")
    model: str = Field(
        default="Qwen/Qwen3-Reranker-8B",
        description="Rerank Model Name"
    )
    provider: str = Field(
        default="siliconflow",
        description="Rerank Provider (siliconflow/openai)"
    )

    class Config:
        env_prefix = "RERANK_"
        env_file = ".env"
        extra = "ignore"


# ==================== Storage Configuration ====================

class StorageConfig(BaseSettings):
    """External Storage Configuration"""

    use_external: bool = Field(
        default=True,
        description="Use External Storage",
        alias="USE_EXTERNAL_STORAGE"
    )
    kv_storage: str = Field(
        default="RedisKVStorage",
        description="KV Storage Type",
        alias="KV_STORAGE"
    )
    vector_storage: str = Field(
        default="QdrantStorage",
        description="Vector Storage Type",
        alias="VECTOR_STORAGE"
    )
    graph_storage: str = Field(
        default="MemgraphStorage",
        description="Graph Storage Type",
        alias="GRAPH_STORAGE"
    )
    redis_uri: str = Field(
        default="redis://dragonflydb:6379/0",
        description="Redis Connection URI",
        alias="REDIS_URI"
    )
    qdrant_url: str = Field(
        default="http://qdrant:6333",
        description="Qdrant Connection URL",
        alias="QDRANT_URL"
    )
    memgraph_uri: str = Field(
        default="bolt://memgraph:7687",
        description="Memgraph Connection URI",
        alias="MEMGRAPH_URI"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"
        populate_by_name = True


# ==================== LightRAG Query Configuration ====================

class LightRAGQueryConfig(BaseSettings):
    """LightRAG Query Optimization Parameters"""

    top_k: int = Field(default=20, description="Number of Entities/Relations to Retrieve", alias="TOP_K")
    chunk_top_k: int = Field(default=10, description="Number of Text Chunks to Retrieve", alias="CHUNK_TOP_K")
    max_entity_tokens: int = Field(default=6000, description="Max Entity Context Tokens", alias="MAX_ENTITY_TOKENS")
    max_relation_tokens: int = Field(default=8000, description="Max Relation Context Tokens", alias="MAX_RELATION_TOKENS")
    max_total_tokens: int = Field(default=30000, description="Max Total Tokens", alias="MAX_TOTAL_TOKENS")
    max_parallel_insert: int = Field(default=2, description="Max Parallel Document Inserts", alias="MAX_PARALLEL_INSERT")
    max_source_ids_per_entity: int = Field(default=300, description="Max Source IDs per Entity", alias="MAX_SOURCE_IDS_PER_ENTITY")
    max_source_ids_per_relation: int = Field(default=300, description="Max Source IDs per Relation", alias="MAX_SOURCE_IDS_PER_RELATION")
    source_ids_limit_method: str = Field(default="FIFO", description="Source IDs Limit Method", alias="SOURCE_IDS_LIMIT_METHOD")
    max_file_paths: int = Field(default=100, description="Max File Paths", alias="MAX_FILE_PATHS")

    class Config:
        env_file = ".env"
        extra = "ignore"
        populate_by_name = True


# ==================== Multi-Tenant Configuration ====================

class MultiTenantConfig(BaseSettings):
    """Multi-Tenant Configuration"""

    max_tenant_instances: int = Field(
        default=50,
        description="Maximum Cached Tenant Instances (LRU)",
        alias="MAX_TENANT_INSTANCES"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"
        populate_by_name = True


# ==================== Tenant Configuration (for override) ====================

class TenantConfig:
    """Tenant Configuration (Used for Overriding Global Config)"""

    def __init__(
        self,
        llm_config: Optional[dict] = None,
        embedding_config: Optional[dict] = None,
        rerank_config: Optional[dict] = None,
        quota_daily_queries: int = 1000,
        quota_storage_mb: int = 1000,
        status: str = "active"
    ):
        self.llm_config = llm_config
        self.embedding_config = embedding_config
        self.rerank_config = rerank_config
        self.quota_daily_queries = quota_daily_queries
        self.quota_storage_mb = quota_storage_mb
        self.status = status

    def dict(self):
        """Convert to dictionary"""
        return {
            "llm_config": self.llm_config,
            "embedding_config": self.embedding_config,
            "rerank_config": self.rerank_config,
            "quota_daily_queries": self.quota_daily_queries,
            "quota_storage_mb": self.quota_storage_mb,
            "status": self.status
        }


# ==================== Application Configuration ====================

class AppConfig:
    """Application Root Configuration"""

    def __init__(self):
        """Initialize all configuration classes"""
        self.llm = LLMConfig()
        self.embedding = EmbeddingConfig()
        self.rerank = RerankConfig()
        self.storage = StorageConfig()
        self.lightrag_query = LightRAGQueryConfig()
        self.multi_tenant = MultiTenantConfig()

    def validate(self) -> None:
        """Validate Configuration Integrity"""
        # Check required fields
        if not self.llm.api_key:
            raise ValueError("LLM_API_KEY is required")
        if not self.embedding.api_key:
            raise ValueError("EMBEDDING_API_KEY is required")
        if not self.rerank.api_key:
            raise ValueError("RERANK_API_KEY is required")

        # Check embedding dimension
        valid_dims = [512, 1024, 1536, 2048, 4096]
        if self.embedding.dim not in valid_dims:
            raise ValueError(
                f"EMBEDDING_DIM must be one of {valid_dims}, got {self.embedding.dim}. "
                f"Please ensure it matches your embedding model output dimension."
            )

        # Check provider values
        valid_llm_providers = ["ark", "openai", "claude", "anthropic"]
        if self.llm.provider not in valid_llm_providers:
            raise ValueError(
                f"LLM_PROVIDER must be one of {valid_llm_providers}, got {self.llm.provider}"
            )

        valid_embedding_providers = ["siliconflow", "openai"]
        if self.embedding.provider not in valid_embedding_providers:
            raise ValueError(
                f"EMBEDDING_PROVIDER must be one of {valid_embedding_providers}, got {self.embedding.provider}"
            )

    def print_summary(self) -> None:
        """Print Configuration Summary (for debugging)"""
        print("=" * 60)
        print("Configuration Summary")
        print("=" * 60)
        print(f"LLM Provider: {self.llm.provider}")
        print(f"LLM Model: {self.llm.model}")
        print(f"Embedding Provider: {self.embedding.provider}")
        print(f"Embedding Model: {self.embedding.model}")
        print(f"Embedding Dimension: {self.embedding.dim}")
        print(f"Rerank Provider: {self.rerank.provider}")
        print(f"Rerank Model: {self.rerank.model}")
        print(f"Storage - KV: {self.storage.kv_storage}")
        print(f"Storage - Vector: {self.storage.vector_storage}")
        print(f"Storage - Graph: {self.storage.graph_storage}")
        print(f"Max Tenant Instances: {self.multi_tenant.max_tenant_instances}")
        print("=" * 60)


# ==================== Global Configuration Instance ====================

# Initialize global config instance
config = AppConfig()

# Validate config on module import (fail fast)
try:
    config.validate()
    print("✅ Configuration loaded and validated successfully")
except Exception as e:
    print(f"❌ Configuration validation failed: {e}")
    print("Please check your .env file and ensure all required variables are set correctly.")
    # In production, you might want to raise the exception instead
    # raise


# ==================== Utility Functions ====================

def get_config() -> AppConfig:
    """Get Global Configuration Instance"""
    return config


def reload_config() -> AppConfig:
    """Reload Configuration (useful for testing)"""
    global config
    config = AppConfig()
    config.validate()
    return config


# Example usage (for testing)
if __name__ == "__main__":
    config.print_summary()
