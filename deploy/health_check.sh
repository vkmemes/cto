#!/bin/bash
# Health check script for YGK Schedule

WEB_URL="${WEB_URL:-http://localhost:8000}"
BOT_SERVICE="ygk-bot"
WEB_SERVICE="ygk-web"
ERRORS=0

echo "=========================================="
echo "YGK Schedule Health Check"
echo "Time: $(date)"
echo "=========================================="

# Check bot service
if systemctl is-active --quiet "$BOT_SERVICE"; then
    BOT_PID=$(systemctl show -p MainPID "$BOT_SERVICE" | cut -d= -f2)
    BOT_MEMORY=$(ps -o rss= -p "$BOT_PID" 2>/dev/null | awk '{print int($1/1024)}')
    echo "✅ Bot service: RUNNING (PID: $BOT_PID, Memory: ${BOT_MEMORY}MB)"
else
    echo "❌ Bot service: NOT RUNNING"
    ERRORS=$((ERRORS + 1))
fi

# Check web service
if systemctl is-active --quiet "$WEB_SERVICE"; then
    WEB_PID=$(systemctl show -p MainPID "$WEB_SERVICE" | cut -d= -f2)
    WEB_MEMORY=$(ps -o rss= -p "$WEB_PID" 2>/dev/null | awk '{print int($1/1024)}')
    echo "✅ Web service: RUNNING (PID: $WEB_PID, Memory: ${WEB_MEMORY}MB)"
else
    echo "❌ Web service: NOT RUNNING"
    ERRORS=$((ERRORS + 1))
fi

# Check HTTP response
if command -v curl >/dev/null 2>&1; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$WEB_URL" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✅ Web endpoint: HTTP $HTTP_CODE"
    else
        echo "❌ Web endpoint: HTTP $HTTP_CODE"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "⚠️  curl not available, skipping HTTP check"
fi

# Check database
DB_FILE="/opt/ygk/ygk.db"
if [ -f "$DB_FILE" ]; then
    DB_SIZE=$(stat -c%s "$DB_FILE" 2>/dev/null | numfmt --to=iec 2>/dev/null || stat -f%z "$DB_FILE" 2>/dev/null)
    echo "✅ Database: EXISTS (Size: ${DB_SIZE})"
else
    echo "❌ Database: MISSING"
    ERRORS=$((ERRORS + 1))
fi

# Check disk space
DISK_USAGE=$(df -h /opt/ygk 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')
if [ -n "$DISK_USAGE" ] && [ "$DISK_USAGE" -lt 90 ]; then
    echo "✅ Disk usage: ${DISK_USAGE}%"
else
    echo "⚠️  Disk usage: ${DISK_USAGE}% (consider cleanup)"
fi

# Check memory
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
if [ -n "$MEMORY_USAGE" ] && [ "$MEMORY_USAGE" -lt 90 ]; then
    echo "✅ Memory usage: ${MEMORY_USAGE}%"
else
    echo "⚠️  Memory usage: ${MEMORY_USAGE}% (high)"
fi

# Check for recent errors in logs
echo ""
echo "Recent errors (if any):"
journalctl -u "$BOT_SERVICE" -u "$WEB_SERVICE" --since "1 hour ago" --no-pager -q | grep -i "error\|exception" | tail -5 || echo "No recent errors found"

echo ""
echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo "✅ All checks passed!"
    exit 0
else
    echo "❌ Found $ERRORS error(s)"
    exit 1
fi
