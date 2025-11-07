"""
租户配置管理 API

支持租户级配置的 CRUD 操作和热重载。
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from src.tenant_config import (
    get_tenant_config_manager,
    TenantConfigModel
)
from src.logger import logger


router = APIRouter(prefix="/tenants", tags=["tenant-config"])


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    llm_config: Optional[Dict[str, Any]] = None
    embedding_config: Optional[Dict[str, Any]] = None
    rerank_config: Optional[Dict[str, Any]] = None
    ds_ocr_config: Optional[Dict[str, Any]] = None  # 🆕 DeepSeek-OCR 配置
    mineru_config: Optional[Dict[str, Any]] = None  # 🆕 MinerU 配置


class ConfigResponse(BaseModel):
    """配置响应"""
    tenant_id: str
    llm_config: Optional[Dict[str, Any]]
    embedding_config: Optional[Dict[str, Any]]
    rerank_config: Optional[Dict[str, Any]]
    ds_ocr_config: Optional[Dict[str, Any]]  # 🆕 DeepSeek-OCR 配置
    mineru_config: Optional[Dict[str, Any]]  # 🆕 MinerU 配置
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    merged_config: Optional[Dict[str, Any]] = None


def mask_api_key(key: Optional[str]) -> Optional[str]:
    """
    脱敏 API Key

    Args:
        key: API Key

    Returns:
        str: 脱敏后的 Key（如 sk-***cdef）
    """
    if not key:
        return None
    if len(key) <= 8:
        return "***"
    return key[:3] + "***" + key[-4:]


def mask_config(config_dict: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    脱敏配置中的 API Key / API Token

    Args:
        config_dict: 配置字典

    Returns:
        Dict: 脱敏后的配置
    """
    if not config_dict:
        return None

    masked = config_dict.copy()
    # 脱敏 api_key（LLM, Embedding, Rerank, DeepSeek-OCR）
    if "api_key" in masked:
        masked["api_key"] = mask_api_key(masked["api_key"])
    # 脱敏 api_token（MinerU）
    if "api_token" in masked:
        masked["api_token"] = mask_api_key(masked["api_token"])
    return masked


# TODO: 实现鉴权机制（P2 优先级）
# async def verify_admin_token(authorization: str = Header(...)) -> str:
#     """验证管理员 Token"""
#     if not authorization.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="Invalid token format")
#
#     token = authorization.replace("Bearer ", "")
#     if not is_valid_admin_token(token):
#         raise HTTPException(status_code=401, detail="Unauthorized")
#
#     return token


@router.get("/{tenant_id}/config", response_model=ConfigResponse)
async def get_tenant_config(tenant_id: str):
    """
    获取租户配置

    Args:
        tenant_id: 租户 ID

    Returns:
        ConfigResponse: 租户配置（合并全局配置）

    Raises:
        HTTPException 404: 租户配置不存在
    """
    manager = get_tenant_config_manager()

    # 获取租户配置
    tenant_config = manager.get(tenant_id)

    if not tenant_config:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Tenant config not found",
                "tenant_id": tenant_id,
                "using_global_config": True
            }
        )

    # 合并全局配置
    merged_config = manager.merge_with_global(tenant_config)

    # 脱敏 API Key
    masked_merged = {
        "llm": mask_config(merged_config["llm"]),
        "embedding": mask_config(merged_config["embedding"]),
        "rerank": mask_config(merged_config["rerank"]),
        "ds_ocr": mask_config(merged_config["ds_ocr"]),  # 🆕 DeepSeek-OCR
        "mineru": mask_config(merged_config["mineru"]),  # 🆕 MinerU
    }

    return ConfigResponse(
        tenant_id=tenant_config.tenant_id,
        llm_config=mask_config(tenant_config.llm_config),
        embedding_config=mask_config(tenant_config.embedding_config),
        rerank_config=mask_config(tenant_config.rerank_config),
        ds_ocr_config=mask_config(tenant_config.ds_ocr_config),  # 🆕 DeepSeek-OCR
        mineru_config=mask_config(tenant_config.mineru_config),  # 🆕 MinerU
        created_at=tenant_config.created_at,
        updated_at=tenant_config.updated_at,
        merged_config=masked_merged
    )


