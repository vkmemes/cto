#!/bin/bash
set -e

PROJECT_DIR="/opt/ygk"
VENV_DIR="$PROJECT_DIR/venv"
LOG_FILE="/var/log/ygk-deploy.log"
BACKUP_DIR="$PROJECT_DIR/backups"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

cd "$PROJECT_DIR"

# Create backup directory if not exists
mkdir -p "$BACKUP_DIR"

# Get current git commit for rollback info
CURRENT_COMMIT=$(git rev-parse --short HEAD)
log "Starting deployment. Current commit: $CURRENT_COMMIT"

# Backup database before deployment
if [ -f "ygk.db" ]; then
    BACKUP_NAME="ygk_$(date +%Y%m%d_%H%M%S).db"
    cp ygk.db "$BACKUP_DIR/$BACKUP_NAME"
    log "✅ Database backed up to backups/$BACKUP_NAME"
    
    # Keep only last 10 backups
    ls -t "$BACKUP_DIR"/ygk_*.db 2>/dev/null | tail -n +11 | xargs -r rm --
fi

# Backup .env
if [ -f ".env" ]; then
    cp .env .env.backup
fi

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip --quiet

# Install/update dependencies
log "Installing dependencies..."
pip install -r requirements.txt --quiet

# Run database migrations
log "Running migrations..."
python migrate.py

# Check for syntax errors
log "Checking Python syntax..."
python -m py_compile bot_main.py web_main.py core.py database.py

# Check for changes in service files
RELOAD_NEEDED=false

if [ -f "ygk-bot.service" ]; then
    if ! diff -q "ygk-bot.service" /etc/systemd/system/ygk-bot.service >/dev/null 2>&1; then
        log "Updating ygk-bot.service..."
        sudo cp ygk-bot.service /etc/systemd/system/
        RELOAD_NEEDED=true
    fi
fi

if [ -f "ygk-web.service" ]; then
    if ! diff -q "ygk-web.service" /etc/systemd/system/ygk-web.service >/dev/null 2>&1; then
        log "Updating ygk-web.service..."
        sudo cp ygk-web.service /etc/systemd/system/
        RELOAD_NEEDED=true
    fi
fi

if [ "$RELOAD_NEEDED" = true ]; then
    log "Reloading systemd..."
    sudo systemctl daemon-reload
fi

# Pre-deployment health check
log "Pre-deployment health check..."
if systemctl is-active --quiet ygk-bot; then
    BOT_WAS_ACTIVE=true
else
    BOT_WAS_ACTIVE=false
fi

if systemctl is-active --quiet ygk-web; then
    WEB_WAS_ACTIVE=true
else
    WEB_WAS_ACTIVE=false
fi

# Restart services
log "Restarting services..."
sudo systemctl restart ygk-bot
sudo systemctl restart ygk-web

# Wait for services to start
log "Waiting for services to start..."
sleep 5

# Verify services are running
DEPLOYMENT_FAILED=false

if ! systemctl is-active --quiet ygk-bot; then
    log "❌ ERROR: ygk-bot failed to start!"
    sudo journalctl -u ygk-bot -n 20 --no-pager | tee -a "$LOG_FILE"
    DEPLOYMENT_FAILED=true
else
    log "✅ ygk-bot is running"
fi

if ! systemctl is-active --quiet ygk-web; then
    log "❌ ERROR: ygk-web failed to start!"
    sudo journalctl -u ygk-web -n 20 --no-pager | tee -a "$LOG_FILE"
    DEPLOYMENT_FAILED=true
else
    log "✅ ygk-web is running"
fi

# Test web endpoint
if curl -sf http://localhost:8000/ >/dev/null 2>&1; then
    log "✅ Web endpoint responding"
else
    log "❌ WARNING: Web endpoint not responding"
    # Don't fail deployment for this, but log it
fi

# Cleanup old logs (keep last 30 days)
find "$PROJECT_DIR/logs" -name "*.log" -mtime +30 -delete 2>/dev/null || true

if [ "$DEPLOYMENT_FAILED" = true ]; then
    log "❌ Deployment failed!"
    exit 1
fi

log "✅ Deployment completed successfully!"
exit 0
