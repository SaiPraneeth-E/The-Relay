FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies for PDF parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Download exact arXiv papers and initialize indices
RUN python scripts/download_papers.py && \
    python -m app.main ingest

EXPOSE 8000

CMD ["python", "-m", "app.main", "benchmark", "--scenario", "steady"]

