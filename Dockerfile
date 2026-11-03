# syntax=docker/dockerfile:1
FROM python:3.14-slim AS builder

WORKDIR /build
COPY pyproject.toml .
COPY keelway keelway/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

FROM python:3.14-slim AS runtime

# Create unprivileged security user
RUN groupadd -g 10001 keelway && \
    useradd -u 10001 -g keelway -s /bin/bash -m keelway && \
    apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY keelway keelway/

USER 10001:10001

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

ENTRYPOINT ["python3", "-m", "keelway.cli.main", "serve", "--host", "0.0.0.0", "--port", "8000"]
