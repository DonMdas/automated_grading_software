# Multi-stage Dockerfile for AI Grading Software
FROM python:3.10-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    wget \
    git \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching (before creating user)
COPY requirements.txt .

# Install Python dependencies as root (more reliable)
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user and change ownership
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PATH="/home/appuser/.local/bin:${PATH}"

# Set default environment variables for the application (these will be overridden by docker-compose)
ENV SECRET_KEY="GVjxDlp2mC_Av6teOEFxYVYhJCF2HwDkrLfb5xsXCiM"
ENV POSTGRES_USERNAME="postgres"
ENV POSTGRES_PASSWORD="root"
ENV POSTGRES_DATABASE="grading_system_pg"
ENV POSTGRES_HOST="postgres"
ENV POSTGRES_PORT="5432"
ENV MONGODB_HOST="mongodb"
ENV MONGODB_PORT="27017"
ENV MONGODB_DATABASE="grading_system_mongo"
ENV GOOGLE_CLIENT_ID="placeholder_client_id"
ENV GOOGLE_CLIENT_SECRET="placeholder_client_secret"
ENV GOOGLE_REDIRECT_URI="http://localhost:8000/auth/callback"
ENV ENVIRONMENT="development"

# Copy application code and necessary files
COPY --chown=appuser:appuser . .

# Ensure all required directories exist
RUN mkdir -p server_data static templates training_data ssl && \
    mkdir -p api services ocr_code && \
    chmod -R 755 server_data static templates

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
