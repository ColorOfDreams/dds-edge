# DriveFocus device-gateway. Chỉ dùng thư viện chuẩn của Python nên ảnh rất nhẹ.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    GATEWAY_HOST=0.0.0.0 \
    GATEWAY_PORT=8099 \
    DATA_DIR=/data

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . \
 && useradd --create-home --uid 10001 app \
 && mkdir -p /data && chown app /data

USER app
VOLUME ["/data"]
EXPOSE 8099
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/health', timeout=3)" || exit 1

CMD ["python", "-m", "drivefocus_cloud.gateway"]
