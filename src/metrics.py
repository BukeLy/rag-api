"""
性能监控模块

功能：
- 采集系统性能指标（CPU、内存、磁盘、网络）
- 记录 API 性能指标（响应时间、吞吐量、错误率）
- 记录文档处理性能指标（解析时间、插入时间、质量指标）
- 基于阈值的性能告警
- 定期生成性能报告
"""

import asyncio
import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psutil

from src.config import get_config
from src.logger import logger


@dataclass
class PerformanceMetric:
    """单个性能指标"""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    unit: str = ""
    threshold: float | None = None  # 告警阈值


@dataclass
class APIMetrics:
    """API 性能指标"""
    endpoint: str
    method: str
    response_times: list[float] = field(default_factory=list)
    status_codes: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    request_count: int = 0
    error_count: int = 0

    @property
    def average_response_time(self) -> float:
        """平均响应时间"""
        return statistics.mean(self.response_times) if self.response_times else 0.0

    @property
    def p95_response_time(self) -> float:
        """95分位数响应时间"""
        if len(self.response_times) < 20:
            return self.average_response_time
        return statistics.quantiles(self.response_times, n=20)[18]

    @property
    def error_rate(self) -> float:
        """错误率"""
        return self.error_count / self.request_count if self.request_count > 0 else 0.0

    @property
    def throughput(self) -> float:
        """吞吐量（请求/秒）"""
        return self.request_count / 60 if self.request_count > 0 else 0.0


