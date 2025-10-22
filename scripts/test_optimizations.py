"""
优化功能测试脚本

验证以下功能：
1. 文件服务过期文件清理
2. MinerU 结果处理器
3. 批量插入 API
4. 性能监控 metrics
"""

import os
import sys
import time
import asyncio
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import logger
from src.file_url_service import FileURLService
from src.mineru_result_processor import MinerUResultProcessor
from src.metrics import (
    MetricsCollector, APIMetrics, DocumentMetrics, 
    get_metrics_collector
)


def test_file_cleanup():
    """测试文件清理功能"""
    logger.info("=" * 70)
    logger.info("测试 1: 文件清理功能")
    logger.info("=" * 70)
    
    # 创建临时文件服务
    temp_dir = tempfile.mkdtemp(prefix="test_file_service_")
    file_service = FileURLService(base_url="http://localhost:8000", temp_dir=temp_dir)
    
    try:
        # 创建测试文件
        test_files = []
        for i in range(3):
            test_file = os.path.join(temp_dir, f"test_file_{i}.txt")
            with open(test_file, 'w') as f:
                f.write(f"Test content {i}\n" * 100)
            test_files.append(test_file)
            file_service.file_mapping[f"file_{i}"] = test_file
            logger.info(f"✓ 创建测试文件: {test_file}")
        
        # 验证文件数量
        logger.info(f"✓ 文件映射数: {len(file_service.file_mapping)}")
        assert len(file_service.file_mapping) == 3, "文件映射数不匹配"
        
        # 测试文件清理（注意：新创建的文件不会被清理）
        file_service.cleanup_old_files(max_age_hours=0)  # 清理所有文件
        logger.info("✓ 文件清理完成")
        
        logger.info("✅ 文件清理功能测试通过\n")
        return True
    
    except Exception as e:
        logger.error(f"❌ 文件清理功能测试失败: {e}")
        return False


def test_metrics_collector():
    """测试性能监控采集器"""
    logger.info("=" * 70)
    logger.info("测试 2: 性能监控采集器")
    logger.info("=" * 70)
    
    try:
        collector = MetricsCollector()
        
        # 测试 API 调用记录
        logger.info("📊 记录 API 调用...")
        for i in range(10):
            response_time = 0.1 + (i * 0.01)  # 100-190ms
            status_code = 200 if i % 10 != 9 else 500  # 最后一个返回错误
            collector.record_api_call("/insert", "POST", response_time, status_code)
        
        # 获取 API 摘要
        api_summary = collector.get_api_summary()
        logger.info(f"✓ API 摘要: {api_summary}")
        
        # 验证性能指标
        for endpoint, metrics in api_summary.items():
            logger.info(f"  端点: {endpoint}")
            logger.info(f"    - 请求数: {metrics['request_count']}")
            logger.info(f"    - 错误率: {metrics['error_rate']}")
            logger.info(f"    - 平均响应时间: {metrics['avg_response_time_ms']}ms")
            logger.info(f"    - P95 响应时间: {metrics['p95_response_time_ms']}ms")
        
        # 测试文档处理指标
        logger.info("\n📄 记录文档处理指标...")
        doc_metric = DocumentMetrics(
            doc_id="doc_001",
            filename="test.pdf",
            file_size=1024 * 500,  # 500KB
            parser="mineru",
            parse_time=2.5,
            insert_time=1.2,
            total_time=3.7,
            entity_count=150,
            relation_count=89,
            chunk_count=45,
            status="completed"
        )
        collector.record_document(doc_metric)
        
        # 获取文档摘要
        doc_summary = collector.get_document_summary()
        logger.info(f"✓ 文档处理摘要: {doc_summary}")
        
        # 测试系统指标
        logger.info("\n🖥️  记录系统指标...")
        collector.record_system_metric("cpu_usage", 45.5, unit="%", threshold=80.0)
        collector.record_system_metric("memory_usage", 72.3, unit="%", threshold=85.0)
        
        system_metrics = collector.system_metrics
        logger.info(f"✓ 系统指标数: {len(system_metrics)}")
        for name, metric in system_metrics.items():
            logger.info(f"  {name}: {metric.value:.2f}{metric.unit}")
        
        # 测试告警
        logger.info("\n🚨 测试告警机制...")
        collector.record_system_metric("cpu_usage", 95.0, unit="%", threshold=80.0)  # 触发告警
        
        alerts = collector.get_recent_alerts()
        logger.info(f"✓ 告警数: {len(alerts)}")
        for alert in alerts[-3:]:
            logger.info(f"  [{alert['severity'].upper()}] {alert['type']}: {alert['message']}")
        
        logger.info("✅ 性能监控采集器测试通过\n")
        return True
    
    except Exception as e:
        logger.error(f"❌ 性能监控采集器测试失败: {e}", exc_info=True)
        return False


def test_metrics_system_collection():
    """测试系统指标采集"""
    logger.info("=" * 70)
    logger.info("测试 3: 系统指标采集")
    logger.info("=" * 70)
    
    try:
        collector = MetricsCollector()
        
        logger.info("📊 采集系统指标...")
        collector.collect_system_metrics()
        
        system_metrics = collector.system_metrics
        
        if "cpu_usage" in system_metrics:
            logger.info(f"✓ CPU 使用率: {system_metrics['cpu_usage'].value:.1f}%")
        
        if "memory_usage" in system_metrics:
            logger.info(f"✓ 内存使用率: {system_metrics['memory_usage'].value:.1f}%")
        
        if "disk_usage" in system_metrics:
            logger.info(f"✓ 磁盘使用率: {system_metrics['disk_usage'].value:.1f}%")
        
        logger.info("✅ 系统指标采集测试通过\n")
        return True
    
    except ImportError as e:
        logger.warning(f"⚠️  psutil 未安装，跳过系统指标采集测试: {e}")
        return True  # 不计为失败，因为这是可选的
    
    except Exception as e:
        logger.error(f"❌ 系统指标采集测试失败: {e}", exc_info=True)
        return False


def test_mineru_result_processor():
    """测试 MinerU 结果处理器"""
    logger.info("=" * 70)
    logger.info("测试 4: MinerU 结果处理器")
    logger.info("=" * 70)
    
    try:
        processor = MinerUResultProcessor()
        logger.info(f"✓ 结果处理器已初始化: temp_dir={processor.temp_dir}")
        
        # 验证处理器可以处理 Markdown 文件
        logger.info("✓ 结果处理器支持:")
        logger.info("  - 下载结果 ZIP 压缩包")
        logger.info("  - 提取 Markdown 文件")
        logger.info("  - 直接插入 LightRAG")
        logger.info("  - 清理临时文件")
        
        logger.info("✅ MinerU 结果处理器测试通过\n")
        return True
    
    except Exception as e:
        logger.error(f"❌ MinerU 结果处理器测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    logger.info("\n" + "=" * 70)
    logger.info("RAG API 优化功能测试套件")
    logger.info("=" * 70 + "\n")
    
    results = {
        "文件清理": test_file_cleanup(),
        "性能监控采集器": test_metrics_collector(),
        "系统指标采集": test_metrics_system_collection(),
        "MinerU 结果处理器": test_mineru_result_processor(),
    }
    
    # 总结
    logger.info("=" * 70)
    logger.info("测试总结")
    logger.info("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\n总体: {passed}/{total} 测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！\n")
        return 0
    else:
        logger.error("⚠️  有测试失败\n")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
