# 严格 Grounding 模式

## 问题背景

默认情况下，当知识库中的 chunks 不足以回答用户问题时，AI 可能会"强行编造"一个答案，即使这个答案没有依据。这是因为 LLM 有强大的生成能力，即使在没有足够上下文的情况下也会尝试给出"看起来合理"的回答。

## 解决方案

通过启用 **严格 Grounding 模式**，系统会使用增强版的 prompt，明确要求 AI 在信息不足时：

1. **评估上下文充分性**：在生成答案前，先判断上下文是否足够回答问题
2. **明确拒绝回答**：如果信息不足，使用标准化的拒绝回答格式
3. **禁止编造内容**：严格禁止使用 AI 的通用知识来填补知识库的空白

## 使用方法

### 方式 1：环境变量（全局配置）

在 `.env` 文件中添加：

```bash
# 启用严格 Grounding 模式
LIGHTRAG_STRICT_GROUNDING=true
```

### 方式 2：租户配置（租户级覆盖）

通过 API 更新租户配置：

```bash
curl -X PUT "http://localhost:8000/tenants/your_tenant/config" \
  -H "Content-Type: application/json" \
  -d '{
    "custom_prompts": {
      "strict_grounding": "true"
    }
  }'
```

### 方式 3：完全自定义 Prompt

如果需要更精细的控制，可以完全自定义 RAG 响应 prompt：

```bash
# 环境变量方式
LIGHTRAG_RAG_RESPONSE_PROMPT="你的自定义 prompt..."
LIGHTRAG_NAIVE_RAG_RESPONSE_PROMPT="你的自定义 naive 模式 prompt..."
```

或通过租户配置 API：

```bash
curl -X PUT "http://localhost:8000/tenants/your_tenant/config" \
  -H "Content-Type: application/json" \
  -d '{
    "custom_prompts": {
      "rag_response": "你的自定义 KG 模式 prompt...",
      "naive_rag_response": "你的自定义 naive 模式 prompt..."
    }
  }'
```

## 配置优先级

从高到低：

1. **租户配置的 `rag_response`/`naive_rag_response`**（完全自定义）
2. **环境变量 `LIGHTRAG_RAG_RESPONSE_PROMPT`/`LIGHTRAG_NAIVE_RAG_RESPONSE_PROMPT`**
3. **`strict_grounding=true`**（使用增强版默认 prompt）
4. **LightRAG 原生 prompt**（默认行为）

## 增强版 Prompt 的关键指令

启用严格 Grounding 模式后，prompt 会包含以下关键指令：

```markdown
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
```

## 效果对比

### 未启用严格 Grounding 模式

用户问题：`公司的年度收入是多少？`

（假设知识库中没有收入数据）

AI 可能回答：
> 根据相关文档，该公司是一家成熟的企业...虽然具体年度收入数据未在文档中明确提及，但从其业务规模来看，估计年收入应该在...

### 启用严格 Grounding 模式

同样的问题，AI 会回答：
> 抱歉，根据当前知识库中的内容，我无法找到与您问题直接相关的信息。请尝试：
> - 重新表述您的问题
> - 提供更多上下文信息
> - 确认相关文档是否已上传到知识库

## 刷新配置

修改配置后，需要刷新租户实例缓存：

```bash
# 刷新特定租户
curl -X POST "http://localhost:8000/tenants/your_tenant/config/refresh"

# 或重启服务（全局生效）
docker compose restart rag-api
```

## Prompt 与查询模式的对应关系

LightRAG 有 5 种查询模式，但只使用 2 种响应 Prompt：

| 查询模式 | 使用的 Prompt | 说明 |
|---------|--------------|------|
| `naive` | `naive_rag_response` | 纯向量搜索，不使用知识图谱 |
| `local` | `rag_response` | 局部知识图谱搜索 |
| `global` | `rag_response` | 全局知识图谱搜索 |
| `hybrid` | `rag_response` | 混合模式（local + global） |
| `mix` | `rag_response` | 全功能混合（KG + 向量） |

因此，自定义 `rag_response` 会影响除 `naive` 以外的所有模式，而 `naive_rag_response` 仅影响 `naive` 模式。

## 相关配置

| 配置项 | 类型 | 描述 |
|-------|------|------|
| `LIGHTRAG_STRICT_GROUNDING` | 环境变量 | 全局启用严格 Grounding 模式 |
| `strict_grounding` | 租户配置 | 租户级启用严格 Grounding 模式 |
| `rag_response` | 租户配置 | 自定义 KG 模式响应 prompt（影响 local/global/hybrid/mix） |
| `naive_rag_response` | 租户配置 | 自定义 naive 模式响应 prompt（仅影响 naive） |

## 注意事项

1. **语言适配**：当前默认拒绝回答消息是中文，如需英文或其他语言，请使用完全自定义 prompt
2. **性能影响**：严格 Grounding 模式不会影响性能，仅修改 prompt 内容
3. **兼容性**：此功能与所有查询模式（naive、local、global、hybrid、mix）兼容
4. **Prompt 复用**：LightRAG 的设计中，`rag_response` 被 local/global/hybrid/mix 四种模式共享
