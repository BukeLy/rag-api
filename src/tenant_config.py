"""
租户配置管理器

支持本地文件存储和 Redis 存储的租户配置热重载，无需重启服务。
"""

import os
import json
import redis
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from src.logger import logger
from src.config import config


class TenantConfigModel(BaseModel):
    """租户配置模型"""

    tenant_id: str = Field(..., description="租户 ID")

    # LLM 配置（可选，缺失字段使用全局配置）
    llm_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="LLM 配置覆盖",
        example={
            "model": "gpt-4",
            "api_key": "sk-xxx",
            "base_url": "https://api.openai.com/v1"
        }
    )

    # Embedding 配置（可选）
    embedding_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Embedding 配置覆盖",
        example={
            "model": "Qwen/Qwen3-Embedding-0.6B",
            "api_key": "sk-yyy",
            "base_url": "https://api.siliconflow.cn/v1",
            "dim": 1024
        }
    )

    # Rerank 配置（可选）
    rerank_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Rerank 配置覆盖"
    )

    # DeepSeek-OCR 配置（可选）
    ds_ocr_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="DeepSeek-OCR 配置覆盖",
        example={
            "api_key": "sk-xxx",
            "base_url": "https://api.siliconflow.cn/v1",
            "model": "deepseek-ai/DeepSeek-OCR",
            "timeout": 60
        }
    )

    # MinerU 配置（可选）
    mineru_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="MinerU 配置覆盖",
        example={
            "api_token": "your_token",
            "base_url": "https://mineru.net",
            "model_version": "vlm",
            "timeout": 60
        }
    )

    # 🆕 Custom Prompts 配置（可选）
    custom_prompts: Optional[Dict[str, Any]] = Field(
        default=None,
        description="LightRAG 自定义 Prompts 覆盖",
        example={
            "entity_extraction_system_prompt": "你的自定义 system prompt...",
            "entity_extraction_user_prompt": "你的自定义 user prompt...",
            "entity_continue_extraction_user_prompt": "你的自定义 continue prompt...",
            "entity_extraction_examples": ["示例1", "示例2"],
            "entity_types": ["product", "feature", "error_code", "configuration"]
        }
    )

    # 元数据
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)


