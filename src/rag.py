import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from functools import partial

from src.logger import logger
from src.config import config  # 新增：使用集中配置管理

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

    # 读取 LLM 和 Embedding 配置（使用新的配置管理类）
    # 配置已在 src/config.py 中验证，无需重复检查
    ark_api_key = config.llm.api_key
    ark_base_url = config.llm.base_url
    ark_model = config.llm.model

    sf_api_key = config.embedding.api_key
    sf_base_url = config.embedding.base_url
    sf_embedding_model = config.embedding.model

    rerank_model = config.rerank.model  # 可选配置

    # 读取 LightRAG 查询优化参数
    top_k = config.lightrag_query.top_k
    chunk_top_k = config.lightrag_query.chunk_top_k
    max_async = config.llm.max_async
    max_parallel_insert = config.lightrag_query.max_parallel_insert
    max_entity_tokens = config.lightrag_query.max_entity_tokens
    max_relation_tokens = config.lightrag_query.max_relation_tokens
    max_total_tokens = config.lightrag_query.max_total_tokens

    # 读取多租户配置
    max_tenant_instances = config.multi_tenant.max_tenant_instances

    # 读取 Embedding 维度配置
    embedding_dim = config.embedding.dim

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

def select_parser_by_file(filename: str, file_size: int, file_path: str = None) -> tuple[str | None, str | None]:
    """
    智能选择解析器（v2.0 基于 DeepSeek-OCR 完整测试优化）

    策略：
    - 纯文本 (.txt, .md) → 返回 (None, None)（直接插入 LightRAG）
    - 支持 Parser 的文件：
      - 根据 PARSER_MODE 环境变量决定：
        - "auto": 使用智能选择器（推荐）
        - "deepseek-ocr": 强制使用 DeepSeek-OCR
        - "mineru": 强制使用 MinerU
        - "docling": 强制使用 Docling
      - 智能选择器会根据复杂度评分选择最优 Parser 和模式

    Args:
        filename: 文件名
        file_size: 文件大小（字节）
        file_path: 文件路径（用于复杂度分析，可选）

    Returns:
        (parser_name, deepseek_mode)
        - parser_name: "deepseek-ocr", "mineru", "docling", 或 None
        - deepseek_mode: "free_ocr", "grounding", 或 None
    """
    import os
    from pathlib import Path

    ext = os.path.splitext(filename)[1].lower()

    # 纯文本文件 → 不需要解析器（直接插入 LightRAG）
    if ext in ['.txt', '.md', '.markdown', '.json', '.csv']:
        return (None, None)

    # 读取 Parser 模式配置
    parser_mode = os.getenv("PARSER_MODE", "auto").lower()

    # 如果不是 auto 模式，直接返回指定 Parser
    if parser_mode != "auto":
        if parser_mode == "deepseek-ocr":
            # 使用默认模式（从环境变量读取）
            default_mode = os.getenv("DEEPSEEK_OCR_DEFAULT_MODE", "free_ocr")
            return ("deepseek-ocr", default_mode)
        elif parser_mode == "mineru":
            return ("mineru", None)
        elif parser_mode == "docling":
            return ("docling", None)
        else:
            logger.warning(f"Unknown PARSER_MODE: {parser_mode}, falling back to 'auto'")

    # Auto 模式：使用智能选择器
    # 如果没有提供 file_path，使用简单规则（兼容旧逻辑）
    if not file_path or not Path(file_path).exists():
        logger.warning(f"file_path not provided or invalid, using simple rules")

        # 图片文件 → DeepSeek-OCR（OCR 能力强 + 速度快）
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
            return ("deepseek-ocr", "free_ocr")

        # PDF/Office 小文件 → DeepSeek-OCR（快速）
        size_threshold_bytes = config.parser.size_threshold_kb * 1024
        if ext in ['.pdf', '.docx', '.xlsx', '.pptx'] and file_size < size_threshold_bytes:
            return ("deepseek-ocr", "free_ocr")

        # 大文件或其他 → MinerU（默认）
        return ("mineru", None)

    # 使用智能选择器（基于复杂度分析）
    try:
        from src.smart_parser_selector import create_selector, ParserType
        from src.deepseek_ocr_client import DSSeekMode

        selector = create_selector()
        parser_type, ds_mode = selector.select_parser(
            file_path=file_path,
            vlm_mode=os.getenv("VLM_MODE", "off"),
            prefer_speed=os.getenv("COMPLEXITY_PREFER_SPEED", "true").lower() == "true"
        )

        # 转换为字符串返回值
        parser_name = parser_type.value
        deepseek_mode = ds_mode.value if ds_mode else None

        logger.info(
            f"Smart selector: {filename} → parser={parser_name}, "
            f"mode={deepseek_mode or 'N/A'}"
        )

        return (parser_name, deepseek_mode)

    except Exception as e:
        logger.error(f"Smart selector failed: {e}, falling back to simple rules")

        # 降级：使用简单规则
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
            return ("deepseek-ocr", "free_ocr")
        elif file_size < config.parser.size_threshold_kb * 1024:
            return ("deepseek-ocr", "free_ocr")
        else:
            return ("mineru", None)
