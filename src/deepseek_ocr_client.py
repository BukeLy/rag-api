"""
DeepSeek-OCR Client

官方文档：https://api-docs.deepseek.com/quick_start/multimodal_vision
SiliconFlow API：https://siliconflow.cn/zh-cn/models

功能特性：
- 支持多种 OCR 模式：Free OCR、Grounding Document、OCR Image
- 智能降级策略：Free OCR → Grounding Document
- 支持中文识别（中文密度 >30% 场景优化）
- 自动 PDF 转图片（支持自定义 DPI）
- 异步/同步双接口
"""

import os
import base64
from typing import Optional
from enum import Enum
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import aiohttp
import requests

from src.logger import logger
from src.config import config  # 使用集中配置管理


class DSSeekMode(Enum):
    """DeepSeek-OCR 模式枚举"""
    FREE_OCR = "free_ocr"        # 纯 Markdown 输出（最快）
    GROUNDING = "grounding"      # HTML + bounding boxes（复杂表格最佳）
    OCR_IMAGE = "ocr_image"      # 词级 bounding boxes（不稳定）


@dataclass
class DSSeekConfig:
    """DeepSeek-OCR 配置（已弃用，建议使用 config.ds_ocr）"""
    api_key: str = field(default_factory=lambda: config.ds_ocr.api_key)
    base_url: str = field(default_factory=lambda: config.ds_ocr.base_url)
    model_name: str = field(default_factory=lambda: config.ds_ocr.model)

    # 请求配置
    timeout: int = field(default_factory=lambda: config.ds_ocr.timeout)
    max_tokens: int = field(default_factory=lambda: config.ds_ocr.max_tokens)
    temperature: float = 0.0  # 确定性输出

    # DPI 配置（200 DPI 是最佳平衡点）
    dpi: int = field(default_factory=lambda: config.ds_ocr.dpi)

    # 智能降级配置
    fallback_enabled: bool = field(default_factory=lambda: config.ds_ocr.fallback_enabled)
    fallback_mode: str = field(default_factory=lambda: config.ds_ocr.fallback_mode)
    min_output_threshold: int = field(default_factory=lambda: config.ds_ocr.min_output_threshold)

    def __post_init__(self):
        """验证配置"""
        if not self.api_key:
            raise ValueError("DS_OCR_API_KEY is required. Please set it in environment variables.")


