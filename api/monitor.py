"""
性能监控 API 路由

提供系统性能指标、API 性能、文档处理性能和告警信息的接口
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from src.metrics import get_metrics_collector

router = APIRouter(prefix="/monitor", tags=["monitoring"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    健康检查端点
    
    返回系统整体健康状态
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
        "system_metrics": {
            "cpu_usage_percent": f"{cpu_usage.value:.1f}" if cpu_usage else "N/A",
            "memory_usage_percent": f"{memory_usage.value:.1f}" if memory_usage else "N/A",
            "disk_usage_percent": f"{disk_usage.value:.1f}" if disk_usage else "N/A",
        },
        "issues": issues,
        "recent_alerts_count": len(recent_alerts),
        "critical_alerts_count": len(critical_alerts),
    }


@router.get("/api-metrics")
async def get_api_metrics() -> Dict[str, Any]:
    """
    获取 API 性能指标
    
    返回所有 API 端点的性能统计（响应时间、吞吐量、错误率等）
    """
    collector = get_metrics_collector()
    return collector.get_api_summary()


@router.get("/document-metrics")
async def get_document_metrics() -> Dict[str, Any]:
    """
    获取文档处理性能指标
    
    返回文档处理的性能统计（解析时间、插入时间、成功率等）
    """
    collector = get_metrics_collector()
    return collector.get_document_summary()


@router.get("/system-metrics")
async def get_system_metrics() -> Dict[str, Any]:
    """
    获取系统性能指标
    
    返回 CPU、内存、磁盘和网络等系统指标
    """
    collector = get_metrics_collector()
    
    metrics = {}
    for name, metric in collector.system_metrics.items():
        metrics[name] = {
            "value": f"{metric.value:.2f}",
            "unit": metric.unit,
            "threshold": f"{metric.threshold:.2f}" if metric.threshold else "N/A",
            "timestamp": metric.timestamp.isoformat(),
        }
    
    return metrics


@router.get("/alerts")
async def get_alerts(limit: int = 50, severity: str = None) -> Dict[str, Any]:
    """
    获取性能告警信息
    
    参数：
    - `limit`: 返回最近 N 条告警（默认 50）
    - `severity`: 筛选特定严重程度 ('info', 'warning', 'critical')
    
    返回值：
    ```json
    {
        "total_alerts": 150,
        "recent_alerts": [
            {
                "type": "HIGH_CPU_USAGE",
                "message": "CPU usage high",
                "severity": "warning",
                "timestamp": "2024-01-01T12:00:00"
            }
        ]
    }
    ```
    """
    collector = get_metrics_collector()
    alerts = collector.get_recent_alerts(limit=limit)
    
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity]
    
    return {
        "total_alerts": len(collector.alerts),
        "recent_alerts": alerts,
        "severity_filter": severity or "all"
    }


@router.get("/report")
async def get_performance_report() -> Dict[str, Any]:
    """
    获取完整的性能报告
    
    包含系统、API 和文档处理的综合性能数据
    """
    collector = get_metrics_collector()
    
    return {
        "timestamp": collector.system_metrics.get("cpu_usage").timestamp.isoformat()
                    if collector.system_metrics.get("cpu_usage") else None,
        "system": {
            "cpu_usage_percent": f"{collector.system_metrics.get('cpu_usage').value:.1f}"
                               if collector.system_metrics.get("cpu_usage") else "N/A",
            "memory_usage_percent": f"{collector.system_metrics.get('memory_usage').value:.1f}"
                                   if collector.system_metrics.get("memory_usage") else "N/A",
            "disk_usage_percent": f"{collector.system_metrics.get('disk_usage').value:.1f}"
                                 if collector.system_metrics.get("disk_usage") else "N/A",
        },
        "api_performance": collector.get_api_summary(),
        "document_processing": collector.get_document_summary(),
        "alerts": {
            "total": len(collector.alerts),
            "recent": collector.get_recent_alerts(limit=10),
        },
    }


@router.post("/clear-alerts")
async def clear_alerts() -> Dict[str, str]:
    """
    清空所有告警记录
    """
    collector = get_metrics_collector()
    alert_count = len(collector.alerts)
    collector.alerts.clear()
    
    return {
        "message": f"Cleared {alert_count} alerts",
        "status": "success"
    }
