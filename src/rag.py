import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from functools import partial

from src.logger import logger

# -- 从 raganything_example.py 抄过来的组件 --
from lightrag import LightRAG
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status
from raganything import RAGAnything, RAGAnythingConfig

# 导入 rerank 函数
try:
    from lightrag.rerank import cohere_rerank
except ImportError:
    cohere_rerank = None
    logger.warning("lightrag.rerank not available, rerank功能将被禁用")

# --- 配置 ---
load_dotenv()

# Seed 1.6 model returns <think> tags by default, breaking API responses
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant. Provide direct answers without showing your reasoning process."

# EC2 t3.small has 2 vCPUs. 4x oversubscription for I/O-bound LLM API calls.
# Empirically tested: 8 gives best throughput without hitting rate limits.
DEFAULT_MAX_ASYNC = 8

# --- 全局实例（单一 LightRAG 架构）---
global_lightrag_instance = None  # 单一共享的 LightRAG 实例（核心知识图谱）
rag_instance_mineru = None  # MinerU: 强大多模态解析器，共享 LightRAG
rag_instance_docling = None  # Docling: 轻量快速解析器，共享 LightRAG
rag_instance = None  # 默认实例（向后兼容）

# --- RAG 实例管理 ---
@asynccontextmanager
async def lifespan(app):
    # 启动时创建单一 LightRAG 实例 + 多解析器架构
    global global_lightrag_instance, rag_instance, rag_instance_mineru, rag_instance_docling
    logger.info("Starting up: Single LightRAG + Multiple Parsers architecture...")

    # 读取 LLM 和 Embedding 配置
    ark_api_key = os.getenv("ARK_API_KEY")
    ark_base_url = os.getenv("ARK_BASE_URL")
    ark_model = os.getenv("ARK_MODEL", "seed-1-6-250615")
    
    sf_api_key = os.getenv("SF_API_KEY")
    sf_base_url = os.getenv("SF_BASE_URL")
    sf_embedding_model = os.getenv("SF_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
    
    rerank_model = os.getenv("RERANK_MODEL", "")  # 可选配置
    
    # 验证必需配置
    if not ark_api_key:
        raise RuntimeError("ARK_API_KEY is not set!")
    if not sf_api_key:
        raise RuntimeError("SF_API_KEY is not set!")
    if not sf_base_url:
        raise RuntimeError("SF_BASE_URL is not set!")
    if not ark_base_url:
        raise RuntimeError("ARK_BASE_URL is not set!")
    
    # 读取 LightRAG 查询优化参数
    top_k = int(os.getenv("TOP_K", "20"))
    chunk_top_k = int(os.getenv("CHUNK_TOP_K", "10"))
    max_async = int(os.getenv("MAX_ASYNC", str(DEFAULT_MAX_ASYNC)))
    max_parallel_insert = int(os.getenv("MAX_PARALLEL_INSERT", "2"))
    max_entity_tokens = int(os.getenv("MAX_ENTITY_TOKENS", "6000"))
    max_relation_tokens = int(os.getenv("MAX_RELATION_TOKENS", "8000"))
    max_total_tokens = int(os.getenv("MAX_TOTAL_TOKENS", "30000"))
    
    # 输出配置信息
    logger.info("=" * 70)
    logger.info("📊 RAG API 配置总览")
    logger.info("=" * 70)
    logger.info(f"🤖 LLM: {ark_model}")
    logger.info(f"🔤 Embedding: {sf_embedding_model} (dim={4096})")
    logger.info(f"🎯 Rerank: {rerank_model or 'Disabled'}")
    logger.info(f"📈 Query: top_k={top_k}, chunk_top_k={chunk_top_k}, max_async={max_async}")
    logger.info(f"💾 Tokens: entity={max_entity_tokens}, relation={max_relation_tokens}, total={max_total_tokens}")
    logger.info(f"⚙️  Concurrency: doc_processing=1, parallel_insert={max_parallel_insert}")
    logger.info("=" * 70)

    # 1. 定义共享的 LLM 和 Embedding 函数
    def llm_model_func(prompt, **kwargs):
        kwargs['enable_cot'] = False
        if 'system_prompt' not in kwargs:
            kwargs['system_prompt'] = DEFAULT_SYSTEM_PROMPT
        return openai_complete_if_cache(
            ark_model, prompt, api_key=ark_api_key, base_url=ark_base_url, **kwargs
        )

    embedding_func = EmbeddingFunc(
        embedding_dim=4096,  # Qwen/Qwen3-Embedding-8B 实际返回 4096 维向量
        func=lambda texts: openai_embed(
            texts, model=sf_embedding_model, api_key=sf_api_key, base_url=sf_base_url
        ),
    )
    
    def vision_model_func(prompt, **kwargs):
        return openai_complete_if_cache(
            ark_model, prompt, api_key=ark_api_key, base_url=ark_base_url, **kwargs
        )
    
    # 配置 Rerank 函数（可选，提升检索相关性）
    rerank_func = None
    if rerank_model and cohere_rerank:
        rerank_func = partial(
            cohere_rerank,
            model=rerank_model,  # 例如：Qwen/Qwen3-Reranker-8B
            api_key=sf_api_key,  # 复用硅基流动的 API Key
            base_url=f"{sf_base_url}/rerank"  # 硅基流动的 Rerank 端点
        )
        logger.info(f"✓ Rerank enabled with model: {rerank_model}")
    else:
        logger.info("⚠ Rerank disabled (RERANK_MODEL not set or cohere_rerank unavailable)")

    # 2. 创建单一 LightRAG 实例（核心知识图谱，所有解析器共享）
    logger.info("Creating shared LightRAG instance...")

    # 读取外部存储配置
    use_external_storage = os.getenv("USE_EXTERNAL_STORAGE", "false").lower() == "true"
    kv_storage = os.getenv("KV_STORAGE", "JsonKVStorage")
    vector_storage = os.getenv("VECTOR_STORAGE", "NanoVectorDB")
    graph_storage = os.getenv("GRAPH_STORAGE", "NetworkXStorage")

    # 根据配置创建 LightRAG 实例
    if use_external_storage:
        logger.info("=" * 70)
        logger.info("🔌 Using external storage backends:")
        logger.info(f"   - KV Storage: {kv_storage}")
        logger.info(f"   - Vector Storage: {vector_storage}")
        logger.info(f"   - Graph Storage: {graph_storage}")
        logger.info("=" * 70)

        # 准备存储配置
        storage_kwargs = {}

        # Redis KV 存储配置
        if kv_storage == "RedisKVStorage":
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))
            logger.info(f"   Redis: {redis_host}:{redis_port} (db={redis_db})")

            storage_kwargs["kv_storage"] = "RedisKVStorage"
            storage_kwargs["kv_storage_cls_kwargs"] = {
                "host": redis_host,
                "port": redis_port,
                "db": redis_db
            }
            # 可选：Redis 密码
            redis_password = os.getenv("REDIS_PASSWORD", "")
            if redis_password:
                storage_kwargs["kv_storage_cls_kwargs"]["password"] = redis_password

        # PostgreSQL 向量存储配置
        if vector_storage == "PGVectorStorage":
            postgres_host = os.getenv("POSTGRES_HOST", "localhost")
            postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
            postgres_db = os.getenv("POSTGRES_DB", "lightrag")
            postgres_user = os.getenv("POSTGRES_USER", "lightrag")
            logger.info(f"   PostgreSQL: {postgres_host}:{postgres_port}/{postgres_db}")

            storage_kwargs["vector_storage"] = "PGVectorStorage"
            storage_kwargs["vector_storage_cls_kwargs"] = {
                "host": postgres_host,
                "port": postgres_port,
                "database": postgres_db,
                "user": postgres_user,
                "password": os.getenv("POSTGRES_PASSWORD", "")
            }

        # Neo4j 图存储配置
        if graph_storage == "Neo4JStorage":
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
            logger.info(f"   Neo4j: {neo4j_uri}")

            storage_kwargs["graph_storage"] = "Neo4JStorage"
            storage_kwargs["graph_storage_cls_kwargs"] = {
                "uri": neo4j_uri,
                "user": neo4j_username,
                "password": os.getenv("NEO4J_PASSWORD", "")
            }

        global_lightrag_instance = LightRAG(
            working_dir="./rag_local_storage",  # 仅用于临时文件
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
            llm_model_max_async=max_async,
            **storage_kwargs  # 应用外部存储配置
        )
    else:
        logger.info("=" * 70)
        logger.info("📁 Using local file storage (default)")
        logger.info("=" * 70)

        global_lightrag_instance = LightRAG(
            working_dir="./rag_local_storage",
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
            llm_model_max_async=max_async,  # 优化并发性能（从 4 提升到 8）
        )
    
    # 初始化 LightRAG 存储
    await global_lightrag_instance.initialize_storages()
    await initialize_pipeline_status()
    
    # 配置 Rerank（如果启用）
    if rerank_func:
        global_lightrag_instance.rerank_model_func = rerank_func
        logger.info("✓ LightRAG Rerank configured")
    
    logger.info("✓ Shared LightRAG instance created successfully")

    # 3. 创建 MinerU 解析器实例（共享 LightRAG）
    config_mineru = RAGAnythingConfig(
        working_dir="./rag_local_storage",
        parser="mineru",  # 强大的多模态解析
        enable_image_processing=True,
        enable_table_processing=True,
        enable_equation_processing=True,
    )
    rag_instance_mineru = RAGAnything(
        config=config_mineru,
        lightrag=global_lightrag_instance,  # 传入共享的 LightRAG 实例
        vision_model_func=vision_model_func,
    )
    logger.info("✓ MinerU parser initialized (shares LightRAG instance)")

    # 4. 创建 Docling 解析器实例（共享 LightRAG）
    config_docling = RAGAnythingConfig(
        working_dir="./rag_local_storage",  # 共享相同的 working_dir
        parser="docling",  # 轻量级解析器
        enable_image_processing=False,  # Docling 不支持多模态
        enable_table_processing=False,
        enable_equation_processing=False,
    )
    rag_instance_docling = RAGAnything(
        config=config_docling,
        lightrag=global_lightrag_instance,  # 传入共享的 LightRAG 实例
        vision_model_func=vision_model_func,
    )
    logger.info("✓ Docling parser initialized (shares LightRAG instance)")

    # 5. 设置默认实例为 MinerU（向后兼容）
    rag_instance = rag_instance_mineru
    
    logger.info("=" * 70)
    logger.info("✅ Architecture: Single LightRAG + Multiple Parsers")
    logger.info("   - Shared LightRAG: 1 instance (knowledge graph core)")
    logger.info("   - MinerU Parser: for complex multimodal documents")
    logger.info("   - Docling Parser: for simple documents")
    logger.info("   - Direct Query: bypass parsers for 95% text queries")
    logger.info("=" * 70)

    # 6. 初始化文件服务和清理任务
    from src.file_url_service import get_file_service
    file_service = get_file_service()
    
    # 启动后台文件清理任务
    cleanup_interval = int(os.getenv("FILE_CLEANUP_INTERVAL", "3600"))  # 默认 1 小时
    cleanup_hours = int(os.getenv("FILE_CLEANUP_HOURS", "24"))  # 默认 24 小时保留
    file_service.start_cleanup_task(interval_seconds=cleanup_interval, max_age_hours=cleanup_hours)
    logger.info(f"✓ File cleanup task started: interval={cleanup_interval}s, retention={cleanup_hours}h")

    # 7. 启动性能监控
    from src.metrics import get_metrics_collector
    metrics_collector = get_metrics_collector()
    metrics_collector.start_system_monitoring(interval=60)  # 每 60 秒采集一次系统指标
    logger.info("✓ Performance monitoring started")

    # 8. 预热 Workers（减少首次查询延迟）
    import time
    import asyncio
    logger.info("=" * 70)
    logger.info("🔥 Warming up Workers (Embedding + LLM)...")
    logger.info("=" * 70)
    warmup_start = time.time()

    try:
        # 并行预热Embedding和LLM Workers
        warmup_tasks = []

        # 预热Embedding Workers
        async def warmup_embedding():
            try:
                test_embedding = await embedding_func(["warmup test query"])
                logger.info(f"✓ Embedding Workers warmed up ({len(test_embedding[0])} dimensions)")
                return True
            except Exception as e:
                logger.warning(f"⚠️  Embedding warmup failed: {e}")
                return False

        # 预热LLM Workers
        async def warmup_llm():
            try:
                test_response = await llm_model_func("Hello, respond with 'Hi'")
                logger.info(f"✓ LLM Workers warmed up (response: {len(test_response)} chars)")
                return True
            except Exception as e:
                logger.warning(f"⚠️  LLM warmup failed: {e}")
                return False

        warmup_tasks.append(warmup_embedding())
        warmup_tasks.append(warmup_llm())

        # 并行执行预热
        results = await asyncio.gather(*warmup_tasks, return_exceptions=True)

        warmup_elapsed = time.time() - warmup_start
        success_count = sum(1 for r in results if r is True)

        if success_count == len(warmup_tasks):
            logger.info(f"✅ All Workers ready in {warmup_elapsed:.2f}s")
        else:
            logger.warning(f"⚠️  Partial warmup completed in {warmup_elapsed:.2f}s ({success_count}/{len(warmup_tasks)} succeeded)")
            logger.warning("   Workers will be initialized on first request")

    except Exception as e:
        logger.error(f"❌ Worker warmup failed: {e}")
        logger.warning("   Workers will be initialized on first request")

    logger.info("=" * 70)

    yield  # 应用运行期间保持实例可用

    # 关闭时清理资源
    logger.info("Shutting down RAGAnything instance...")
    # 如果需要清理资源，可以在这里添加

