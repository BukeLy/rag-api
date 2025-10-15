"""
MinerU 远程 API 测试脚本

测试 MinerU 远程 API 客户端的功能
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mineru_client import (
    MinerUClient,
    MinerUConfig,
    ParseOptions,
    FileTask,
    create_client
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_async_parsing():
    """测试异步文档解析"""
    print("\n" + "="*60)
    print("🚀 测试 MinerU 远程 API（异步模式）")
    print("="*60)
    
    try:
        # 创建客户端
        client = create_client()
        print("✓ 客户端创建成功")
        
        # 准备测试文件
        files = [
            FileTask(
                url="https://example.com/test-document.pdf",  # 替换为实际的文件 URL
                data_id="test_doc_001",
                is_ocr=True
            ),
        ]
        
        # 配置解析选项
        options = ParseOptions(
            enable_formula=True,   # 启用公式解析
            enable_table=True,     # 启用表格解析
            language="ch",         # 中文
            is_ocr=True,          # 使用 OCR
            output_format="markdown"
        )
        
        print(f"\n📄 准备解析 {len(files)} 个文件...")
        print(f"   - enable_formula: {options.enable_formula}")
        print(f"   - enable_table: {options.enable_table}")
        print(f"   - language: {options.language}")
        print(f"   - is_ocr: {options.is_ocr}")
        
        # 方式 1：创建任务，不等待完成
        print("\n📤 方式 1: 创建任务（不等待）")
        task = await client.create_batch_task(files, options)
        print(f"✓ 任务已创建")
        print(f"   - batch_id: {task.batch_id}")
        print(f"   - status: {task.status}")
        print(f"   - created_at: {task.created_at}")
        
        # 手动查询任务状态
        print(f"\n🔍 查询任务状态: {task.batch_id}")
        result = await client.get_batch_result(task.batch_id)
        print(f"✓ 当前状态: {result.status}")
        
        # 方式 2：一站式解析（推荐）
        print("\n📤 方式 2: 一站式解析（创建 + 等待）")
        print("⏳ 正在解析文档...")
        
        result = await client.parse_documents(
            files=files,
            options=options,
            wait_for_completion=True,  # 等待任务完成
            timeout=300  # 最多等待 5 分钟
        )
        
        print(f"✅ 解析完成！")
        print(f"   - batch_id: {result.batch_id}")
        print(f"   - status: {result.status}")
        print(f"   - files: {len(result.files)}")
        
        # 显示每个文件的结果
        for i, file_result in enumerate(result.files, 1):
            print(f"\n   文件 {i}:")
            print(f"     - data_id: {file_result.get('data_id')}")
            print(f"     - status: {file_result.get('status')}")
            print(f"     - content_length: {len(file_result.get('content', ''))}")
            if file_result.get('error'):
                print(f"     - error: {file_result.get('error')}")
        
        return result
        
    except ValueError as e:
        print(f"\n❌ 配置错误: {e}")
        print("\n💡 提示：请在 .env 文件中配置以下环境变量：")
        print("   - MINERU_API_TOKEN=your_token")
        print("   - MINERU_USER_TOKEN=your_user_token")
        return None
    
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)
        return None


def test_sync_parsing():
    """测试同步文档解析"""
    print("\n" + "="*60)
    print("🚀 测试 MinerU 远程 API（同步模式）")
    print("="*60)
    
    try:
        # 创建客户端
        client = create_client()
        print("✓ 客户端创建成功")
        
        # 准备测试文件
        files = [
            FileTask(
                url="https://example.com/test-document.pdf",
                data_id="test_doc_sync_001"
            ),
        ]
        
        options = ParseOptions(
            enable_formula=True,
            enable_table=True,
            language="ch"
        )
        
        print(f"\n📄 准备解析 {len(files)} 个文件（同步模式）...")
        
        # 同步解析
        result = client.parse_documents_sync(
            files=files,
            options=options,
            wait_for_completion=True,
            timeout=300
        )
        
        print(f"✅ 解析完成！")
        print(f"   - batch_id: {result.batch_id}")
        print(f"   - status: {result.status}")
        print(f"   - files: {len(result.files)}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)
        return None


def test_rate_limiting():
    """测试限流功能"""
    print("\n" + "="*60)
    print("🚀 测试限流功能")
    print("="*60)
    
    try:
        # 创建配置了严格限流的客户端
        config = MinerUConfig(
            requests_per_minute=10,  # 每分钟最多 10 个请求
            max_concurrent_requests=2  # 最多 2 个并发请求
        )
        client = MinerUClient(config)
        
        print(f"✓ 客户端配置:")
        print(f"   - requests_per_minute: {config.requests_per_minute}")
        print(f"   - max_concurrent_requests: {config.max_concurrent_requests}")
        
        # 模拟多个请求
        files = [
            FileTask(url=f"https://example.com/doc{i}.pdf", data_id=f"doc_{i:03d}")
            for i in range(5)
        ]
        
        print(f"\n📤 准备发送 {len(files)} 个请求...")
        
        async def send_requests():
            tasks = []
            for file in files:
                task = client.create_batch_task([file])
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        
        results = asyncio.run(send_requests())
        
        print(f"✓ 完成 {len(results)} 个请求")
        for i, result in enumerate(results, 1):
            if isinstance(result, Exception):
                print(f"   {i}. 错误: {result}")
            else:
                print(f"   {i}. 成功: {result.batch_id}")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)


def main():
    """主函数"""
    print("\n" + "="*60)
    print("📚 MinerU 远程 API 客户端测试")
    print("="*60)
    
    # 测试选项
    tests = [
        ("1", "异步解析测试", test_async_parsing),
        ("2", "同步解析测试", test_sync_parsing),
        ("3", "限流功能测试", test_rate_limiting),
    ]
    
    print("\n请选择测试项目：")
    for code, name, _ in tests:
        print(f"  {code}. {name}")
    print("  q. 退出")
    
    choice = input("\n请输入选项 [1]: ").strip() or "1"
    
    if choice.lower() == 'q':
        print("👋 再见！")
        return
    
    # 执行测试
    for code, name, test_func in tests:
        if choice == code:
            print(f"\n▶ 执行: {name}\n")
            if asyncio.iscoroutinefunction(test_func):
                asyncio.run(test_func())
            else:
                test_func()
            break
    else:
        print(f"❌ 无效选项: {choice}")
    
    print("\n" + "="*60)
    print("✅ 测试完成")
    print("="*60)


if __name__ == "__main__":
    main()

