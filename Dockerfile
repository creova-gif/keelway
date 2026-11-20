# syntax=docker/dockerfile:1
FROM python:3.15-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md cli.py ./
COPY core core/
COPY keelway keelway/
COPY research research/
COPY evaluations evaluations/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

FROM python:3.15-slim AS runtime

RUN groupadd -g 10001 keelway && \
    useradd -u 10001 -g keelway -s /bin/bash -m keelway && \
    apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /app /data/.keelway && \
    chown -R 10001:10001 /app /data

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=10001:10001 pyproject.toml README.md cli.py ./
COPY --chown=10001:10001 core core/
COPY --chown=10001:10001 keelway keelway/
COPY --chown=10001:10001 research research/
COPY --chown=10001:10001 evaluations evaluations/

ENV PYTHONUNBUFFERED=1 \
    HOME=/data \
    KEELWAY_STATE_DIR=/data/.keelway \
    KEELWAY_DB_PATH=/data/keelway_audit.db

VOLUME ["/data"]
EXPOSE 7420 8000
USER 10001:10001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

ENTRYPOINT ["python3", "-m", "keelway.cli.main", "serve", "--host", "0.0.0.0", "--port", "8000"]
