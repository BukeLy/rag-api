"""
文档插入路由（多租户隔离）
"""

import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Query, Depends
from typing import Optional, List

from src.logger import logger
from src.rag import select_parser_by_file
from src.tenant_deps import get_tenant_id
from src.multi_tenant import get_tenant_lightrag
from .models import TaskStatus, TaskInfo
from .task_store import create_task, create_batch, get_batch, get_task, update_task

# 导入 RAG-Anything 异常类型
try:
    from raganything.parser import MineruExecutionError
except ImportError:
    class MineruExecutionError(Exception):
        pass

# 导入远程 MinerU 处理相关模块
from src.file_url_service import get_file_service

router = APIRouter()


async def process_document_task(
    task_id: str,
    tenant_id: str,
    doc_id: str,
    temp_file_path: str,
    original_filename: str,
    parser: Optional[str] = "auto",
    vlm_mode: str = "off",
    deepseek_mode: Optional[str] = None
):
    """
    后台异步处理文档（支持多租户隔离 + VLM 模式 + DeepSeek-OCR）

    Args:
        task_id: 任务ID
        tenant_id: 租户ID
        doc_id: 文档ID
        temp_file_path: 临时文件路径
        original_filename: 原始文件名
        parser: 解析器类型 ("deepseek-ocr" / "mineru" / "docling" / "auto" / None)
                None 表示纯文本文件，直接插入无需解析
        vlm_mode: VLM 处理模式（"off" / "selective" / "full"）
        deepseek_mode: DeepSeek-OCR 模式 ("free_ocr" / "grounding" / None)
    """
    try:
        # 更新任务状态为处理中
        update_task(task_id, tenant_id, status=TaskStatus.PROCESSING, updated_at=datetime.now().isoformat())
        logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Started processing: {original_filename} (parser: {parser})")
        
        # 获取租户专属的 LightRAG 实例
        lightrag_instance = await get_tenant_lightrag(tenant_id)
        if not lightrag_instance:
            raise Exception(f"LightRAG is not ready for tenant: {tenant_id}")
        
        # 检查是否为纯文本文件，使用轻量级直接插入
        file_ext = Path(original_filename).suffix.lower()
        if file_ext in ['.txt', '.md', '.markdown']:
            logger.info(f"[Task {task_id}] Detected text file, using lightweight direct insertion")
            
            # 直接读取文本内容
            with open(temp_file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            if not text_content or len(text_content.strip()) == 0:
                raise ValueError(f"Empty text file: {original_filename}")
            
            # 直接插入到租户的 LightRAG 实例（轻量级，无需解析）
            await lightrag_instance.ainsert(text_content, file_paths=original_filename)
            logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Text content inserted directly to LightRAG ({len(text_content)} characters, file: {original_filename})")
        else:
            # 非文本文件，需要使用解析器
            if parser is None:
                raise ValueError(f"Parser is None for non-text file: {original_filename}. This should not happen.")

            # 处理 DeepSeek-OCR
            if parser == "deepseek-ocr":
                try:
                    from src.deepseek_ocr_client import create_client, DSSeekMode
                    from src.document_complexity import DocumentComplexityAnalyzer
                    from src.tenant_config import get_tenant_config_manager

                    # 🆕 加载租户配置
                    config_manager = get_tenant_config_manager()
                    tenant_config = config_manager.get(tenant_id)
                    merged_config = config_manager.merge_with_global(tenant_config)
                    ds_ocr_config = merged_config["ds_ocr"]

                    # 创建 DeepSeek-OCR 客户端（使用租户配置）
                    ds_client = create_client(
                        api_key=ds_ocr_config["api_key"],
                        base_url=ds_ocr_config["base_url"],
                        model_name=ds_ocr_config["model"],
                        timeout=ds_ocr_config["timeout"],
                        max_tokens=ds_ocr_config["max_tokens"],
                        dpi=ds_ocr_config["dpi"],
                        default_mode=ds_ocr_config["default_mode"],
                        fallback_enabled=ds_ocr_config["fallback_enabled"],
                        fallback_mode=ds_ocr_config["fallback_mode"],
                        min_output_threshold=ds_ocr_config["min_output_threshold"]
                    )

                    # 确定使用的模式
                    if deepseek_mode:
                        mode = DSSeekMode(deepseek_mode)
                    else:
                        mode = DSSeekMode.FREE_OCR  # 默认模式

                    # 检查是否需要中文语言提示（简单表格 <10 字场景）
                    chinese_hint = False
                    try:
                        analyzer = DocumentComplexityAnalyzer()
                        features = analyzer.get_document_features(temp_file_path)
                        if (features.chinese_char_count > 0 and
                            features.chinese_char_count < 10):
                            chinese_hint = True
                            logger.info(f"[Task {task_id}] Chinese hint enabled (chars={features.chinese_char_count})")
                    except Exception as e:
                        logger.warning(f"[Task {task_id}] Failed to analyze Chinese chars: {e}")

                    # 调用 DeepSeek-OCR（异步）
                    markdown_text = await ds_client.parse_document(
                        file_path=temp_file_path,
                        mode=mode,
                        chinese_hint=chinese_hint
                    )

                    # 直接插入到租户的 LightRAG 实例
                    await lightrag_instance.ainsert(markdown_text, file_paths=original_filename)
                    logger.info(
                        f"[Task {task_id}] [Tenant {tenant_id}] Document parsed using DeepSeek-OCR "
                        f"(mode={mode.value}, {len(markdown_text)} chars, file: {original_filename})"
                    )
                except Exception as e:
                    logger.error(f"[Task {task_id}] DeepSeek-OCR failed: {e}", exc_info=True)
                    raise

            # 处理 MinerU
            elif parser == "mineru":
                mineru_mode = os.getenv("MINERU_MODE", "local")

                # 根据 MinerU 模式选择处理策略
                if mineru_mode == "remote":
                    # 使用远程 MinerU 处理
                    try:
                        await process_with_remote_mineru(
                            task_id=task_id,
                            tenant_id=tenant_id,
                            file_path=temp_file_path,
                            filename=original_filename,
                            doc_id=doc_id,
                            vlm_mode=vlm_mode
                        )
                        logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Document processed using remote MinerU API (vlm_mode={vlm_mode})")
                    except Exception as e:
                        logger.warning(f"[Task {task_id}] [Tenant {tenant_id}] Remote MinerU failed: {e}")
                        raise  # 不再回退到本地处理，直接抛出错误
                else:
                    # 本地处理：需要使用 RAGAnything 解析器
                    # 注意：这里需要创建临时的 RAGAnything 实例（使用租户的 LightRAG）
                    from raganything import RAGAnything, RAGAnythingConfig

                    config = RAGAnythingConfig(
                        working_dir="./rag_local_storage",
                        parser="mineru",
                        enable_image_processing=True,  # 🔥 启用图片处理（所有 parser 都支持）
                        enable_table_processing=True,
                        enable_equation_processing=True,
                    )

                    # 🆕 从 LightRAG 实例获取 vision_model_func
                    vision_func = getattr(lightrag_instance, 'vision_model_func', None)

                    if vision_func is None:
                        logger.warning(f"[Task {task_id}] [Tenant {tenant_id}] vision_model_func not found, image understanding disabled")

                    rag_anything = RAGAnything(
                        config=config,
                        lightrag=lightrag_instance,
                        vision_model_func=vision_func  # 🆕 传递 VLM 函数
                    )
                    await rag_anything.process_document_complete(file_path=temp_file_path, output_dir="./output")
                    logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Document parsed using MinerU parser with VLM (mode: {mineru_mode})")

            # 处理 Docling
            else:
                # Docling 或其他 parser：使用 RAGAnything
                from raganything import RAGAnything, RAGAnythingConfig

                config = RAGAnythingConfig(
                    working_dir="./rag_local_storage",
                    parser=parser,
                    enable_image_processing=True,
                    enable_table_processing=(parser == "docling"),
                    enable_equation_processing=False,
                )

                vision_func = getattr(lightrag_instance, 'vision_model_func', None)

                if vision_func is None:
                    logger.warning(f"[Task {task_id}] [Tenant {tenant_id}] vision_model_func not found, image understanding disabled")

                rag_anything = RAGAnything(
                    config=config,
                    lightrag=lightrag_instance,
                    vision_model_func=vision_func
                )
                await rag_anything.process_document_complete(file_path=temp_file_path, output_dir="./output")
                logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Document parsed using {parser} parser")
        
        # 处理成功
        update_task(
            task_id, tenant_id,
            status=TaskStatus.COMPLETED,
            updated_at=datetime.now().isoformat(),
            result={
                "message": "Document processed successfully",
                "doc_id": doc_id,
                "filename": original_filename
            }
        )
        logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Completed successfully: {original_filename}")
        
    except ValueError as e:
        # 验证错误（客户端错误）
        update_task(
            task_id, tenant_id,
            status=TaskStatus.FAILED,
            updated_at=datetime.now().isoformat(),
            error=f"Validation error: {str(e)}"
        )
        logger.error(f"[Task {task_id}] [Tenant {tenant_id}] Validation error: {e}", exc_info=True)

    except MineruExecutionError as e:
        # MinerU 解析错误
        error_msg = str(e)
        if "Unknown file suffix" in error_msg or "Unsupported" in error_msg:
            error_text = f"Unsupported file format: {original_filename}"
        else:
            error_text = f"Document parsing failed: {original_filename}"

        update_task(
            task_id, tenant_id,
            status=TaskStatus.FAILED,
            updated_at=datetime.now().isoformat(),
            error=error_text
        )
        logger.error(f"[Task {task_id}] [Tenant {tenant_id}] MinerU error: {error_msg}", exc_info=True)

    except OSError as e:
        # 文件系统错误
        update_task(
            task_id, tenant_id,
            status=TaskStatus.FAILED,
            updated_at=datetime.now().isoformat(),
            error="File system error occurred"
        )
        logger.error(f"[Task {task_id}] [Tenant {tenant_id}] File system error: {e}", exc_info=True)

    except Exception as e:
        # 其他未预期的错误
        update_task(
            task_id, tenant_id,
            status=TaskStatus.FAILED,
            updated_at=datetime.now().isoformat(),
            error=f"Internal server error: {str(e)}"
        )
        logger.error(f"[Task {task_id}] [Tenant {tenant_id}] Unexpected error: {e}", exc_info=True)
        
    finally:
        # 确保临时文件总是被删除
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"[Task {task_id}] Cleaned up temporary file: {temp_file_path}")
            except OSError as e:
                logger.warning(f"[Task {task_id}] Failed to clean up temporary file: {e}")


