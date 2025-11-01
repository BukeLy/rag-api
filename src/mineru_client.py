"""
MinerU Remote API Client

官方文档：https://mineru.net/apiManage/docs

功能特性：
- 支持远程 API 调用，减少本地性能开销
- 支持批量文档解析
- 内置限流机制，防止超过 API 限制
- 支持所有 MinerU API 参数
- 自动重试和错误处理
- 异步任务状态轮询
"""

import os
import time
import asyncio
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import requests
from pathlib import Path

from src.logger import logger


class TaskStatus(str, Enum):
    """任务状态枚举（根据 MinerU API 官方文档）"""
    WAITING_FILE = "waiting-file"  # 等待文件上传
    PENDING = "pending"            # 排队中
    RUNNING = "running"            # 正在解析
    CONVERTING = "converting"      # 格式转换中
    DONE = "done"                  # 已完成
    FAILED = "failed"              # 解析失败


@dataclass
class MinerUConfig:
    """MinerU API 配置"""
    api_token: str = field(default_factory=lambda: os.getenv("MINERU_API_TOKEN", ""))
    base_url: str = field(default_factory=lambda: os.getenv("MINERU_API_BASE_URL", "https://mineru.net"))
    api_version: str = "v4"
    
    # 限流配置（从环境变量读取）
    max_concurrent_requests: int = field(
        default_factory=lambda: int(os.getenv("MINERU_MAX_CONCURRENT_REQUESTS", "5"))
    )
    requests_per_minute: int = field(
        default_factory=lambda: int(os.getenv("MINERU_REQUESTS_PER_MINUTE", "60"))
    )
    retry_max_attempts: int = field(
        default_factory=lambda: int(os.getenv("MINERU_RETRY_MAX_ATTEMPTS", "3"))
    )
    retry_delay: float = 1.0  # 重试延迟（秒）
    
    # 轮询配置（从环境变量读取）
    poll_interval: float = 2.0  # 状态轮询间隔（秒）
    poll_timeout: float = field(
        default_factory=lambda: float(os.getenv("MINERU_POLL_TIMEOUT", "600.0"))
    )

    # HTTP 请求超时配置（从环境变量读取）
    http_timeout: float = field(
        default_factory=lambda: float(os.getenv("MINERU_HTTP_TIMEOUT", "60.0"))
    )

    def __post_init__(self):
        """验证配置"""
        if not self.api_token:
            raise ValueError("MINERU_API_TOKEN is required. Please set it in environment variables or config.")


@dataclass
class ParseOptions:
    """文档解析选项（根据 MinerU API 官方文档）"""
    enable_formula: bool = True       # 启用公式解析（默认 true）
    enable_table: bool = True         # 启用表格解析（默认 true）
    language: str = "ch"              # 语言：ch（中文）/ en（英文）
    callback: Optional[str] = None    # 解析结果回调 URL
    seed: Optional[str] = None        # 回调签名种子（使用 callback 时必填）
    extra_formats: Optional[List[str]] = None  # 额外导出格式：["docx", "html", "latex"]
    model_version: str = field(
        default_factory=lambda: os.getenv("MINERU_MODEL_VERSION", "vlm")
    )  # 模型版本：vlm（默认，高精度）/ pipeline（传统稳定）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为 API 参数字典"""
        result = {
            "enable_formula": self.enable_formula,
            "enable_table": self.enable_table,
            "language": self.language,
            "model_version": self.model_version,
        }
        if self.callback:
            result["callback"] = self.callback
        if self.seed:
            result["seed"] = self.seed
        if self.extra_formats:
            result["extra_formats"] = self.extra_formats
        return result


@dataclass
class FileTask:
    """单个文件任务（根据 MinerU API 官方文档）"""
    url: str                              # 文件 URL（必填）支持 .pdf/.doc/.docx/.ppt/.pptx/.png/.jpg/.jpeg
    data_id: Optional[str] = None        # 数据 ID（可选，用于标识文件）
    is_ocr: Optional[bool] = None        # 是否使用 OCR（可选，覆盖全局设置，默认 false）
    page_ranges: Optional[str] = None    # 页码范围（可选）如 "2,4-6" 或 "2--2"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为 API 参数字典"""
        result = {"url": self.url}
        
        if self.data_id:
            result["data_id"] = self.data_id
        if self.is_ocr is not None:
            result["is_ocr"] = self.is_ocr
        if self.page_ranges:
            result["page_ranges"] = self.page_ranges
        
        return result


