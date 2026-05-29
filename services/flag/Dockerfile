FROM python:3.11-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /wheels /wheels

RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels


COPY app.py .

EXPOSE 8002

CMD ["gunicorn", "--bind", "0.0.0.0:8002", "app:app"]
