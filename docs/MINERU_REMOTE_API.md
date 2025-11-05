# MinerU 远程 API 配置指南

## 📋 概述

MinerU 远程 API 允许您将文档解析任务卸载到远程服务器，从而：
- ✅ **减少本地资源消耗**（无需 GPU、无需下载大型模型）
- ✅ **提升处理性能**（利用远程高性能服务器）
- ✅ **降低 OOM 风险**（不占用本地内存）
- ✅ **支持水平扩展**（多客户端共享同一服务）

**官方文档：** https://mineru.net/apiManage/docs

---

## 🚀 快速开始

### 1. 注册并获取 API Token

访问 [https://mineru.net](https://mineru.net) 注册账号并获取：
- `MINERU_API_TOKEN`: API 访问令牌
- `MINERU_USER_TOKEN`: 用户唯一标识

### 2. 配置环境变量

在 `.env` 文件中添加：

```bash
# MinerU 远程 API 配置
MINERU_API_TOKEN=your_mineru_api_token_here
MINERU_USER_TOKEN=your_mineru_user_token_here
USE_REMOTE_MINERU=true  # 启用远程 API
```

### 3. 安装依赖

远程 API 客户端只需要基础的 HTTP 库，已包含在项目依赖中：

```bash
# 已包含在 pyproject.toml 中
# - aiohttp（异步 HTTP）
# - requests（同步 HTTP）
```

---

## 📖 API 参考

### 核心类

#### `MinerUClient`

主客户端类，提供同步和异步两种调用方式。

**初始化：**

```python
from src.mineru_client import MinerUClient, MinerUConfig

# 使用默认配置（从环境变量读取）
client = MinerUClient()

# 使用自定义配置
config = MinerUConfig(
    api_token="your_token",
    user_token="your_user_token",
    max_concurrent_requests=5,
    requests_per_minute=60
)
client = MinerUClient(config)
```

#### `ParseOptions`

文档解析选项。

```python
from src.mineru_client import ParseOptions

options = ParseOptions(
    enable_formula=True,      # 启用公式解析
    enable_table=True,        # 启用表格解析
    language="ch",            # 语言：ch / en
    is_ocr=True,             # 是否使用 OCR
    parse_method="auto",     # 解析方法：auto / ocr / txt
    output_format="markdown" # 输出格式：markdown / json
)
```

#### `FileTask`

单个文件任务。

```python
from src.mineru_client import FileTask

task = FileTask(
    url="https://example.com/document.pdf",  # 文件 URL（必填）
    data_id="doc_001",                       # 数据 ID（必填）
    is_ocr=True,                             # 是否使用 OCR（可选，覆盖全局设置）
    language="ch"                            # 语言（可选，覆盖全局设置）
)
```

---

## 💡 使用示例

### 异步模式（推荐）

```python
import asyncio
from src.mineru_client import create_client, FileTask, ParseOptions

async def parse_documents():
    # 创建客户端
    client = create_client()
    
    # 准备文件
    files = [
        FileTask(url="https://example.com/doc1.pdf", data_id="doc_001"),
        FileTask(url="https://example.com/doc2.pdf", data_id="doc_002"),
    ]
    
    # 配置选项
    options = ParseOptions(
        enable_formula=True,
        enable_table=True,
        language="ch"
    )
    
    # 一站式解析（推荐）
    result = await client.parse_documents(
        files=files,
        options=options,
        wait_for_completion=True,  # 等待任务完成
        timeout=600  # 最多等待 10 分钟
    )
    
    # 处理结果
    print(f"✓ 解析完成！文件数: {len(result.files)}")
    for file in result.files:
        print(f"  - {file['data_id']}: {file['status']}")
        print(f"    内容长度: {len(file.get('content', ''))}")

# 运行
asyncio.run(parse_documents())
```

### 同步模式

```python
from src.mineru_client import create_client, FileTask, ParseOptions

def parse_documents():
    client = create_client()
    
    files = [
        FileTask(url="https://example.com/doc.pdf", data_id="doc_001")
    ]
    
    options = ParseOptions(enable_formula=True, language="ch")
    
    # 同步解析
    result = client.parse_documents_sync(
        files=files,
        options=options,
        wait_for_completion=True
    )
    
    print(f"✓ 解析完成！")
    return result

parse_documents()
```

### 分步操作（高级用法）

```python
async def advanced_usage():
    client = create_client()
    files = [FileTask(url="https://example.com/doc.pdf", data_id="doc_001")]
    
    # 步骤 1: 创建任务（不等待）
    task = await client.create_batch_task(files)
    print(f"任务已创建: {task.batch_id}")
    
    # 步骤 2: 做其他事情...
    await asyncio.sleep(5)
    
    # 步骤 3: 查询状态
    result = await client.get_batch_result(task.batch_id)
    print(f"当前状态: {result.status}")
    
    # 步骤 4: 等待完成
    if result.is_processing:
        result = await client.wait_for_completion(task.batch_id, timeout=300)
    
    print(f"最终状态: {result.status}")
```

---

## ⚙️ 配置参数说明

### MinerUConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `api_token` | str | 环境变量 | API 访问令牌 |
| `user_token` | str | 环境变量 | 用户唯一标识 |
| `base_url` | str | `https://mineru.net` | API 基础 URL |
| `api_version` | str | `v4` | API 版本 |
| `max_concurrent_requests` | int | `5` | 最大并发请求数 |
| `requests_per_minute` | int | `60` | 每分钟最大请求数 |
| `retry_max_attempts` | int | `3` | 最大重试次数 |
| `retry_delay` | float | `1.0` | 重试延迟（秒） |
| `poll_interval` | float | `2.0` | 状态轮询间隔（秒） |
| `poll_timeout` | float | `600.0` | 轮询超时（秒） |

### ParseOptions 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `enable_formula` | bool | `True` | 启用公式解析 |
| `enable_table` | bool | `True` | 启用表格解析 |
| `language` | str | `"ch"` | 语言：ch（中文）/ en（英文） |
| `is_ocr` | bool | `True` | 是否使用 OCR |
| `parse_method` | str | `"auto"` | 解析方法：auto / ocr / txt |
| `output_format` | str | `"markdown"` | 输出格式：markdown / json |

---

## 🔧 限流机制

### 内置限流器

客户端内置了智能限流器，自动控制请求频率：

```python
from src.mineru_client import MinerUConfig, MinerUClient

# 配置严格的限流
config = MinerUConfig(
    requests_per_minute=30,      # 每分钟最多 30 个请求
    max_concurrent_requests=3     # 最多 3 个并发请求
)

client = MinerUClient(config)

# 客户端会自动：
# 1. 限制并发请求数（使用 asyncio.Semaphore）
# 2. 限制每分钟请求数（使用 RateLimiter）
# 3. 在达到限制时自动等待
```

### 限流日志

当触发限流时，会输出警告日志：

```
WARNING:src.mineru_client:Rate limit reached, waiting 5.2s
```

---

## 🎯 测试脚本

运行测试脚本验证配置：

```bash
# 运行测试脚本
python scripts/test_mineru_remote.py

# 选择测试项目：
#   1. 异步解析测试
#   2. 同步解析测试
#   3. 限流功能测试
```

---

## 🔄 与 RAG-Anything 集成

目前客户端已创建，下一步可以集成到 RAG-Anything：

### 选项 1：完全替换本地 MinerU

将 RAG-Anything 的 MinerU 解析器替换为远程 API 调用。

### 选项 2：混合模式

- 小文件：使用本地解析器
- 大文件：使用远程 API

### 选项 3：降级策略

- 优先使用远程 API
- 远程 API 失败时降级到本地解析

---

## 📊 性能对比

| 模式 | 本地资源占用 | 处理速度 | GPU 需求 | 内存占用 |
|------|------------|---------|---------|---------|
| **本地 MinerU** | 高 | 快 | 需要 | 14GB+ |
| **远程 API** | 极低 | 中等（网络延迟）| 无 | <100MB |

---

## 🚨 注意事项

### 1. 文件访问

远程 API 需要通过 **公网可访问的 URL** 获取文件，因此：

**不支持：**
- ❌ 本地文件路径（`/tmp/file.pdf`）
- ❌ 私有网络 URL（`http://192.168.1.100/file.pdf`）

**支持：**
- ✅ 公网 HTTP/HTTPS URL（`https://example.com/file.pdf`）
- ✅ OSS/S3 公开链接

**解决方案：**
- 方案 1：上传文件到 OSS/S3，获取临时公开链接
- 方案 2：使用本地文件时，降级到本地 MinerU 解析

### 2. API 限制

根据 MinerU 官方 API 文档：
- 每分钟请求数限制（具体数值以官方文档为准）
- 并发请求数限制
- 单个文件大小限制

客户端已内置限流机制，会自动处理。

### 3. 成本

- 远程 API 可能产生使用费用
- 请查阅 MinerU 官方定价

---

## 🛠️ 故障排查

### 问题 1：认证失败

**错误信息：**
```
API Error: Invalid token
```

**解决方案：**
1. 检查 `.env` 中的 `MINERU_API_TOKEN` 和 `MINERU_USER_TOKEN`
2. 确认 Token 未过期
3. 访问 https://mineru.net 重新生成 Token

### 问题 2：限流触发

**日志：**
```
Rate limit reached, waiting 5.2s
```

**说明：** 这是正常行为，客户端会自动等待并重试。

**优化：**
- 减少 `max_concurrent_requests`
- 减少 `requests_per_minute`

### 问题 3：任务超时

**错误信息：**
```
TimeoutError: Task xxx timed out after 600s
```

**解决方案：**
1. 增加 `poll_timeout` 配置
2. 检查文件大小是否过大
3. 稍后手动查询任务结果

---

## 📚 完整示例

```python
"""
完整的远程 MinerU API 使用示例
"""

import asyncio
from src.mineru_client import create_client, FileTask, ParseOptions

async def main():
    # 1. 创建客户端
    client = create_client()
    
    # 2. 准备文件（必须是公网可访问的 URL）
    files = [
        FileTask(
            url="https://example.com/research-paper.pdf",
            data_id="paper_001",
            is_ocr=True  # 启用 OCR
        ),
        FileTask(
            url="https://example.com/financial-report.xlsx",
            data_id="report_001",
            language="ch"  # 指定中文
        ),
    ]
    
    # 3. 配置解析选项
    options = ParseOptions(
        enable_formula=True,   # 启用公式解析（论文、报告）
        enable_table=True,     # 启用表格解析
        language="ch",         # 默认中文
        is_ocr=True,          # 默认启用 OCR
        output_format="markdown"
    )
    
    # 4. 执行解析
    try:
        print("📤 开始解析文档...")
        
        result = await client.parse_documents(
            files=files,
            options=options,
            wait_for_completion=True,
            timeout=600  # 10 分钟超时
        )
        
        print(f"✅ 解析完成！")
        print(f"   Batch ID: {result.batch_id}")
        print(f"   Status: {result.status}")
        print(f"   Files: {len(result.files)}")
        
        # 5. 处理结果
        for file_result in result.files:
            data_id = file_result.get("data_id")
            status = file_result.get("status")
            content = file_result.get("content", "")
            
            print(f"\n📄 {data_id}:")
            print(f"   状态: {status}")
            print(f"   内容长度: {len(content)} 字符")
            
            if status == "completed":
                # 保存结果
                output_path = f"./output/{data_id}.md"
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"   ✓ 已保存到: {output_path}")
            elif file_result.get("error"):
                print(f"   ✗ 错误: {file_result['error']}")
        
        return result
        
    except TimeoutError as e:
        print(f"❌ 超时: {e}")
        print("💡 提示：可以稍后使用 batch_id 查询结果")
    
    except Exception as e:
        print(f"❌ 错误: {e}")

# 运行
asyncio.run(main())
```

---

## 🎛️ 高级配置

### 自定义限流策略

```python
from src.mineru_client import MinerUConfig, MinerUClient

# 高频访问配置（需要高级 API 套餐）
config_high_freq = MinerUConfig(
    requests_per_minute=120,  # 每分钟 120 个请求
    max_concurrent_requests=10  # 最多 10 个并发
)

# 低频访问配置（节省成本）
config_low_freq = MinerUConfig(
    requests_per_minute=10,   # 每分钟 10 个请求
    max_concurrent_requests=2   # 最多 2 个并发
)

client = MinerUClient(config_high_freq)
```

### 自定义重试策略

```python
config = MinerUConfig(
    retry_max_attempts=5,  # 最多重试 5 次
    retry_delay=2.0        # 初始延迟 2 秒（指数退避）
)
```

### 自定义轮询策略

```python
config = MinerUConfig(
    poll_interval=5.0,   # 每 5 秒查询一次状态
    poll_timeout=1800.0  # 最多等待 30 分钟
)
```

---

## 📝 API 端点

根据官方文档 (https://mineru.net/apiManage/docs)：

### 1. 创建批量任务

**端点：** `POST /api/v4/extract/task/batch`

**请求头：**
```
Content-Type: application/json
Authorization: Bearer {MINERU_API_TOKEN}
token: {MINERU_USER_TOKEN}
```

**请求体：**
```json
{
  "enable_formula": true,
  "enable_table": true,
  "language": "ch",
  "is_ocr": true,
  "files": [
    {
      "url": "https://example.com/document.pdf",
      "data_id": "doc_001",
      "is_ocr": true
    }
  ]
}
```

**响应：**
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "batch_id": "batch_xxxxxxxx",
    "created_at": "2025-10-15T12:00:00Z"
  }
}
```

### 2. 查询批量任务结果

**端点：** `GET /api/v4/extract-results/batch/{batch_id}`

**请求头：**
```
Authorization: Bearer {MINERU_API_TOKEN}
token: {MINERU_USER_TOKEN}
```

**响应：**
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "batch_id": "batch_xxxxxxxx",
    "status": "completed",
    "files": [
      {
        "data_id": "doc_001",
        "status": "completed",
        "content": "# Document Title\n\nContent here...",
        "error": null
      }
    ],
    "created_at": "2025-10-15T12:00:00Z",
    "completed_at": "2025-10-15T12:05:00Z"
  }
}
```

---

## 🎯 下一步

客户端已创建完成，包含：
- ✅ 完整的 API 调用封装
- ✅ 限流机制
- ✅ 自动重试
- ✅ 异步/同步两种模式
- ✅ 所有参数支持

**集成建议：**
1. 在 RAG-Anything 中添加远程 API 适配器
2. 实现本地/远程自动切换逻辑
3. 添加文件上传到 OSS 的功能（用于本地文件）

---

## 📞 参考资源

- **官方 API 文档：** https://mineru.net/apiManage/docs
- **MinerU GitHub：** https://github.com/opendatalab/mineru
- **RAG-Anything GitHub：** https://github.com/hkuds/rag-anything

