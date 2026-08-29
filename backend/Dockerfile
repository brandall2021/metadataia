FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# OCR (FASE 8): OCRmyPDF + Tesseract (idiomas iniciales spa/eng/por)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ocrmypdf \
        tesseract-ocr \
        tesseract-ocr-spa \
        tesseract-ocr-eng \
        tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests

# Instalacion editable: el codigo montado por volumen en desarrollo siempre gana
# sobre la copia que quedaria en site-packages (evita imports obsoletos).
RUN pip install --upgrade pip && pip install -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]