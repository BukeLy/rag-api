"""
统一日志配置模块

使用 loguru 作为唯一的日志实例，拦截所有标准 logging 日志。

特性：
- 控制台彩色输出（便于开发调试）
- 文件按日期自动轮转（logs/app_{date}.log）
- 自动清理旧日志（默认保留 30 天）
- 拦截第三方库日志（FastAPI、uvicorn、lightrag 等）
- 通过环境变量配置日志级别
"""

import os
import sys
import logging
from pathlib import Path
from loguru import logger

# ===== 配置参数 =====

# 日志级别（从环境变量读取，默认 INFO）
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# 日志保留天数（从环境变量读取，默认 30 天）
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))

# 日志目录
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 日志格式
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{name}:{function}:{line} - "
    "{message}"
)


# ===== Loguru 配置 =====

# 移除默认的 handler
logger.remove()

# 添加控制台输出（彩色格式）
logger.add(
    sys.stderr,
    format=CONSOLE_FORMAT,
    level=LOG_LEVEL,
    colorize=True,
    backtrace=True,
    diagnose=True,
)

# 添加文件输出（每日轮转）
logger.add(
    LOG_DIR / "app_{time:YYYY-MM-DD}.log",
    format=FILE_FORMAT,
    level=LOG_LEVEL,
    rotation="00:00",  # 每天午夜轮转
    retention=f"{LOG_RETENTION_DAYS} days",  # 保留天数
    compression="zip",  # 压缩旧日志
    encoding="utf-8",
    backtrace=True,
    diagnose=True,
)

logger.info(f"日志系统已初始化：级别={LOG_LEVEL}, 保留={LOG_RETENTION_DAYS}天")


# ===== 拦截标准 logging =====

class InterceptHandler(logging.Handler):
    """
    拦截标准 logging 日志，转发到 loguru
    
    这样可以捕获所有第三方库（FastAPI、uvicorn、lightrag 等）的日志
    """
    
    def emit(self, record: logging.LogRecord) -> None:
        # 获取对应的 loguru 级别
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        
        # 找到调用者的帧（跳过日志框架的帧）
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        
        # 转发到 loguru
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# 配置标准 logging，使用拦截器
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

# 为所有已存在的 logger 添加拦截器
for name in logging.root.manager.loggerDict.keys():
    logging.getLogger(name).handlers = []
    logging.getLogger(name).propagate = True

logger.success("✓ 标准 logging 拦截已启用（第三方库日志将被统一管理）")


# ===== 导出 =====

__all__ = ["logger"]

