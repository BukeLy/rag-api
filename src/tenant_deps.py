"""
租户依赖注入和鉴权模块

提供 FastAPI 依赖注入函数，用于从请求中提取和验证租户 ID。
"""

from typing import Optional
from fastapi import Query, HTTPException

from src.logger import logger


async def validate_tenant_access(tenant_id: str) -> bool:
    """
    验证租户访问权限（鉴权预留接口）

    当前实现：简单格式验证
    未来扩展方向：
    - JWT Token 验证
    - API Key 白名单验证
    - 租户状态检查（是否已禁用/过期）
    - 资源配额检查
    - 访问频率限制

    Args:
        tenant_id: 租户 ID

    Returns:
        bool: 是否有权限访问该租户
    """
    # 基本格式验证
    if not tenant_id:
        logger.warning("Empty tenant_id")
        return False

    # 长度验证（3-50 字符）
    if len(tenant_id) < 3 or len(tenant_id) > 50:
        logger.warning(f"Invalid tenant_id length: {len(tenant_id)}")
        return False

    # 字符验证（仅允许字母、数字、下划线、连字符）
    if not tenant_id.replace('_', '').replace('-', '').isalnum():
        logger.warning(f"Invalid tenant_id format: {tenant_id}")
        return False

    # TODO: 后续添加白名单验证（如果配置了 TENANT_ID_WHITELIST）
    # whitelist = os.getenv("TENANT_ID_WHITELIST", "").split(",")
    # if whitelist and tenant_id not in whitelist:
    #     return False

    # TODO: 后续添加租户状态检查（从数据库查询租户是否激活）
    # tenant_status = await get_tenant_status(tenant_id)
    # if tenant_status != "active":
    #     return False

    return True


async def get_tenant_id(
    tenant_id: Optional[str] = Query(
        default=None,
        description="租户ID（必填，3-50字符，支持字母数字下划线连字符）",
        min_length=3,
        max_length=50,
        regex=r'^[a-zA-Z0-9_-]+$'
    )
) -> str:
    """
    FastAPI 依赖：从 Query Parameter 获取租户ID（强制必填）

    使用方式：
    ```python
    @router.post("/query")
    async def query_rag(
        request: QueryRequest,
        tenant_id: str = Depends(get_tenant_id)
    ):
        # tenant_id 已验证通过
        ...
    ```

    Args:
        tenant_id: 从 URL Query Parameter 提取的租户 ID

    Returns:
        str: 验证通过的租户 ID

    Raises:
        HTTPException 400: 缺少 tenant_id 参数
        HTTPException 403: 租户访问权限验证失败
    """
    # 验证是否提供了 tenant_id
    if not tenant_id:
        logger.warning("Request missing required parameter: tenant_id")
        raise HTTPException(
            status_code=400,
            detail="Missing required parameter: tenant_id. Please provide ?tenant_id=your_tenant_id"
        )

    # 调用鉴权钩子验证访问权限
    if not await validate_tenant_access(tenant_id):
        logger.warning(f"Access denied for tenant: {tenant_id}")
        raise HTTPException(
            status_code=403,
            detail=f"Access denied for tenant: {tenant_id}. Invalid format or insufficient permissions."
        )

    logger.debug(f"Tenant validated: {tenant_id}")
    return tenant_id
