FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend files
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/

# Ensure data dir exists
RUN mkdir -p app/data

EXPOSE 8080

ENV EXOBRAIN_STORAGE=sqlite
ENV EXOBRAIN_RAG_INDEX=app/data/mpc_rag.json

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
