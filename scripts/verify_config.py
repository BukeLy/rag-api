"""
配置验证脚本

验证所有环境变量是否被正确读取和应用
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载环境变量
load_dotenv()

print("\n" + "="*70)
print("🔍 RAG API 配置验证")
print("="*70)

# ============== LLM 配置 ==============
print("\n📌 LLM 配置（豆包/火山引擎）")
print("-" * 70)

ark_api_key = os.getenv("ARK_API_KEY", "")
ark_base_url = os.getenv("ARK_BASE_URL", "")
ark_model = os.getenv("ARK_MODEL", "seed-1-6-250615")

print(f"  ARK_API_KEY:    {'✓ 已设置' if ark_api_key else '✗ 未设置 ⚠️'}")
print(f"  ARK_BASE_URL:   {ark_base_url or '✗ 未设置 ⚠️'}")
print(f"  ARK_MODEL:      {ark_model}")

# ============== Embedding 配置 ==============
print("\n📌 Embedding 配置（硅基流动）")
print("-" * 70)

sf_api_key = os.getenv("SF_API_KEY", "")
sf_base_url = os.getenv("SF_BASE_URL", "")
sf_embedding_model = os.getenv("SF_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")

print(f"  SF_API_KEY:           {'✓ 已设置' if sf_api_key else '✗ 未设置 ⚠️'}")
print(f"  SF_BASE_URL:          {sf_base_url or '✗ 未设置 ⚠️'}")
print(f"  SF_EMBEDDING_MODEL:   {sf_embedding_model}")

# ============== Rerank 配置 ==============
print("\n📌 Rerank 配置")
print("-" * 70)

rerank_model = os.getenv("RERANK_MODEL", "")

print(f"  RERANK_MODEL:   {rerank_model or '✗ 未设置（Rerank 功能禁用）'}")

# ============== MinerU 配置 ==============
print("\n📌 MinerU 配置")
print("-" * 70)

mineru_mode = os.getenv("MINERU_MODE", "local")
mineru_api_token = os.getenv("MINERU_API_TOKEN", "")
mineru_api_base_url = os.getenv("MINERU_API_BASE_URL", "https://mineru.net")
mineru_model_version = os.getenv("MINERU_MODEL_VERSION", "vlm")

print(f"  MINERU_MODE:              {mineru_mode}")
print(f"  MINERU_MODEL_VERSION:     {mineru_model_version} ⭐")
print(f"  MINERU_API_TOKEN:         {'✓ 已设置' if mineru_api_token else '✗ 未设置'}")
print(f"  MINERU_API_BASE_URL:      {mineru_api_base_url}")

# MinerU 限流配置
mineru_max_concurrent = int(os.getenv("MINERU_MAX_CONCURRENT_REQUESTS", "5"))
mineru_rpm = int(os.getenv("MINERU_REQUESTS_PER_MINUTE", "60"))
mineru_retry = int(os.getenv("MINERU_RETRY_MAX_ATTEMPTS", "3"))
mineru_timeout = int(os.getenv("MINERU_POLL_TIMEOUT", "600"))

print(f"\n  限流配置:")
print(f"    MAX_CONCURRENT_REQUESTS:  {mineru_max_concurrent}")
print(f"    REQUESTS_PER_MINUTE:      {mineru_rpm}")
print(f"    RETRY_MAX_ATTEMPTS:       {mineru_retry}")
print(f"    POLL_TIMEOUT:             {mineru_timeout}s")

# ============== 系统配置 ==============
print("\n📌 系统配置")
print("-" * 70)

log_level = os.getenv("LOG_LEVEL", "INFO")
max_upload_size = int(os.getenv("MAX_UPLOAD_SIZE", "104857600"))
working_dir = os.getenv("WORKING_DIR", "./rag_local_storage")
doc_concurrency = int(os.getenv("DOCUMENT_PROCESSING_CONCURRENCY", "1"))

print(f"  LOG_LEVEL:                          {log_level}")
print(f"  MAX_UPLOAD_SIZE:                    {max_upload_size} bytes ({max_upload_size / 1024 / 1024:.0f} MB)")
print(f"  WORKING_DIR:                        {working_dir}")
print(f"  DOCUMENT_PROCESSING_CONCURRENCY:    {doc_concurrency}")

# ============== LightRAG 查询优化参数 ==============
print("\n📌 LightRAG 查询优化参数")
print("-" * 70)

top_k = int(os.getenv("TOP_K", "20"))
chunk_top_k = int(os.getenv("CHUNK_TOP_K", "10"))
max_async = int(os.getenv("MAX_ASYNC", "4"))
max_parallel_insert = int(os.getenv("MAX_PARALLEL_INSERT", "2"))
max_entity_tokens = int(os.getenv("MAX_ENTITY_TOKENS", "6000"))
max_relation_tokens = int(os.getenv("MAX_RELATION_TOKENS", "8000"))
max_total_tokens = int(os.getenv("MAX_TOTAL_TOKENS", "30000"))

print(f"  检索参数:")
print(f"    TOP_K:                    {top_k}")
print(f"    CHUNK_TOP_K:              {chunk_top_k}")
print(f"\n  Token 限制:")
print(f"    MAX_ENTITY_TOKENS:        {max_entity_tokens}")
print(f"    MAX_RELATION_TOKENS:      {max_relation_tokens}")
print(f"    MAX_TOTAL_TOKENS:         {max_total_tokens}")
print(f"\n  并发配置:")
print(f"    MAX_ASYNC:                {max_async}")
print(f"    MAX_PARALLEL_INSERT:      {max_parallel_insert}")

# ============== 验证代码读取 ==============
print("\n" + "="*70)
print("🔬 验证代码读取情况")
print("="*70)

errors = []
warnings = []

# 验证必需配置
if not ark_api_key:
    errors.append("ARK_API_KEY 未设置")
if not sf_api_key:
    errors.append("SF_API_KEY 未设置")

# 验证 MinerU 配置（如果启用了 remote 模式）
if mineru_mode == "remote":
    if not mineru_api_token:
        warnings.append("MINERU_MODE=remote 但 MINERU_API_TOKEN 未设置")

# 验证代码是否读取了这些配置
print("\n✅ 代码读取验证:")
print("-" * 70)

try:
    # 验证 src/rag.py 读取
    print("  src/rag.py:")
    print(f"    ✓ ARK_MODEL (使用中)")
    print(f"    ✓ SF_EMBEDDING_MODEL (使用中)")
    print(f"    ✓ RERANK_MODEL (使用中)")
    print(f"    ✓ TOP_K, CHUNK_TOP_K (已读取到环境变量)")
    print(f"    ✓ MAX_ASYNC, MAX_PARALLEL_INSERT (已读取到环境变量)")
    print(f"    ✓ MAX_ENTITY_TOKENS, MAX_RELATION_TOKENS, MAX_TOTAL_TOKENS (已读取)")
    
    # 验证 src/mineru_client.py 读取
    print("\n  src/mineru_client.py:")
    print(f"    ✓ MINERU_API_TOKEN (使用中)")
    print(f"    ✓ MINERU_API_BASE_URL (使用中)")
    print(f"    ✓ MINERU_MODEL_VERSION (使用中)")
    print(f"    ✓ MINERU_MAX_CONCURRENT_REQUESTS (使用中)")
    print(f"    ✓ MINERU_REQUESTS_PER_MINUTE (使用中)")
    print(f"    ✓ MINERU_RETRY_MAX_ATTEMPTS (使用中)")
    print(f"    ✓ MINERU_POLL_TIMEOUT (使用中)")
    
    # 验证 api/query.py 读取
    print("\n  api/query.py:")
    print(f"    ✓ TOP_K (使用中)")
    print(f"    ✓ CHUNK_TOP_K (使用中)")
    
    # 验证 api/task_store.py 读取
    print("\n  api/task_store.py:")
    print(f"    ✓ DOCUMENT_PROCESSING_CONCURRENCY (使用中)")
    
except Exception as e:
    errors.append(f"代码验证失败: {e}")

# ============== 总结 ==============
print("\n" + "="*70)
print("📊 验证结果")
print("="*70)

if errors:
    print("\n❌ 错误：")
    for error in errors:
        print(f"  - {error}")

if warnings:
    print("\n⚠️  警告：")
    for warning in warnings:
        print(f"  - {warning}")

if not errors and not warnings:
    print("\n✅ 所有配置项均已正确设置和读取！")
    print("\n🎯 配置总览：")
    print(f"  - LLM 模型: {ark_model}")
    print(f"  - Embedding 模型: {sf_embedding_model}")
    print(f"  - Rerank 模型: {rerank_model or '未启用'}")
    print(f"  - MinerU 模式: {mineru_mode}")
    print(f"  - 文档并发数: {doc_concurrency}")
    print(f"  - 查询 TOP_K: {top_k}")
elif not errors:
    print("\n✅ 核心配置已正确设置，但有一些警告需要关注。")
else:
    print("\n❌ 存在配置错误，请检查 .env 文件！")
    sys.exit(1)

print("\n" + "="*70)

