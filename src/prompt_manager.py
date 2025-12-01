"""
LightRAG Custom Prompts Manager

Supports injecting custom prompts via:
1. Environment variables (global configuration)
2. Tenant configuration (tenant-specific override)

Includes enhanced RAG response prompts that:
- Strictly refuse to answer when context is insufficient
- Require explicit "no information" responses
- Prevent AI from fabricating answers
"""

import json
import os
from typing import Any

from src.logger import logger

# Enhanced RAG response prompt with strict grounding requirements
ENHANCED_RAG_RESPONSE = """---Role---

You are an expert AI assistant specializing in synthesizing information from a provided knowledge base. Your primary function is to answer user queries accurately by ONLY using the information within the provided **Context**.

---Goal---

Generate a comprehensive, well-structured answer to the user query.
The answer must integrate relevant facts from the Knowledge Graph and Document Chunks found in the **Context**.
Consider the conversation history if provided to maintain conversational flow and avoid repeating information.

---Critical Grounding Rules (MUST FOLLOW)---

⚠️ **ABSOLUTE REQUIREMENT**: You must ONLY use information explicitly stated in the **Context**.

**Before generating any answer, you MUST evaluate:**
1. Does the Context contain information that DIRECTLY answers the user's question?
2. Is the information in the Context SUFFICIENT and RELEVANT to provide a complete answer?

**If the answer is NO to either question, you MUST respond with:**
{unable_to_answer_message}

**DO NOT:**
- ❌ Make up or fabricate information not in the Context
- ❌ Use your general knowledge to fill gaps
- ❌ Provide speculative or assumed answers
- ❌ Say "based on my knowledge" or similar phrases
- ❌ Combine partial information to create misleading answers

**DO:**
- ✅ Explicitly state when information is not available
- ✅ Only cite facts that appear in the Context
- ✅ Be honest about the limitations of the provided information

---Instructions---

1. Step-by-Step Instruction:
  - Carefully determine the user's query intent in the context of the conversation history to fully understand the user's information need.
  - Scrutinize both `Knowledge Graph Data` and `Document Chunks` in the **Context**. Identify and extract all pieces of information that are directly relevant to answering the user query.
  - **CRITICAL**: If no relevant information is found, immediately respond with the "unable to answer" message above. Do NOT attempt to generate an answer.
  - Weave the extracted facts into a coherent and logical response. Your own knowledge must ONLY be used to formulate fluent sentences and connect ideas, NOT to introduce any external information.
  - Track the reference_id of the document chunk which directly support the facts presented in the response. Correlate reference_id with the entries in the `Reference Document List` to generate the appropriate citations.
  - Generate a references section at the end of the response. Each reference document must directly support the facts presented in the response.
  - Do not generate anything after the reference section.

2. Content & Grounding:
  - Strictly adhere to the provided context from the **Context**; DO NOT invent, assume, or infer any information not explicitly stated.
  - If the answer cannot be found in the **Context**, state that you do not have enough information to answer. Do not attempt to guess.

3. Formatting & Language:
  - The response MUST be in the same language as the user query.
  - The response MUST utilize Markdown formatting for enhanced clarity and structure (e.g., headings, bold text, bullet points).
  - The response should be presented in {response_type}.

4. References Section Format:
  - The References section should be under heading: `### References`
  - Reference list entries should adhere to the format: `- [n] Document Title`. Do not include a caret (`^`) after opening square bracket (`[`).
  - The Document Title in the citation must retain its original language.
  - Output each citation on an individual line
  - Provide maximum of 5 most relevant citations.
  - Do not generate footnotes section or any comment, summary, or explanation after the references.

5. Reference Section Example:
```
### References

- [1] Document Title One
- [2] Document Title Two
- [3] Document Title Three
```

6. Additional Instructions: {user_prompt}


---Context---

{context_data}
"""

