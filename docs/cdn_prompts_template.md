# CDN 技术文档优化 Prompts

针对 CDN 技术支持文档的实体和关系提取优化 Prompts。

## 使用方法

### 方式 1：环境变量（全局配置）

在 `.env` 文件中添加：

```bash
# CDN 实体类型
LIGHTRAG_ENTITY_TYPES='["product", "feature", "error_code", "configuration", "api_endpoint", "company", "technology"]'

# CDN 实体提取 System Prompt
LIGHTRAG_ENTITY_EXTRACTION_SYSTEM_PROMPT="You are a technical documentation expert specializing in CDN (Content Delivery Network) systems. Your task is to extract structured information about CDN products, features, error codes, configurations, and technical relationships from support documentation."
```

### 方式 2：租户配置（租户级覆盖）

通过 API 更新租户配置：

```bash
curl -X PUT "http://localhost:8000/tenants/siraya/config" \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "custom_prompts": {
    "entity_types": [
      "product",
      "feature",
      "error_code",
      "configuration",
      "api_endpoint",
      "company",
      "technology"
    ],
    "entity_extraction_system_prompt": "You are a technical documentation expert specializing in CDN (Content Delivery Network) systems. Your task is to extract structured information about CDN products, features, error codes, configurations, and technical relationships from support documentation.",
    "entity_extraction_user_prompt": "# Technical Documentation Analysis\n\nExtract entities and relationships from the following CDN technical support documentation.\n\n## Critical Format Requirements\n\n1. **Entities** (4 fields, MANDATORY):\n   ```\n   entity{tuple_delimiter}name{tuple_delimiter}type{tuple_delimiter}description\n   ```\n   - name: Use UPPERCASE for technical terms\n   - type: MUST be one of: {entity_types}\n   - description: Brief, technical description (10-20 words)\n\n2. **Relations** (5 fields, ALL MANDATORY):\n   ```\n   relation{tuple_delimiter}source{tuple_delimiter}target{tuple_delimiter}keywords{tuple_delimiter}description\n   ```\n   - source/target: Entity names (UPPERCASE)\n   - keywords: Relationship type (e.g., \"uses\", \"configures\", \"causes\", \"resolves\")\n   - description: MANDATORY - Explain how source relates to target (10-20 words)\n\n## Entity Types\n\n- **product**: CDN products or services (e.g., \"CDN SERVICE\", \"EDGE COMPUTING\")\n- **feature**: Product features (e.g., \"CACHE CONTROL\", \"GZIP COMPRESSION\")\n- **error_code**: HTTP status codes or error messages (e.g., \"ERROR 403\", \"STATUS 502\")\n- **configuration**: Configuration parameters (e.g., \"TTL SETTING\", \"ORIGIN SERVER\")\n- **api_endpoint**: API paths or endpoints (e.g., \"API /v1/purge\")\n- **company**: Company names or brands\n- **technology**: Technologies or protocols (e.g., \"HTTP/3\", \"TLS 1.3\")\n\n## Important Rules\n\n1. ⚠️ **NEVER skip the description field in relations** - this causes processing failures\n2. ✅ Use technical terminology from the document\n3. ✅ Focus on actionable relationships (e.g., \"ERROR 403~AUTHENTICATION FAILURE\" instead of vague connections)\n4. ✅ Preserve exact error codes and configuration names\n\n## Examples\n\n```\nentity{tuple_delimiter}CDN SERVICE{tuple_delimiter}product{tuple_delimiter}Content delivery network platform providing global edge caching\nentity{tuple_delimiter}CACHE CONTROL{tuple_delimiter}feature{tuple_delimiter}Feature for managing cache expiration and validation policies\nentity{tuple_delimiter}ERROR 403{tuple_delimiter}error_code{tuple_delimiter}HTTP forbidden error indicating access denied by server\nentity{tuple_delimiter}ORIGIN SERVER{tuple_delimiter}configuration{tuple_delimiter}Upstream server that hosts the original content\nrelation{tuple_delimiter}CDN SERVICE{tuple_delimiter}CACHE CONTROL{tuple_delimiter}provides{tuple_delimiter}CDN SERVICE offers CACHE CONTROL as a core feature for optimizing content delivery performance\nrelation{tuple_delimiter}ERROR 403{tuple_delimiter}ORIGIN SERVER{tuple_delimiter}originates_from{tuple_delimiter}ERROR 403 is returned by ORIGIN SERVER when authentication or authorization fails\n```\n\n---\n\n# Input Text\n\n{input_text}\n\n---\n\n# Output Format\n\nReturn ONLY the extracted entities and relations in the format above. Use {completion_delimiter} to separate multiple extractions.\n",
    "entity_continue_extraction_user_prompt": "## Continuation Extraction\n\nThe previous extraction reached the token limit. Continue extracting entities and relationships from where we left off.\n\n⚠️ **CRITICAL**: Continue to follow the 5-field relation format:\n```\nrelation{tuple_delimiter}source{tuple_delimiter}target{tuple_delimiter}keywords{tuple_delimiter}description\n```\n\nNEVER skip the description field.\n\n---\n\n# Additional Text\n\n{input_text}\n\n---\n\n# Output\n\nContinue extraction using the same format. Use {completion_delimiter} to separate items.\n",
    "entity_extraction_examples": [
      "entity{tuple_delimiter}CDN PLATFORM{tuple_delimiter}product{tuple_delimiter}Global content delivery network service with edge caching\nentity{tuple_delimiter}SSL CERTIFICATE{tuple_delimiter}configuration{tuple_delimiter}Digital certificate for HTTPS encryption and authentication\nentity{tuple_delimiter}ERROR 502{tuple_delimiter}error_code{tuple_delimiter}Bad gateway error indicating origin server communication failure\nrelation{tuple_delimiter}CDN PLATFORM{tuple_delimiter}SSL CERTIFICATE{tuple_delimiter}requires{tuple_delimiter}CDN PLATFORM requires valid SSL CERTIFICATE for secure HTTPS connections\nrelation{tuple_delimiter}ERROR 502{tuple_delimiter}ORIGIN SERVER{tuple_delimiter}indicates_failure{tuple_delimiter}ERROR 502 occurs when CDN cannot reach ORIGIN SERVER or receives invalid response"
    ]
  }
}
EOF
```

