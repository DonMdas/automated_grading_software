#!/bin/bash

# Test script for AI Grading Software deployment
# This script validates the deployment and tests all services

set -e

# Configuration
APP_URL="http://localhost:8000"
GRADING_URL="http://localhost:8001"
NGINX_URL="http://localhost"

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

# Test function
test_endpoint() {
    local url=$1
    local service=$2
    local expected_code=${3:-200}
    
    log "Testing $service: $url"
    
    if response=$(curl -s -o /dev/null -w "%{http_code}" "$url"); then
        if [ "$response" -eq "$expected_code" ]; then
            log "✅ $service is responding correctly (HTTP $response)"
            return 0
        else
            error "❌ $service returned HTTP $response, expected $expected_code"
            return 1
        fi
    else
        error "❌ $service is not responding"
        return 1
    fi
}

# Test Docker containers
test_containers() {
    log "Testing Docker containers..."
    
    # Check if containers are running
    if docker-compose ps | grep -q "Up"; then
        log "✅ Docker containers are running"
    else
        error "❌ Docker containers are not running"
        return 1
    fi
    
    # Check individual services
    local services=("ai-grading-app" "grading-service" "nginx")
    for service in "${services[@]}"; do
        if docker-compose ps "$service" | grep -q "Up"; then
            log "✅ $service container is running"
        else
            error "❌ $service container is not running"
            return 1
        fi
    done
}

# Test network connectivity
test_network() {
    log "Testing network connectivity..."
    
    # Test internal network
    if docker network ls | grep -q "ai-grading-network"; then
        log "✅ Docker network exists"
    else
        error "❌ Docker network does not exist"
        return 1
    fi
}

# Test database connectivity
test_databases() {
    log "Testing database connectivity..."
    
    # Test PostgreSQL connection
    if docker-compose exec -T ai-grading-app python -c "
import psycopg2
from config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USERNAME, POSTGRES_PASSWORD, POSTGRES_DATABASE
try:
    conn = psycopg2.connect(
        host='$POSTGRES_HOST',
        port='$POSTGRES_PORT',
        user='$POSTGRES_USERNAME',
        password='$POSTGRES_PASSWORD',
        database='$POSTGRES_DATABASE'
    )
    conn.close()
    print('PostgreSQL connection successful')
except Exception as e:
    print(f'PostgreSQL connection failed: {e}')
    exit(1)
" 2>/dev/null; then
        log "✅ PostgreSQL connection successful"
    else
        warning "⚠️ PostgreSQL connection test failed"
    fi
    
    # Test MongoDB connection
    if docker-compose exec -T ai-grading-app python -c "
import pymongo
from config import MONGODB_HOST, MONGODB_PORT, MONGODB_DATABASE
try:
    client = pymongo.MongoClient('$MONGODB_HOST', $MONGODB_PORT)
    db = client['$MONGODB_DATABASE']
    db.command('ping')
    print('MongoDB connection successful')
except Exception as e:
    print(f'MongoDB connection failed: {e}')
    exit(1)
" 2>/dev/null; then
        log "✅ MongoDB connection successful"
    else
        warning "⚠️ MongoDB connection test failed"
    fi
}

# Test file permissions
test_permissions() {
    log "Testing file permissions..."
    
    # Check if server_data directory is writable
    if docker-compose exec -T ai-grading-app test -w /app/server_data; then
        log "✅ Server data directory is writable"
    else
        error "❌ Server data directory is not writable"
        return 1
    fi
}

# Test environment variables
test_environment() {
    log "Testing environment variables..."
    
    # Check if critical environment variables are set
    local required_vars=("POSTGRES_HOST" "MONGODB_HOST" "SECRET_KEY" "GOOGLE_CLIENT_ID")
    
    for var in "${required_vars[@]}"; do
        if docker-compose exec -T ai-grading-app sh -c "[ -n \"\$$var\" ]"; then
            log "✅ $var is set"
        else
            error "❌ $var is not set"
            return 1
        fi
    done
}

# Main test function
main() {
    log "Starting AI Grading Software deployment tests..."
    
    local failed_tests=0
    
    # Test Docker containers
    if ! test_containers; then
        ((failed_tests++))
    fi
    
    # Test network
    if ! test_network; then
        ((failed_tests++))
    fi
    
    # Test service endpoints
    if ! test_endpoint "$APP_URL/health" "Main Application"; then
        ((failed_tests++))
    fi
    
    if ! test_endpoint "$GRADING_URL/health" "Grading Service"; then
        ((failed_tests++))
    fi
    
    if ! test_endpoint "$NGINX_URL/health" "Nginx Proxy"; then
        ((failed_tests++))
    fi
    
    # Test database connectivity
    if ! test_databases; then
        ((failed_tests++))
    fi
    
    # Test file permissions
    if ! test_permissions; then
        ((failed_tests++))
    fi
    
    # Test environment variables
    if ! test_environment; then
        ((failed_tests++))
    fi
    
    # Test API endpoints
    log "Testing API endpoints..."
    if ! test_endpoint "$APP_URL/" "Main Page"; then
        ((failed_tests++))
    fi
    
    if ! test_endpoint "$APP_URL/api/auth/status" "Auth Status" 401; then
        ((failed_tests++))
    fi
    
    # Summary
    log "Test Summary:"
    if [ "$failed_tests" -eq 0 ]; then
        log "✅ All tests passed successfully!"
        log "🚀 Deployment is ready for use"
        return 0
    else
        error "❌ $failed_tests test(s) failed"
        error "🔧 Please check the deployment and fix any issues"
        return 1
    fi
}

# Run tests
main "$@"
