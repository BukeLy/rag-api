#!/usr/bin/env python3
"""
完整的 RAG API 测试脚本
测试文件上传、文档处理和查询功能
"""

import requests
import time
import sys
import os
from pathlib import Path

# API 配置
API_BASE_URL = "http://localhost:8000"
UPLOAD_ENDPOINT = f"{API_BASE_URL}/insert"
QUERY_ENDPOINT = f"{API_BASE_URL}/query"
HEALTH_ENDPOINT = f"{API_BASE_URL}/"

def wait_for_api_ready(max_retries=30, retry_interval=2):
    """等待 API 启动"""
    print("等待 API 启动...")
    for i in range(max_retries):
        try:
            response = requests.get(HEALTH_ENDPOINT, timeout=5)
            if response.status_code == 200:
                print(f"✓ API 已就绪: {response.json()}")
                return True
        except requests.exceptions.RequestException:
            pass
        
        print(f"  尝试 {i+1}/{max_retries}...")
        time.sleep(retry_interval)
    
    print("✗ API 启动超时")
    return False

def create_test_txt_file():
    """创建一个简单的文本测试文件"""
    test_file_path = "/tmp/test_document.txt"
    content = """
这是一个测试文档。

关于人工智能：
人工智能（Artificial Intelligence，简称 AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。

关于机器学习：
机器学习是人工智能的一个子领域，它使计算机能够从数据中学习，而无需显式编程。

关于深度学习：
深度学习是机器学习的一个分支，使用多层神经网络来学习数据的复杂表示。
"""
    
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"✓ 创建测试文本文件: {test_file_path}")
    return test_file_path

def test_upload_document(file_path, doc_id):
    """测试文件上传"""
    print(f"\n{'='*60}")
    print(f"测试上传文档: {file_path}")
    print(f"{'='*60}")
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            params = {"doc_id": doc_id}
            
            print(f"正在上传文件 {os.path.basename(file_path)}...")
            response = requests.post(UPLOAD_ENDPOINT, files=files, params=params, timeout=120)
            
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ 上传成功!")
                print(f"  响应: {result}")
                return True
            else:
                print(f"✗ 上传失败!")
                print(f"  错误信息: {response.text}")
                return False
                
    except Exception as e:
        print(f"✗ 上传过程出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_query(query_text, mode="hybrid"):
    """测试查询"""
    print(f"\n{'='*60}")
    print(f"测试查询: {query_text}")
    print(f"{'='*60}")
    
    try:
        payload = {
            "query": query_text,
            "mode": mode
        }
        
        print(f"正在查询...")
        response = requests.post(QUERY_ENDPOINT, json=payload, timeout=60)
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 查询成功!")
            print(f"\n问题: {query_text}")
            print(f"答案:\n{result.get('answer', 'No answer')}")
            return True
        else:
            print(f"✗ 查询失败!")
            print(f"  错误信息: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ 查询过程出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试流程"""
    print("="*60)
    print("RAG API 完整测试")
    print("="*60)
    
    # 1. 等待 API 就绪
    if not wait_for_api_ready():
        print("\n✗ 测试失败：API 未启动")
        return False
    
    # 2. 创建测试文件
    test_file = create_test_txt_file()
    
    # 3. 上传文档
    upload_success = test_upload_document(test_file, doc_id="test_doc_001")
    
    if not upload_success:
        print("\n✗ 测试失败：文档上传失败")
        return False
    
    # 等待一下，确保文档被处理
    print("\n等待 5 秒，让文档处理完成...")
    time.sleep(5)
    
    # 4. 测试查询
    test_queries = [
        "什么是人工智能？",
        "机器学习和深度学习有什么关系？",
        "这个文档讲了什么内容？"
    ]
    
    all_queries_success = True
    for query in test_queries:
        query_success = test_query(query)
        all_queries_success = all_queries_success and query_success
        time.sleep(2)  # 查询间隔
    
    # 5. 总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    
    if upload_success and all_queries_success:
        print("✓ 所有测试通过！")
        return True
    else:
        print("✗ 部分测试失败")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试过程出现未处理的异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

