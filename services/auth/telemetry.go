package main

import (
	"context"
	"log"
	"os"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
)

// InitTelemetry inicializa os providers de traces e métricas com exportadores
// OTLP via gRPC apontando para o OTel Collector. O otelhttp passa a emitir a
// métrica http.server.duration automaticamente com o MeterProvider global.
// Retorna uma função de shutdown que faz flush dos dados pendentes.
func InitTelemetry(serviceName string) (func(context.Context) error, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		// Endpoint padrão dentro do cluster
		endpoint = "otel-collector.monitoring.svc.cluster.local:4317"
	}

	log.Printf("Inicializando telemetria OTel para %s enviando para %s", serviceName, endpoint)

	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceNameKey.String(serviceName),
		),
	)
	if err != nil {
		return nil, err
	}

	traceExporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithInsecure(),
		otlptracegrpc.WithEndpoint(endpoint),
	)
	if err != nil {
		log.Printf("Warning: Não foi possível criar o exportador de traces OTel: %v", err)
		return nil, err
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithResource(res),
	)
	otel.SetTracerProvider(tp)

	metricExporter, err := otlpmetricgrpc.New(ctx,
		otlpmetricgrpc.WithInsecure(),
		otlpmetricgrpc.WithEndpoint(endpoint),
	)
	if err != nil {
		log.Printf("Warning: Não foi possível criar o exportador de métricas OTel: %v", err)
		return nil, err
	}

	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExporter,
			sdkmetric.WithInterval(15*time.Second))),
		sdkmetric.WithResource(res),
	)
	otel.SetMeterProvider(mp)

	shutdown := func(ctx context.Context) error {
		err := tp.Shutdown(ctx)
		if merr := mp.Shutdown(ctx); merr != nil && err == nil {
			err = merr
		}
		return err
	}
	return shutdown, nil
}
