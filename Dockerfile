FROM python:3.12-slim

LABEL org.opencontainers.image.title="einkauf" \
      org.opencontainers.image.description="Shopping list companion for OpenTodo" \
      org.opencontainers.image.source="https://github.com/kuenne72/opentodo-shopping-list" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    EINKAUF_DB=/data/einkauf.db

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY seed ./seed
RUN pip install --no-cache-dir . \
 && useradd -r -u 1000 -d /app einkauf \
 && mkdir -p /data && chown einkauf /data

USER einkauf
VOLUME ["/data"]
EXPOSE 8086
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8086/api/status', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8086", "--proxy-headers", "--forwarded-allow-ips", "*"]