## 配置优先级

租户配置 > 环境变量 > LightRAG 默认值

## 效果预期

使用优化后的 Prompts，实体和关系提取将：
- ✅ **减少格式错误**：强调 5 字段关系格式，减少 "4/5 fields" 错误
- ✅ **技术术语规范化**：使用 UPPERCASE 统一技术实体名称
- ✅ **关系描述强制要求**：避免 "Relation XXX has no description" 错误
- ✅ **CDN 领域优化**：针对 CDN 文档特点（产品、功能、错误码、配置）定制实体类型

## 测试步骤

1. **配置租户 Prompts**：
   ```bash
   curl -X PUT "http://localhost:8000/tenants/siraya/config" \
     -H "Content-Type: application/json" \
     -d @cdn_tenant_config.json
   ```

2. **验证配置生效**：
   ```bash
   curl "http://localhost:8000/tenants/siraya/config"
   ```

3. **清理旧数据**（如果需要重新处理文档）：
   ```bash
   # 清理 Redis LLM 缓存
   docker exec rag-dragonflydb redis-cli --scan --pattern "siraya_llm_response_cache:*" | \
     xargs -I {} docker exec rag-dragonflydb redis-cli DEL {}

   # 清理实例缓存（强制重新创建 LightRAG 实例）
   curl -X POST "http://localhost:8000/tenants/siraya/config/refresh"
   ```

4. **上传文档测试**：
   ```bash
   curl -X POST "http://localhost:8000/insert?tenant_id=siraya&doc_id=cdn_faq_v2" \
     -F "file=@cdn_support_docs.md" \
     -F "parser=auto"
   ```

5. **监控日志**：
   ```bash
   docker logs -f rag-api 2>&1 | grep -E "(Applied custom prompts|Chunk [0-9]+ of|found 4/5 fields)"
   ```

## 日志示例

成功应用 Prompts 后，日志应显示：

```
[Tenant siraya] Applied custom prompts: system_prompt, user_prompt, continue_prompt, examples(1), entity_types(7)
✓ LightRAG instance created for tenant: siraya (workspace=siraya, VLM enabled)
```

处理文档时，应看到 **零** "found 4/5 fields" 警告。

## 故障排查

### 问题 1：Prompts 未生效

**症状**：日志中没有 "Applied custom prompts" 消息

**解决**：
```bash
# 1. 检查配置是否保存
curl "http://localhost:8000/tenants/siraya/config" | jq .custom_prompts

# 2. 强制刷新实例缓存
curl -X POST "http://localhost:8000/tenants/siraya/config/refresh"

# 3. 重启服务（如果是开发环境）
docker compose -f docker-compose.dev.yml restart rag-api
```

### 问题 2：仍有格式错误

**症状**：日志仍显示 "found 4/5 fields on RELATION"

**可能原因**：
1. LLM 缓存未清理（使用旧结果）
2. Prompt 格式占位符错误（检查 `{tuple_delimiter}` 等占位符）

**解决**：
```bash
# 清理 LLM 缓存
docker exec rag-dragonflydb redis-cli --scan --pattern "siraya_llm_response_cache:*" | \
  xargs -I {} docker exec rag-dragonflydb redis-cli DEL {}

# 清理文档状态并重新上传
docker exec rag-dragonflydb redis-cli DEL "siraya_doc_status:{doc_id}"
```

### 问题 3：Entity Types 未应用

**症状**：提取的实体类型不符合预期

**注意**：当前实现中，`entity_types` 通过 Prompt 注入，不需要额外的 `addon_params` 配置。

## 参考资料

- [LightRAG Prompt 格式说明](../docs/lightrag_entity_extraction_format.md)
- [租户配置 API 文档](../api/tenant_config.py)
- [Prompt Manager 源码](../src/prompt_manager.py)