class DeepSeekOCRClient:
    """DeepSeek-OCR 客户端（基于 v2.0 智能选择方案）"""

    def __init__(self, config: Optional[DSSeekConfig] = None):
        """
        初始化客户端

        Args:
            config: DeepSeek-OCR 配置，如果为 None 则使用默认配置
        """
        self.config = config or DSSeekConfig()

        logger.info(f"DeepSeek-OCR Client initialized: {self.config.base_url}")

    def _build_prompt(self, mode: DSSeekMode, chinese_hint: bool = False) -> str:
        """
        构建提示词（基于 v2.0 官方格式）

        Args:
            mode: OCR 模式
            chinese_hint: 是否添加中文语言提示（用于简单中文表格 <10 字）

        Returns:
            提示词字符串

        教训来源：
        - Statement 测试：错误 prompts 导致输出垃圾
        - IELTS 测试：简单中文表格 <10 字需语言提示
        """
        if mode == DSSeekMode.FREE_OCR:
            prompt = "Free OCR."
            if chinese_hint:
                prompt += " Please extract all text in Chinese (中文) and English."
            return prompt
        elif mode == DSSeekMode.GROUNDING:
            return "<|grounding|>Convert the document to markdown."
        elif mode == DSSeekMode.OCR_IMAGE:
            return "<|grounding|>OCR this image."
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _pdf_to_base64(self, file_path: str, dpi: Optional[int] = None) -> str:
        """
        PDF 转 Base64 图片

        Args:
            file_path: PDF 文件路径
            dpi: 图片 DPI（150=可能幻觉，200=稳定，300=文件大）

        Returns:
            Base64 编码的 PNG 图片

        教训来源：
        - Statement 测试（150 DPI）：Free OCR 幻觉生成 Col1, Col2...
        - Statement 测试（200 DPI）：Grounding 完美提取 27 行
        """
        dpi = dpi or self.config.dpi

        doc = fitz.open(file_path)
        page = doc[0]  # 只处理第一页
        pix = page.get_pixmap(dpi=dpi)
        img_data = pix.tobytes("png")
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        doc.close()

        logger.debug(f"PDF converted to base64 (DPI={dpi}): {len(img_base64)} bytes")
        return img_base64

    def _post_process(self, content: str, mode: DSSeekMode) -> str:
        """
        后处理输出

        1. 移除特殊标记：<|ref|>、<|det|>
        2. 保留 HTML 表格（LightRAG 支持）

        Args:
            content: API 返回的原始内容
            mode: OCR 模式

        Returns:
            处理后的 Markdown 文本
        """
        import re

        # 移除特殊标记
        content = re.sub(r'<\|ref\|>.*?</\|ref\|>', '', content, flags=re.DOTALL)
        content = re.sub(r'<\|det\|>.*?</\|det\|>', '', content, flags=re.DOTALL)

        # Grounding 模式：保留 HTML 表格（LightRAG 支持）
        if mode == DSSeekMode.GROUNDING:
            return content

        # Free OCR 模式：已经是纯 Markdown，无需转换
        return content

    async def parse_document(
        self,
        file_path: str,
        mode: DSSeekMode = DSSeekMode.FREE_OCR,
        dpi: Optional[int] = None,
        chinese_hint: bool = False
    ) -> str:
        """
        解析文档（异步）

        Args:
            file_path: 文件路径
            mode: OCR 模式
            dpi: PDF 转图片 DPI（None 表示使用默认配置）
            chinese_hint: 是否添加中文语言提示

        Returns:
            Markdown 文本

        教训来源：
        - Visa 测试：Free OCR 输出 <500 字符需降级 Grounding
        """
        # 1. PDF 转图片
        img_base64 = self._pdf_to_base64(file_path, dpi=dpi)

        # 2. 构建提示词
        prompt = self._build_prompt(mode, chinese_hint=chinese_hint)

        # 3. 调用 API
        result = await self._call_api(img_base64, prompt)

        # 4. 智能降级（基于 Visa 测试经验）
        if (self.config.fallback_enabled and
            mode == DSSeekMode.FREE_OCR and
            len(result) < self.config.min_output_threshold):

            logger.warning(
                f"Free OCR output too short ({len(result)} chars < {self.config.min_output_threshold}), "
                f"falling back to {self.config.fallback_mode} mode"
            )

            fallback_mode = DSSeekMode(self.config.fallback_mode)
            prompt_fallback = self._build_prompt(fallback_mode)
            result = await self._call_api(img_base64, prompt_fallback)
            mode = fallback_mode  # 更新模式用于后处理

        # 5. 后处理（移除特殊标记）
        result = self._post_process(result, mode)

        logger.info(f"Document parsed successfully: {len(result)} characters (mode={mode.value})")
        return result

    def parse_document_sync(
        self,
        file_path: str,
        mode: DSSeekMode = DSSeekMode.FREE_OCR,
        dpi: Optional[int] = None,
        chinese_hint: bool = False
    ) -> str:
        """
        解析文档（同步）

        Args:
            file_path: 文件路径
            mode: OCR 模式
            dpi: PDF 转图片 DPI
            chinese_hint: 是否添加中文语言提示

        Returns:
            Markdown 文本
        """
        # 1. PDF 转图片
        img_base64 = self._pdf_to_base64(file_path, dpi=dpi)

        # 2. 构建提示词
        prompt = self._build_prompt(mode, chinese_hint=chinese_hint)

        # 3. 调用 API
        result = self._call_api_sync(img_base64, prompt)

        # 4. 智能降级
        if (self.config.fallback_enabled and
            mode == DSSeekMode.FREE_OCR and
            len(result) < self.config.min_output_threshold):

            logger.warning(
                f"Free OCR output too short ({len(result)} chars < {self.config.min_output_threshold}), "
                f"falling back to {self.config.fallback_mode} mode"
            )

            fallback_mode = DSSeekMode(self.config.fallback_mode)
            prompt_fallback = self._build_prompt(fallback_mode)
            result = self._call_api_sync(img_base64, prompt_fallback)
            mode = fallback_mode

        # 5. 后处理
        result = self._post_process(result, mode)

        logger.info(f"Document parsed successfully: {len(result)} characters (mode={mode.value})")
        return result

    async def _call_api(self, img_base64: str, prompt: str) -> str:
        """
        调用 DeepSeek-OCR API（异步）

        Args:
            img_base64: Base64 编码的图片
            prompt: 提示词

        Returns:
            API 返回的文本内容

        Raises:
            Exception: API 调用失败时抛出异常
        """
        payload = {
            "model": self.config.model_name,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        url = f"{self.config.base_url}/chat/completions"

        async with aiohttp.ClientSession() as session:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            async with session.post(url, headers=headers, json=payload, timeout=timeout) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API error {response.status}: {error_text}")

                result = await response.json()
                content = result['choices'][0]['message']['content']

                # 记录 token 消耗（用于成本分析）
                usage = result.get('usage', {})
                logger.debug(
                    f"API usage: prompt_tokens={usage.get('prompt_tokens')}, "
                    f"completion_tokens={usage.get('completion_tokens')}, "
                    f"total_tokens={usage.get('total_tokens')}"
                )

                return content

    def _call_api_sync(self, img_base64: str, prompt: str) -> str:
        """
        调用 DeepSeek-OCR API（同步）

        Args:
            img_base64: Base64 编码的图片
            prompt: 提示词

        Returns:
            API 返回的文本内容
        """
        payload = {
            "model": self.config.model_name,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        url = f"{self.config.base_url}/chat/completions"

        response = requests.post(url, headers=headers, json=payload, timeout=self.config.timeout)

        if response.status_code != 200:
            raise Exception(f"API error {response.status_code}: {response.text}")

        result = response.json()
        content = result['choices'][0]['message']['content']

        # 记录 token 消耗
        usage = result.get('usage', {})
        logger.debug(
            f"API usage: prompt_tokens={usage.get('prompt_tokens')}, "
            f"completion_tokens={usage.get('completion_tokens')}, "
            f"total_tokens={usage.get('total_tokens')}"
        )

        return content


# ============== 便捷函数 ==============

def create_client(
    api_key: Optional[str] = None,
    **kwargs
) -> DeepSeekOCRClient:
    """
    创建 DeepSeek-OCR 客户端（便捷函数）

    Args:
        api_key: API Key（可选，优先使用配置管理类 config.ds_ocr）
        **kwargs: 其他配置参数

    Returns:
        DeepSeekOCRClient: 客户端实例

    Example:
        # 使用集中配置（推荐）
        client = create_client()

        # 手动指定 API key（测试用）
        client = create_client(api_key="your_api_key_here")
    """
    ds_config = DSSeekConfig(
        api_key=api_key or config.ds_ocr.api_key,
        **kwargs
    )
    return DeepSeekOCRClient(ds_config)


# ============== 示例代码 ==============

async def example_async():
    """异步使用示例"""
    client = create_client()

    try:
        # 方式 1：简单文档（Free OCR）
        result = await client.parse_document(
            file_path="/path/to/simple.pdf",
            mode=DSSeekMode.FREE_OCR
        )
        print(f"✓ Parsed: {len(result)} characters")

        # 方式 2：复杂表格（Grounding Document）
        result = await client.parse_document(
            file_path="/path/to/complex_table.pdf",
            mode=DSSeekMode.GROUNDING
        )
        print(f"✓ Parsed: {len(result)} characters")

        # 方式 3：简单中文表格（Free OCR + 语言提示）
        result = await client.parse_document(
            file_path="/path/to/chinese_simple.pdf",
            mode=DSSeekMode.FREE_OCR,
            chinese_hint=True
        )
        print(f"✓ Parsed: {len(result)} characters")

    except Exception as e:
        print(f"✗ Parse failed: {e}")


def example_sync():
    """同步使用示例"""
    client = create_client()

    try:
        result = client.parse_document_sync(
            file_path="/path/to/document.pdf",
            mode=DSSeekMode.FREE_OCR
        )
        print(f"✓ Parsed: {len(result)} characters")
    except Exception as e:
        print(f"✗ Parse failed: {e}")


if __name__ == "__main__":
    # 运行示例
    # asyncio.run(example_async())
    # example_sync()
    pass
