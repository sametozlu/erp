# Synology Docker (Container Manager) Kurulum

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

## 5) Roller + Saha Portali
- Roller: `admin`, `planner`, `field`, `user`, `gözlemci`
  - `field`: sadece mobil portali gorur: `/me`
  - `admin/planner`: plan/admin ekranlarini gorur
- Varsayilan kullanicilar `init_users()` ile ilk acilista olusturulur (veritabani bossa).

### Saha kullanicisi olusturma
1) Admin/planlayici ile giris yap
2) `Tanımlar > Kullanıcılar` (`/admin/users`)
3) `Kullanıcı Ekle`:
   - `Rol = Saha (Field)`
   - Email + Sifre (opsiyonel kullanici adi)

### Sahaya is atama
1) `Plan` ekraninda ilgili hucreye cift tikla (Is Detayi modali)
2) `Saha Kullanıcısı (My Jobs)` alanindan kullanici sec
3) `Kaydet`
4) Saha kullanicisi telefondan giris yapinca `/me` altinda sadece kendi isleri listelenir.

### Saha raporlari
- Saha kullanicisi: is detayinda `Rapor / Geri Bildirim Gonder`
- Admin/planlayici: `Tanımlar > Saha Raporları` (`/admin/reports`)
- Yeni rapor geldiginde bildirim (zil) guncellenir ve SocketIO ile anlik event (`new_report`) yayini yapilir.

## 6) Hızlı Komut (SSH ile)
Klasöre gir:
`cd /volume1/docker/staff_planner`
Çalıştır:
`docker compose up -d --build`
Durdur:
`docker compose down`
Log:
`docker logs -f staff_planner`
