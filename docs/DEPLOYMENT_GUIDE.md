# Deployment Rehberi

## Netmon Proje Takip Sistemi - Kurulum ve Dağıtım

**Versiyon:** 2.0  
**Son Güncelleme:** 2026-02-02

---

## 📋 Gereksinimler

### Sistem Gereksinimleri

| Bileşen | Minimum | Önerilen |
|---------|---------|----------|
| CPU | 2 Core | 4 Core |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 50 GB |
| OS | Ubuntu 20.04+ / Windows Server 2019+ | Ubuntu 22.04 LTS |

### Yazılım Gereksinimleri

- Python 3.10+
- Node.js 18+ (opsiyonel, frontend build için)
- Docker & Docker Compose (opsiyonel)
- Nginx (reverse proxy)

---

## 🚀 Kurulum Yöntemleri

### Yöntem 1: Docker ile Kurulum (Önerilen)

#### 1. Repoyu klonlayın
```bash
git clone https://github.com/company/netmon-tracker.git
cd netmon-tracker
```

#### 2. Environment dosyasını oluşturun
```bash
cp .env.example .env
nano .env
```

**Gerekli değişkenler:**
```env
SECRET_KEY=your-super-secret-key-minimum-32-chars
DB_URL=sqlite:///planner.db
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

#### 3. Docker Compose ile başlatın
```bash
docker-compose up -d
```

#### 4. Veritabanını başlatın
```bash
docker-compose exec web flask db upgrade
```

### Yöntem 2: Manuel Kurulum

#### 1. Python virtual environment oluşturun
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

#### 2. Bağımlılıkları yükleyin
```bash
pip install -r requirements.txt
```

#### 3. Veritabanını başlatın
```bash
flask db upgrade
```

#### 4. Uygulamayı başlatın
```bash
# Development
flask run --host=0.0.0.0 --port=5000

# Production (Gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

---

## 🔒 HTTPS Yapılandırması

### Self-Signed Sertifika (Test)

```bash
# SSL klasörü oluştur
mkdir -p ssl

# Sertifika oluştur
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout ssl/key.pem \
    -out ssl/cert.pem \
    -subj "/CN=localhost"
```

### Let's Encrypt (Production)

```bash
# Certbot yükle
sudo apt install certbot python3-certbot-nginx

# Sertifika al
sudo certbot --nginx -d yourdomain.com
```

---

## 🔧 Nginx Yapılandırması

`/etc/nginx/sites-available/netmon`:

```nginx
upstream netmon_app {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # WebSocket desteği
    location /socket.io {
        proxy_pass http://netmon_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://netmon_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Statik dosyalar
    location /static {
        alias /opt/netmon/static;
        expires 30d;
    }

    # Upload limiti
    client_max_body_size 100M;
}
```

---

## 📊 Monitoring

### Systemd Service

`/etc/systemd/system/netmon.service`:

```ini
[Unit]
Description=Netmon Proje Takip Sistemi
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/netmon
Environment="PATH=/opt/netmon/.venv/bin"
Environment="SECRET_KEY=your-secret-key"
ExecStart=/opt/netmon/.venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable netmon
sudo systemctl start netmon
```

### Log Rotasyonu

`/etc/logrotate.d/netmon`:

```
/opt/netmon/instance/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
}
```

---

## 🔄 Backup Stratejisi

### Otomatik Backup Script

```bash
#!/bin/bash
# /opt/netmon/scripts/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups/netmon"

mkdir -p $BACKUP_DIR

# Veritabanı backup
sqlite3 /opt/netmon/instance/planner.db ".backup '$BACKUP_DIR/db_$DATE.sqlite'"

# Uploads backup
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /opt/netmon/instance/uploads

# 30 günden eski backupları sil
find $BACKUP_DIR -type f -mtime +30 -delete
```

### Crontab

```bash
# Her gün 02:00'da backup al
0 2 * * * /opt/netmon/scripts/backup.sh
```

---

## 🆘 Sorun Giderme

### Yaygın Hatalar

| Hata | Çözüm |
|------|-------|
| `SQLALCHEMY_DATABASE_URI not set` | `.env` dosyasında `DB_URL` tanımlayın |
| `SECRET_KEY environment variable is required` | `.env` dosyasında `SECRET_KEY` tanımlayın |
| WebSocket bağlantı hatası | Nginx WebSocket proxy ayarlarını kontrol edin |
| 502 Bad Gateway | Gunicorn servisinin çalıştığından emin olun |

### Log Dosyaları

```bash
# Uygulama logları
tail -f /opt/netmon/instance/logs/app.log

# Nginx logları
tail -f /var/log/nginx/error.log

# Systemd logları
journalctl -u netmon -f
```

---

## 📚 Ek Kaynaklar

- [API Dokümantasyonu](API_DOKUMENTASYON.md)
- [Mimari Dökümantasyonu](ARCHITECTURE.md)
- [Güvenlik Rehberi](SECURITY_GUIDELINES.md)
