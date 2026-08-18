FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN sed -i 's|http://deb.debian.org/debian|http://mirrors.tencentyun.com/debian|g; \
            s|http://deb.debian.org/debian-security|http://mirrors.tencentyun.com/debian-security|g' \
            /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --default-timeout=300 -r /app/requirements.txt

COPY app /app/app
COPY web /app/web
COPY scripts /app/scripts
COPY run.py /app/run.py

RUN mkdir -p /app/data/uploads /app/data/exports /app/logs

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
