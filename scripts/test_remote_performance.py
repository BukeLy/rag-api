#!/usr/bin/env python3
"""
远程API性能测试脚本
测试文档上传、查询性能，以及MinerU等服务的可用性
"""

import json
import time
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Any
import requests
from datetime import datetime

# 配置
REMOTE_API = "http://45.78.223.205:8000"
CORPUS_FILE = "/Users/chengjie/projects/rag-test/data/faq_corpus.jsonl"
BENCHMARK_FILE = "/Users/chengjie/projects/rag-test/data/faq_benchmark.jsonl"
NUM_DOCS = 10  # 测试文档数量
NUM_QUERIES = 10  # 测试查询数量


class PerformanceTestRunner:
    def __init__(self, api_base_url: str):
        self.api_base = api_base_url
        self.session = requests.Session()
        self.results = {
            "upload_times": [],
            "query_times": [],
            "task_completion_times": [],
            "errors": [],
            "timestamp": datetime.now().isoformat()
        }

    def load_jsonl(self, file_path: str, limit: int = None) -> List[Dict[str, Any]]:
        """加载JSONL文件"""
        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break
                data.append(json.loads(line.strip()))
        return data

    def upload_document(self, doc_id: str, content: str) -> Dict[str, Any]:
        """上传单个文档"""
        # 创建临时txt文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name

        try:
            start_time = time.time()

            with open(tmp_path, 'rb') as f:
                files = {'file': (f'doc_{doc_id}.txt', f, 'text/plain')}
                # doc_id 作为查询参数传递
                response = self.session.post(
                    f"{self.api_base}/insert?doc_id={doc_id}",
                    files=files,
                    timeout=30
                )

            upload_time = time.time() - start_time

            # API返回202表示任务已接受
            if response.status_code in [200, 202]:
                result = response.json()
                return {
                    "success": True,
                    "task_id": result.get("task_id"),
                    "upload_time": upload_time,
                    "doc_id": doc_id
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "upload_time": upload_time,
                    "doc_id": doc_id
                }
        finally:
            # 清理临时文件
            os.unlink(tmp_path)

    def wait_for_task(self, task_id: str, timeout: int = 120) -> Dict[str, Any]:
        """等待任务完成"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.session.get(
                    f"{self.api_base}/task/{task_id}",
                    timeout=10
                )

                if response.status_code == 200:
                    task_status = response.json()
                    status = task_status.get("status")

                    if status == "completed":
                        elapsed = time.time() - start_time
                        return {
                            "success": True,
                            "elapsed_time": elapsed,
                            "task_id": task_id
                        }
                    elif status == "failed":
                        return {
                            "success": False,
                            "error": task_status.get("error", "Unknown error"),
                            "elapsed_time": time.time() - start_time,
                            "task_id": task_id
                        }

                    # 继续等待
                    time.sleep(2)
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "elapsed_time": time.time() - start_time,
                        "task_id": task_id
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "elapsed_time": time.time() - start_time,
                    "task_id": task_id
                }

        return {
            "success": False,
            "error": "Timeout",
            "elapsed_time": timeout,
            "task_id": task_id
        }

    def query(self, question: str, mode: str = "naive") -> Dict[str, Any]:
        """查询API"""
        start_time = time.time()

        try:
            response = self.session.post(
                f"{self.api_base}/query",
                json={"query": question, "mode": mode},
                timeout=60
            )

            query_time = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "answer": result.get("response", ""),
                    "query_time": query_time,
                    "question": question
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "query_time": query_time,
                    "question": question
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query_time": time.time() - start_time,
                "question": question
            }

    def run_upload_test(self, corpus_data: List[Dict[str, Any]]) -> None:
        """运行上传测试"""
        print(f"\n{'='*60}")
        print(f"开始上传 {len(corpus_data)} 条文档...")
        print(f"{'='*60}\n")

        task_ids = []

        for i, doc in enumerate(corpus_data, 1):
            doc_id = doc.get("id")
            content = doc.get("contents", "")

            print(f"[{i}/{len(corpus_data)}] 上传文档 ID: {doc_id}")

            result = self.upload_document(doc_id, content)

            if result["success"]:
                print(f"  ✓ 上传成功，耗时: {result['upload_time']:.2f}秒")
                print(f"  ✓ Task ID: {result['task_id']}")
                task_ids.append(result['task_id'])
                self.results["upload_times"].append(result['upload_time'])
            else:
                print(f"  ✗ 上传失败: {result['error']}")
                self.results["errors"].append({
                    "type": "upload",
                    "doc_id": doc_id,
                    "error": result['error']
                })

        # 等待所有任务完成
        print(f"\n{'='*60}")
        print(f"等待 {len(task_ids)} 个任务完成...")
        print(f"{'='*60}\n")

        for i, task_id in enumerate(task_ids, 1):
            print(f"[{i}/{len(task_ids)}] 等待任务: {task_id}")

            result = self.wait_for_task(task_id)

            if result["success"]:
                print(f"  ✓ 任务完成，耗时: {result['elapsed_time']:.2f}秒")
                self.results["task_completion_times"].append(result['elapsed_time'])
            else:
                print(f"  ✗ 任务失败: {result['error']}")
                self.results["errors"].append({
                    "type": "task_completion",
                    "task_id": task_id,
                    "error": result['error']
                })

    def run_query_test(self, benchmark_data: List[Dict[str, Any]], mode: str = "naive") -> None:
        """运行查询测试"""
        print(f"\n{'='*60}")
        print(f"开始查询测试（模式: {mode}），共 {len(benchmark_data)} 个问题...")
        print(f"{'='*60}\n")

        query_results = []

        for i, item in enumerate(benchmark_data, 1):
            question = item.get("question", "")
            golden_answers = item.get("golden_answers", [])

            print(f"[{i}/{len(benchmark_data)}] 查询: {question[:50]}...")

            result = self.query(question, mode)

            if result["success"]:
                print(f"  ✓ 查询成功，耗时: {result['query_time']:.2f}秒")
                print(f"  ✓ 答案长度: {len(result['answer'])} 字符")
                self.results["query_times"].append(result['query_time'])

                query_results.append({
                    "question": question,
                    "answer": result['answer'],
                    "golden_answer": golden_answers[0] if golden_answers else "",
                    "query_time": result['query_time']
                })
            else:
                print(f"  ✗ 查询失败: {result['error']}")
                self.results["errors"].append({
                    "type": "query",
                    "question": question,
                    "error": result['error']
                })

        self.results["query_results"] = query_results

    def print_summary(self) -> None:
        """打印测试总结"""
        print(f"\n{'='*60}")
        print("测试总结")
        print(f"{'='*60}\n")

        # 上传统计
        if self.results["upload_times"]:
            upload_times = self.results["upload_times"]
            print(f"📤 文档上传统计:")
            print(f"  - 成功数量: {len(upload_times)}")
            print(f"  - 平均耗时: {sum(upload_times) / len(upload_times):.2f}秒")
            print(f"  - 最快: {min(upload_times):.2f}秒")
            print(f"  - 最慢: {max(upload_times):.2f}秒")
            print()

        # 任务完成统计
        if self.results["task_completion_times"]:
            completion_times = self.results["task_completion_times"]
            print(f"⏱️  任务处理统计:")
            print(f"  - 完成数量: {len(completion_times)}")
            print(f"  - 平均耗时: {sum(completion_times) / len(completion_times):.2f}秒")
            print(f"  - 最快: {min(completion_times):.2f}秒")
            print(f"  - 最慢: {max(completion_times):.2f}秒")
            print()

        # 查询统计
        if self.results["query_times"]:
            query_times = self.results["query_times"]
            print(f"🔍 查询统计:")
            print(f"  - 成功数量: {len(query_times)}")
            print(f"  - 平均耗时: {sum(query_times) / len(query_times):.2f}秒")
            print(f"  - 最快: {min(query_times):.2f}秒")
            print(f"  - 最慢: {max(query_times):.2f}秒")
            print()

        # 错误统计
        if self.results["errors"]:
            print(f"❌ 错误统计:")
            print(f"  - 总错误数: {len(self.results['errors'])}")

            error_types = {}
            for error in self.results["errors"]:
                error_type = error["type"]
                error_types[error_type] = error_types.get(error_type, 0) + 1

            for error_type, count in error_types.items():
                print(f"  - {error_type}: {count}")
            print()

        # 总体评估
        total_operations = (len(self.results["upload_times"]) +
                          len(self.results["task_completion_times"]) +
                          len(self.results["query_times"]))
        total_errors = len(self.results["errors"])

        success_rate = ((total_operations - total_errors) / total_operations * 100) if total_operations > 0 else 0

        print(f"📊 总体评估:")
        print(f"  - 总操作数: {total_operations}")
        print(f"  - 成功率: {success_rate:.1f}%")
        print(f"  - 测试时间: {self.results['timestamp']}")
        print()

        # 保存结果到文件
        output_file = f"/tmp/rag_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"📁 详细结果已保存到: {output_file}")


def main():
    print("="*60)
    print("RAG API 远程性能测试")
    print("="*60)
    print(f"API地址: {REMOTE_API}")
    print(f"测试文档数: {NUM_DOCS}")
    print(f"测试查询数: {NUM_QUERIES}")
    print("="*60)

    # 初始化测试器
    tester = PerformanceTestRunner(REMOTE_API)

    # 加载数据
    print("\n加载测试数据...")
    corpus_data = tester.load_jsonl(CORPUS_FILE, NUM_DOCS)
    benchmark_data = tester.load_jsonl(BENCHMARK_FILE, NUM_QUERIES)
    print(f"✓ 已加载 {len(corpus_data)} 条文档和 {len(benchmark_data)} 个测试问题")

    # 运行上传测试
    tester.run_upload_test(corpus_data)

    # 等待一段时间，让数据完全处理
    print("\n等待5秒，确保数据完全处理...")
    time.sleep(5)

    # 运行查询测试
    tester.run_query_test(benchmark_data, mode="naive")

    # 打印总结
    tester.print_summary()


if __name__ == "__main__":
    main()
