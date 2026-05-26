FROM golang:1.25-alpine3.23 AS builder

WORKDIR /app

COPY . .

RUN go mod tidy

RUN go build -o evaluation-service .


FROM alpine:3.23

WORKDIR /app

COPY --from=builder /app/evaluation-service .

EXPOSE 8004

ENTRYPOINT ["./evaluation-service"]

