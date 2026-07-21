import logging
import os

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter as GRPCLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as GRPCMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCSpanExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter as HTTPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as HTTPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def _strip_scheme(endpoint):
    for prefix in ("http://", "https://"):
        if endpoint.startswith(prefix):
            return endpoint[len(prefix):]
    return endpoint


def init_telemetry(service_name):
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        endpoint = "http://otel-collector.monitoring.svc.cluster.local:4317"

    resource = Resource(attributes={
        "service.name": service_name
    })

    if ":4318" in endpoint:
        # OTLP via HTTP: cada sinal tem seu próprio path
        base = endpoint.rstrip("/")
        span_exporter = HTTPSpanExporter(endpoint=f"{base}/v1/traces")
        metric_exporter = HTTPMetricExporter(endpoint=f"{base}/v1/metrics")
        log_exporter = HTTPLogExporter(endpoint=f"{base}/v1/logs")
    else:
        grpc_endpoint = _strip_scheme(endpoint)
        span_exporter = GRPCSpanExporter(endpoint=grpc_endpoint, insecure=True)
        metric_exporter = GRPCMetricExporter(endpoint=grpc_endpoint, insecure=True)
        log_exporter = GRPCLogExporter(endpoint=grpc_endpoint, insecure=True)

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Métricas — com um MeterProvider ativo, o FlaskInstrumentor emite
    # http.server.duration, usada no alerta e no dashboard do Grafana
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(metric_exporter, export_interval_millis=15000)
        ],
    )
    metrics.set_meter_provider(meter_provider)

    # Logs da aplicação enviados ao OTel Collector, que roteia para o Loki
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(logger_provider)
    logging.getLogger().addHandler(
        LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    )


def instrument_app(app, service_name):
    try:
        init_telemetry(service_name)
        FlaskInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()
    except Exception as e:
        print(f"Warning: Failed to initialize OpenTelemetry: {e}")
