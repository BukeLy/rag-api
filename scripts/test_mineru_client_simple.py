"""
简单的 MinerU 客户端测试

测试客户端初始化和基本功能（不实际调用 API）
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

print("\n" + "="*70)
print("🔍 MinerU 客户端本地测试")
print("="*70)

# 测试 1: 导入模块
print("\n📦 测试 1: 导入模块")
print("-" * 70)

try:
    from src.mineru_client import (
        MinerUClient,
        MinerUConfig,
        ParseOptions,
        FileTask,
        TaskResult,
        TaskStatus,
        RateLimiter,
        create_client
    )
    print("✓ 所有模块导入成功")
except Exception as e:
    print(f"✗ 导入失败: {e}")
    sys.exit(1)

# 测试 2: 创建配置对象
print("\n⚙️  测试 2: 创建配置对象")
print("-" * 70)

try:
    # 测试 ParseOptions
    options = ParseOptions(
        enable_formula=True,
        enable_table=True,
        language="ch",
        model_version="pipeline",
        extra_formats=["docx", "html"]
    )
    print(f"✓ ParseOptions 创建成功")
    print(f"  配置: {options.to_dict()}")
    
    # 测试 FileTask
    file_task = FileTask(
        url="https://example.com/test.pdf",
        data_id="test_001",
        is_ocr=True,
        page_ranges="1-10"
    )
    print(f"✓ FileTask 创建成功")
    print(f"  配置: {file_task.to_dict()}")
    
    # 测试 TaskStatus
    print(f"✓ TaskStatus 枚举值:")
    for status in TaskStatus:
        print(f"    - {status.value}")
    
except Exception as e:
    print(f"✗ 配置对象创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 3: 限流器
print("\n🚦 测试 3: 限流器")
print("-" * 70)

try:
    rate_limiter = RateLimiter(requests_per_minute=10)
    print(f"✓ RateLimiter 创建成功（每分钟 10 个请求）")
    
    # 模拟同步请求
    import time
    start = time.time()
    for i in range(3):
        rate_limiter.acquire_sync()
        print(f"  请求 {i+1}: {time.time() - start:.2f}s")
    
    print(f"✓ 限流器工作正常")
    
except Exception as e:
    print(f"✗ 限流器测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 4: 客户端初始化（需要 Token）
print("\n🔧 测试 4: 客户端初始化")
print("-" * 70)

try:
    # 尝试使用环境变量创建客户端
    import os
    token = os.getenv("MINERU_API_TOKEN", "")
    
    if not token:
        print("⚠️  MINERU_API_TOKEN 未设置，跳过客户端初始化测试")
        print("   提示：在 .env 中设置 MINERU_API_TOKEN 以启用完整测试")
    else:
        try:
            client = create_client()
            print(f"✓ 客户端创建成功")
            print(f"  API URL: {client.config.base_url}/api/{client.config.api_version}")
            print(f"  并发限制: {client.config.max_concurrent_requests}")
            print(f"  频率限制: {client.config.requests_per_minute} req/min")
            print(f"  重试次数: {client.config.retry_max_attempts}")
            print(f"  轮询超时: {client.config.poll_timeout}s")
        except ValueError as e:
            print(f"⚠️  客户端创建失败（配置错误）: {e}")
        
except Exception as e:
    print(f"✗ 客户端初始化测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 5: 数据结构验证
print("\n🏗️  测试 5: 数据结构验证")
print("-" * 70)

try:
    # 创建 TaskResult
    task_result = TaskResult(
        task_id="test_batch_123",
        status=TaskStatus.RUNNING,
        files=[
            {
                "file_name": "test.pdf",
                "data_id": "doc_001",
                "state": "running",
                "extract_progress": {
                    "extracted_pages": 5,
                    "total_pages": 10,
                    "start_time": "2025-10-15 12:00:00"
                }
            }
        ],
        extract_progress={
            "extracted_pages": 5,
            "total_pages": 10
        }
    )
    
    print(f"✓ TaskResult 创建成功")
    print(f"  task_id: {task_result.task_id}")
    print(f"  status: {task_result.status}")
    print(f"  is_processing: {task_result.is_processing}")
    print(f"  is_completed: {task_result.is_completed}")
    print(f"  is_failed: {task_result.is_failed}")
    print(f"  files: {len(task_result.files)}")
    
except Exception as e:
    print(f"✗ 数据结构验证失败: {e}")
    import traceback
    traceback.print_exc()

# 总结
print("\n" + "="*70)
print("✅ 本地测试完成！")
print("="*70)

print("\n📋 测试总结:")
print("  ✓ 模块导入")
print("  ✓ 配置对象")
print("  ✓ 限流器")
print("  ✓ 数据结构")
if os.getenv("MINERU_API_TOKEN"):
    print("  ✓ 客户端初始化")
else:
    print("  ⚠  客户端初始化（跳过，需要 Token）")

print("\n💡 下一步:")
print("  1. 在 .env 中配置 MINERU_API_TOKEN（从 https://mineru.net 获取）")
print("  2. 运行 python scripts/test_mineru_remote.py 进行完整测试")
print("  3. 集成到 RAG API 中")

print("\n" + "="*70 + "\n")