@dataclass
class TaskResult:
    """任务结果（根据 MinerU API 官方文档）"""
    task_id: str                                      # 单个任务 ID 或批量任务 ID
    status: TaskStatus                                # 任务状态
    files: List[Dict[str, Any]] = field(default_factory=list)  # 文件结果列表
    error_message: Optional[str] = None               # 错误信息
    full_zip_url: Optional[str] = None               # 结果压缩包 URL（单个任务）
    extract_progress: Optional[Dict[str, Any]] = None  # 解析进度（running 状态时）
    
    @property
    def is_completed(self) -> bool:
        """任务是否完成"""
        return self.status == TaskStatus.DONE
    
    @property
    def is_failed(self) -> bool:
        """任务是否失败"""
        return self.status == TaskStatus.FAILED
    
    @property
    def is_processing(self) -> bool:
        """任务是否处理中"""
        return self.status in [TaskStatus.WAITING_FILE, TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.CONVERTING]


class RateLimiter:
    """限流器"""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.request_times: List[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """获取请求许可（异步版本）"""
        async with self._lock:
            now = time.time()
            # 清理一分钟前的记录
            self.request_times = [t for t in self.request_times if now - t < 60]
            
            # 如果达到限制，等待
            if len(self.request_times) >= self.requests_per_minute:
                wait_time = 60 - (now - self.request_times[0])
                if wait_time > 0:
                    logger.warning(f"Rate limit reached, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    return await self.acquire()
            
            # 记录本次请求时间
            self.request_times.append(now)
    
    def acquire_sync(self):
        """获取请求许可（同步版本）"""
        now = time.time()
        # 清理一分钟前的记录
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        # 如果达到限制，等待
        if len(self.request_times) >= self.requests_per_minute:
            wait_time = 60 - (now - self.request_times[0])
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.2f}s")
                time.sleep(wait_time)
                return self.acquire_sync()
        
        # 记录本次请求时间
        self.request_times.append(now)


class MinerUClient:
    """MinerU 远程 API 客户端"""
    
    def __init__(self, config: Optional[MinerUConfig] = None):
        """
        初始化客户端
        
        Args:
            config: MinerU 配置，如果为 None 则使用默认配置
        """
        self.config = config or MinerUConfig()
        self.rate_limiter = RateLimiter(self.config.requests_per_minute)
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        
        logger.info(f"MinerU Client initialized: {self.config.base_url}/api/{self.config.api_version}")
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头（根据官方文档）"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_token}",
            "Accept": "*/*"
        }
    
    def _get_api_url(self, endpoint: str) -> str:
        """获取完整 API URL"""
        return f"{self.config.base_url}/api/{self.config.api_version}/{endpoint}"
    
    async def create_batch_task(
        self, 
        files: List[FileTask], 
        options: Optional[ParseOptions] = None
    ) -> TaskResult:
        """
        创建批量解析任务（异步）
        
        Args:
            files: 文件任务列表
            options: 解析选项
        
        Returns:
            TaskResult: 任务结果对象
        
        Raises:
            Exception: 创建任务失败时抛出异常
        """
        if not files:
            raise ValueError("Files list cannot be empty")
        
        options = options or ParseOptions()
        
        # 准备请求数据
        data = {
            **options.to_dict(),
            "files": [f.to_dict() for f in files]
        }
        
        url = self._get_api_url("extract/task/batch")
        headers = self._get_headers()
        
        # 限流
        await self.rate_limiter.acquire()
        
        # 发送请求（带重试）
        for attempt in range(self.config.retry_max_attempts):
            try:
                async with self.semaphore:
                    async with aiohttp.ClientSession() as session:
                        # 使用配置的 HTTP 超时
                        timeout = aiohttp.ClientTimeout(total=self.config.http_timeout)
                        async with session.post(url, headers=headers, json=data, timeout=timeout) as response:
                            result = await response.json()
                            
                            if response.status == 200 and result.get("code") == 0:
                                batch_id = result["data"]["batch_id"]
                                logger.info(f"✓ Batch task created successfully: {batch_id}")
                                
                                return TaskResult(
                                    task_id=batch_id,
                                    status=TaskStatus.PENDING
                                )
                            else:
                                error_msg = result.get("msg", "Unknown error")
                                logger.error(f"✗ Failed to create batch task: {error_msg}")
                                raise Exception(f"API Error: {error_msg}")
            
            except Exception as e:
                if attempt < self.config.retry_max_attempts - 1:
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    raise
    
    def create_batch_task_sync(
        self, 
        files: List[FileTask], 
        options: Optional[ParseOptions] = None
    ) -> TaskResult:
        """
        创建批量解析任务（同步）
        
        Args:
            files: 文件任务列表
            options: 解析选项
        
        Returns:
            TaskResult: 任务结果对象
        """
        if not files:
            raise ValueError("Files list cannot be empty")
        
        options = options or ParseOptions()
        
        data = {
            **options.to_dict(),
            "files": [f.to_dict() for f in files]
        }
        
        url = self._get_api_url("extract/task/batch")
        headers = self._get_headers()
        
        # 限流
        self.rate_limiter.acquire_sync()
        
        # 发送请求（带重试）
        for attempt in range(self.config.retry_max_attempts):
            try:
                response = requests.post(url, headers=headers, json=data, timeout=self.config.http_timeout)
                result = response.json()
                
                if response.status_code == 200 and result.get("code") == 0:
                    batch_id = result["data"]["batch_id"]
                    logger.info(f"✓ Batch task created successfully: {batch_id}")
                    
                    return TaskResult(
                        task_id=batch_id,
                        status=TaskStatus.PENDING
                    )
                else:
                    error_msg = result.get("msg", "Unknown error")
                    logger.error(f"✗ Failed to create batch task: {error_msg}")
                    raise Exception(f"API Error: {error_msg}")
            
            except Exception as e:
                if attempt < self.config.retry_max_attempts - 1:
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise
    
    async def get_batch_result(self, batch_id: str) -> TaskResult:
        """
        查询批量任务结果（异步）
        
        Args:
            batch_id: 批量任务 ID
        
        Returns:
            TaskResult: 任务结果对象
        """
        url = self._get_api_url(f"extract-results/batch/{batch_id}")
        headers = self._get_headers()
        
        # 限流
        await self.rate_limiter.acquire()
        
        try:
            async with self.semaphore:
                async with aiohttp.ClientSession() as session:
                    # 使用配置的 HTTP 超时，避免长时间等待
                    timeout = aiohttp.ClientTimeout(total=self.config.http_timeout)
                    async with session.get(url, headers=headers, timeout=timeout) as response:
                        result = await response.json()
                        
                        if response.status == 200 and result.get("code") == 0:
                            data = result["data"]
                            
                            # 解析状态（官方文档：state 字段）
                            state_map = {
                                "waiting-file": TaskStatus.WAITING_FILE,
                                "pending": TaskStatus.PENDING,
                                "running": TaskStatus.RUNNING,
                                "converting": TaskStatus.CONVERTING,
                                "done": TaskStatus.DONE,
                                "failed": TaskStatus.FAILED,
                            }
                            
                            # 处理批量结果
                            files_result = []
                            if "extract_result" in data:
                                for item in data["extract_result"]:
                                    files_result.append({
                                        "file_name": item.get("file_name"),
                                        "data_id": item.get("data_id"),
                                        "state": item.get("state"),
                                        "full_zip_url": item.get("full_zip_url"),
                                        "err_msg": item.get("err_msg"),
                                        "extract_progress": item.get("extract_progress"),
                                    })
                            
                            return TaskResult(
                                task_id=batch_id,
                                status=state_map.get(data.get("state", "pending"), TaskStatus.PENDING),
                                files=files_result,
                                error_message=data.get("err_msg"),
                                full_zip_url=data.get("full_zip_url"),
                                extract_progress=data.get("extract_progress"),
                            )
                        else:
                            error_msg = result.get("msg", "Unknown error")
                            raise Exception(f"API Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Failed to get batch result: {e}")
            raise
    
    def get_batch_result_sync(self, batch_id: str) -> TaskResult:
        """
        查询批量任务结果（同步）
        
        Args:
            batch_id: 批量任务 ID
        
        Returns:
            TaskResult: 任务结果对象
        """
        url = self._get_api_url(f"extract-results/batch/{batch_id}")
        headers = self._get_headers()
        
        # 限流
        self.rate_limiter.acquire_sync()
        
        try:
            response = requests.get(url, headers=headers, timeout=self.config.http_timeout)
            result = response.json()
            
            if response.status_code == 200 and result.get("code") == 0:
                data = result["data"]
                
                # 解析状态（官方文档：state 字段）
                state_map = {
                    "waiting-file": TaskStatus.WAITING_FILE,
                    "pending": TaskStatus.PENDING,
                    "running": TaskStatus.RUNNING,
                    "converting": TaskStatus.CONVERTING,
                    "done": TaskStatus.DONE,
                    "failed": TaskStatus.FAILED,
                }
                
                # 处理批量结果
                files_result = []
                if "extract_result" in data:
                    for item in data["extract_result"]:
                        files_result.append({
                            "file_name": item.get("file_name"),
                            "data_id": item.get("data_id"),
                            "state": item.get("state"),
                            "full_zip_url": item.get("full_zip_url"),
                            "err_msg": item.get("err_msg"),
                            "extract_progress": item.get("extract_progress"),
                        })
                
                return TaskResult(
                    task_id=batch_id,
                    status=state_map.get(data.get("state", "pending"), TaskStatus.PENDING),
                    files=files_result,
                    error_message=data.get("err_msg"),
                    full_zip_url=data.get("full_zip_url"),
                    extract_progress=data.get("extract_progress"),
                )
            else:
                error_msg = result.get("msg", "Unknown error")
                raise Exception(f"API Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Failed to get batch result: {e}")
            raise
    
    async def wait_for_completion(
        self, 
        batch_id: str, 
        timeout: Optional[float] = None
    ) -> TaskResult:
        """
        等待任务完成（异步轮询）
        
        Args:
            batch_id: 批量任务 ID
            timeout: 超时时间（秒），None 表示使用默认配置
        
        Returns:
            TaskResult: 完成后的任务结果
        
        Raises:
            TimeoutError: 超时时抛出异常
        """
        timeout = timeout or self.config.poll_timeout
        start_time = time.time()
        
        logger.info(f"Waiting for task {batch_id} to complete (timeout: {timeout}s)...")
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Task {batch_id} timed out after {timeout}s")
            
            result = await self.get_batch_result(batch_id)
            
            if result.is_completed:
                logger.info(f"✓ Task {batch_id} completed successfully")
                return result
            
            if result.is_failed:
                error_msg = result.error_message or "Unknown error"
                logger.error(f"✗ Task {batch_id} failed: {error_msg}")
                raise Exception(f"Task failed: {error_msg}")
            
            # 仍在处理中，继续等待
            progress_info = ""
            if result.extract_progress:
                prog = result.extract_progress
                progress_info = f" ({prog.get('extracted_pages')}/{prog.get('total_pages')} pages)"
            
            logger.info(f"Task {batch_id} status: {result.status}{progress_info}, elapsed: {elapsed:.1f}s")
            await asyncio.sleep(self.config.poll_interval)
    
    def wait_for_completion_sync(
        self, 
        batch_id: str, 
        timeout: Optional[float] = None
    ) -> TaskResult:
        """
        等待任务完成（同步轮询）
        
        Args:
            batch_id: 批量任务 ID
            timeout: 超时时间（秒），None 表示使用默认配置
        
        Returns:
            TaskResult: 完成后的任务结果
        """
        timeout = timeout or self.config.poll_timeout
        start_time = time.time()
        
        logger.info(f"Waiting for task {batch_id} to complete (timeout: {timeout}s)...")
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Task {batch_id} timed out after {timeout}s")
            
            result = self.get_batch_result_sync(batch_id)
            
            if result.is_completed:
                logger.info(f"✓ Task {batch_id} completed successfully")
                return result
            
            if result.is_failed:
                error_msg = result.error_message or "Unknown error"
                logger.error(f"✗ Task {batch_id} failed: {error_msg}")
                raise Exception(f"Task failed: {error_msg}")
            
            # 仍在处理中，继续等待
            progress_info = ""
            if result.extract_progress:
                prog = result.extract_progress
                progress_info = f" ({prog.get('extracted_pages')}/{prog.get('total_pages')} pages)"
            
            logger.info(f"Task {batch_id} status: {result.status}{progress_info}, elapsed: {elapsed:.1f}s")
            time.sleep(self.config.poll_interval)
    
    async def parse_documents(
        self, 
        files: List[FileTask], 
        options: Optional[ParseOptions] = None,
        wait_for_completion: bool = True,
        timeout: Optional[float] = None
    ) -> TaskResult:
        """
        一站式文档解析（异步）
        
        创建任务 + 等待完成（可选）
        
        Args:
            files: 文件任务列表
            options: 解析选项
            wait_for_completion: 是否等待任务完成
            timeout: 超时时间（秒）
        
        Returns:
            TaskResult: 任务结果
        """
        # 创建任务
        result = await self.create_batch_task(files, options)
        
        # 等待完成（如果需要）
        if wait_for_completion:
            result = await self.wait_for_completion(result.task_id, timeout)
        
        return result
    
    def parse_documents_sync(
        self, 
        files: List[FileTask], 
        options: Optional[ParseOptions] = None,
        wait_for_completion: bool = True,
        timeout: Optional[float] = None
    ) -> TaskResult:
        """
        一站式文档解析（同步）
        
        Args:
            files: 文件任务列表
            options: 解析选项
            wait_for_completion: 是否等待任务完成
            timeout: 超时时间（秒）
        
        Returns:
            TaskResult: 任务结果
        """
        # 创建任务
        result = self.create_batch_task_sync(files, options)
        
        # 等待完成（如果需要）
        if wait_for_completion:
            result = self.wait_for_completion_sync(result.task_id, timeout)
        
        return result


