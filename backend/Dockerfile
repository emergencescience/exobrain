FROM python:3.12-slim

WORKDIR /app

# Install system deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Ensure data dir exists (for SQLite / RAG index)
RUN mkdir -p app/data

# RAG index is committed to the repo, included in image
# mpc_rag.json at app/data/mpc_rag.json

EXPOSE 8080

# Default: SQLite (offline mode). Set EXOBRAIN_STORAGE=postgres on Railway.
ENV EXOBRAIN_STORAGE=sqlite
ENV EXOBRAIN_RAG_INDEX=app/data/mpc_rag.json

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
