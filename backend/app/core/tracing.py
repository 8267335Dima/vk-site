# backend/app/core/tracing.py
import structlog
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

log = structlog.get_logger(__name__)

def setup_tracing(app: FastAPI):
    """
    Настраивает OpenTelemetry для трассировки запросов.
    В данный момент выводит трейсы в консоль для отладки.
    """
    try:
        # Устанавливаем ресурс (имя сервиса)
        resource = Resource(attributes={"service.name": "social-pulse-backend"})

        # Настраиваем провайдер трассировки
        provider = TracerProvider(resource=resource)

        # Для локальной отладки будем выводить трейсы в консоль
        # В production это заменяется на OTLP Exporter, который отправляет данные
        # в Jaeger, Grafana Tempo, Datadog и т.д.
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)

        # Устанавливаем глобальный провайдер
        trace.set_tracer_provider(provider)

        # Инструментируем FastAPI приложение
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        
        log.info("tracing.setup.success", message="OpenTelemetry tracing configured successfully.")

    except Exception as e:
        log.error("tracing.setup.failed", error=str(e))