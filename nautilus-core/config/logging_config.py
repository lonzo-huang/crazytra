"""
Nautilus 核心日志配置

统一的日志配置，遵循 LOGGING_SPEC.md 规范。
"""

import logging
import os
import sys
from pathlib import Path

import structlog


def configure_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
    json_format: bool = False,
) -> structlog.BoundLogger:
    """
    配置结构化日志
    
    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径（可选）
        json_format: 是否使用 JSON 格式（生产环境推荐）
    
    Returns:
        配置好的 logger
    """
    # 转换日志级别
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 配置标准 logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )
    
    # 如果指定了日志文件，添加文件处理器
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,  # 100 MB
            backupCount=10,
        )
        file_handler.setLevel(numeric_level)
        logging.root.addHandler(file_handler)
    
    # 配置 structlog 处理器
    processors = [
        # 添加时间戳（UTC）
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # 添加日志级别
        structlog.processors.add_log_level,
        # 添加调用者信息（仅 DEBUG）
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ) if log_level == "DEBUG" else lambda _, __, event_dict: event_dict,
        # 添加堆栈信息（仅错误）
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # 选择渲染器
    if json_format:
        # 生产环境：JSON 格式
        processors.append(structlog.processors.JSONRenderer())
    else:
        # 开发环境：彩色控制台输出
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # 配置 structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger()


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    获取 logger 实例
    
    Args:
        name: logger 名称（可选）
    
    Returns:
        structlog.BoundLogger
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


# 环境变量配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", None)
ENV = os.getenv("ENV", "development")

# 生产环境使用 JSON 格式
JSON_FORMAT = ENV == "production"

# 默认 logger
logger = configure_logging(
    log_level=LOG_LEVEL,
    log_file=LOG_FILE,
    json_format=JSON_FORMAT,
)


# 使用示例
if __name__ == "__main__":
    log = get_logger("example")
    
    # 不同级别的日志
    log.debug("debug_message", variable="value")
    log.info("info_message", count=42)
    log.warning("warning_message", retry_attempt=3)
    log.error("error_message", error="Something went wrong")
    
    # 结构化日志
    log.info(
        "order_submitted",
        order_id="ORD-001",
        symbol="BTC-USDT",
        side="BUY",
        quantity="0.01",
        price="67840.50",
    )
    
    # 异常日志
    try:
        raise ValueError("Test error")
    except Exception as e:
        log.error(
            "operation_failed",
            operation="test",
            error=str(e),
            exc_info=True,
        )
