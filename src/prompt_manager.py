"""
LightRAG Custom Prompts Manager

Supports injecting custom prompts via:
1. Environment variables (global configuration)
2. Tenant configuration (tenant-specific override)
"""

import os
import json
from typing import Dict, Any, Optional
from src.logger import logger


def apply_custom_prompts(
    tenant_id: Optional[str] = None,
    tenant_custom_prompts: Optional[Dict[str, Any]] = None
) -> None:
    """
    Apply custom prompts to LightRAG global PROMPTS dictionary.

    Priority: Tenant Config > Environment Variables > Default

    Args:
        tenant_id: Tenant ID (for logging)
        tenant_custom_prompts: Custom prompts from tenant configuration
    """
    from lightrag.prompt import PROMPTS

    applied_prompts = []

    # 1. Entity Extraction System Prompt
    system_prompt = _get_prompt_value(
        env_key="LIGHTRAG_ENTITY_EXTRACTION_SYSTEM_PROMPT",
        tenant_key="entity_extraction_system_prompt",
        tenant_config=tenant_custom_prompts
    )
    if system_prompt:
        PROMPTS["entity_extraction_system_prompt"] = system_prompt
        applied_prompts.append("system_prompt")

    # 2. Entity Extraction User Prompt
    user_prompt = _get_prompt_value(
        env_key="LIGHTRAG_ENTITY_EXTRACTION_USER_PROMPT",
        tenant_key="entity_extraction_user_prompt",
        tenant_config=tenant_custom_prompts
    )
    if user_prompt:
        PROMPTS["entity_extraction_user_prompt"] = user_prompt
        applied_prompts.append("user_prompt")

    # 3. Entity Continue Extraction User Prompt
    continue_prompt = _get_prompt_value(
        env_key="LIGHTRAG_ENTITY_CONTINUE_EXTRACTION_USER_PROMPT",
        tenant_key="entity_continue_extraction_user_prompt",
        tenant_config=tenant_custom_prompts
    )
    if continue_prompt:
        PROMPTS["entity_continue_extraction_user_prompt"] = continue_prompt
        applied_prompts.append("continue_prompt")

    # 4. Entity Extraction Examples (JSON array)
    examples_json = _get_prompt_value(
        env_key="LIGHTRAG_ENTITY_EXTRACTION_EXAMPLES",
        tenant_key="entity_extraction_examples",
        tenant_config=tenant_custom_prompts
    )
    if examples_json:
        try:
            # Parse JSON if it's a string
            if isinstance(examples_json, str):
                examples = json.loads(examples_json)
            else:
                examples = examples_json

            if isinstance(examples, list):
                PROMPTS["entity_extraction_examples"] = examples
                applied_prompts.append(f"examples({len(examples)})")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse entity_extraction_examples JSON: {e}")

    # 5. Entity Types (list of types)
    entity_types = _get_prompt_value(
        env_key="LIGHTRAG_ENTITY_TYPES",
        tenant_key="entity_types",
        tenant_config=tenant_custom_prompts
    )
    if entity_types:
        try:
            # Parse JSON if it's a string
            if isinstance(entity_types, str):
                types = json.loads(entity_types)
            else:
                types = entity_types

            if isinstance(types, list):
                # Entity types are passed via addon_params, not PROMPTS
                # We'll return them separately
                applied_prompts.append(f"entity_types({len(types)})")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse entity_types JSON: {e}")

    if applied_prompts:
        tenant_info = f"[Tenant {tenant_id}]" if tenant_id else "[Global]"
        logger.info(f"{tenant_info} Applied custom prompts: {', '.join(applied_prompts)}")


def get_custom_entity_types(
    tenant_custom_prompts: Optional[Dict[str, Any]] = None
) -> Optional[list]:
    """
    Get custom entity types from environment or tenant configuration.

    Returns:
        list: Custom entity types or None (use LightRAG default)
    """
    entity_types = _get_prompt_value(
        env_key="LIGHTRAG_ENTITY_TYPES",
        tenant_key="entity_types",
        tenant_config=tenant_custom_prompts
    )

    if not entity_types:
        return None

    try:
        # Parse JSON if it's a string
        if isinstance(entity_types, str):
            types = json.loads(entity_types)
        else:
            types = entity_types

        if isinstance(types, list) and types:
            return types
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse entity_types JSON: {e}")

    return None


def _get_prompt_value(
    env_key: str,
    tenant_key: str,
    tenant_config: Optional[Dict[str, Any]]
) -> Optional[str]:
    """
    Get prompt value with priority: Tenant Config > Environment Variable.

    Args:
        env_key: Environment variable key
        tenant_key: Tenant configuration key
        tenant_config: Tenant custom prompts dictionary

    Returns:
        str: Prompt value or None
    """
    # Priority 1: Tenant configuration
    if tenant_config and tenant_key in tenant_config:
        value = tenant_config[tenant_key]
        if value:  # Non-empty
            return value

    # Priority 2: Environment variable
    env_value = os.getenv(env_key)
    if env_value:
        return env_value

    return None
