#!/bin/bash
#
# PlantMind AI - Production Deployment Script
# Usage: ./scripts/deploy.sh [staging|production]
#

set -e

ENVIRONMENT=${1:-staging}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🏭 PlantMind AI - Production Deployment"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check if .env exists
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        log_warn ".env file not found. Copying from .env.example"
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        log_warn "Please edit .env file with your production settings"
    fi
    
    log_info "Prerequisites check passed"
}

# Build and deploy with Docker Compose
deploy_docker() {
    log_info "Building and deploying with Docker Compose..."
    
    cd "$PROJECT_ROOT"
    
    # Pull latest images
    docker-compose pull
    
    # Build application
    docker-compose build --no-cache
    
    # Stop existing containers
    log_info "Stopping existing containers..."
    docker-compose down || true
    
    # Start services
    log_info "Starting services..."
    docker-compose up -d
    
    # Wait for database
    log_info "Waiting for database to be ready..."
    sleep 10
    
    # Run health check
    log_info "Running health checks..."
    for i in {1..30}; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log_info "Application is healthy"
            return 0
        fi
        echo -n "."
        sleep 2
    done
    
    log_error "Health check failed"
    docker-compose logs app
    return 1
}

# Setup SSL certificates with Let's Encrypt
setup_ssl() {
    log_info "Setting up SSL certificates..."
    
    if [ -d "$PROJECT_ROOT/ssl" ]; then
        log_warn "SSL directory already exists. Skipping certificate generation."
        return 0
    fi
    
    mkdir -p "$PROJECT_ROOT/ssl"
    
    # Generate self-signed certificate for initial setup
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$PROJECT_ROOT/ssl/plantmind.key" \
        -out "$PROJECT_ROOT/ssl/plantmind.crt" \
        -subj "/C=IN/ST=Maharashtra/L=Mumbai/O=PlantMind AI/OU=Factory/CN=localhost"
    
    log_info "Self-signed SSL certificate generated"
    log_warn "For production, replace with valid certificates from Let's Encrypt or your provider"
}

# Configure firewall (Linux only)
configure_firewall() {
    if [ "$EUID" -ne 0 ]; then
        log_warn "Not running as root, skipping firewall configuration"
        return 0
    fi
    
    log_info "Configuring firewall..."
    
    # UFW (Ubuntu/Debian)
    if command -v ufw &> /dev/null; then
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw allow 8000/tcp
        log_info "UFW rules added"
    fi
    
    # firewalld (RHEL/CentOS)
    if command -v firewall-cmd &> /dev/null; then
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --permanent --add-port=8000/tcp
        firewall-cmd --reload
        log_info "firewalld rules added"
    fi
}

# Backup database
backup_database() {
    log_info "Creating database backup..."
    
    BACKUP_DIR="$PROJECT_ROOT/backups"
    mkdir -p "$BACKUP_DIR"
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/plantmind_backup_$TIMESTAMP.sql"
    
    # Get database credentials from .env
    DB_URL=$(grep DATABASE_URL "$PROJECT_ROOT/.env" | cut -d'=' -f2)
    
    # Extract credentials (simplified parsing)
    if [[ $DB_URL =~ postgresql://([^:]+):([^@]+)@([^:]+):([^/]+)/(.+) ]]; then
        DB_USER="${BASH_REMATCH[1]}"
        DB_PASS="${BASH_REMATCH[2]}"
        DB_HOST="${BASH_REMATCH[3]}"
        DB_PORT="${BASH_REMATCH[4]}"
        DB_NAME="${BASH_REMATCH[5]}"
        
        PGPASSWORD="$DB_PASS" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE"
        
        log_info "Database backup created: $BACKUP_FILE"
    else
        log_warn "Could not parse database URL for backup"
    fi
}

# Cleanup old backups
cleanup_backups() {
    log_info "Cleaning up old backups (keeping last 7 days)..."
    
    BACKUP_DIR="$PROJECT_ROOT/backups"
    if [ -d "$BACKUP_DIR" ]; then
        find "$BACKUP_DIR" -name "plantmind_backup_*.sql" -mtime +7 -delete
        log_info "Old backups cleaned up"
    fi
}

# Main deployment function
deploy() {
    check_prerequisites
    
    if [ "$ENVIRONMENT" == "production" ]; then
        backup_database
        setup_ssl
        configure_firewall
    fi
    
    deploy_docker
    
    if [ "$ENVIRONMENT" == "production" ]; then
        cleanup_backups
    fi
    
    log_info "Deployment completed successfully!"
    echo ""
    echo "=========================================="
    echo "🎉 PlantMind AI is now running!"
    echo "=========================================="
    echo ""
    echo "Local URL:    http://localhost:8000"
    echo "Health Check: http://localhost:8000/health"
    echo ""
    echo "To view logs:"
    echo "  docker-compose logs -f app"
    echo ""
    echo "To stop:"
    echo "  docker-compose down"
    echo ""
}

# Show help
show_help() {
    echo "PlantMind AI - Deployment Script"
    echo ""
    echo "Usage: $0 [environment]"
    echo ""
    echo "Environments:"
    echo "  staging     Deploy to staging environment (default)"
    echo "  production  Deploy to production environment"
    echo ""
    echo "Examples:"
    echo "  $0              # Deploy to staging"
    echo "  $0 production   # Deploy to production"
    echo ""
}

# Main
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    show_help
    exit 0
fi

if [ "$ENVIRONMENT" != "staging" ] && [ "$ENVIRONMENT" != "production" ]; then
    log_error "Invalid environment: $ENVIRONMENT"
    show_help
    exit 1
fi

deploy