@router.put("/{tenant_id}/config", response_model=ConfigResponse)
async def update_tenant_config(
    tenant_id: str,
    request: ConfigUpdateRequest
):
    """
    更新租户配置

    Args:
        tenant_id: 租户 ID
        request: 配置更新请求

    Returns:
        ConfigResponse: 更新后的配置

    Raises:
        HTTPException 400: 配置验证失败
    """
    manager = get_tenant_config_manager()

    # 获取现有配置
    existing_config = manager.get(tenant_id)

    # 获取请求中实际设置的字段（区分"未设置"和"设置为 null"）
    request_data = request.model_dump(exclude_unset=True)

    # 构建新配置
    if existing_config:
        # 更新现有配置（只更新请求中出现的字段）
        config_data = existing_config.model_dump()
        for key in request_data:
            config_data[key] = request_data[key]
    else:
        # 创建新配置
        config_data = {
            "tenant_id": tenant_id,
            "llm_config": request.llm_config,
            "embedding_config": request.embedding_config,
            "rerank_config": request.rerank_config,
            "ds_ocr_config": request.ds_ocr_config,  # 🆕 DeepSeek-OCR
            "mineru_config": request.mineru_config,  # 🆕 MinerU
        }

    try:
        # 验证并保存配置
        new_config = TenantConfigModel(**config_data)
        success = manager.set(tenant_id, new_config)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update config")

        logger.info(f"[{tenant_id}] Config updated via API")

        # 返回更新后的配置
        return ConfigResponse(
            tenant_id=new_config.tenant_id,
            llm_config=mask_config(new_config.llm_config),
            embedding_config=mask_config(new_config.embedding_config),
            rerank_config=mask_config(new_config.rerank_config),
            ds_ocr_config=mask_config(new_config.ds_ocr_config),  # 🆕 DeepSeek-OCR
            mineru_config=mask_config(new_config.mineru_config),  # 🆕 MinerU
            created_at=new_config.created_at,
            updated_at=new_config.updated_at,
            merged_config=None
        )
    except Exception as e:
        logger.error(f"[{tenant_id}] Config validation failed: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid config",
                "errors": [{"field": "config", "message": str(e)}]
            }
        )


@router.delete("/{tenant_id}/config")
async def delete_tenant_config(tenant_id: str):
    """
    删除租户配置（恢复使用全局配置）

    Args:
        tenant_id: 租户 ID

    Returns:
        Dict: 删除结果

    Raises:
        HTTPException 404: 租户配置不存在
    """
    manager = get_tenant_config_manager()

    success = manager.delete(tenant_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Tenant config not found",
                "tenant_id": tenant_id
            }
        )

    logger.info(f"[{tenant_id}] Config deleted via API")

    return {
        "tenant_id": tenant_id,
        "status": "deleted",
        "message": "Tenant config deleted, now using global config"
    }


@router.post("/{tenant_id}/config/refresh", response_model=ConfigResponse)
async def refresh_tenant_config(tenant_id: str):
    """
    刷新配置缓存（清除缓存并重新加载）

    Args:
        tenant_id: 租户 ID

    Returns:
        ConfigResponse: 刷新后的配置

    Raises:
        HTTPException 404: 租户配置不存在
    """
    manager = get_tenant_config_manager()

    # 强制刷新缓存
    tenant_config = manager.refresh(tenant_id)

    if not tenant_config:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Tenant config not found after refresh",
                "tenant_id": tenant_id,
                "using_global_config": True
            }
        )

    # 合并全局配置
    merged_config = manager.merge_with_global(tenant_config)

    # 脱敏 API Key
    masked_merged = {
        "llm": mask_config(merged_config["llm"]),
        "embedding": mask_config(merged_config["embedding"]),
        "rerank": mask_config(merged_config["rerank"]),
        "ds_ocr": mask_config(merged_config["ds_ocr"]),  # 🆕 DeepSeek-OCR
        "mineru": mask_config(merged_config["mineru"]),  # 🆕 MinerU
    }

    logger.info(f"[{tenant_id}] Config refreshed via API")

    return ConfigResponse(
        tenant_id=tenant_config.tenant_id,
        llm_config=mask_config(tenant_config.llm_config),
        embedding_config=mask_config(tenant_config.embedding_config),
        rerank_config=mask_config(tenant_config.rerank_config),
        ds_ocr_config=mask_config(tenant_config.ds_ocr_config),  # 🆕 DeepSeek-OCR
        mineru_config=mask_config(tenant_config.mineru_config),  # 🆕 MinerU
        created_at=tenant_config.created_at,
        updated_at=tenant_config.updated_at,
        merged_config=masked_merged
    )