class TenantConfigManager:
    """
    租户配置管理器

    支持两种存储方式：
    - local: 本地 JSON 文件存储（开发/测试环境）
    - redis: Redis 存储（生产环境）

    注意：租户配置不会降级到全局配置，不存在时返回 None
    """

    def __init__(
        self,
        storage_type: str = "local",
        local_storage_dir: str = "./tenant_configs",
        redis_uri: str = None
    ):
        """
        初始化租户配置管理器

        Args:
            storage_type: 存储类型 ("local" 或 "redis")
            local_storage_dir: 本地存储目录（storage_type="local" 时使用）
            redis_uri: Redis 连接 URI（storage_type="redis" 时使用，默认从全局配置读取）
        """
        self.storage_type = storage_type

        if storage_type == "local":
            # 本地文件存储
            self.local_storage_dir = local_storage_dir
            import os
            os.makedirs(self.local_storage_dir, exist_ok=True)
            logger.info(f"TenantConfigManager initialized (storage=local, dir={self.local_storage_dir})")

        elif storage_type == "redis":
            # Redis 存储
            self.redis_uri = redis_uri or config.storage.redis_uri
            try:
                self.redis_client = redis.from_url(self.redis_uri, decode_responses=True)
                self.redis_client.ping()
                logger.info(f"TenantConfigManager initialized (storage=redis, uri={self.redis_uri})")
            except Exception as e:
                raise ConnectionError(
                    f"Failed to connect to Redis ({self.redis_uri}): {e}. "
                    f"For local development, use storage_type='local' instead."
                )
        else:
            raise ValueError(f"Invalid storage_type: {storage_type}. Must be 'local' or 'redis'.")

    def get(self, tenant_id: str) -> Optional[TenantConfigModel]:
        """
        获取租户配置

        Args:
            tenant_id: 租户 ID

        Returns:
            TenantConfigModel: 租户配置（如果存在）
            None: 租户配置不存在

        注意：不会降级到全局配置，调用方需自行处理 None 情况
        """
        try:
            if self.storage_type == "local":
                # 本地文件存储
                config_file = f"{self.local_storage_dir}/{tenant_id}.json"
                if os.path.exists(config_file):
                    with open(config_file, "r", encoding="utf-8") as f:
                        config_dict = json.load(f)
                    logger.debug(f"[{tenant_id}] Loaded config from local file")
                    return TenantConfigModel(**config_dict)
                else:
                    logger.debug(f"[{tenant_id}] No tenant config found")
                    return None

            elif self.storage_type == "redis":
                # Redis 存储
                config_json = self.redis_client.get(f"tenant:config:{tenant_id}")
                if config_json:
                    config_dict = json.loads(config_json)
                    logger.debug(f"[{tenant_id}] Loaded config from Redis")
                    return TenantConfigModel(**config_dict)
                else:
                    logger.debug(f"[{tenant_id}] No tenant config found")
                    return None

        except Exception as e:
            logger.error(f"[{tenant_id}] Failed to load config: {e}")
            return None

    def set(self, tenant_id: str, config: TenantConfigModel) -> bool:
        """
        更新租户配置

        Args:
            tenant_id: 租户 ID
            config: 租户配置

        Returns:
            bool: 是否成功
        """
        try:
            # 更新时间戳
            config.tenant_id = tenant_id
            config.updated_at = datetime.utcnow()
            if not config.created_at:
                config.created_at = config.updated_at

            # 序列化为 JSON
            config_json = config.model_dump_json(indent=2)

            if self.storage_type == "local":
                # 本地文件存储
                config_file = f"{self.local_storage_dir}/{tenant_id}.json"
                with open(config_file, "w", encoding="utf-8") as f:
                    f.write(config_json)
                logger.info(f"[{tenant_id}] Config saved to local file")
                return True

            elif self.storage_type == "redis":
                # Redis 存储（永久保存，无 TTL）
                self.redis_client.set(
                    f"tenant:config:{tenant_id}",
                    config_json
                )
                logger.info(f"[{tenant_id}] Config saved to Redis (persistent)")
                return True

        except Exception as e:
            logger.error(f"[{tenant_id}] Failed to update config: {e}")
            return False

    def delete(self, tenant_id: str) -> bool:
        """
        删除租户配置

        Args:
            tenant_id: 租户 ID

        Returns:
            bool: 是否成功
        """
        try:
            if self.storage_type == "local":
                # 本地文件存储
                config_file = f"{self.local_storage_dir}/{tenant_id}.json"
                if os.path.exists(config_file):
                    os.remove(config_file)
                    logger.info(f"[{tenant_id}] Config file deleted")
                    return True
                else:
                    logger.warning(f"[{tenant_id}] Config file not found")
                    return False

            elif self.storage_type == "redis":
                # Redis 存储
                deleted_count = self.redis_client.delete(f"tenant:config:{tenant_id}")
                if deleted_count > 0:
                    logger.info(f"[{tenant_id}] Config deleted from Redis")
                    return True
                else:
                    logger.warning(f"[{tenant_id}] Config not found in Redis")
                    return False

        except Exception as e:
            logger.error(f"[{tenant_id}] Failed to delete config: {e}")
            return False

    def refresh(self, tenant_id: str) -> Optional[TenantConfigModel]:
        """
        强制刷新配置（对于 Redis 重新读取，对于 local 重新加载文件）

        Args:
            tenant_id: 租户 ID

        Returns:
            TenantConfigModel: 刷新后的配置（如果存在）
        """
        logger.info(f"[{tenant_id}] Forcing config refresh")
        return self.get(tenant_id)

    def merge_with_global(self, tenant_config: Optional[TenantConfigModel]) -> Dict[str, Any]:
        """
        将租户配置与全局配置合并

        Args:
            tenant_config: 租户配置（可选）

        Returns:
            Dict: 合并后的最终配置
        """
        merged = {
            "llm": self._merge_llm_config(tenant_config),
            "embedding": self._merge_embedding_config(tenant_config),
            "rerank": self._merge_rerank_config(tenant_config),
            "ds_ocr": self._merge_ds_ocr_config(tenant_config),
            "mineru": self._merge_mineru_config(tenant_config),
        }
        return merged

    def _merge_llm_config(self, tenant_config: Optional[TenantConfigModel]) -> Dict[str, Any]:
        """合并 LLM 配置（包含速率限制）

        Note: max_async 控制 RateLimiter 的并发数，不直接控制 LightRAG 的 llm_model_max_async。
        LightRAG 的并发数会在 multi_tenant.py 中被强制设置为 RateLimiter 的实际值，确保一致性。
        """
        base = {
            "model": config.llm.model,
            "api_key": config.llm.api_key,
            "base_url": config.llm.base_url,
            "timeout": config.llm.timeout,
            "max_async": config.llm.max_async,  # RateLimiter 的并发数（可选，未设置时自动计算）
            "vlm_timeout": config.llm.vlm_timeout,
            # 速率限制配置
            "requests_per_minute": config.llm.requests_per_minute,
            "tokens_per_minute": config.llm.tokens_per_minute,
        }

        if tenant_config and tenant_config.llm_config:
            base.update(tenant_config.llm_config)

        return base

    def _merge_embedding_config(self, tenant_config: Optional[TenantConfigModel]) -> Dict[str, Any]:
        """合并 Embedding 配置（包含速率限制）

        Note: max_async 控制 RateLimiter 的并发数（可选，未设置时基于 TPM/RPM 自动计算）。
        """
        base = {
            "model": config.embedding.model,
            "api_key": config.embedding.api_key,
            "base_url": config.embedding.base_url,
            "dim": config.embedding.dim,
            # 速率限制配置
            "requests_per_minute": config.embedding.requests_per_minute,
            "tokens_per_minute": config.embedding.tokens_per_minute,
            "max_async": config.embedding.max_async,  # RateLimiter 的并发数（可选）
            "timeout": config.embedding.timeout,
        }

        if tenant_config and tenant_config.embedding_config:
            base.update(tenant_config.embedding_config)

        return base

    def _merge_rerank_config(self, tenant_config: Optional[TenantConfigModel]) -> Dict[str, Any]:
        """合并 Rerank 配置（包含速率限制）

        Note: max_async 控制 RateLimiter 的并发数（可选，未设置时基于 TPM/RPM 自动计算）。
        """
        base = {
            "model": config.rerank.model,
            "api_key": config.rerank.api_key,
            "base_url": config.rerank.base_url,
            # 速率限制配置
            "requests_per_minute": config.rerank.requests_per_minute,
            "tokens_per_minute": config.rerank.tokens_per_minute,
            "max_async": config.rerank.max_async,  # RateLimiter 的并发数（可选）
            "timeout": config.rerank.timeout,
        }

        if tenant_config and tenant_config.rerank_config:
            base.update(tenant_config.rerank_config)

        return base

    def _merge_ds_ocr_config(self, tenant_config: Optional[TenantConfigModel]) -> Dict[str, Any]:
        """合并 DeepSeek-OCR 配置（包含速率限制）"""
        base = {
            "api_key": config.ds_ocr.api_key,
            "base_url": config.ds_ocr.base_url,
            "model": config.ds_ocr.model,
            "timeout": config.ds_ocr.timeout,
            "max_tokens": config.ds_ocr.max_tokens,
            "dpi": config.ds_ocr.dpi,
            "default_mode": config.ds_ocr.default_mode,
            "fallback_enabled": config.ds_ocr.fallback_enabled,
            "fallback_mode": config.ds_ocr.fallback_mode,
            "min_output_threshold": config.ds_ocr.min_output_threshold,
            # 速率限制配置
            "requests_per_minute": config.ds_ocr.requests_per_minute,
            "tokens_per_minute": config.ds_ocr.tokens_per_minute,
            "max_async": config.ds_ocr.max_async,
        }

        if tenant_config and tenant_config.ds_ocr_config:
            base.update(tenant_config.ds_ocr_config)

        return base

    def _merge_mineru_config(self, tenant_config: Optional[TenantConfigModel]) -> Dict[str, Any]:
        """合并 MinerU 配置"""
        base = {
            "api_token": os.getenv("MINERU_API_TOKEN", ""),
            "base_url": os.getenv("MINERU_API_BASE_URL", "https://mineru.net"),
            "model_version": os.getenv("MINERU_MODEL_VERSION", "vlm"),
            "timeout": int(os.getenv("MINERU_HTTP_TIMEOUT", "60")),
            "max_concurrent_requests": int(os.getenv("MINERU_MAX_CONCURRENT_REQUESTS", "5")),
            "requests_per_minute": int(os.getenv("MINERU_REQUESTS_PER_MINUTE", "60")),
            "retry_max_attempts": int(os.getenv("MINERU_RETRY_MAX_ATTEMPTS", "3")),
            "poll_timeout": int(os.getenv("MINERU_POLL_TIMEOUT", "600")),
        }

        if tenant_config and tenant_config.mineru_config:
            base.update(tenant_config.mineru_config)

        return base


# 全局单例管理器
_tenant_config_manager: Optional[TenantConfigManager] = None


def get_tenant_config_manager() -> TenantConfigManager:
    """
    获取全局租户配置管理器（单例）

    存储类型通过环境变量 TENANT_CONFIG_STORAGE 控制：
    - "local": 本地文件存储（默认，适合开发/测试）
    - "redis": Redis 存储（适合生产环境）
    """
    global _tenant_config_manager
    if _tenant_config_manager is None:
        # 从环境变量读取存储类型
        storage_type = os.getenv("TENANT_CONFIG_STORAGE", "local")
        storage_type = storage_type.lower()

        if storage_type == "local":
            local_dir = os.getenv("TENANT_CONFIG_DIR", "./tenant_configs")
            _tenant_config_manager = TenantConfigManager(
                storage_type="local",
                local_storage_dir=local_dir
            )
        elif storage_type == "redis":
            _tenant_config_manager = TenantConfigManager(
                storage_type="redis"
            )
        else:
            # 默认使用本地存储
            logger.warning(f"Invalid TENANT_CONFIG_STORAGE={storage_type}, using 'local'")
            _tenant_config_manager = TenantConfigManager(storage_type="local")

    return _tenant_config_manager
