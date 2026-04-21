# 📧 MAİL SİSTEMİ ANALİZ ve DÜZELTME GÖREVİ

## 🔍 TESPİT EDİLEN SORUNLAR

### 1. Kritik: Veritabanı Bozuk (Database Corruption)
**Dosya:** `app.db` veya `planner.db`

**Hata:**
```
sqlite3.DatabaseError: database disk image is malformed
```

**Etki:** Tüm veritabanı işlemleri başarısız oluyor (mailler dahil)

**Çözüm:**
1. Mevcut veritabanını yedekle
2. Yeni veritabanı oluştur
3. Verileri taşı

### 2. Kritik: MailLog Modelinde `team_id` Eksik
**Dosya:** [`models.py`](models.py:227) - `MailLog` modeli

**Sorun:** `create_mail_log()` fonksiyonunda `log_data["team_id"]` kullanılıyor ama modelde bu alan tanımlı değil.

**Mevcut Model (eksik alan):**
```python
class MailLog(db.Model):
    team_id = db.Column(db.Integer, nullable=True)  # ❌ EKLENMELİ!
```

### 3. Orta: Mail Worker Çalışmıyor Olabilir
**Dosya:** [`app.py`](app.py) - `start_mail_worker()` fonksiyonu

**Kontrol Edilmeli:**
- Worker thread'i başlatılıyor mu?
- `process_mail_queue()` fonksiyonu çalışıyor mu?
- SMTP ayarları doğru mu?

### 4. Orta: Environment Import Hatası
**Dosya:** [`error.log`](error.log:65)

**Hata:**
```
NameError: name 'Environment' is not defined
```

**Neden:** utils.py'de jinja2'den Environment import edilmiş ama kullanımda sorun var.

---

## 📋 YAPILACAKLAR LİSTESİ

### AŞAMA 1: Acil Düzeltmeler

#### 1.1 Veritabanı Sorununu Çöz
```bash
# 1. Mevcut veritabanını yedekle
cp app.db app.db.backup
cp planner.db planner.db.backup

# 2. Veritabanını onarmayı dene
sqlite3 app.db ".dump" | sqlite3 app.db.new
mv app.db.new app.db

# 3. Veya tamamen yeniden oluştur
# (tüm veriler kaybolur!)
```

#### 1.2 MailLog Modelini Düzelt
[`models.py`](models.py:227) dosyasına `team_id` alanı ekle:

```python
class MailLog(db.Model):
    # ... mevcut alanlar ...
    team_id = db.Column(db.Integer, nullable=True, index=True)  # EKLE!
```

#### 1.3 Environment Import Sorununu Çöz
[`utils.py`](utils.py:23) - Import satırını kontrol et:
```python
from jinja2 import Environment, BaseLoader, select_autoescape, StrictUndefined
# ✓ Doğru görünüyor - Sorun başka yerde olabilir
```

---

### AŞAMA 2: Mail Sistemi Testi

#### 2.1 SMTP Ayarlarını Kontrol Et
Admin panelden veya config dosyasından:
- `host`: SMTP sunucu adresi
- `port`: Port (genellikle 587 veya 465)
- `user`: Kullanıcı adı
- `password`: Şifre
- `from_addr`: Gönderen adres
- `from_name`: Gönderen ismi

#### 2.2 Manuel Mail Test
```python
# Python ile test et
from utils import send_test_email, create_mail_log
send_test_email("test@alan.com")
```

#### 2.3 Mail Kuyruğunu Kontrol Et
http://127.0.0.1:5000/admin/mail-queue adresine git:
- Bekleyen (pending) mail var mı?
- Hatalı (failed) mail var mı?
- Hata mesajları ne diyor?

---

### AŞAMA 3: Kod Düzeltmeleri

#### 3.1 `create_mail_log()` Fonksiyonu
[`utils.py`](utils.py:1001) - `team_id` referansını düzelt:

```python
# Eski (hatalı):
if not log_data["team_id"] and log_data.get("team_name"):

# Yeni (doğru - modelde team_id yoksa bu satırı kaldır veya düzelt):
if not hasattr(MailLog, 'team_id') and log_data.get("team_name"):
    # veya sadece try-catch ile gizle
```

#### 3.2 Mail Worker'ı Etkinleştir
[`app.py`](app.py) dosyasında:

```python
# Worker'ı başlat
if __name__ == '__main__':
    start_mail_worker(app)  # ← Bu satır var mı?
    app.run(...)
```

---

## 📊 TEST SENARYOLARI

### Test 1: Basit Mail Gönderimi
```python
from services.mail_service import MailService

# Test maili gönder
result = MailService.send(
    mail_type="test",
    recipients="test@alan.com",
    subject="Test Mail",
    html="<h1>Test</h1><p>Bu bir test mailidir.</p>",
)
print("Kuyruğa eklendi:", result)
```

### Test 2: Kuyruk İşleme
```python
from services.mail_service import MailService
from app import create_app

app = create_app()
with app.app_context():
    MailService.process_queue(app)
```

### Test 3: Admin Panel
1. http://127.0.0.1:5000/admin/mail-queue aç
2. "Şimdi İşle" butonuna tıkla
3. Sonuçları gözlemle

---

## 🎯 BAŞARI KRİTERLERİ

- [ ] Veritabanı sorunsuz çalışıyor
- [ ] MailQueue tablosu oluşturulmuş ve erişilebilir
- [ ] MailLog tablosu `team_id` alanını içeriyor
- [ ] Test maili başarıyla gönderiliyor
- [ ] Admin panelde mail kuyruğu görünüyor
- [ ] Bekleyen mailler işleniyor

---

## 📌 NOTLAR

1. **Yedekleme:** Herhangi bir değişiklik yapmadan önce veritabanını yedekleyin
2. **Sıralama:** Aşama 1'deki adımları sırayla izleyin
3. **Test:** Her düzeltmeden sonra sistemi test edin

---

## 🔗 İLGİLİ DOSYALAR

| Dosya | Açıklama |
|-------|----------|
| [`models.py`](models.py) | MailLog ve MailQueue modelleri |
| [`utils.py`](utils.py) | Mail gönderme fonksiyonları |
| [`services/mail_service.py`](services/mail_service.py) | Asenkron mail servisi |
| [`routes/admin_mail_queue.py`](routes/admin_mail_queue.py) | Admin mail kuyruğu sayfası |
| [`templates/admin_mail_queue.html`](templates/admin_mail_queue.html) | Admin mail kuyruğu şablonu |
| [`app.py`](app.py) | Uygulama giriş noktası |
