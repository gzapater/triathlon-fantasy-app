FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app

EXPOSE 8080

CMD ["sh", "-c", "exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 8 --timeout 120 backend.app:app"]
