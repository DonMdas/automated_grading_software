#!/bin/bash

# Simple deployment script for AI Grading Software
# This script is adapted for your current environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Check if .env file exists
if [ ! -f .env ]; then
    error ".env file not found! Please create it from .env.example"
    log "Run: cp .env.example .env && nano .env"
    exit 1
fi

# Load environment variables
source .env

# Check required environment variables
log "Checking required environment variables..."
required_vars=("POSTGRES_HOST" "MONGODB_HOST" "SECRET_KEY" "GOOGLE_CLIENT_ID" "GOOGLE_CLIENT_SECRET")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        error "Required environment variable $var is not set in .env file"
        exit 1
    fi
done

log "✅ All required environment variables are set"

# Create necessary directories
log "Creating necessary directories..."
mkdir -p server_data static templates
mkdir -p grading-fastapi/server_data grading-fastapi/Model_files grading-fastapi/Saved_models grading-fastapi/Training_models

# Stop existing containers if running
log "Stopping existing containers..."
docker compose down 2>/dev/null || true

# Pull latest changes if in git repo
if [ -d ".git" ]; then
    log "Pulling latest changes from git..."
    git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || warning "Could not pull from git"
fi

# Build and start containers
log "Building and starting containers..."
docker compose -f docker-compose.dev.yml build --no-cache
docker compose -f docker-compose.dev.yml up -d

# Wait for services to be ready
log "Waiting for services to start..."
sleep 10

# Test services
log "Testing services..."
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        log "✅ Main application is ready"
        break
    fi
    
    retry_count=$((retry_count + 1))
    if [ $retry_count -eq $max_retries ]; then
        error "Main application failed to start after $max_retries attempts"
        docker compose -f docker-compose.dev.yml logs ai-grading-app
        exit 1
    fi
    
    log "Waiting for main application... (attempt $retry_count/$max_retries)"
    sleep 5
done

# Test grading service
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if curl -f http://localhost:8001/health >/dev/null 2>&1; then
        log "✅ Grading service is ready"
        break
    fi
    
    retry_count=$((retry_count + 1))
    if [ $retry_count -eq $max_retries ]; then
        error "Grading service failed to start after $max_retries attempts"
        docker compose -f docker-compose.dev.yml logs grading-service
        exit 1
    fi
    
    log "Waiting for grading service... (attempt $retry_count/$max_retries)"
    sleep 5
done

# Show deployment status
log "Deployment completed successfully! 🚀"
log ""
log "Services are running:"
log "  • Main Application: http://localhost:8000"
log "  • Grading Service: http://localhost:8001"
log ""
log "Container Status:"
docker compose -f docker-compose.dev.yml ps
log ""
log "To view logs:"
log "  docker compose -f docker-compose.dev.yml logs -f"
log ""
log "To stop services:"
log "  docker compose -f docker-compose.dev.yml down"
