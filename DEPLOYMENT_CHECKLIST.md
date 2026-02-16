# STTEC Schedule - Deployment Checklist

## 📋 Pre-Deployment Checklist

### System Requirements
- [ ] Linux server (Ubuntu 20.04+ or similar)
- [ ] Python 3.8 or higher installed
- [ ] pip and venv available
- [ ] At least 512MB RAM available
- [ ] At least 1GB disk space
- [ ] Internet connection
- [ ] Root or sudo access

### Telegram Setup
- [ ] Telegram bot created via @BotFather
- [ ] Bot token obtained and saved securely
- [ ] Bot username decided (e.g., @sttec_schedule_bot)
- [ ] Bot commands configured in @BotFather:
  ```
  start - Начать работу и выбрать группу
  today - Расписание на сегодня
  tomorrow - Расписание на завтра
  week - Расписание на неделю
  setpin - Установить PIN-код группы
  ```
- [ ] Channel created for subscription requirement
- [ ] Channel username set (e.g., @sttec_channel)
- [ ] Bot added as admin to channel

### Data Preparation
- [ ] Schedule data collected from college
- [ ] Groups list prepared
- [ ] Teacher names verified
- [ ] Room numbers confirmed
- [ ] Replacement HTML page URL identified
- [ ] HTML structure analyzed for parsing

---

## 🚀 Deployment Steps

### Step 1: Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and tools
sudo apt install python3 python3-venv python3-pip git -y

# Create application directory
sudo mkdir -p /opt/sttec
sudo chown $USER:$USER /opt/sttec
cd /opt/sttec
```
- [ ] System updated
- [ ] Python installed
- [ ] Directory created

### Step 2: File Transfer
```bash
# Option A: Git clone
git clone <repository-url> .