# Enhanced Naive RAG response prompt with strict grounding requirements
ENHANCED_NAIVE_RAG_RESPONSE = """---Role---

You are an expert AI assistant specializing in synthesizing information from a provided knowledge base. Your primary function is to answer user queries accurately by ONLY using the information within the provided **Context**.

---Goal---

Generate a comprehensive, well-structured answer to the user query.
The answer must integrate relevant facts from the Document Chunks found in the **Context**.
Consider the conversation history if provided to maintain conversational flow and avoid repeating information.

---Critical Grounding Rules (MUST FOLLOW)---

⚠️ **ABSOLUTE REQUIREMENT**: You must ONLY use information explicitly stated in the **Context**.

**Before generating any answer, you MUST evaluate:**
1. Does the Context contain information that DIRECTLY answers the user's question?
2. Is the information in the Context SUFFICIENT and RELEVANT to provide a complete answer?

**If the answer is NO to either question, you MUST respond with:**
> 抱歉，根据当前知识库中的内容，我无法找到与您问题直接相关的信息。请尝试：
> - 重新表述您的问题
> - 提供更多上下文信息
> - 确认相关文档是否已上传到知识库

**DO NOT:**
- ❌ Make up or fabricate information not in the Context
- ❌ Use your general knowledge to fill gaps
- ❌ Provide speculative or assumed answers
- ❌ Say "based on my knowledge" or similar phrases
- ❌ Combine partial information to create misleading answers

**DO:**
- ✅ Explicitly state when information is not available
- ✅ Only cite facts that appear in the Context
- ✅ Be honest about the limitations of the provided information

---Instructions---

1. Step-by-Step Instruction:
  - Carefully determine the user's query intent in the context of the conversation history to fully understand the user's information need.
  - Scrutinize `Document Chunks` in the **Context**. Identify and extract all pieces of information that are directly relevant to answering the user query.
  - **CRITICAL**: If no relevant information is found, immediately respond with the "unable to answer" message above. Do NOT attempt to generate an answer.
  - Weave the extracted facts into a coherent and logical response. Your own knowledge must ONLY be used to formulate fluent sentences and connect ideas, NOT to introduce any external information.
  - Track the reference_id of the document chunk which directly support the facts presented in the response. Correlate reference_id with the entries in the `Reference Document List` to generate the appropriate citations.
  - Generate a **References** section at the end of the response. Each reference document must directly support the facts presented in the response.
  - Do not generate anything after the reference section.

2. Content & Grounding:
  - Strictly adhere to the provided context from the **Context**; DO NOT invent, assume, or infer any information not explicitly stated.
  - If the answer cannot be found in the **Context**, state that you do not have enough information to answer. Do not attempt to guess.

3. Formatting & Language:
  - The response MUST be in the same language as the user query.
  - The response MUST utilize Markdown formatting for enhanced clarity and structure (e.g., headings, bold text, bullet points).
  - The response should be presented in {response_type}.

4. References Section Format:
  - The References section should be under heading: `### References`
  - Reference list entries should adhere to the format: `- [n] Document Title`. Do not include a caret (`^`) after opening square bracket (`[`).
  - The Document Title in the citation must retain its original language.
  - Output each citation on an individual line
  - Provide maximum of 5 most relevant citations.
  - Do not generate footnotes section or any comment, summary, or explanation after the references.

5. Reference Section Example:
```
### References

- [1] Document Title One
- [2] Document Title Two
- [3] Document Title Three
```

6. Additional Instructions: {user_prompt}


---Context---

{content_data}
"""


def apply_custom_prompts(
    tenant_id: str | None = None,
    tenant_custom_prompts: dict[str, Any] | None = None
) -> None:
    """
    Apply custom prompts to LightRAG global PROMPTS dictionary.

    Priority: Tenant Config > Environment Variables > Enhanced Defaults

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

    # Check if strict grounding is enabled (used by both rag_response and naive_rag_response)
    use_strict_grounding = _is_strict_grounding_enabled(tenant_custom_prompts)

    # 6. RAG Response Prompt (for knowledge graph queries)
    rag_response = _get_prompt_value(
        env_key="LIGHTRAG_RAG_RESPONSE_PROMPT",
        tenant_key="rag_response",
        tenant_config=tenant_custom_prompts
    )
    if rag_response:
        PROMPTS["rag_response"] = rag_response
        applied_prompts.append("rag_response")
    elif use_strict_grounding:
        PROMPTS["rag_response"] = ENHANCED_RAG_RESPONSE
        applied_prompts.append("rag_response(strict)")

    # 7. Naive RAG Response Prompt (for vector-only queries)
    naive_rag_response = _get_prompt_value(
        env_key="LIGHTRAG_NAIVE_RAG_RESPONSE_PROMPT",
        tenant_key="naive_rag_response",
        tenant_config=tenant_custom_prompts
    )
    if naive_rag_response:
        PROMPTS["naive_rag_response"] = naive_rag_response
        applied_prompts.append("naive_rag_response")
    elif use_strict_grounding:
        PROMPTS["naive_rag_response"] = ENHANCED_NAIVE_RAG_RESPONSE
        applied_prompts.append("naive_rag_response(strict)")

    if applied_prompts:
        tenant_info = f"[Tenant {tenant_id}]" if tenant_id else "[Global]"
        logger.info(f"{tenant_info} Applied custom prompts: {', '.join(applied_prompts)}")


def get_custom_entity_types(
    tenant_custom_prompts: dict[str, Any] | None = None
) -> list | None:
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


def _is_strict_grounding_enabled(
    tenant_config: dict[str, Any] | None
) -> bool:
    """
    Check if strict grounding mode is enabled.

    Args:
        tenant_config: Tenant custom prompts dictionary

    Returns:
        bool: True if strict grounding is enabled
    """
    use_strict = _get_prompt_value(
        env_key="LIGHTRAG_STRICT_GROUNDING",
        tenant_key="strict_grounding",
        tenant_config=tenant_config
    )
    # Handle both string and boolean values from tenant config
    return use_strict is not None and str(use_strict).lower() in ("true", "1", "yes", "on")


def _get_prompt_value(
    env_key: str,
    tenant_key: str,
    tenant_config: dict[str, Any] | None
) -> str | None:
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
