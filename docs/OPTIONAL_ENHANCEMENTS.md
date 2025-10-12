# 可选增强功能清单

基于 RAG-Anything 官方文档，以下是一些可选的增强功能。这些**不是必需的**，只是在需要时可以参考。

## 1. 批量文件夹处理端点

**官方功能：**
```python
await rag.process_folder_complete(
    folder_path="./documents",
    output_dir="./output",
    file_extensions=[".pdf", ".docx", ".pptx"],
    recursive=True,
    max_workers=4
)
```

**如果需要，可以添加：**
```python
@app.post("/insert-batch")
async def insert_batch_folder(folder_path: str, recursive: bool = True):
    """批量处理文件夹中的所有文档"""
    rag_instance = get_rag_instance()
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG service is not ready.")
    
    # 验证路径安全性（不允许路径遍历）
    if ".." in folder_path or folder_path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid folder path")
    
    try:
        result = await rag_instance.process_folder_complete(
            folder_path=folder_path,
            output_dir="./output",
            file_extensions=[".pdf", ".docx", ".txt"],
            recursive=recursive,
            max_workers=4
        )
        return {"message": "Batch processing completed", "result": result}
    except Exception as e:
        logger.error(f"Batch processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

**是否需要：** 只有在需要批量初始化知识库时才有用

## 2. 多模态查询端点（带特定内容）

**官方功能：**
```python
result = await rag.aquery_with_multimodal(
    "Explain this formula",
    multimodal_content=[{
        "type": "equation",
        "latex": "E=mc^2",
        "equation_caption": "Mass-energy equivalence"
    }],
    mode="hybrid"
)
```

**如果需要，可以添加：**
```python
class MultimodalQueryRequest(BaseModel):
    query: str
    mode: str = "mix"
    multimodal_content: List[Dict[str, Any]]

@app.post("/query-multimodal")
async def query_multimodal(request: MultimodalQueryRequest):
    """查询时附带特定的多模态内容（如公式、表格）"""
    rag_instance = get_rag_instance()
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG service is not ready.")
    
    try:
        answer = await rag_instance.aquery_with_multimodal(
            request.query,
            multimodal_content=request.multimodal_content,
            mode=request.mode
        )
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Multimodal query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

**是否需要：** 只有在用户需要在查询时动态传入图片/表格/公式才有用

## 3. VLM 增强查询开关

**官方功能：**
```python
# 强制启用 VLM 增强
result = await rag.aquery(query, mode="hybrid", vlm_enhanced=True)

# 强制禁用 VLM 增强
result = await rag.aquery(query, mode="hybrid", vlm_enhanced=False)
```

**如果需要，可以添加：**
```python
class QueryRequest(BaseModel):
    query: str
    mode: str = "mix"
    vlm_enhanced: bool = True  # 添加 VLM 开关

@app.post("/query")
async def query_rag(request: QueryRequest):
    rag_instance = get_rag_instance()
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG service is not ready.")
    try:
        answer = await rag_instance.aquery(
            request.query, 
            mode=request.mode,
            vlm_enhanced=request.vlm_enhanced  # 传递 VLM 开关
        )
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Error during query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

**是否需要：** 只有在需要精细控制 VLM 使用时才有用

## 4. 高级解析参数

**官方功能：**
```python
await rag.process_document_complete(
    file_path="document.pdf",
    parser="mineru",
    lang="ch",           # 语言优化
    device="cuda:0",     # GPU 加速
    start_page=0,        # 页码范围
    end_page=10,
    formula=True,        # 公式解析
    table=True,          # 表格解析
)
```

**如果需要，可以添加：**
```python
class AdvancedInsertRequest(BaseModel):
    doc_id: str
    lang: str = "auto"
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    formula: bool = True
    table: bool = True

@app.post("/insert-advanced")
async def insert_advanced(
    doc_id: str,
    file: UploadFile = File(...),
    lang: str = "auto",
    start_page: Optional[int] = None,
    end_page: Optional[int] = None
):
    # ... (保存文件逻辑同前) ...
    
    kwargs = {}
    if start_page is not None:
        kwargs["start_page"] = start_page
    if end_page is not None:
        kwargs["end_page"] = end_page
    kwargs["lang"] = lang
    
    await rag_instance.process_document_complete(
        file_path=temp_file_path,
        output_dir="./output",
        **kwargs
    )
```

**是否需要：** 只有在需要精细控制解析行为时才有用

## 5. 查询模式说明端点

**可以添加一个辅助端点：**
```python
@app.get("/query-modes")
def get_query_modes():
    """返回可用的查询模式及其说明"""
    return {
        "modes": {
            "local": "聚焦于上下文相关信息",
            "global": "利用全局知识",
            "hybrid": "结合 local 和 global",
            "mix": "整合知识图谱和向量检索（推荐）",
            "naive": "基础搜索"
        },
        "recommended": "mix"
    }
```

**是否需要：** 只是方便前端展示，不影响核心功能

## 6. 健康检查增强

**可以增强现有的健康检查：**
```python
@app.get("/health")
def health_check():
    """详细的健康检查"""
    rag_instance = get_rag_instance()
    
    return {
        "status": "healthy" if rag_instance else "initializing",
        "rag_ready": rag_instance is not None,
        "version": "0.1.0",
        "features": {
            "vlm_enabled": True,
            "multimodal_processing": True,
            "max_file_size_mb": 100
        }
    }
```

## 总结

**你当前的实现已经非常完善，涵盖了核心场景：**

✅ 文件上传和处理
✅ 智能查询
✅ 安全性（UUID、验证、错误处理）
✅ VLM 多模态支持

**以上可选功能只在以下情况需要：**

1. **批量处理** - 需要初始化大量文档
2. **多模态查询** - 需要动态传入图片/公式
3. **高级参数** - 需要精细控制解析
4. **辅助端点** - 方便前端集成

**建议：**
- 先不加这些功能
- 等实际使用时发现需要再添加
- 保持当前代码的简洁性

你的实现已经是生产就绪的了。🎯

