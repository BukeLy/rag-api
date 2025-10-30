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

# --- 多租户架构：移除全局单实例 ---
# 使用多租户管理器替代全局单实例
# 每个租户拥有独立的 LightRAG 实例（通过 workspace 隔离）

# --- RAG 实例管理 ---
@asynccontextmanager
async def lifespan(app):
    # 启动时初始化多租户管理器
    logger.info("Starting up: Multi-Tenant RAG API...")
    logger.info("=" * 70)
    logger.info("🏢 Multi-Tenant Mode Enabled")
    logger.info("=" * 70)

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
    
    # 读取多租户配置
    max_tenant_instances = int(os.getenv("MAX_TENANT_INSTANCES", "50"))
    
    # 读取 Embedding 维度配置
    embedding_dim = os.getenv("EMBEDDING_DIM", "1024")

    # 输出配置信息
    logger.info("=" * 70)
    logger.info("📊 RAG API 配置总览（多租户模式）")
    logger.info("=" * 70)
    logger.info(f"🏢 Max Tenant Instances: {max_tenant_instances}")
    logger.info(f"🤖 LLM: {ark_model}")
    logger.info(f"🔤 Embedding: {sf_embedding_model} (dim={embedding_dim})")
    logger.info(f"🎯 Rerank: {rerank_model or 'Disabled'}")
    logger.info(f"📈 Query: top_k={top_k}, chunk_top_k={chunk_top_k}, max_async={max_async}")
    logger.info(f"💾 Tokens: entity={max_entity_tokens}, relation={max_relation_tokens}, total={max_total_tokens}")
    logger.info(f"⚙️  Concurrency: parallel_insert={max_parallel_insert}")
    logger.info("=" * 70)

    # 1. 初始化多租户管理器（懒加载，不创建实例）
    from src.multi_tenant import get_multi_tenant_manager

    manager = get_multi_tenant_manager()
    logger.info(f"✓ Multi-Tenant Manager initialized (max_instances={max_tenant_instances})")

    logger.info("=" * 70)
    logger.info("✅ Multi-Tenant Architecture Ready")
    logger.info("   - Tenant Isolation: workspace-based")
    logger.info("   - Instance Pool: LRU cache (懒加载)")
    logger.info("   - Shared Resources: LLM/Embedding functions")
    logger.info("   - Parser Support: MinerU/Docling (按需创建)")
    logger.info("=" * 70)

    # 2. 初始化文件服务和清理任务
    from src.file_url_service import get_file_service
    file_service = get_file_service()

    # 启动后台文件清理任务
    cleanup_interval = int(os.getenv("FILE_CLEANUP_INTERVAL", "3600"))  # 默认 1 小时
    cleanup_hours = int(os.getenv("FILE_CLEANUP_HOURS", "24"))  # 默认 24 小时保留
    file_service.start_cleanup_task(interval_seconds=cleanup_interval, max_age_hours=cleanup_hours)
    logger.info(f"✓ File cleanup task started: interval={cleanup_interval}s, retention={cleanup_hours}h")

    # 3. 启动性能监控
    from src.metrics import get_metrics_collector
    metrics_collector = get_metrics_collector()
    metrics_collector.start_system_monitoring(interval=60)  # 每 60 秒采集一次系统指标
    logger.info("✓ Performance monitoring started")

    logger.info("=" * 70)
    logger.info("✅ Multi-Tenant RAG API Started Successfully")
    logger.info("=" * 70)

    yield  # 应用运行期间保持实例可用

    # 关闭时清理资源
    logger.info("Shutting down Multi-Tenant RAG API...")
    # 清理多租户管理器（如需要）

def select_parser_by_file(filename: str, file_size: int) -> str | None:
    """
    根据文件特征智能选择解析器

    策略：
    - 纯文本 (.txt, .md) → 返回 None（直接插入 LightRAG，不需要解析器）
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
        "mineru", "docling", 或 None（纯文本文件不需要解析器）
    """
    import os
    ext = os.path.splitext(filename)[1].lower()

    # 纯文本文件 → 不需要解析器（直接插入 LightRAG）
    if ext in ['.txt', '.md', '.markdown']:
        return None

    # 图片文件 → MinerU（需要 OCR）
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
        return "mineru"

    # PDF/Office 小文件 → Docling（快速）
    if ext in ['.pdf', '.docx', '.xlsx', '.pptx', '.html', '.htm'] and file_size < 500 * 1024:  # < 500KB
        return "docling"

    # 大文件或其他 → MinerU
    return "mineru"
