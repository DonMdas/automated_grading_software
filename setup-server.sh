#!/bin/bash

# Setup script for AI Grading Software on fresh server
# This script installs all necessary dependencies and sets up the environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root"
   exit 1
fi

# Update system
log "Updating system packages..."
apt-get update -y
apt-get upgrade -y

# Install essential packages
log "Installing essential packages..."
apt-get install -y \
    curl \
    wget \
    git \
    unzip \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common \
    ufw \
    fail2ban \
    htop \
    vim \
    tree

# Install Docker
log "Installing Docker..."
if ! command -v docker &> /dev/null; then
    # Add Docker's official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Add Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Update package index
    apt-get update -y
    
    # Install Docker
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Start and enable Docker
    systemctl start docker
    systemctl enable docker
    
    log "Docker installed successfully"
else
    log "Docker is already installed"
fi

# Install Docker Compose
log "Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    log "Docker Compose installed successfully"
else
    log "Docker Compose is already installed"
fi

# Create application user
log "Creating application user..."
if ! id "appuser" &>/dev/null; then
    useradd -m -s /bin/bash appuser
    usermod -aG docker appuser
    log "Application user created successfully"
else
    log "Application user already exists"
fi

# Create application directory
log "Creating application directory..."
mkdir -p /opt/ai-grading-software
chown -R appuser:appuser /opt/ai-grading-software

# Create backup directory
mkdir -p /opt/backups/ai-grading-software
chown -R appuser:appuser /opt/backups/ai-grading-software

# Setup firewall
log "Setting up firewall..."
ufw --force enable
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp  # Main application
ufw allow 8001/tcp  # Grading service
log "Firewall configured"

# Setup fail2ban
log "Setting up fail2ban..."
systemctl start fail2ban
systemctl enable fail2ban

# Create log directory
mkdir -p /var/log/ai-grading-software
chown -R appuser:appuser /var/log/ai-grading-software

# Setup logrotate
log "Setting up log rotation..."
cat > /etc/logrotate.d/ai-grading-software << 'EOF'
/var/log/ai-grading-software/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 appuser appuser
}
EOF

# Setup systemd service for auto-start
log "Setting up systemd service..."
cat > /etc/systemd/system/ai-grading-software.service << 'EOF'
[Unit]
Description=AI Grading Software
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/ai-grading-software
ExecStart=/usr/local/bin/docker-compose -f docker-compose.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.yml down
TimeoutStartSec=0
User=appuser
Group=appuser

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ai-grading-software.service

# Create environment file template
log "Creating environment file template..."
cat > /opt/ai-grading-software/.env.example << 'EOF'
# Database Configuration - PostgreSQL (On-premise)
POSTGRES_HOST=your-postgres-host.example.com
POSTGRES_PORT=5432
POSTGRES_USERNAME=your_postgres_username
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_DATABASE=grading_system_pg

# Database Configuration - MongoDB (On-premise)
MONGODB_HOST=your-mongodb-host.example.com
MONGODB_PORT=27017
MONGODB_DATABASE=grading_system_mongo

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://your-domain.com/auth/callback

# Application Configuration
SECRET_KEY=your_super_secret_key_here_make_it_long_and_random
ENVIRONMENT=production

# Domain Configuration
DOMAIN=your-domain.com
EOF

chown appuser:appuser /opt/ai-grading-software/.env.example

log "Server setup completed successfully!"
log ""
log "Next steps:"
log "1. Clone your repository to /opt/ai-grading-software"
log "2. Copy .env.example to .env and configure it"
log "3. Run the deployment script as the appuser"
log ""
log "Commands to run:"
log "su - appuser"
log "cd /opt/ai-grading-software"
log "git clone <your-repository-url> ."
log "cp .env.example .env"
log "nano .env  # Edit with your configuration"
log "./deploy.sh"
