# Wound AI System - Production Deployment Guide

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Configuration](#database-configuration)
4. [Application Deployment](#application-deployment)
5. [Security Best Practices](#security-best-practices)
6. [Scaling Strategy](#scaling-strategy)
7. [Monitoring & Maintenance](#monitoring--maintenance)

---

## 1. Prerequisites

### System Requirements
- **Server**: 4+ CPU cores, 8+ GB RAM, 100+ GB storage
- **Operating System**: Ubuntu 22.04 LTS or similar
- **Python**: 3.10+
- **Database**: PostgreSQL 14+
- **Reverse Proxy**: Nginx
- **SSL**: Let's Encrypt (Certbot)

### Cloud Platform Options

#### Option A: AWS EC2
```bash
# Recommended instance: t3.large or t3.xlarge
# OS: Ubuntu 22.04 LTS
# Storage: 100GB SSD
# Security Group: Allow 22 (SSH), 80 (HTTP), 443 (HTTPS)
```

#### Option B: Google Cloud Platform
```bash
# Recommended: e2-standard-4
# OS: Ubuntu 22.04 LTS
# Disk: 100GB Standard Persistent Disk
# Firewall: Allow HTTP, HTTPS, SSH
```

#### Option C: Azure VM
```bash
# Recommended: Standard_D4s_v3
# OS: Ubuntu Server 22.04 LTS
# Disk: 100GB Premium SSD
# NSG: Allow HTTP, HTTPS, SSH
```

#### Option D: Managed Platform (Easiest)
- **Render** (recommended for MVP): https://render.com
- **Railway**: https://railway.app
- **Fly.io**: https://fly.io
- **Heroku**: https://heroku.com

---

## 2. Environment Setup

### A. Initial Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    python3.10 \
    python3-pip \
    python3-venv \
    postgresql \
    postgresql-contrib \
    nginx \
    git \
    curl \
    build-essential \
    libpq-dev \
    certbot \
    python3-certbot-nginx

# Install Docker (optional, for containerized deployment)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### B. Application Directory Setup

```bash
# Create application directory
sudo mkdir -p /opt/woundai
sudo chown $USER:$USER /opt/woundai
cd /opt/woundai

# Clone repository
git clone https://github.com/yourusername/wound-ai-system.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### C. Environment Variables

Create `.env` file:

```bash
# .env
# DO NOT COMMIT THIS FILE TO VERSION CONTROL

# Database
DATABASE_URL=postgresql://woundai_user:STRONG_PASSWORD@localhost:5432/woundai_db

# JWT Secrets (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your-secret-key-here-64-chars-minimum
JWT_REFRESH_SECRET_KEY=your-refresh-secret-key-here-64-chars-minimum

# OpenAI API
OPENAI_API_KEY=sk-your-openai-key-here

# Application
APP_ENV=production
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Security
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# File Storage
UPLOAD_DIR=/opt/woundai/uploads
MAX_UPLOAD_SIZE=10485760  # 10MB

# Email (optional, for password reset)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@yourdomain.com

# Monitoring (optional)
SENTRY_DSN=https://your-sentry-dsn
```

---

## 3. Database Configuration

### A. PostgreSQL Setup

```bash
# Switch to postgres user
sudo -i -u postgres

# Create database and user
psql << EOF
CREATE DATABASE woundai_db;
CREATE USER woundai_user WITH ENCRYPTED PASSWORD 'STRONG_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON DATABASE woundai_db TO woundai_user;
\c woundai_db
GRANT ALL ON SCHEMA public TO woundai_user;
EOF

# Exit postgres user
exit
```

### B. Initialize Database Schema

```bash
cd /opt/woundai
source venv/bin/activate

# Run database initialization
python database_schema_multiuser.py

# Create admin user
python << EOF
from database_schema_multiuser import create_admin_user
create_admin_user(
    username="admin",
    email="admin@yourdomain.com",
    password="CHANGE_THIS_PASSWORD",
    full_name="System Administrator"
)
EOF
```

### C. Database Backup Strategy

```bash
# Create backup script
sudo tee /opt/woundai/backup_db.sh > /dev/null << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/woundai/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Dump database
pg_dump -U woundai_user -h localhost woundai_db | gzip > $BACKUP_DIR/woundai_backup_$DATE.sql.gz

# Keep only last 30 days of backups
find $BACKUP_DIR -name "woundai_backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: woundai_backup_$DATE.sql.gz"
EOF

# Make executable
sudo chmod +x /opt/woundai/backup_db.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/woundai/backup_db.sh") | crontab -
```

---

## 4. Application Deployment

### Option 1: Systemd Service (Recommended)

```bash
# Create systemd service file
sudo tee /etc/systemd/system/woundai.service > /dev/null << EOF
[Unit]
Description=Wound AI FastAPI Application
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/woundai
Environment="PATH=/opt/woundai/venv/bin"
EnvironmentFile=/opt/woundai/.env
ExecStart=/opt/woundai/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 wound_ai_system_full_fixed:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable woundai
sudo systemctl start woundai
sudo systemctl status woundai
```

### Option 2: Docker Deployment

See `Dockerfile` and `docker-compose.yml` files (created separately).

---

## 5. Nginx Configuration

```bash
# Create Nginx configuration
sudo tee /etc/nginx/sites-available/woundai > /dev/null << 'EOF'
# Rate limiting
limit_req_zone $binary_remote_addr zone=woundai_limit:10m rate=10r/s;

upstream woundai_backend {
    server 127.0.0.1:8000 fail_timeout=30s max_fails=3;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration (managed by Certbot)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # File upload size limit
    client_max_body_size 10M;

    # Rate limiting
    limit_req zone=woundai_limit burst=20 nodelay;

    # Logging
    access_log /var/log/nginx/woundai_access.log;
    error_log /var/log/nginx/woundai_error.log;

    # Proxy to FastAPI
    location / {
        proxy_pass http://woundai_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files (if needed)
    location /static {
        alias /opt/woundai/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /health {
        proxy_pass http://woundai_backend;
        access_log off;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/woundai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Obtain SSL Certificate

```bash
# Install SSL certificate with Certbot
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal is set up automatically
# Test renewal
sudo certbot renew --dry-run
```

---

## 6. Security Best Practices

### A. Firewall Configuration

```bash
# UFW (Uncomplicated Firewall)
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
sudo ufw status
```

### B. PostgreSQL Security

```bash
# Edit PostgreSQL config
sudo nano /etc/postgresql/14/main/pg_hba.conf

# Change this line:
# local   all             all                                     peer
# To:
local   all             all                                     md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### C. SSH Hardening

```bash
# Edit SSH config
sudo nano /etc/ssh/sshd_config

# Recommended settings:
PermitRootLogin no
PasswordAuthentication no  # Use SSH keys only
PubkeyAuthentication yes
X11Forwarding no

# Restart SSH
sudo systemctl restart sshd
```

### D. Application Security Checklist

- [ ] Strong JWT secret keys (64+ characters)
- [ ] HTTPS enforced
- [ ] Rate limiting enabled
- [ ] CORS properly configured
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (using ORMs)
- [ ] File upload restrictions
- [ ] Regular security updates
- [ ] Password complexity requirements
- [ ] MFA for admin accounts (optional)

---

## 7. Scaling Strategy

### Horizontal Scaling

```bash
# Use load balancer with multiple application servers
# Example Nginx load balancing:

upstream woundai_backend {
    least_conn;
    server app1.internal:8000 max_fails=3 fail_timeout=30s;
    server app2.internal:8000 max_fails=3 fail_timeout=30s;
    server app3.internal:8000 max_fails=3 fail_timeout=30s;
}
```

### Database Scaling

```sql
-- Create read replicas for read-heavy workloads
-- Use connection pooling (pgBouncer)

-- Install pgBouncer
sudo apt install pgbouncer

-- Configuration in /etc/pgbouncer/pgbouncer.ini
[databases]
woundai_db = host=localhost port=5432 dbname=woundai_db

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = md5
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
```

### File Storage Scaling

```python
# Move to cloud storage (S3, GCS, Azure Blob)
# Example with AWS S3:

import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION', 'us-east-1')
)

def upload_to_s3(file_obj, bucket_name, object_name):
    try:
        s3_client.upload_fileobj(file_obj, bucket_name, object_name)
        return f"https://{bucket_name}.s3.amazonaws.com/{object_name}"
    except ClientError as e:
        print(f"Error uploading to S3: {e}")
        return None
```

---

## 8. Monitoring & Maintenance

### A. Application Monitoring

```bash
# Install monitoring tools
pip install prometheus-client sentry-sdk

# Add to FastAPI app:
from prometheus_client import Counter, Histogram
import sentry_sdk

# Sentry for error tracking
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"))

# Prometheus metrics
REQUEST_COUNT = Counter('app_requests_total', 'Total requests')
REQUEST_LATENCY = Histogram('app_request_latency_seconds', 'Request latency')
```

### B. Log Management

```bash
# Centralized logging with journalctl
sudo journalctl -u woundai -f  # Follow logs

# Log rotation
sudo tee /etc/logrotate.d/woundai > /dev/null << EOF
/var/log/woundai/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0640 ubuntu ubuntu
}
EOF
```

### C. Health Checks

```python
# Add to FastAPI app
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        # Check database connection
        db.execute("SELECT 1")
        
        # Check disk space
        import shutil
        disk = shutil.disk_usage("/")
        disk_free_percent = (disk.free / disk.total) * 100
        
        return {
            "status": "healthy",
            "database": "connected",
            "disk_free_percent": round(disk_free_percent, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Unhealthy: {str(e)}")
```

### D. Automated Monitoring Script

```bash
# Create monitoring script
sudo tee /opt/woundai/monitor.sh > /dev/null << 'EOF'
#!/bin/bash

HEALTH_URL="http://localhost:8000/health"
ALERT_EMAIL="admin@yourdomain.com"

# Check if service is running
if ! systemctl is-active --quiet woundai; then
    echo "Wound AI service is down! Attempting restart..." | mail -s "ALERT: Wound AI Down" $ALERT_EMAIL
    sudo systemctl restart woundai
fi

# Check health endpoint
if ! curl -f -s $HEALTH_URL > /dev/null; then
    echo "Wound AI health check failed!" | mail -s "ALERT: Wound AI Health Check Failed" $ALERT_EMAIL
fi

# Check disk space
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "Disk usage is at ${DISK_USAGE}%!" | mail -s "WARNING: High Disk Usage" $ALERT_EMAIL
fi
EOF

sudo chmod +x /opt/woundai/monitor.sh

# Run every 5 minutes
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/woundai/monitor.sh") | crontab -
```

---

## 9. Managed Platform Deployment (Easiest)

### Render.com (Recommended for Quick Deployment)

1. **Connect GitHub Repository**
   - Sign up at https://render.com
   - Connect your GitHub account
   - Select the wound-ai-system repository

2. **Create PostgreSQL Database**
   - Click "New +" → "PostgreSQL"
   - Choose plan (Starter: $7/month)
   - Note the Internal Database URL

3. **Create Web Service**
   - Click "New +" → "Web Service"
   - Connect repository
   - Configure:
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT wound_ai_system_full_fixed:app`
     - **Environment Variables**: Add all from `.env`

4. **Deploy**
   - Click "Create Web Service"
   - Automatic HTTPS enabled
   - Auto-deploy on git push

---

## 10. Post-Deployment Checklist

- [ ] Application accessible via HTTPS
- [ ] Database backups automated
- [ ] SSL certificate auto-renewal configured
- [ ] Monitoring and alerting set up
- [ ] Log rotation configured
- [ ] Firewall rules active
- [ ] Admin account created and secured
- [ ] API rate limiting tested
- [ ] Health check endpoint responding
- [ ] Documentation updated with deployment details

---

## Support & Maintenance

### Regular Tasks
- **Daily**: Monitor logs and health checks
- **Weekly**: Review security alerts, update dependencies
- **Monthly**: Review database performance, optimize queries
- **Quarterly**: Security audit, backup restoration test

### Useful Commands
```bash
# View logs
sudo journalctl -u woundai -f

# Restart service
sudo systemctl restart woundai

# Check service status
sudo systemctl status woundai

# Database backup
/opt/woundai/backup_db.sh

# Update application
cd /opt/woundai
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart woundai
```

---

## Emergency Contacts
- **Technical Support**: support@yourdomain.com
- **Security Issues**: security@yourdomain.com
- **On-Call**: +1-XXX-XXX-XXXX

---

**Last Updated**: 2024
**Version**: 1.0.0
