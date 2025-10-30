"""
性能监控 API 路由（简化版）

提供系统健康检查和统一的性能指标接口
"""

from fastapi import APIRouter
from typing import Dict, Any

from src.metrics import get_metrics_collector

router = APIRouter(prefix="/monitor", tags=["monitoring"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    健康检查端点（简化版）

    返回系统整体健康状态和关键指标
    """
    collector = get_metrics_collector()

    # 获取最新的系统指标
    system_metrics = collector.system_metrics

    cpu_usage = system_metrics.get("cpu_usage")
    memory_usage = system_metrics.get("memory_usage")
    disk_usage = system_metrics.get("disk_usage")

    # 判断整体健康状态
    status = "healthy"
    issues = []

    if cpu_usage and cpu_usage.value > 85:
        issues.append(f"CPU usage high: {cpu_usage.value:.1f}%")
        status = "warning" if status == "healthy" else status

    if memory_usage and memory_usage.value > 90:
        issues.append(f"Memory usage high: {memory_usage.value:.1f}%")
        status = "warning" if status == "healthy" else status

    if disk_usage and disk_usage.value > 95:
        issues.append(f"Disk usage critical: {disk_usage.value:.1f}%")
        status = "critical"

    recent_alerts = collector.get_recent_alerts(limit=5)
    critical_alerts = [a for a in recent_alerts if a.get("severity") == "critical"]
    if critical_alerts:
        status = "critical"

    return {
        "status": status,
        "timestamp": collector.system_metrics.get("cpu_usage").timestamp.isoformat()
                    if cpu_usage else None,
        "system": {
            "cpu_usage_percent": f"{cpu_usage.value:.1f}" if cpu_usage else "N/A",
            "memory_usage_percent": f"{memory_usage.value:.1f}" if memory_usage else "N/A",
            "disk_usage_percent": f"{disk_usage.value:.1f}" if disk_usage else "N/A",
        },
        "issues": issues,
        "recent_alerts_count": len(recent_alerts),
        "critical_alerts_count": len(critical_alerts),
    }


@router.get("/metrics")
async def get_all_metrics(
    alerts_limit: int = 10,
    severity: str = None
) -> Dict[str, Any]:
    """
    获取所有性能指标（统一端点）

    **包含内容**：
    - 系统指标（CPU、内存、磁盘）
    - API 性能指标（响应时间、吞吐量、错误率）
    - 文档处理指标（解析时间、成功率）
    - 告警信息（可筛选严重程度）

    **参数**：
    - `alerts_limit`: 返回最近 N 条告警（默认 10）
    - `severity`: 筛选特定严重程度（'info', 'warning', 'critical'）

    **示例响应**：
    ```json
    {
        "timestamp": "2025-10-30T...",
        "system": {
            "cpu_usage": {"value": 45.2, "unit": "%", "threshold": 80},
            "memory_usage": {"value": 68.5, "unit": "%", "threshold": 85},
            "disk_usage": {"value": 32.1, "unit": "%", "threshold": 90}
        },
        "api_performance": {
            "/query": {
                "avg_response_time": 8.5,
                "total_requests": 120,
                "error_count": 2,
                "error_rate": 0.017
            }
        },
        "document_processing": {
            "total_processed": 50,
            "avg_parse_time": 15.2,
            "avg_insert_time": 12.8,
            "success_rate": 0.96
        },
        "alerts": {
            "total": 25,
            "recent": [
                {"type": "HIGH_CPU", "severity": "warning", "timestamp": "..."}
            ]
        }
    }
    ```
    """
    collector = get_metrics_collector()

    # 1. 系统指标
    system_data = {}
    for name, metric in collector.system_metrics.items():
        system_data[name] = {
            "value": round(metric.value, 2),
            "unit": metric.unit,
            "threshold": round(metric.threshold, 2) if metric.threshold else None,
            "timestamp": metric.timestamp.isoformat(),
        }

    # 2. API 性能指标
    api_performance = collector.get_api_summary()

    # 3. 文档处理指标
    document_processing = collector.get_document_summary()

    # 4. 告警信息
    all_alerts = collector.get_recent_alerts(limit=alerts_limit * 2)  # 先获取更多，再筛选

    # 按严重程度筛选
    if severity:
        filtered_alerts = [a for a in all_alerts if a.get("severity") == severity]
    else:
        filtered_alerts = all_alerts

    # 限制数量
    recent_alerts = filtered_alerts[:alerts_limit]

    return {
        "timestamp": system_data.get("cpu_usage", {}).get("timestamp"),
        "system": system_data,
        "api_performance": api_performance,
        "document_processing": document_processing,
        "alerts": {
            "total": len(collector.alerts),
            "returned": len(recent_alerts),
            "severity_filter": severity or "all",
            "recent": recent_alerts,
        }
    }
