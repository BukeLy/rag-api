"""
MinerU 远程解析结果处理器

功能：
- 下载 MinerU 解析结果压缩包
- 解析 Markdown 文档
- 支持三种处理模式：off（仅 Markdown）/ selective（选择性 VLM）/ full（完整 RAG-Anything）
- 直接将内容插入 LightRAG
- 优化了结果处理流程，避免重复解析
"""

import os
import aiohttp
import zipfile
import tempfile
from typing import Optional, List, Dict, Any

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

    def extract_content_list(self, zip_path: str) -> tuple[List[Dict[str, Any]], str]:
        """
        从 MinerU ZIP 压缩包中提取 content_list.json
        使用 RAG-Anything 原生的 _read_output_files 方法

        支持两种 MinerU 输出格式：
        - Local 模式：{file_stem}_content_list.json
        - Remote API 模式：{uuid}_content_list.json

        Args:
            zip_path: ZIP 文件路径

        Returns:
            tuple[List[Dict[str, Any]], str]: (content_list 数据, 提取目录路径)

        Raises:
            Exception: 提取失败或 content_list.json 不存在
        """
        try:
            extract_dir = os.path.join(self.temp_dir, f"mineru_full_{os.path.basename(zip_path)}")
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 提取所有文件（包含 content_list.json + images/）
                zip_ref.extractall(extract_dir)
                logger.info(f"✓ Extracted all files to: {extract_dir}")

            # 使用 RAG-Anything 原生方法读取 MinerU 输出
            # 这会自动处理文件名匹配和路径转换
            from pathlib import Path
            from raganything.parser import MineruParser

            # 1. 查找文件前缀（通过 _content_list.json 后缀）
            file_stem = None
            for _, _, files in os.walk(extract_dir):
                for file in files:
                    if file.endswith("_content_list.json"):
                        file_stem = file.replace("_content_list.json", "")
                        logger.info(f"✓ Detected file_stem from MinerU output: {file_stem}")
                        break
                if file_stem:
                    break

            if not file_stem:
                raise Exception("No content_list.json file found in ZIP")

            # 2. 使用 RAG-Anything 原生的 _read_output_files 方法
            # 这会自动处理：
            # - 文件名格式 ({file_stem}_content_list.json)
            # - 图片路径转换为绝对路径
            # - 支持子目录结构（local vs remote 模式）
            content_list, _ = MineruParser._read_output_files(
                output_dir=Path(extract_dir),
                file_stem=file_stem,
                method="auto"
            )

            logger.info(f"✓ Loaded content_list using RAG-Anything native method: {len(content_list)} items")
            return content_list, extract_dir

        except Exception as e:
            logger.error(f"Failed to extract content_list.json: {e}")
            raise

    @staticmethod
    def is_important(item: Dict[str, Any], threshold: float = 0.5) -> bool:
        """
        判断图表是否重要（用于 selective 模式）

        Args:
            item: content_list 中的一项
            threshold: bbox 面积阈值（0-1，默认 0.5）

        Returns:
            bool: 是否为重要图表
        """
        # 策略 1：有标题的图表（通常更重要）
        if item.get("image_caption") or item.get("table_caption"):
            return True

        # 策略 2：大尺寸图表（bbox 面积 > threshold）
        bbox = item.get("bbox")
        if bbox and len(bbox) == 4:
            # MinerU bbox 格式：[x1, y1, x2, y2]，坐标范围 0-1000（归一化）
            area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) / (1000 * 1000)
            if area > threshold:
                return True

        # 策略 3：首页内容（通常包含关键信息）
        if item.get("page_idx", 999) < 3:
            return True

        return False
    
    async def process_markdown_content(self, markdown_files: List[str], lightrag_instance, original_filename: str = "document") -> int:
        """
        处理 Markdown 文件，将内容插入 LightRAG

        Args:
            markdown_files: Markdown 文件路径列表
            lightrag_instance: LightRAG 实例
            original_filename: 原始文件名（用于参考文献生成）

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
                await lightrag_instance.ainsert(content, file_paths=original_filename)

                success_count += 1
                logger.info(f"✓ Successfully inserted: {os.path.basename(md_file)} (file: {original_filename})")
            
            except Exception as e:
                logger.error(f"Failed to process Markdown file {md_file}: {e}")
        
        return success_count
    
    async def process_mineru_result(
        self,
        result,  # TaskResult 对象
        lightrag_instance,
        mode: str = "off",
        vision_func=None,
        original_filename: str = "document",
        importance_threshold: float = 0.5,
        rag_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        一站式处理 MinerU 解析结果（支持三种模式）

        Args:
            result: MinerU TaskResult 对象（包含 full_zip_url）
            lightrag_instance: LightRAG 实例
            mode: 处理模式 ("off" / "selective" / "full")
            vision_func: VLM 函数（mode=selective/full 时必需）
            original_filename: 原始文件名（用于 RAG-Anything）
            importance_threshold: 重要性阈值（mode=selective 时使用）
            rag_config: RAG-Anything 配置字典（mode=full 时使用）

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

            # 根据模式选择处理策略
            if mode == "off":
                # 模式 1：仅 Markdown（当前方案）
                return await self._process_markdown_only(zip_path, lightrag_instance, result.task_id, original_filename)

            elif mode == "selective":
                # 模式 2：混合模式（Markdown + 选择性 VLM）
                return await self._process_selective_mode(
                    zip_path, lightrag_instance, vision_func,
                    original_filename, importance_threshold, result.task_id
                )

            elif mode == "full":
                # 模式 3：完整 RAG-Anything 处理
                return await self._process_full_mode(
                    zip_path, lightrag_instance, vision_func,
                    original_filename, rag_config, result.task_id
                )

            else:
                raise ValueError(f"Invalid mode: {mode}. Must be 'off', 'selective', or 'full'")

        except Exception as e:
            logger.error(f"Failed to process MinerU result: {e}")
            raise

    async def _process_markdown_only(
        self, zip_path: str, lightrag_instance, task_id: str, original_filename: str = "document"
    ) -> Dict[str, Any]:
        """模式 1：仅提取 Markdown 文件并插入（最快）"""
        try:
            logger.info(f"[Task {task_id}] Processing with mode=off (Markdown only)")

            # 1. 提取 Markdown 文件
            markdown_files = self.extract_markdown_files(zip_path)

            if not markdown_files:
                raise Exception("No Markdown files found in result")

            # 2. 插入 LightRAG
            success_count = await self.process_markdown_content(markdown_files, lightrag_instance, original_filename)

            # 3. 清理临时文件
            self._cleanup_temp_files(zip_path, markdown_files)

            logger.info(f"✓ [Task {task_id}] Successfully processed: {success_count}/{len(markdown_files)} files inserted")

            return {
                "status": "success",
                "mode": "off",
                "files_processed": success_count,
                "total_files": len(markdown_files),
                "task_id": task_id
            }

        except Exception:
            # 清理失败时也要删除临时文件
            self._cleanup_temp_files(zip_path, [])
            raise

    async def _process_selective_mode(
        self, zip_path: str, lightrag_instance, vision_func,
        original_filename: str, threshold: float, task_id: str
    ) -> Dict[str, Any]:
        """模式 2：Markdown + 选择性 VLM（平衡性能和质量）"""
        try:
            logger.info(f"[Task {task_id}] Processing with mode=selective (threshold={threshold})")

            if not vision_func:
                logger.warning(f"[Task {task_id}] vision_func is None, fallback to off mode")
                return await self._process_markdown_only(zip_path, lightrag_instance, task_id, original_filename)

            # 1. 快速路径：提取并插入 Markdown
            markdown_files = self.extract_markdown_files(zip_path)
            if markdown_files:
                await self.process_markdown_content(markdown_files, lightrag_instance, original_filename)
                logger.info(f"✓ [Task {task_id}] Markdown inserted ({len(markdown_files)} files)")

            # 2. 提取 content_list.json 和图片
            content_list, extract_dir = self.extract_content_list(zip_path)

            # 3. 过滤重要图表
            important_items = [
                item for item in content_list
                if item.get("type") in ["image", "table"] and self.is_important(item, threshold)
            ]

            logger.info(f"[Task {task_id}] Found {len(important_items)}/{len(content_list)} important visuals")

            if not important_items:
                # 没有重要图表，直接返回
                self._cleanup_temp_files_full(zip_path, extract_dir)
                return {
                    "status": "success",
                    "mode": "selective",
                    "files_processed": len(markdown_files),
                    "visuals_processed": 0,
                    "task_id": task_id
                }

            # 4. 仅处理重要图表（不重复插入文本）
            # 注意：这里不需要创建 RAGAnything 实例，直接使用模态处理器
            visual_count = 0
            for item in important_items:
                try:
                    # 使用 RAG-Anything 的模态处理器
                    from raganything.modalprocessors import ImageModalProcessor, TableModalProcessor

                    if item["type"] == "image":
                        processor = ImageModalProcessor(
                            lightrag=lightrag_instance,
                            modal_caption_func=vision_func
                        )
                    else:  # table
                        processor = TableModalProcessor(
                            lightrag=lightrag_instance,
                            modal_caption_func=vision_func
                        )

                    # 处理单个多模态内容
                    await processor.process_multimodal_content(
                        modal_content=item,
                        content_type=item["type"],
                        file_path=original_filename,
                        entity_name=f"{original_filename}_{item.get('type')}_{item.get('page_idx')}",
                        item_info=item
                    )

                    visual_count += 1
                    logger.info(f"✓ [Task {task_id}] Processed {item['type']} on page {item.get('page_idx')}")

                except Exception as exc:
                    logger.warning(f"[Task {task_id}] Failed to process {item['type']}: {exc}")

            # 6. 清理临时文件
            self._cleanup_temp_files_full(zip_path, extract_dir)

            logger.info(f"✓ [Task {task_id}] Selective mode completed: {visual_count} visuals processed")

            return {
                "status": "success",
                "mode": "selective",
                "files_processed": len(markdown_files),
                "visuals_processed": visual_count,
                "visuals_total": len(important_items),
                "task_id": task_id
            }

        except Exception:
            self._cleanup_temp_files_full(zip_path, "")
            raise

    async def _process_full_mode(
        self, zip_path: str, lightrag_instance, vision_func,
        original_filename: str, rag_config: Optional[Dict[str, Any]], task_id: str
    ) -> Dict[str, Any]:
        """模式 3：完整 RAG-Anything 处理（最高质量）"""
        try:
            logger.info(f"[Task {task_id}] Processing with mode=full (RAG-Anything)")

            if not vision_func:
                logger.warning(f"[Task {task_id}] vision_func is None, fallback to off mode")
                return await self._process_markdown_only(zip_path, lightrag_instance, task_id, original_filename)

            # 1. 提取 content_list.json 和图片
            content_list, extract_dir = self.extract_content_list(zip_path)

            # 2. 配置 RAG-Anything
            from raganything import RAGAnything, RAGAnythingConfig

            # 合并用户配置和默认配置
            default_config = {
                "working_dir": "./rag_local_storage",
                "parser": "mineru",
                "content_format": "minerU",
                "enable_image_processing": True,
                "enable_table_processing": True,
                "enable_equation_processing": True,
                # 上下文增强配置
                "context_window": 2,
                "context_mode": "page",
                "max_context_tokens": 3000,
                "include_headers": True,
                "include_captions": True,
                "context_filter_content_types": ["text", "image", "table"],
            }

            if rag_config:
                default_config.update(rag_config)

            config = RAGAnythingConfig(**default_config)

            rag_anything = RAGAnything(
                config=config,
                lightrag=lightrag_instance,
                vision_model_func=vision_func
            )

            # 3. 设置 MinerU content_list 为上下文源
            rag_anything.set_content_source_for_context(content_list, "minerU")

            # 4. 使用 RAG-Anything 插入完整内容
            await rag_anything.insert_content_list(
                content_list=content_list,
                file_path=original_filename
            )

            logger.info(f"✓ [Task {task_id}] RAG-Anything processing completed ({len(content_list)} items)")

            # 5. 清理临时文件
            self._cleanup_temp_files_full(zip_path, extract_dir)

            return {
                "status": "success",
                "mode": "full",
                "items_processed": len(content_list),
                "task_id": task_id
            }

        except Exception:
            self._cleanup_temp_files_full(zip_path, "")
            raise

    def _cleanup_temp_files(self, zip_path: str, markdown_files: List[str]):
        """清理临时文件（仅 Markdown 模式）"""
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

    def _cleanup_temp_files_full(self, zip_path: str, extract_dir: str):
        """清理临时文件（完整模式，包含图片目录）"""
        try:
            import shutil

            # 删除 ZIP 文件
            if os.path.exists(zip_path):
                os.remove(zip_path)
                logger.info(f"Cleaned up: {zip_path}")

            # 删除提取目录（包含所有文件）
            if extract_dir and os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
                logger.info(f"Cleaned up directory: {extract_dir}")

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