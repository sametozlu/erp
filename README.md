# Synology Docker (Container Manager) Kurulum

## Her bilgisayardan giriş (domain almadan)

Bu projeyi ücretsiz olarak Render'a deploy ederek tek bir URL ile her bilgisayardan açabilirsin.

1. [Render Dashboard](https://dashboard.render.com/) > **New +** > **Blueprint**
2. GitHub repo olarak `sametozlu/erp` seç
3. Render, repodaki `render.yaml` dosyasını otomatik algılar
4. Deploy tamamlanınca URL: `https://stafff-erp.onrender.com`
5. Giriş ekranı: `https://stafff-erp.onrender.com/login`

## 1) Dosyaları NAS'a kopyala
Bu klasörü NAS üzerinde örnek olarak şuraya koy:
`/volume1/docker/staff_planner`

Klasör içinde şu dosyalar olmalı:
- app.py
- templates/
- instance/planner.db
- requirements.txt
- Dockerfile
- docker-compose.yml

## 2) Container Manager ile çalıştırma (Önerilen: Project)
1. DSM > **Container Manager** > **Project (Proje)** > **Create**
2. "docker-compose.yml" dosyasının bulunduğu klasörü seç
3. Project adı ver (ör. staff_planner)
4. Deploy

## 3) Erişim
Tarayıcıdan:
- LAN: `http://NAS_IP:8888`

## 4) Notlar
- Veritabanı `instance/planner.db` dosyasıdır. Compose içinde `./instance:/app/instance` mount edildiği için kalıcıdır.
- Port değiştirmek istersen `docker-compose.yml` içindeki `8888:5000` değerini değiştir.

## 5) Hızlı Komut (SSH ile)
Klasöre gir:
`cd /volume1/docker/staff_planner`
Çalıştır:
`docker compose up -d --build`
Durdur:
`docker compose down`
Log:
`docker logs -f staff_planner`
