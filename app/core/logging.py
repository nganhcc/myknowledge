import logging
import sys

import structlog


def setup_logging(json_logs: bool = False) -> None:
    """Cấu hình structlog kết hợp với thư viện standard logging của Python."""
    
    # các processor xử lý dữ liệu log qua từng bước (pipeline)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,  # Nạp context ngầm (như request_id, user_id)
        structlog.stdlib.add_logger_name,         # Thêm tên logger
        structlog.stdlib.add_log_level,           # Thêm log level (info, error, ...)
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"), # Tự động thêm timestamp dạng ISO
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,     # Format exception traceback nếu có
    ]

    render_processor: structlog.types.Processor
    if json_logs:
        # Trong Production: Xuất định dạng JSON hoàn chỉnh (phù hợp cho Datadog, ELK, Vector)
        render_processor = structlog.processors.JSONRenderer()
    else:
        # Trong Local Dev: Xuất định dạng màu sắc, dễ đọc trực quan trên Terminal
        render_processor = structlog.dev.ConsoleRenderer(colors=True)

    # 1. Cấu hình structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 2. Cấu hình Standard Logging của Python để format đồng bộ
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            render_processor,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)