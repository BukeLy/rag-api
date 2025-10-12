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

# --- 全局 RAG 实例 ---
rag_instance = None

# --- RAG 实例管理 ---
@asynccontextmanager
async def lifespan(app):
    # 启动时创建 RAG 实例
    global rag_instance
    logger.info("Starting up and creating RAGAnything instance...")

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

    # 1. 配置 RAGAnything，使用默认的本地存储
    # 不要去碰 lightrag_kwargs，让它自己处理本地文件存储
    config = RAGAnythingConfig(
        working_dir="./rag_local_storage", # 明确指定本地存储路径
        # 关掉这些烦人的东西，避免之前的 bug
        enable_image_processing=True,
        enable_table_processing=True,
        enable_equation_processing=True,
    )

    # 2. 定义 LLM 和 Embedding 函数 (直接从 example 抄)
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
    # 3. 实例化 RAGAnything
    rag_instance = RAGAnything(
        config=config,
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
        vision_model_func=vision_model_func,
    )
    
    # 4. 显式初始化 LightRAG 实例（确保查询时可用）
    await rag_instance._ensure_lightrag_initialized()
    logger.info("RAGAnything instance created and LightRAG initialized. Ready to serve.")

    yield  # 应用运行期间保持实例可用

    # 关闭时清理资源
    logger.info("Shutting down RAGAnything instance...")
    # 如果需要清理资源，可以在这里添加

# 获取 RAG 实例的函数
def get_rag_instance():
    """获取全局 RAG 实例"""
    return rag_instance
