#!/bin/bash

# Backup script for AI Grading Software
# This script creates backups of application data and configurations

set -e

# Configuration
PROJECT_DIR="/opt/ai-grading-software"
BACKUP_BASE_DIR="/opt/backups/ai-grading-software"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$BACKUP_BASE_DIR/backup_$TIMESTAMP"

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

# Create backup directory
log "Creating backup directory: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# Backup application files
log "Backing up application files..."
cp -r "$PROJECT_DIR" "$BACKUP_DIR/application"

# Backup Docker volumes
log "Backing up Docker volumes..."
docker run --rm -v ai-grading-software_server_data:/data -v "$BACKUP_DIR:/backup" alpine tar czf /backup/server_data.tar.gz -C /data .

# Backup environment file
log "Backing up environment configuration..."
if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" "$BACKUP_DIR/env_backup"
fi

# Create backup manifest
log "Creating backup manifest..."
cat > "$BACKUP_DIR/manifest.txt" << EOF
Backup Created: $(date)
Backup Type: Full Application Backup
Application Directory: $PROJECT_DIR
Docker Volumes: ai-grading-software_server_data
Environment File: .env
EOF

# Compress backup
log "Compressing backup..."
cd "$BACKUP_BASE_DIR"
tar czf "backup_$TIMESTAMP.tar.gz" "backup_$TIMESTAMP"
rm -rf "backup_$TIMESTAMP"

# Clean old backups (keep last 7 days)
log "Cleaning old backups..."
find "$BACKUP_BASE_DIR" -name "backup_*.tar.gz" -mtime +7 -delete

log "Backup completed successfully: $BACKUP_BASE_DIR/backup_$TIMESTAMP.tar.gz"
log "Backup size: $(du -h "$BACKUP_BASE_DIR/backup_$TIMESTAMP.tar.gz" | cut -f1)"
