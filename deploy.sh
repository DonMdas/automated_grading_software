#!/bin/bash

# Deployment script for AI Grading Software
# This script handles the deployment process on the target server

set -e

# Configuration
PROJECT_DIR="/opt/ai-grading-software"
BACKUP_DIR="/opt/backups/ai-grading-software"
LOG_FILE="/var/log/ai-grading-deployment.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}" | tee -a "$LOG_FILE"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root for security reasons"
   exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create directories if they don't exist
log "Creating necessary directories..."
mkdir -p "$PROJECT_DIR" "$BACKUP_DIR"

# Function to create backup
create_backup() {
    if [ -d "$PROJECT_DIR/.git" ]; then
        log "Creating backup of current deployment..."
        TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
        cp -r "$PROJECT_DIR" "$BACKUP_DIR/backup_$TIMESTAMP"
        log "Backup created at $BACKUP_DIR/backup_$TIMESTAMP"
    fi
}

# Function to pull latest code
pull_code() {
    log "Pulling latest code from repository..."
    cd "$PROJECT_DIR"
    
    if [ -d ".git" ]; then
        git fetch --all
        git reset --hard origin/main
        git clean -fd
    else
        error "Not a git repository. Please clone the repository first."
        exit 1
    fi
}

# Function to check environment file
check_env_file() {
    log "Checking environment configuration..."
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        if [ -f "$PROJECT_DIR/.env.example" ]; then
            warning ".env file not found. Please copy .env.example to .env and configure it."
            cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
            error "Please edit $PROJECT_DIR/.env with your configuration and run this script again."
            exit 1
        else
            error "No .env or .env.example file found."
            exit 1
        fi
    fi
}

# Function to build and deploy
deploy() {
    log "Starting deployment process..."
    cd "$PROJECT_DIR"
    
    # Build images
    log "Building Docker images..."
    docker-compose -f docker-compose.yml build --no-cache
    
    # Stop existing containers
    log "Stopping existing containers..."
    docker-compose -f docker-compose.yml down
    
    # Start new containers
    log "Starting new containers..."
    docker-compose -f docker-compose.yml up -d
    
    # Wait for services to be ready
    log "Waiting for services to be ready..."
    sleep 30
    
    # Check if services are healthy
    check_health
}

# Function to check health
check_health() {
    log "Checking service health..."
    
    # Check main app
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log "Main application is healthy"
    else
        error "Main application is not responding"
        return 1
    fi
    
    # Check grading service
    if curl -f http://localhost:8001/health > /dev/null 2>&1; then
        log "Grading service is healthy"
    else
        error "Grading service is not responding"
        return 1
    fi
    
    log "All services are healthy"
}

# Function to cleanup old images
cleanup() {
    log "Cleaning up old Docker images..."
    docker system prune -f
    docker volume prune -f
}

# Main deployment process
main() {
    log "Starting AI Grading Software deployment..."
    
    create_backup
    pull_code
    check_env_file
    deploy
    cleanup
    
    log "Deployment completed successfully!"
    log "Application is running at http://localhost:8000"
    log "Grading service is running at http://localhost:8001"
}

# Run main function
main "$@"
