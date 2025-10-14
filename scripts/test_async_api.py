#!/usr/bin/env python3
"""
测试异步任务 API

测试流程：
1. 上传文件 -> 获得 task_id (202)
2. 轮询任务状态 -> pending/processing/completed/failed
3. 查询 RAG 系统
"""

import sys
import time
import requests
from pathlib import Path

# API 配置
API_BASE_URL = "http://localhost:8000"


def create_test_file(filename: str, content: str):
    """创建测试文件"""
    filepath = Path(f"/tmp/{filename}")
    filepath.write_text(content, encoding="utf-8")
    return filepath


def upload_document(doc_id: str, filepath: Path):
    """上传文档"""
    print(f"\n📤 上传文档: {filepath.name}")
    
    with open(filepath, "rb") as f:
        files = {"file": (filepath.name, f, "text/plain")}
        response = requests.post(
            f"{API_BASE_URL}/insert",
            params={"doc_id": doc_id},
            files=files
        )
    
    if response.status_code == 202:
        data = response.json()
        print(f"✅ 文档已接受处理")
        print(f"   Task ID: {data['task_id']}")
        print(f"   Status: {data['status']}")
        return data['task_id']
    else:
        print(f"❌ 上传失败: {response.status_code}")
        print(f"   错误: {response.text}")
        return None


def get_task_status(task_id: str):
    """查询任务状态"""
    response = requests.get(f"{API_BASE_URL}/task/{task_id}")
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ 查询失败: {response.status_code}")
        return None


def wait_for_task_completion(task_id: str, timeout=300):
    """等待任务完成"""
    print(f"\n⏳ 等待任务完成 (最多等待 {timeout} 秒)...")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < timeout:
        task_info = get_task_status(task_id)
        
        if not task_info:
            break
        
        current_status = task_info['status']
        
        # 状态变化时打印
        if current_status != last_status:
            elapsed = int(time.time() - start_time)
            print(f"   [{elapsed}s] 状态: {current_status}")
            last_status = current_status
        
        if current_status == "completed":
            print(f"✅ 任务完成！")
            print(f"   结果: {task_info.get('result')}")
            return True
        elif current_status == "failed":
            print(f"❌ 任务失败！")
            print(f"   错误: {task_info.get('error')}")
            return False
        
        time.sleep(2)  # 每 2 秒轮询一次
    
    print(f"⏰ 任务超时（超过 {timeout} 秒）")
    return False


def query_rag(query: str, mode: str = "mix"):
    """查询 RAG"""
    print(f"\n🔍 查询: {query}")
    
    response = requests.post(
        f"{API_BASE_URL}/query",
        json={"query": query, "mode": mode}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 查询成功")
        print(f"   答案: {data['answer'][:200]}...")
        return data['answer']
    else:
        print(f"❌ 查询失败: {response.status_code}")
        print(f"   错误: {response.text}")
        return None


def main():
    print("=" * 60)
    print("🚀 RAG API 异步任务测试")
    print("=" * 60)
    
    # 1. 检查健康状态
    print("\n1️⃣ 检查 API 健康状态...")
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code == 200:
            print(f"✅ API 运行正常: {response.json()}")
        else:
            print(f"❌ API 不可用: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 无法连接到 API: {e}")
        sys.exit(1)
    
    # 2. 创建测试文件
    print("\n2️⃣ 创建测试文件...")
    test_content = """
    人工智能（AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。
    这些任务包括学习、推理、问题解决、感知和语言理解。
    
    机器学习是 AI 的一个子领域，专注于开发能够从数据中学习并改进性能的算法。
    深度学习是机器学习的一个分支，使用多层神经网络来处理复杂的数据模式。
    """
    
    test_file = create_test_file("ai_introduction.txt", test_content)
    print(f"✅ 测试文件已创建: {test_file}")
    
    # 3. 上传文档
    print("\n3️⃣ 上传文档...")
    task_id = upload_document("ai_doc_001", test_file)
    
    if not task_id:
        print("❌ 文档上传失败")
        sys.exit(1)
    
    # 4. 等待处理完成
    print("\n4️⃣ 等待文档处理...")
    success = wait_for_task_completion(task_id)
    
    if not success:
        print("❌ 文档处理失败")
        sys.exit(1)
    
    # 5. 查询 RAG
    print("\n5️⃣ 查询 RAG 系统...")
    query_rag("什么是人工智能？")
    query_rag("深度学习和机器学习有什么关系？")
    
    # 6. 清理测试文件
    print("\n6️⃣ 清理测试文件...")
    test_file.unlink()
    print("✅ 测试文件已删除")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

