"""
MinerU 远程解析结果处理器

功能：
- 下载 MinerU 解析结果压缩包
- 解析 Markdown 文档
- 直接将内容插入 LightRAG
- 优化了结果处理流程，避免重复解析
"""

import os
import asyncio
import aiohttp
import zipfile
import tempfile
from typing import Optional, List, Dict, Any
from pathlib import Path

from src.logger import logger


class MinerUResultProcessor:
    """MinerU 解析结果处理器"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
    
    async def download_result_zip(self, zip_url: str) -> str:
        """
        下载 MinerU 解析结果压缩包
        
        Args:
            zip_url: 结果 ZIP 文件 URL
        
        Returns:
            str: 本地 ZIP 文件路径
        
        Raises:
            Exception: 下载失败
        """
        try:
            zip_path = os.path.join(self.temp_dir, f"mineru_{os.path.basename(zip_url)}")
            
            logger.info(f"Downloading MinerU result: {zip_url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(zip_url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status != 200:
                        raise Exception(f"Download failed with status {response.status}")
                    
                    # 写入文件
                    with open(zip_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
            
            logger.info(f"✓ Downloaded result ZIP: {zip_path}")
            return zip_path
        
        except Exception as e:
            logger.error(f"Failed to download result ZIP: {e}")
            raise
    
    def extract_markdown_files(self, zip_path: str) -> List[str]:
        """
        从压缩包中提取 Markdown 文件
        
        Args:
            zip_path: ZIP 文件路径
        
        Returns:
            List[str]: 提取的 Markdown 文件路径列表
        """
        try:
            extracted_files = []
            extract_dir = os.path.join(self.temp_dir, f"mineru_extracted_{os.path.basename(zip_path)}")
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 列出所有文件
                for file_info in zip_ref.filelist:
                    if file_info.filename.endswith('.md'):
                        zip_ref.extract(file_info, extract_dir)
                        md_file = os.path.join(extract_dir, file_info.filename)
                        extracted_files.append(md_file)
                        logger.info(f"Extracted: {file_info.filename}")
            
            logger.info(f"✓ Extracted {len(extracted_files)} Markdown files from {zip_path}")
            return extracted_files
        
        except Exception as e:
            logger.error(f"Failed to extract Markdown files: {e}")
            raise
    
    async def process_markdown_content(self, markdown_files: List[str], lightrag_instance) -> int:
        """
        处理 Markdown 文件，将内容插入 LightRAG
        
        Args:
            markdown_files: Markdown 文件路径列表
            lightrag_instance: LightRAG 实例
        
        Returns:
            int: 成功插入的文件数量
        """
        success_count = 0
        
        for md_file in markdown_files:
            try:
                # 读取 Markdown 文件
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if not content or len(content.strip()) == 0:
                    logger.warning(f"Empty Markdown file: {md_file}")
                    continue
                
                # 直接插入到 LightRAG
                logger.info(f"Inserting Markdown content to LightRAG: {os.path.basename(md_file)} ({len(content)} chars)")
                await lightrag_instance.ainsert(content)
                
                success_count += 1
                logger.info(f"✓ Successfully inserted: {os.path.basename(md_file)}")
            
            except Exception as e:
                logger.error(f"Failed to process Markdown file {md_file}: {e}")
        
        return success_count
    
    async def process_mineru_result(
        self, 
        result,  # TaskResult 对象
        lightrag_instance
    ) -> Dict[str, Any]:
        """
        一站式处理 MinerU 解析结果
        
        Args:
            result: MinerU TaskResult 对象（包含 full_zip_url）
            lightrag_instance: LightRAG 实例
        
        Returns:
            Dict[str, Any]: 处理结果摘要
        """
        try:
            # 检查任务是否成功完成
            if not result.is_completed:
                raise Exception(f"MinerU task failed: {result.error_message}")
            
            if not result.full_zip_url:
                raise Exception("MinerU result missing full_zip_url")
            
            # 1. 下载结果压缩包
            zip_path = await self.download_result_zip(result.full_zip_url)
            
            # 2. 提取 Markdown 文件
            markdown_files = self.extract_markdown_files(zip_path)
            
            if not markdown_files:
                raise Exception("No Markdown files found in result")
            
            # 3. 处理 Markdown 文件，插入 LightRAG
            success_count = await self.process_markdown_content(markdown_files, lightrag_instance)
            
            # 4. 清理临时文件
            self._cleanup_temp_files(zip_path, markdown_files)
            
            logger.info(f"✓ Successfully processed MinerU result: {success_count}/{len(markdown_files)} files inserted")
            
            return {
                "status": "success",
                "files_processed": success_count,
                "total_files": len(markdown_files),
                "task_id": result.task_id
            }
        
        except Exception as e:
            logger.error(f"Failed to process MinerU result: {e}")
            raise
    
    def _cleanup_temp_files(self, zip_path: str, markdown_files: List[str]):
        """清理临时文件"""
        try:
            # 删除 ZIP 文件
            if os.path.exists(zip_path):
                os.remove(zip_path)
                logger.info(f"Cleaned up: {zip_path}")
            
            # 删除提取的文件和目录
            for md_file in markdown_files:
                if os.path.exists(md_file):
                    os.remove(md_file)
                    logger.info(f"Cleaned up: {md_file}")
                
                # 删除父目录（如果为空）
                parent_dir = os.path.dirname(md_file)
                try:
                    if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                        os.rmdir(parent_dir)
                except:
                    pass
        
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {e}")


# 全局处理器实例
_processor = None


def get_result_processor() -> MinerUResultProcessor:
    """获取结果处理器单例"""
    global _processor
    if _processor is None:
        _processor = MinerUResultProcessor()
    return _processor