# Option B: Manual copy
scp -r /path/to/sttec/* user@server:/opt/sttec/
```
- [ ] All files transferred
- [ ] File permissions correct
- [ ] Directory structure intact

### Step 3: Virtual Environment
```bash
cd /opt/sttec
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```
- [ ] Virtual environment created
- [ ] Dependencies installed (10 packages)
- [ ] No installation errors

### Step 4: Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

Set these values:
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
CHANNEL_USERNAME=@sttec_channel
REPLACEMENT_URL=https://example.com/replacements.html
DATABASE_URL=sqlite+aiosqlite:///sttec.db
WEB_PORT=8000
```
- [ ] .env file created
- [ ] BOT_TOKEN set
- [ ] CHANNEL_USERNAME set
- [ ] REPLACEMENT_URL set
- [ ] Database path configured
- [ ] Web port configured

### Step 5: Schedule Configuration
```bash
nano schedule.json
```
- [ ] schedule.json edited
- [ ] All groups added
- [ ] Numerator week filled
- [ ] Denominator week filled
- [ ] JSON syntax valid

### Step 6: Database Initialization
```bash
python migrate.py
```
Expected output:
```
Starting database migration...
 Database schema created/updated successfully!

Tables created:
  - users
  - group_settings
  - group_pins
  - students
  - homework
```
- [ ] Migration successful
- [ ] Database file created (sttec.db)
- [ ] All 5 tables created

### Step 7: Verification
```bash
python test_setup.py
```
- [ ] All checks passed (8/8)
- [ ] Python version OK
- [ ] Dependencies OK
- [ ] Core imports OK
- [ ] .env file OK
- [ ] schedule.json OK
- [ ] Templates OK
- [ ] Logs directory OK
- [ ] Database OK

### Step 8: Test Run (Development)
```bash
# Terminal 1 - Bot
python bot_main.py
# Should see: INFO - Starting bot...

# Terminal 2 - Web
python web_main.py
# Should see: INFO - Uvicorn running on http://0.0.0.0:8000
```
- [ ] Bot starts without errors
- [ ] Web server starts without errors
- [ ] No import errors
- [ ] Logs are being written

### Step 9: Manual Testing

**Test Bot:**
1. Open Telegram
2. Find your bot (@your_bot_name)
3. Send `/start`
4. Select a group from keyboard
5. Enter your name
6. Send `/today`
7. Verify schedule appears

- [ ] Bot responds to /start
- [ ] Group selection works
- [ ] Name input works
- [ ] /today shows schedule
- [ ] /tomorrow shows schedule
- [ ] /week shows schedule
- [ ] Subscription check works

**Test Web:**
```bash
# Test schedule API
curl "http://localhost:8000/api/schedule?group=ИС1-11"

# Test web page
curl http://localhost:8000/ | grep "STTEC Schedule"
```
- [ ] Schedule API returns JSON
- [ ] Web pages load
- [ ] No 500 errors

### Step 10: Production Setup (systemd)
```bash
# Edit service files with correct paths
nano sttec-bot.service
nano sttec-web.service

# Change these lines:
# WorkingDirectory=/opt/sttec
# Environment="PATH=/opt/sttec/venv/bin"
# EnvironmentFile=/opt/sttec/.env
# ExecStart=/opt/sttec/venv/bin/python bot_main.py

# Copy to systemd
sudo cp sttec-bot.service /etc/systemd/system/
sudo cp sttec-web.service /etc/systemd/system/

# Set permissions
sudo chmod 644 /etc/systemd/system/sttec-*.service

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable sttec-bot
sudo systemctl enable sttec-web

# Start services
sudo systemctl start sttec-bot
sudo systemctl start sttec-web

# Check status
sudo systemctl status sttec-bot
sudo systemctl status sttec-web
```
- [ ] Service files edited with correct paths
- [ ] Services copied to systemd
- [ ] Services enabled
- [ ] Services started
- [ ] Status shows "active (running)"
- [ ] No errors in status output

### Step 11: Reverse Proxy (Optional but Recommended)
```bash
# Install nginx
sudo apt install nginx -y

# Create config
sudo nano /etc/nginx/sites-available/sttec
```

Nginx config:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/sttec /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```
- [ ] nginx installed
- [ ] Config created
- [ ] Site enabled
- [ ] nginx reloaded
- [ ] Domain accessible

### Step 12: SSL Certificate (Recommended)
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d your-domain.com

# Test auto-renewal
sudo certbot renew --dry-run
```
- [ ] Certbot installed
- [ ] SSL certificate obtained
- [ ] HTTPS working
- [ ] Auto-renewal configured

### Step 13: Monitoring Setup
```bash
# View logs in real-time
sudo journalctl -u sttec-bot -f
sudo journalctl -u sttec-web -f

# Or log files
tail -f /opt/sttec/logs/bot.log
tail -f /opt/sttec/logs/web.log

# Create log rotation
sudo nano /etc/logrotate.d/sttec
```

Logrotate config:
```
/opt/sttec/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
    postrotate
        systemctl reload sttec-bot sttec-web
    endscript
}
```
- [ ] Can view bot logs
- [ ] Can view web logs
- [ ] Log rotation configured

### Step 14: Backup Strategy
```bash
# Database backup script
cat > /opt/sttec/backup.sh << 'SCRIPT'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp /opt/sttec/sttec.db /opt/sttec/backups/sttec_$DATE.db
find /opt/sttec/backups -name "sttec_*.db" -mtime +7 -delete
SCRIPT

chmod +x /opt/sttec/backup.sh
mkdir -p /opt/sttec/backups

# Add to crontab
crontab -e
# Add: 0 2 * * * /opt/sttec/backup.sh
```
- [ ] Backup script created
- [ ] Backup directory created
- [ ] Cron job configured
- [ ] First backup tested

### Step 15: Swap Setup (for low RAM servers)
```bash
# Create 2GB swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify
free -h
```
- [ ] Swap created
- [ ] Swap activated
- [ ] Swap persists after reboot

---

## ✅ Post-Deployment Verification

### Functionality Tests
- [ ] Bot responds within 2 seconds
- [ ] Schedule shows correctly
- [ ] Replacements parse correctly
- [ ] Notifications send at 12:05
- [ ] Duty rotates at 14:00
- [ ] Sick flags reset at midnight
- [ ] Web interface loads
- [ ] Homework form works
- [ ] Headman panel works
- [ ] PIN authentication works

### Performance Tests
```bash
# Check memory usage
free -h
ps aux | grep python

# Should be <100MB per process
```
- [ ] Bot uses <100MB RAM
- [ ] Web uses <100MB RAM
- [ ] Total <512MB RAM
- [ ] Response time <1s

### Security Tests
- [ ] .env file not publicly accessible
- [ ] Database not publicly accessible
- [ ] Bot token not in logs
- [ ] PIN not in logs
- [ ] HTTPS working (if configured)
- [ ] CORS configured correctly

### Reliability Tests
```bash
# Test auto-restart
sudo systemctl stop sttec-bot
sleep 10
sudo systemctl status sttec-bot
# Should show "active (running)"

# Test after reboot
sudo reboot
# Wait and check
sudo systemctl status sttec-bot sttec-web
```
- [ ] Services auto-restart
- [ ] Services start on boot
- [ ] No memory leaks after 24h
- [ ] Logs rotate correctly

---

## 📊 Monitoring Checklist

### Daily Checks
- [ ] Bot is running
- [ ] Web is running
- [ ] No errors in logs
- [ ] Notifications sent
- [ ] Database backed up

### Weekly Checks
- [ ] Disk space available
- [ ] Memory usage normal
- [ ] Log files size OK
- [ ] No failed jobs
- [ ] SSL certificate valid

### Monthly Checks
- [ ] Update dependencies
- [ ] Review logs for issues
- [ ] Backup database manually
- [ ] Test disaster recovery
- [ ] Update schedule.json

---

## 🐛 Troubleshooting Reference

### Bot Not Starting
```bash
sudo journalctl -u sttec-bot -n 50
# Check for:
# - Import errors
# - Token errors
# - Database errors
```

### Web Not Accessible
```bash
sudo systemctl status sttec-web
netstat -tulpn | grep 8000
# Check if port is listening
```

### Notifications Not Sending
```bash
# Check bot logs
tail -f logs/bot.log | grep job_smart_poll
# Verify REPLACEMENT_URL is accessible
curl -I $REPLACEMENT_URL
```

### Database Locked
```bash
# Check for multiple processes
ps aux | grep python
# Kill duplicate processes if needed
```

### Memory Issues
```bash
# Check memory
free -h
# Check swap
swapon --show
# Restart services
sudo systemctl restart sttec-bot sttec-web
```

---

## 📞 Support Contacts

- **Documentation:** README.md, QUICKSTART.md, ARCHITECTURE.md
- **Logs:** /opt/sttec/logs/
- **Database:** /opt/sttec/sttec.db
- **Config:** /opt/sttec/.env

---

## ✨ Success Criteria

Deployment is successful when:

 All checklist items completed  
 All services running  
 All tests passing  
 Bot responding to commands  
 Web interface accessible  
 Logs being written  
 No errors in logs  
 Backups working  
 Monitoring configured  

**Congratulations! Your STTEC Schedule system is now live! 🎉**

---

**Last Updated:** February 16, 2026  
**Version:** 1.0  
**Status:** Production Ready