# 获取 LightRAG 实例的函数（用于查询，直接访问知识图谱）
def get_lightrag_instance():
    """
    获取共享的 LightRAG 实例（用于查询）
    
    优势：
    - 绕过解析器，直接访问知识图谱
    - 适合 95% 的纯文本查询
    - 性能更优，资源占用更低
    
    Returns:
        LightRAG: 共享的 LightRAG 实例
    """
    return global_lightrag_instance

# 获取 RAG 实例的函数（用于文档插入，需要解析器）
def get_rag_instance(parser: str = "auto"):
    """
    获取 RAGAnything 实例（用于文档插入）
    
    Args:
        parser: 解析器类型
            - "mineru": 使用 MinerU（强大多模态，内存占用大）
            - "docling": 使用 Docling（轻量快速，内存占用小）
            - "auto": 自动选择（默认返回 MinerU）
    
    Returns:
        RAGAnything: 对应的解析器实例（共享 LightRAG）
    """
    if parser == "docling":
        return rag_instance_docling
    elif parser == "mineru":
        return rag_instance_mineru
    else:  # "auto" or default
        return rag_instance  # 默认 MinerU

def select_parser_by_file(filename: str, file_size: int) -> str:
    """
    根据文件特征智能选择解析器
    
    策略：
    - 纯文本 (.txt, .md) → 返回 "mineru"（实际会在处理函数中直接插入 LightRAG，不经过解析器）
    - 图片文件 (.jpg, .png) → MinerU（OCR能力强）
    - PDF/Office 小文件 (< 500KB) → Docling（快速）
    - PDF/Office 大文件 (> 500KB) → MinerU（更强大）
    - 其他 → MinerU（默认）
    
    注意：
    - Docling 只支持 PDF 和 Office 格式（.pdf, .docx, .xlsx, .pptx, .html）
    - 纯文本文件会被特殊处理：直接读取内容并插入 LightRAG，无需解析器
    
    Args:
        filename: 文件名
        file_size: 文件大小（字节）
    
    Returns:
        "mineru" 或 "docling"
    """
    import os
    ext = os.path.splitext(filename)[1].lower()
    
    # 图片文件 → MinerU（需要 OCR）
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
        return "mineru"
    
    # 纯文本文件 → MinerU（Docling 不支持 .txt）
    if ext in ['.txt', '.md', '.markdown']:
        return "mineru"
    
    # PDF/Office 小文件 → Docling（快速）
    if ext in ['.pdf', '.docx', '.xlsx', '.pptx', '.html', '.htm'] and file_size < 500 * 1024:  # < 500KB
        return "docling"
    
    # 大文件或其他 → MinerU
    return "mineru"
