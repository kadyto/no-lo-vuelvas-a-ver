# syntax=docker/dockerfile:1
FROM python:3.12.14-slim-bookworm
ARG VERSION=development
ARG SOURCE
ARG REVISION
LABEL org.opencontainers.image.title="No lo vuelvas a ver" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.source=$SOURCE \
      org.opencontainers.image.revision=$REVISION \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data PATH="/app/.venv/bin:$PATH"
WORKDIR /app
ARG SOURCE_DIR=.
COPY ${SOURCE_DIR}/requirements.lock ./
# The optional secret extends build trust in managed environments; it is never copied into a layer.
RUN --mount=type=secret,id=proxy_ca \
    python -m venv .venv && \
    if [ -f /run/secrets/proxy_ca ]; then PIP_CERT=/run/secrets/proxy_ca .venv/bin/pip install --no-cache-dir --require-hashes -r requirements.lock; \
    else .venv/bin/pip install --no-cache-dir --require-hashes -r requirements.lock; fi
COPY ${SOURCE_DIR}/app ./app
COPY ${SOURCE_DIR}/migrations ./migrations
COPY ${SOURCE_DIR}/alembic.ini ${SOURCE_DIR}/LICENSE ./
RUN mkdir /data && chown 10001:10001 /data && chmod -R a+rX /app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers", "--no-access-log"]
