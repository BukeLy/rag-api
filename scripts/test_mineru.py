#!/usr/bin/env python3
"""
MinerU远程服务测试脚本
测试PDF和图片文件的处理能力
"""

import requests
import time
import tempfile
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

REMOTE_API = "http://45.78.223.205:8000"


def create_test_image() -> bytes:
    """创建包含文字的测试图片"""
    # 创建白色背景图片
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)

    # 添加文字
    text_lines = [
        "Console Guide Service Report",
        "",
        "Entrance: [Product] → [Application Services] → [Service Report]",
        "",
        "Introduction:",
        "Service Report provides the service report that you customized",
        "- a monthly/weekly/daily report of your subscribed products.",
        "",
        "Functions:",
        "1. Service Report: customize UI, download reports",
        "2. Subscribed Task: email report settings",
    ]

    try:
        # 尝试使用系统字体
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except:
        # 如果失败，使用默认字体
        font = ImageFont.load_default()

    y_position = 50
    for line in text_lines:
        draw.text((50, y_position), line, fill='black', font=font)
        y_position += 40

    # 转换为bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()

    return img_byte_arr


def create_test_pdf() -> str:
    """创建简单的测试PDF"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter

        # 创建临时PDF文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_path = temp_file.name

        c = canvas.Canvas(pdf_path, pagesize=letter)

        # 添加标题
        c.setFont("Helvetica-Bold", 24)
        c.drawString(100, 750, "Console Guide Service Report")

        # 添加内容
        c.setFont("Helvetica", 12)
        content = [
            "",
            "Entrance:",
            "[Product] → [Application Services] → [Service Report]",
            "",
            "Introduction:",
            "Service Report provides the service report that you customized",
            "- a monthly/weekly/daily report of your subscribed products.",
            "",
            "There are two functions:",
            "",
            "1. Service Report:",
            "   - Customize the Service Report UI",
            "   - Download with Microsoft Doc/XLS format",
            "   - View Bandwidth Trend, Traffic Distribution Map",
            "",
            "2. Subscribed Task:",
            "   - Customize email report settings",
            "   - Send scheduled email reports to recipients",
            "   - Create tasks with report types of products",
        ]

        y_position = 700
        for line in content:
            c.drawString(100, y_position, line)
            y_position -= 20

        c.save()
        return pdf_path

    except ImportError:
        print("⚠️  reportlab not installed, skipping PDF test")
        return None


def upload_file(file_path: str, doc_id: str, file_type: str) -> dict:
    """上传文件到API"""
    print(f"\n{'='*60}")
    print(f"Testing {file_type.upper()} upload: {doc_id}")
    print(f"{'='*60}")

    start_time = time.time()

    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f)}
        response = requests.post(
            f"{REMOTE_API}/insert?doc_id={doc_id}",
            files=files,
            timeout=30
        )

    upload_time = time.time() - start_time

    print(f"✓ Upload completed in {upload_time:.2f}s")
    print(f"  Status: {response.status_code}")

    if response.status_code in [200, 202]:
        result = response.json()
        task_id = result.get('task_id')
        parser = result.get('parser', 'unknown')
        print(f"  Task ID: {task_id}")
        print(f"  Parser: {parser}")

        return {
            'success': True,
            'task_id': task_id,
            'parser': parser,
            'upload_time': upload_time
        }
    else:
        print(f"✗ Upload failed: {response.text}")
        return {'success': False, 'error': response.text}


def wait_for_task(task_id: str, timeout: int = 180) -> dict:
    """等待任务完成"""
    print(f"\nWaiting for task: {task_id}")

    start_time = time.time()
    last_status = None

    while time.time() - start_time < timeout:
        try:
            response = requests.get(
                f"{REMOTE_API}/task/{task_id}",
                timeout=10
            )

            if response.status_code == 200:
                task_status = response.json()
                status = task_status.get('status')

                # 只在状态变化时打印
                if status != last_status:
                    print(f"  [{int(time.time() - start_time)}s] Status: {status}")
                    last_status = status

                if status == 'completed':
                    elapsed = time.time() - start_time
                    print(f"✓ Task completed in {elapsed:.2f}s")

                    # 打印详细信息
                    if 'result' in task_status:
                        result = task_status['result']
                        print(f"  Result: {result}")

                    return {
                        'success': True,
                        'elapsed_time': elapsed,
                        'status': task_status
                    }
                elif status == 'failed':
                    error = task_status.get('error', 'Unknown error')
                    print(f"✗ Task failed: {error}")
                    return {
                        'success': False,
                        'error': error,
                        'elapsed_time': time.time() - start_time
                    }

            time.sleep(2)

        except Exception as e:
            print(f"✗ Error checking task: {e}")
            return {'success': False, 'error': str(e)}

    print(f"✗ Task timeout after {timeout}s")
    return {'success': False, 'error': 'Timeout'}


def test_image_processing():
    """测试图片处理"""
    print("\n" + "="*60)
    print("📸 IMAGE PROCESSING TEST")
    print("="*60)

    # 创建测试图片
    img_bytes = create_test_image()

    # 保存到临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
        tmp.write(img_bytes)
        img_path = tmp.name

    try:
        # 上传
        result = upload_file(img_path, "test_image_001", "IMAGE")

        if result['success']:
            # 等待处理
            task_result = wait_for_task(result['task_id'])

            return {
                'test': 'image',
                'upload_success': True,
                'processing_success': task_result['success'],
                'parser': result['parser'],
                'upload_time': result['upload_time'],
                'processing_time': task_result.get('elapsed_time', 0)
            }
        else:
            return {
                'test': 'image',
                'upload_success': False,
                'error': result.get('error')
            }

    finally:
        # 清理临时文件
        os.unlink(img_path)


def test_pdf_processing():
    """测试PDF处理"""
    print("\n" + "="*60)
    print("📄 PDF PROCESSING TEST")
    print("="*60)

    # 创建测试PDF
    pdf_path = create_test_pdf()

    if not pdf_path:
        return {
            'test': 'pdf',
            'skipped': True,
            'reason': 'reportlab not installed'
        }

    try:
        # 上传
        result = upload_file(pdf_path, "test_pdf_001", "PDF")

        if result['success']:
            # 等待处理
            task_result = wait_for_task(result['task_id'])

            return {
                'test': 'pdf',
                'upload_success': True,
                'processing_success': task_result['success'],
                'parser': result['parser'],
                'upload_time': result['upload_time'],
                'processing_time': task_result.get('elapsed_time', 0)
            }
        else:
            return {
                'test': 'pdf',
                'upload_success': False,
                'error': result.get('error')
            }

    finally:
        # 清理临时文件
        if pdf_path and os.path.exists(pdf_path):
            os.unlink(pdf_path)


def print_summary(results: list):
    """打印测试总结"""
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)

    for result in results:
        test_name = result.get('test', 'unknown').upper()
        print(f"\n{test_name}:")

        if result.get('skipped'):
            print(f"  ⚠️  Skipped: {result.get('reason')}")
            continue

        if result.get('upload_success'):
            print(f"  ✓ Upload: {result.get('upload_time', 0):.2f}s")
            print(f"  ✓ Parser: {result.get('parser')}")

            if result.get('processing_success'):
                print(f"  ✓ Processing: {result.get('processing_time', 0):.2f}s")
                print(f"  ✅ Overall: PASS")
            else:
                print(f"  ✗ Processing: FAIL")
                print(f"  ❌ Overall: FAIL")
        else:
            print(f"  ✗ Upload: FAIL")
            print(f"  Error: {result.get('error')}")
            print(f"  ❌ Overall: FAIL")

    # 统计
    total = len(results)
    skipped = sum(1 for r in results if r.get('skipped'))
    passed = sum(1 for r in results if r.get('processing_success'))
    tested = total - skipped

    print(f"\n{'='*60}")
    print(f"Total Tests: {total}")
    print(f"Tested: {tested}")
    print(f"Skipped: {skipped}")
    print(f"Passed: {passed}/{tested}")
    print(f"Success Rate: {(passed/tested*100 if tested > 0 else 0):.1f}%")
    print(f"{'='*60}")


def main():
    print("="*60)
    print("MinerU Remote Service Test")
    print("="*60)
    print(f"API: {REMOTE_API}")
    print(f"Tests: IMAGE, PDF")
    print("="*60)

    results = []

    # 测试图片处理
    results.append(test_image_processing())

    # 等待一下
    time.sleep(2)

    # 测试PDF处理
    results.append(test_pdf_processing())

    # 打印总结
    print_summary(results)


if __name__ == "__main__":
    main()