@dataclass
class DocumentMetrics:
    """文档处理性能指标"""
    doc_id: str
    filename: str
    file_size: int
    parser: str
    parse_time: float | None = None
    insert_time: float | None = None
    total_time: float | None = None
    entity_count: int = 0
    relation_count: int = 0
    chunk_count: int = 0
    status: str = "pending"  # pending, processing, completed, failed
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """性能指标采集器"""

    def __init__(self):
        self.api_metrics: dict[str, APIMetrics] = {}
        self.doc_metrics: list[DocumentMetrics] = []
        self.system_metrics: dict[str, PerformanceMetric] = {}
        self.alerts: list[dict[str, Any]] = []
        self.lock = threading.Lock()

    def record_api_call(self, endpoint: str, method: str,
                       response_time: float, status_code: int):
        """记录 API 调用"""
        key = f"{method} {endpoint}"

        with self.lock:
            if key not in self.api_metrics:
                self.api_metrics[key] = APIMetrics(endpoint=endpoint, method=method)

            metrics = self.api_metrics[key]
            metrics.response_times.append(response_time)
            metrics.status_codes[status_code] += 1
            metrics.request_count += 1

            # 限制历史数据大小
            cache_size = get_config().metrics.response_times_cache_size
            if len(metrics.response_times) > cache_size * 2:
                metrics.response_times = metrics.response_times[-cache_size:]

            if status_code >= 400:
                metrics.error_count += 1

                # 检查是否触发告警
                if metrics.error_rate > 0.1:  # 错误率 > 10%
                    self._add_alert(
                        "HIGH_ERROR_RATE",
                        f"API {key} error rate: {metrics.error_rate:.1%}",
                        severity="warning"
                    )

    def record_document(self, doc_metrics: DocumentMetrics):
        """记录文档处理指标"""
        with self.lock:
            self.doc_metrics.append(doc_metrics)

            # 限制历史数据大小
            cache_size = get_config().metrics.doc_metrics_cache_size
            if len(self.doc_metrics) > cache_size * 2:
                self.doc_metrics = self.doc_metrics[-cache_size:]

            # 检查处理时间告警
            if doc_metrics.total_time and doc_metrics.total_time > 300:  # > 5 分钟
                self._add_alert(
                    "SLOW_DOCUMENT_PROCESSING",
                    f"Document {doc_metrics.filename} processing took {doc_metrics.total_time:.1f}s",
                    severity="warning"
                )

            # 检查处理失败
            if doc_metrics.status == "failed":
                self._add_alert(
                    "DOCUMENT_PROCESSING_FAILED",
                    f"Document {doc_metrics.filename} processing failed: {doc_metrics.error}",
                    severity="error"
                )

    def record_system_metric(self, name: str, value: float, unit: str = "",
                            threshold: float | None = None):
        """记录系统指标"""
        metric = PerformanceMetric(name=name, value=value, unit=unit, threshold=threshold)

        with self.lock:
            self.system_metrics[name] = metric

            # 检查阈值告警
            if threshold and value > threshold:
                self._add_alert(
                    f"HIGH_{name.upper()}",
                    f"{name}: {value:.2f}{unit} (threshold: {threshold:.2f})",
                    severity="warning"
                )

    def _add_alert(self, alert_type: str, message: str, severity: str = "info"):
        """添加告警"""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }

        with self.lock:
            self.alerts.append(alert)
            cache_size = get_config().metrics.alerts_cache_size
            if len(self.alerts) > cache_size * 2:
                self.alerts = self.alerts[-cache_size:]

        logger.warning(f"[ALERT] {alert_type}: {message}")

    def get_api_summary(self) -> dict[str, Any]:
        """获取 API 性能摘要"""
        with self.lock:
            summary = {}
            for key, metrics in self.api_metrics.items():
                summary[key] = {
                    "request_count": metrics.request_count,
                    "error_count": metrics.error_count,
                    "error_rate": f"{metrics.error_rate:.2%}",
                    "avg_response_time_ms": f"{metrics.average_response_time * 1000:.2f}",
                    "p95_response_time_ms": f"{metrics.p95_response_time * 1000:.2f}",
                    "throughput_req_per_sec": f"{metrics.throughput:.2f}"
                }
            return summary

    def get_document_summary(self) -> dict[str, Any]:
        """获取文档处理性能摘要"""
        with self.lock:
            if not self.doc_metrics:
                return {"total": 0, "summary": {}}

            completed = [m for m in self.doc_metrics if m.status == "completed"]
            failed = [m for m in self.doc_metrics if m.status == "failed"]

            parse_times = [m.parse_time for m in completed if m.parse_time]
            insert_times = [m.insert_time for m in completed if m.insert_time]
            total_times = [m.total_time for m in completed if m.total_time]

            return {
                "total_documents": len(self.doc_metrics),
                "completed": len(completed),
                "failed": len(failed),
                "pending": len([m for m in self.doc_metrics if m.status == "pending"]),
                "processing": len([m for m in self.doc_metrics if m.status == "processing"]),
                "success_rate": f"{len(completed) / len(self.doc_metrics):.2%}" if self.doc_metrics else "0%",
                "avg_parse_time_s": f"{statistics.mean(parse_times):.2f}" if parse_times else "N/A",
                "avg_insert_time_s": f"{statistics.mean(insert_times):.2f}" if insert_times else "N/A",
                "avg_total_time_s": f"{statistics.mean(total_times):.2f}" if total_times else "N/A",
            }

    def get_recent_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取最近的告警"""
        with self.lock:
            return self.alerts[-limit:]

    def collect_system_metrics(self):
        """采集系统性能指标"""
        try:
            # CPU 使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_system_metric("cpu_usage", cpu_percent, unit="%", threshold=80.0)

            # 内存使用率
            memory = psutil.virtual_memory()
            self.record_system_metric("memory_usage", memory.percent, unit="%", threshold=85.0)

            # 磁盘使用率
            disk = psutil.disk_usage('/')
            self.record_system_metric("disk_usage", disk.percent, unit="%", threshold=90.0)

            # 网络 I/O
            net_io = psutil.net_io_counters()
            self.record_system_metric("network_bytes_sent", net_io.bytes_sent / (1024 * 1024), unit="MB")
            self.record_system_metric("network_bytes_recv", net_io.bytes_recv / (1024 * 1024), unit="MB")

        except Exception as e:
            logger.warning(f"Failed to collect system metrics: {e}")

    def start_system_monitoring(self, interval: int = 60):
        """启动系统监控线程"""
        def monitoring_loop():
            while True:
                try:
                    asyncio.run(asyncio.sleep(interval))
                    self.collect_system_metrics()
                except Exception as e:
                    logger.error(f"Error in system monitoring: {e}")
                except asyncio.CancelledError:
                    break

        monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitor_thread.name = "MetricsMonitorThread"
        monitor_thread.start()
        logger.info(f"System metrics monitoring started: interval={interval}s")


# 全局指标采集器实例
_collector = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标采集器"""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


# 装饰器：记录 API 性能
def track_api_performance(endpoint: str, method: str):
    """装饰器：自动记录 API 性能指标"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = 200  # 默认状态码

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception:
                status_code = 500
                raise
            finally:
                response_time = time.time() - start_time
                collector = get_metrics_collector()
                collector.record_api_call(endpoint, method, response_time, status_code)

        return wrapper
    return decorator