@router.post("/insert", status_code=202)
async def insert_document(
    doc_id: str = Query(
        ...,
        description="文档唯一标识符，用于在知识图谱中标识文档",
        example="research_paper_001",
        min_length=1,
        max_length=200
    ),
    file: UploadFile = File(
        ...,
        description="要上传的文档文件（支持 PDF、DOCX、TXT、MD、图片等）"
    ),
    background_tasks: BackgroundTasks = None,
    parser: Optional[str] = Query(
        default="auto",
        description="""解析器选择：
- `auto`: 智能选择（推荐，根据文件类型和大小自动决策）
- `mineru`: 强大的多模态解析器（支持 OCR、表格、公式，内存占用大）
- `docling`: 轻量级解析器（快速处理简单文档，内存占用小）
""",
        pattern="^(auto|mineru|docling)$"
    ),
    vlm_mode: str = Query(
        default=None,
        description="""VLM 处理模式（可选）：
- `off`: 仅 Markdown（最快，默认）
- `selective`: 混合模式（选择性处理重要图表，平衡性能和质量）
- `full`: 完整 RAG-Anything 处理（最高质量，启用上下文增强）
- 如果不提供，将使用环境变量 RAG_VLM_MODE 的默认值
""",
        pattern="^(off|selective|full)?$"
    ),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    上传文档并异步处理（多租户隔离）

    **流程说明**：
    1. 上传文件，立即返回 `task_id`（HTTP 202 Accepted）
    2. 后台异步处理文档（解析、提取实体、构建知识图谱）
    3. 使用 `GET /task/{task_id}` 查询处理状态

    ---

    **🔒 多租户支持**：
    - **租户隔离**：每个租户的文档完全隔离，互不可见
    - **必填参数**：`?tenant_id=your_tenant_id`
    - **示例**：`POST /insert?tenant_id=tenant_a&doc_id=doc_001`

    ---

    **📂 文件处理策略**：

    | 文件类型 | 处理方式 | 性能 |
    |---------|---------|-----|
    | **纯文本** (.txt, .md) | 直接插入 LightRAG | ⚡ 极快（< 1秒） |
    | **图片** (.jpg, .png) | MinerU OCR | 🐢 较慢（OCR 处理） |
    | **PDF/Office < 500KB** | Docling 快速解析 | ⚡ 快速 |
    | **PDF/Office > 500KB** | MinerU 深度解析 | 🐢 较慢但准确 |

    ---

    **⚙️ 解析器参数**（仅对非文本文件生效）：

    - **`auto`**（推荐）：自动选择最佳解析器
    - **`mineru`**：强大的多模态解析器
        - ✅ 支持 OCR（图片、扫描件）
        - ✅ 支持表格提取
        - ✅ 支持数学公式
        - ❌ 内存占用大（建议使用远程模式）
    - **`docling`**：轻量级解析器
        - ✅ 快速处理简单文档
        - ✅ 内存占用小
        - ❌ 不支持复杂布局

    ---

    **📊 支持的文件格式**：
    - **文档**: PDF, DOCX, DOC, TXT, MD
    - **图片**: PNG, JPG, JPEG, BMP
    - **其他**: 根据 RAG-Anything 支持的格式

    ---

    **⚠️ 文件限制**：
    - **最大文件大小**: 100 MB
    - **文件不能为空**（0 字节）
    - **文件名安全检查**：自动过滤路径遍历攻击

    ---

    **📝 返回示例**：

    ```json
    {
        "message": "Document processing started",
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "doc_id": "research_paper_001",
        "filename": "AI研究报告.pdf",
        "tenant_id": "tenant_a",
        "status": "pending"
    }
    ```

    ---

    **🔍 后续操作**：

    使用返回的 `task_id` 查询处理状态：

    ```bash
    GET /task/{task_id}?tenant_id=tenant_a
    ```

    ---

    **❌ 错误处理**：

    - `400 Bad Request`: 空文件、文件过大、不支持的格式
    - `503 Service Unavailable`: RAG 服务未就绪
    """
    # 验证 parser 参数
    if parser not in ["mineru", "docling", "auto"]:
        raise HTTPException(status_code=400, detail=f"Invalid parser: {parser}. Must be 'mineru', 'docling', or 'auto'.")

    # 读取 VLM 模式（优先级：请求参数 > 环境变量）
    effective_vlm_mode = vlm_mode if vlm_mode else os.getenv("RAG_VLM_MODE", "off")
    if effective_vlm_mode not in ["off", "selective", "full"]:
        raise HTTPException(status_code=400, detail=f"Invalid vlm_mode: {effective_vlm_mode}. Must be 'off', 'selective', or 'full'.")

    # 保留原始文件名（仅用于日志）
    original_filename = file.filename or "unnamed_file"

    # 提取文件扩展名（仅用于日志和解析器选择）
    file_extension = Path(original_filename).suffix.lower() if original_filename else ""

    # 使用 UUID 生成安全的临时文件名
    safe_filename = f"{uuid.uuid4()}{file_extension}"
    temp_file_path = f"/tmp/{safe_filename}"
    
    try:
        # 保存上传的文件到临时位置
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 验证文件大小（空文件检查）
        file_size = os.path.getsize(temp_file_path)
        if file_size == 0:
            # 立即删除空文件
            os.remove(temp_file_path)
            raise HTTPException(status_code=400, detail=f"Empty file: {original_filename}")
        
        # 限制文件大小（例如最大 100MB）
        max_file_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_file_size:
            os.remove(temp_file_path)
            raise HTTPException(
                status_code=400, 
                detail=f"File too large: {original_filename} ({file_size} bytes, max: {max_file_size} bytes)"
            )
        
        # 智能选择解析器
        selected_parser = parser
        deepseek_mode = None  # 默认值
        if parser == "auto":
            selected_parser, deepseek_mode = select_parser_by_file(
                original_filename,
                file_size,
                file_path=temp_file_path
            )
            parser_desc = selected_parser if selected_parser else "direct_insert (text file)"
            mode_desc = f", mode={deepseek_mode}" if deepseek_mode else ""
            logger.info(f"Auto-selected parser for {original_filename} ({file_size} bytes): {parser_desc}{mode_desc}")

        # 生成任务 ID
        task_id = str(uuid.uuid4())
        current_time = datetime.now().isoformat()

        # 创建任务记录（按租户隔离）
        task_info = TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            doc_id=doc_id,
            filename=original_filename,
            created_at=current_time,
            updated_at=current_time
        )
        create_task(task_info, tenant_id)

        # 添加后台任务（传递租户ID、解析器、VLM模式、DS-OCR模式）
        background_tasks.add_task(
            process_document_task,
            task_id=task_id,
            tenant_id=tenant_id,
            doc_id=doc_id,
            temp_file_path=temp_file_path,
            original_filename=original_filename,
            parser=selected_parser,
            vlm_mode=effective_vlm_mode,
            deepseek_mode=deepseek_mode
        )

        parser_display = selected_parser if selected_parser else "direct_insert"
        logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Created task for file: {original_filename} (size: {file_size} bytes, doc_id: {doc_id}, parser: {parser_display}, vlm_mode: {effective_vlm_mode})")

        # 立即返回 202 + task_id
        return {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "status": TaskStatus.PENDING,
            "message": "Document upload accepted. Processing in background.",
            "doc_id": doc_id,
            "filename": original_filename,
            "parser": parser_display,
            "vlm_mode": effective_vlm_mode,
            "file_size": file_size
        }
    
    except HTTPException:
        # 直接重新抛出 HTTP 异常
        raise
    
    except Exception as e:
        # 如果创建任务失败，清理临时文件
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass
        logger.error(f"Failed to create processing task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


async def process_with_remote_mineru(
    task_id: str,
    tenant_id: str,
    file_path: str,
    filename: str,
    doc_id: str,
    vlm_mode: str = "off"
):
    """
    使用远程 MinerU 处理文档（支持多租户 + VLM 模式）

    Args:
        task_id: 任务 ID
        tenant_id: 租户 ID
        file_path: 本地文件路径
        filename: 原始文件名
        doc_id: 文档 ID
        vlm_mode: VLM 处理模式（"off" / "selective" / "full"）
    """
    try:
        logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Starting remote MinerU processing: {filename} (vlm_mode={vlm_mode})")

        # 获取文件服务实例和租户的 LightRAG 实例
        file_service = get_file_service()
        lightrag_instance = await get_tenant_lightrag(tenant_id)

        if not lightrag_instance:
            raise Exception(f"LightRAG instance not available for tenant: {tenant_id}")

        # 获取 VLM 函数（用于 selective/full 模式）
        vision_func = getattr(lightrag_instance, 'vision_model_func', None)
        if vlm_mode in ["selective", "full"] and not vision_func:
            logger.warning(f"[Task {task_id}] vision_model_func not found, falling back to off mode")
            vlm_mode = "off"

        # 注册文件获取 URL（8000 端口）
        file_url = await file_service.register_file(file_path, filename)
        logger.info(f"[Task {task_id}] [Tenant {tenant_id}] File registered: {file_url}")

        # 🆕 加载租户配置
        from src.tenant_config import get_tenant_config_manager
        config_manager = get_tenant_config_manager()
        tenant_config = config_manager.get(tenant_id)
        merged_config = config_manager.merge_with_global(tenant_config)
        mineru_config = merged_config["mineru"]

        # 调用 MinerU 客户端（使用租户配置）
        from src.mineru_client import create_client, FileTask, ParseOptions
        client = create_client(
            api_token=mineru_config["api_token"],
            base_url=mineru_config["base_url"],
            timeout=mineru_config["timeout"],
            max_concurrent_requests=mineru_config["max_concurrent_requests"],
            requests_per_minute=mineru_config["requests_per_minute"],
            retry_max_attempts=mineru_config["retry_max_attempts"],
            poll_timeout=mineru_config["poll_timeout"]
        )

        # 创建文件任务
        file_task = FileTask(url=file_url, data_id=doc_id)

        # 配置解析选项（使用租户配置）
        options = ParseOptions(
            enable_formula=True,
            enable_table=True,
            language="ch",
            model_version=mineru_config["model_version"]
        )

        # 调用远程 MinerU API
        logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Calling remote MinerU API...")
        result = await client.parse_documents([file_task], options, wait_for_completion=True)

        if result.is_completed:
            logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Remote MinerU parsing completed")

            # 读取 VLM 配置参数
            importance_threshold = float(os.getenv("RAG_IMPORTANCE_THRESHOLD", "0.5"))
            rag_config = {
                "context_window": int(os.getenv("RAG_CONTEXT_WINDOW", "2")),
                "context_mode": os.getenv("RAG_CONTEXT_MODE", "page"),
                "max_context_tokens": int(os.getenv("RAG_MAX_CONTEXT_TOKENS", "3000")),
            }

            # 使用结果处理器处理 MinerU 结果
            from src.mineru_result_processor import get_result_processor
            processor = get_result_processor()

            # 处理结果并直接插入 LightRAG（支持三种模式）
            logger.info(f"[Task {task_id}] [Tenant {tenant_id}] Processing MinerU result (mode={vlm_mode})...")
            process_result = await processor.process_mineru_result(
                result=result,
                lightrag_instance=lightrag_instance,
                mode=vlm_mode,
                vision_func=vision_func,
                original_filename=filename,
                importance_threshold=importance_threshold,
                rag_config=rag_config
            )

            logger.info(f"[Task {task_id}] [Tenant {tenant_id}] MinerU result processed: {process_result}")

        else:
            error_msg = result.error_message or "Unknown error"
            logger.error(f"[Task {task_id}] [Tenant {tenant_id}] Remote MinerU failed: {error_msg}")
            raise Exception(f"Remote MinerU processing failed: {error_msg}")
        
    except Exception as e:
        logger.error(f"[Task {task_id}] [Tenant {tenant_id}] Remote MinerU processing error: {e}", exc_info=True)
        # 清理文件
        try:
            file_id = file_url.split('/')[-2] if 'file_url' in locals() else None
            if file_id:
                file_service.cleanup_file(file_id=file_id)
        except:
            pass
        raise


@router.post("/batch")
async def insert_batch(
    files: List[UploadFile] = File(...),
    doc_ids: Optional[str] = Query(None),
    parser: str = Query("auto"),
    vlm_mode: str = Query(default=None, pattern="^(off|selective|full)?$"),
    background_tasks: BackgroundTasks = None,
    tenant_id: str = Depends(get_tenant_id)
):
    """
    批量文档插入端点（优化：单次 API 调用处理多个文件）
    
    **参数说明：**
    - `files`: 文件列表（最多 100 个文件）
    - `doc_ids`: 可选的文档 ID 列表（逗号分隔，对应 files 顺序）
    - `parser`: 解析器选择 ('auto', 'mineru', 'docling')
    
    **功能特性：**
    - 并发处理多个文件，充分利用系统资源
    - 支持自动文件类型检测与最优解析器选择
    - 批量任务统一管理和进度跟踪
    - 单个文件失败不影响其他文件处理
    
    **返回值：**
    ```json
    {
        "batch_id": "xxx-yyy-zzz",
        "total_files": 5,
        "tasks": [
            {
                "task_id": "task-1",
                "doc_id": "doc-1",
                "filename": "file1.pdf",
                "status": "PENDING"
            }
        ]
    }
    ```
    """
    # 验证 parser 参数
    if parser not in ["mineru", "docling", "auto"]:
        raise HTTPException(status_code=400, detail=f"Invalid parser: {parser}")

    # 读取 VLM 模式
    effective_vlm_mode = vlm_mode if vlm_mode else os.getenv("RAG_VLM_MODE", "off")
    if effective_vlm_mode not in ["off", "selective", "full"]:
        raise HTTPException(status_code=400, detail=f"Invalid vlm_mode: {effective_vlm_mode}")

    # 限制文件数量
    if not files or len(files) > 100:
        raise HTTPException(status_code=400, detail="File count must be between 1 and 100")
    
    # 解析 doc_ids
    doc_ids_list = []
    if doc_ids:
        doc_ids_list = [did.strip() for did in doc_ids.split(',')]
        if len(doc_ids_list) != len(files):
            raise HTTPException(status_code=400, detail=f"doc_ids count ({len(doc_ids_list)}) must match files count ({len(files)})")
    else:
        # 为每个文件生成随机 doc_id
        doc_ids_list = [str(uuid.uuid4()) for _ in files]
    
    # 创建批量任务 ID
    batch_id = str(uuid.uuid4())
    tasks = []

    logger.info(f"[Batch {batch_id}] [Tenant {tenant_id}] Starting batch insert with {len(files)} files, parser: {parser}")

    try:
        
        # 处理每个文件
        for idx, (file, doc_id) in enumerate(zip(files, doc_ids_list)):
            try:
                # 验证文件名
                original_filename = file.filename or f"file_{idx}"
                
                # 提取文件扩展名（仅用于日志和解析器选择）
                file_extension = Path(original_filename).suffix.lower()
                
                # 生成临时文件路径
                safe_filename = f"{uuid.uuid4()}{file_extension}"
                temp_file_path = f"/tmp/{safe_filename}"
                
                # 保存文件
                with open(temp_file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                # 验证文件大小
                file_size = os.path.getsize(temp_file_path)
                if file_size == 0:
                    os.remove(temp_file_path)
                    logger.warning(f"[Batch {batch_id}] Skipped empty file: {original_filename}")
                    continue
                
                max_file_size = 100 * 1024 * 1024  # 100MB
                if file_size > max_file_size:
                    os.remove(temp_file_path)
                    logger.warning(f"[Batch {batch_id}] Skipped oversized file: {original_filename}")
                    continue
                
                # 智能选择解析器
                selected_parser = parser
                deepseek_mode = None  # 默认值
                if parser == "auto":
                    selected_parser, deepseek_mode = select_parser_by_file(
                        original_filename,
                        file_size,
                        file_path=temp_file_path
                    )

                parser_display = selected_parser if selected_parser else "direct_insert"

                # 生成任务 ID
                task_id = str(uuid.uuid4())
                current_time = datetime.now().isoformat()

                # 创建任务记录（按租户隔离）
                task_info = TaskInfo(
                    task_id=task_id,
                    status=TaskStatus.PENDING,
                    doc_id=doc_id,
                    filename=original_filename,
                    created_at=current_time,
                    updated_at=current_time
                )
                create_task(task_info, tenant_id)

                # 添加后台任务
                background_tasks.add_task(
                    process_document_task,
                    task_id=task_id,
                    tenant_id=tenant_id,
                    doc_id=doc_id,
                    temp_file_path=temp_file_path,
                    original_filename=original_filename,
                    parser=selected_parser,
                    vlm_mode=effective_vlm_mode,
                    deepseek_mode=deepseek_mode
                )

                logger.info(f"[Batch {batch_id}] [Tenant {tenant_id}] Created task {task_id} for file: {original_filename} (parser: {parser_display})")

                tasks.append({
                    "task_id": task_id,
                    "doc_id": doc_id,
                    "filename": original_filename,
                    "status": TaskStatus.PENDING,
                    "parser": parser_display,
                    "file_size": file_size
                })
            
            except Exception as e:
                logger.error(f"[Batch {batch_id}] Error processing file {idx}: {e}")
                continue
        
        if not tasks:
            raise HTTPException(status_code=400, detail="No valid files in batch")

        logger.info(f"[Batch {batch_id}] [Tenant {tenant_id}] Batch insert created: {len(tasks)} tasks")

        # 记录批量任务映射（修复前缀匹配的bug）
        task_ids = [task["task_id"] for task in tasks]
        current_time = datetime.now().isoformat()
        create_batch(
            batch_id=batch_id,
            tenant_id=tenant_id,
            task_ids=task_ids,
            created_at=current_time
        )

        return {
            "batch_id": batch_id,
            "tenant_id": tenant_id,
            "total_files": len(files),
            "accepted_files": len(tasks),
            "message": f"Batch accepted. Processing {len(tasks)} files.",
            "tasks": tasks
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Batch {batch_id}] Failed to create batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create batch: {str(e)}")


@router.get("/batch/{batch_id}")
async def get_batch_status(
    batch_id: str,
    tenant_id: str = Depends(get_tenant_id)
):
    """
    查询批量任务进度（多租户隔离，使用 BATCH_STORE）

    **多租户支持**：
    - 🔒 **租户隔离**：只能查询本租户的批量任务
    - 🎯 **必填参数**：`?tenant_id=your_tenant_id`

    **返回值：**
    ```json
    {
        "batch_id": "xxx-yyy-zzz",
        "tenant_id": "tenant_a",
        "total_tasks": 5,
        "completed": 3,
        "failed": 1,
        "pending": 1,
        "processing": 0,
        "progress": 0.6,
        "created_at": "2025-10-30T...",
        "tasks": [
            {
                "task_id": "task-1",
                "doc_id": "doc-1",
                "filename": "file1.pdf",
                "status": "completed",
                "created_at": "...",
                "updated_at": "..."
            }
        ]
    }
    ```
    """
    logger.info(f"[Batch {batch_id}] [Tenant {tenant_id}] Querying batch status")

    # 从 BATCH_STORE 获取批量任务信息（修复前缀匹配的bug）
    batch_info = get_batch(batch_id, tenant_id)

    if not batch_info:
        raise HTTPException(
            status_code=404,
            detail=f"Batch not found: {batch_id} (tenant: {tenant_id})"
        )

    # 获取所有关联的任务详情
    task_ids = batch_info["task_ids"]
    related_tasks = []

    for task_id in task_ids:
        task_info = get_task(task_id, tenant_id)
        if task_info:
            related_tasks.append({
                "task_id": task_id,
                "doc_id": task_info.doc_id,
                "filename": task_info.filename,
                "status": task_info.status,
                "created_at": task_info.created_at,
                "updated_at": task_info.updated_at,
                "error": task_info.error,  # 包含错误信息（如果有）
                "result": task_info.result  # 包含结果信息（如果有）
            })
        else:
            # 任务可能已被清理，记录警告
            logger.warning(f"[Batch {batch_id}] Task {task_id} not found in task store")
            related_tasks.append({
                "task_id": task_id,
                "doc_id": "unknown",
                "filename": "unknown",
                "status": "unknown",
                "created_at": batch_info["created_at"],
                "updated_at": batch_info["created_at"]
            })

    # 统计进度
    completed = sum(1 for t in related_tasks if t['status'] == TaskStatus.COMPLETED)
    failed = sum(1 for t in related_tasks if t['status'] == TaskStatus.FAILED)
    pending = sum(1 for t in related_tasks if t['status'] == TaskStatus.PENDING)
    processing = sum(1 for t in related_tasks if t['status'] == TaskStatus.PROCESSING)

    return {
        "batch_id": batch_id,
        "tenant_id": tenant_id,
        "total_tasks": batch_info["total"],
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "processing": processing,
        "progress": completed / batch_info["total"] if batch_info["total"] > 0 else 0,
        "created_at": batch_info["created_at"],
        "tasks": related_tasks
    }

