FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_ENV=production \
    PORT=8000

WORKDIR /app

# Runtime/system deps:
# - libgomp1: needed by xgboost/ML stack
# - build-essential: safe fallback for wheels that need local build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt

COPY backend /app/backend
COPY ml_data /app/ml_data

# Ensure writable dirs for generated ML artifacts inside container
RUN mkdir -p /app/ml_data/data/raw \
    /app/ml_data/data/processed \
    /app/ml_data/data/predicted \
    /app/ml_data/models \
    /app/backend/staticfiles

WORKDIR /app/backend

CMD sh -c "ML_ROOT=${ML_DATA_DIR:-/app/ml_data} && \
           mkdir -p ${ML_ROOT}/data/raw ${ML_ROOT}/data/processed ${ML_ROOT}/data/predicted ${ML_ROOT}/models && \
           python manage.py migrate --noinput && \
           python manage.py collectstatic --noinput && \
           gunicorn core.wsgi:application \
             --bind 0.0.0.0:${PORT:-8000} \
             --workers 2 \
             --threads 4 \
             --timeout 300"