# ============== 便捷函数 ==============

def create_client(
    api_token: Optional[str] = None,
    **kwargs
) -> MinerUClient:
    """
    创建 MinerU 客户端（便捷函数）
    
    Args:
        api_token: API Token（可选，优先使用环境变量 MINERU_API_TOKEN）
        **kwargs: 其他配置参数
    
    Returns:
        MinerUClient: 客户端实例
    
    Example:
        # 使用环境变量
        client = create_client()
        
        # 手动指定 token
        client = create_client(api_token="your_token_here")
    """
    config = MinerUConfig(
        api_token=api_token or os.getenv("MINERU_API_TOKEN", ""),
        **kwargs
    )
    return MinerUClient(config)


# ============== 示例代码 ==============

async def example_async():
    """异步使用示例"""
    # 创建客户端
    client = create_client()
    
    # 准备文件任务
    files = [
        FileTask(
            url="https://example.com/document1.pdf",
            data_id="doc_001"
        ),
        FileTask(
            url="https://example.com/document2.pdf",
            data_id="doc_002",
            is_ocr=True  # 单独为此文件启用 OCR
        ),
    ]
    
    # 配置解析选项
    options = ParseOptions(
        enable_formula=True,
        enable_table=True,
        language="ch",
        is_ocr=True
    )
    
    try:
        # 方式 1：一站式解析（推荐）
        result = await client.parse_documents(files, options, wait_for_completion=True)
        print(f"✓ 解析完成！文件数: {len(result.files)}")
        for file in result.files:
            print(f"  - {file.get('data_id')}: {file.get('status')}")
        
        # 方式 2：分步操作
        # task = await client.create_batch_task(files, options)
        # print(f"任务已创建: {task.batch_id}")
        # result = await client.wait_for_completion(task.batch_id)
        # print(f"✓ 解析完成")
    
    except Exception as e:
        print(f"✗ 解析失败: {e}")


def example_sync():
    """同步使用示例"""
    client = create_client()
    
    files = [
        FileTask(url="https://example.com/doc.pdf", data_id="doc_001")
    ]
    
    options = ParseOptions(
        enable_formula=True,
        enable_table=True,
        language="ch"
    )
    
    try:
        result = client.parse_documents_sync(files, options, wait_for_completion=True)
        print(f"✓ 解析完成！文件数: {len(result.files)}")
    except Exception as e:
        print(f"✗ 解析失败: {e}")


if __name__ == "__main__":
    # 运行示例
    # asyncio.run(example_async())
    # example_sync()
    pass
