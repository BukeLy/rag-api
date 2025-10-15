import os
from dotenv import load_dotenv
import logging
from contextlib import asynccontextmanager

# -- 从 raganything_example.py 抄过来的组件 --
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc
from raganything import RAGAnything, RAGAnythingConfig

# --- 配置 ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 全局 RAG 实例（双解析器架构）---
rag_instance_mineru = None  # MinerU: 强大多模态，适合复杂文档（图片、表格、公式）
rag_instance_docling = None  # Docling: 轻量快速，适合纯文本/小文件
rag_instance = None  # 默认实例（向后兼容）

# --- RAG 实例管理 ---
@asynccontextmanager
async def lifespan(app):
    # 启动时创建双 RAG 实例（MinerU + Docling）
    global rag_instance, rag_instance_mineru, rag_instance_docling
    logger.info("Starting up and creating RAGAnything instances (MinerU + Docling)...")

    ark_api_key = os.getenv("ARK_API_KEY")
    ark_base_url = os.getenv("ARK_BASE_URL")
    sf_api_key = os.getenv("SF_API_KEY")
    sf_base_url = os.getenv("SF_BASE_URL")
    if not ark_api_key:
        raise RuntimeError("ARK_API_KEY is not set!")
    if not sf_api_key:
        raise RuntimeError("SF_API_KEY is not set!")
    if not sf_base_url:
        raise RuntimeError("SF_BASE_URL is not set!")
    if not ark_base_url:
        raise RuntimeError("ARK_BASE_URL is not set!")

    # 1. 定义共享的 LLM 和 Embedding 函数
    def llm_model_func(prompt, **kwargs):
        return openai_complete_if_cache(
            "seed-1-6-250615", prompt, api_key=ark_api_key, base_url=ark_base_url, **kwargs
        )

    embedding_func = EmbeddingFunc(
        embedding_dim=4096,  # Qwen/Qwen3-Embedding-8B 实际返回 4096 维向量
        func=lambda texts: openai_embed(
            texts, model="Qwen/Qwen3-Embedding-8B", api_key=sf_api_key, base_url=sf_base_url
        ),
    )
    def vision_model_func(prompt, **kwargs):
        return openai_complete_if_cache(
            "seed-1-6-250615", prompt, api_key=ark_api_key, base_url=ark_base_url, **kwargs
        )

    # 2. 创建 MinerU 实例（强大多模态，内存占用大）
    config_mineru = RAGAnythingConfig(
        working_dir="./rag_local_storage",
        parser="mineru",  # 强大的多模态解析
        enable_image_processing=True,
        enable_table_processing=True,
        enable_equation_processing=True,
    )
    rag_instance_mineru = RAGAnything(
        config=config_mineru,
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
        vision_model_func=vision_model_func,
    )
    await rag_instance_mineru._ensure_lightrag_initialized()
    logger.info("✓ MinerU instance initialized (for complex multimodal documents)")

    # 3. 创建 Docling 实例（轻量快速，内存占用小）
    config_docling = RAGAnythingConfig(
        working_dir="./rag_local_storage",  # 共享相同的 working_dir
        parser="docling",  # 轻量级解析器
        enable_image_processing=False,  # Docling 不支持多模态
        enable_table_processing=False,
        enable_equation_processing=False,
    )
    rag_instance_docling = RAGAnything(
        config=config_docling,
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
        vision_model_func=vision_model_func,
    )
    await rag_instance_docling._ensure_lightrag_initialized()
    logger.info("✓ Docling instance initialized (for fast text processing)")

    # 4. 设置默认实例为 MinerU（向后兼容）
    rag_instance = rag_instance_mineru
    logger.info("✅ Dual-parser RAG system ready (MinerU + Docling)")

    yield  # 应用运行期间保持实例可用

    # 关闭时清理资源
    logger.info("Shutting down RAGAnything instance...")
    # 如果需要清理资源，可以在这里添加

# 获取 RAG 实例的函数
def get_rag_instance(parser: str = "auto"):
    """
    获取 RAG 实例
    
    Args:
        parser: 解析器类型
            - "mineru": 使用 MinerU（强大多模态，内存占用大）
            - "docling": 使用 Docling（轻量快速，内存占用小）
            - "auto": 自动选择（默认返回 MinerU）
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
    - 纯文本文件 (.txt, .md) 且 < 1MB → Docling（快速）
    - 图片文件 (.jpg, .png) → MinerU（OCR能力强）
    - PDF/Office 且 < 500KB → Docling（快速）
    - PDF/Office 且 > 500KB → MinerU（更强大）
    - 其他 → MinerU（默认）
    
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
    
    # 纯文本且小文件 → Docling
    if ext in ['.txt', '.md', '.markdown'] and file_size < 1 * 1024 * 1024:  # < 1MB
        return "docling"
    
    # PDF/Office 小文件 → Docling
    if ext in ['.pdf', '.docx', '.xlsx', '.pptx'] and file_size < 500 * 1024:  # < 500KB
        return "docling"
    
    # 其他或大文件 → MinerU
    return "mineru"
