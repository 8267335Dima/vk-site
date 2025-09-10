# backend/app/core/logging.py
import logging
import sys
import structlog

def configure_logging():
    """Настраивает structlog для вывода структурированных JSON логов."""
    
    # Конфигурация для стандартного модуля logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )

    # Цепочка обработчиков для structlog
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors + [
            # Этот обработчик подготавливает данные для рендеринга
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Настраиваем рендерер, который будет выводить логи в формате JSON
    # Это ключевой шаг для интеграции с Loki/Grafana
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        # Эти обработчики будут применены только к записям, созданным через structlog
        foreign_pre_chain=shared_processors,
    )

    # Применяем наш JSON-форматтер к корневому логгеру
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Пример использования:
    # log = structlog.get_logger(__name__)
    # log.info("logging_configured", detail="Structured logging is ready.")