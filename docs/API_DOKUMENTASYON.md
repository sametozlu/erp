# API Dokümantasyonu

## Netmon Proje Takip Sistemi - API Referansı

**Versiyon:** 2.0  
**Son Güncelleme:** 2026-02-02

---

## 📋 Genel Bilgiler

### Base URL
```
http://localhost:5000/api
```

### Kimlik Doğrulama
Tüm API endpoint'leri session-based authentication kullanır. İsteklerde geçerli bir session cookie'si bulunmalıdır.

### CSRF Koruması
POST, PUT, DELETE isteklerinde `X-CSRF-Token` header'ı gereklidir.

```javascript
headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': document.getElementById('csrfToken').value
}
```

---

## 🔐 Kimlik Doğrulama

### POST /auth/login
Kullanıcı girişi yapar.

**Request Body:**
```json
{
    "username": "string",
    "password": "string"
}
```

**Response:**
```json
{
    "ok": true,
    "user": {
        "id": 1,
        "username": "admin",
        "role": "admin"
    }
}
```

### POST /auth/logout
Kullanıcı çıkışı yapar.

**Response:**
```json
{
    "ok": true
}
```

---

## 📊 Analytics API

### POST /api/analytics/query
İstatistik robotu sorgusu çalıştırır.

**Request Body:**
```json
{
    "date_range": {
        "start": "2026-01-01",
        "end": "2026-12-31"
    },
    "dimensions": ["project", "person"],
    "metrics": ["job_count", "work_hours"],
    "filters": {
        "project_ids": [1, 2, 3],
        "team_ids": [1]
    },
    "bucket": "month",
    "sort_key": "job_count",
    "sort_dir": "desc"
}
```

**Response:**
```json
{
    "ok": true,
    "rows": [
        {
            "project": "Proje A",
            "person": "Ali Veli",
            "job_count": 45,
            "work_hours": 120.5
        }
    ],
    "meta": {
        "dimensions": ["project", "person"],
        "metrics": ["job_count", "work_hours"]
    }
}
```

### POST /api/analytics/tops
En iyi/en kötü listelerini getirir.

**Request Body:**
```json
{
    "date_range": {
        "start": "2026-01-01",
        "end": "2026-12-31"
    },
    "filters": {},
    "limit": 10
}
```

### POST /api/analytics/cancel-overtime
İptal ve mesai istatistiklerini döner.

---

## 📋 Plans API

### GET /api/plan/cells
Belirli tarih aralığı için plan hücrelerini getirir.

**Query Parameters:**
- `start_date` (required): Başlangıç tarihi (YYYY-MM-DD)
- `end_date` (required): Bitiş tarihi (YYYY-MM-DD)
- `team_id` (optional): Ekip filtresi

### POST /api/plan/cell
Yeni hücre oluşturur veya mevcut hücreyi günceller.

**Request Body:**
```json
{
    "project_id": 1,
    "work_date": "2026-02-15",
    "shift": "Gündüz",
    "note": "Açıklama",
    "team_id": 1,
    "personnel_ids": [1, 2, 3]
}
```

### DELETE /api/plan/cell/{cell_id}
Hücreyi siler.

### POST /api/plan/cell/{cell_id}/cancel
Hücreyi iptal eder.

**Request Body:**
```json
{
    "reason": "İptal nedeni"
}
```

---

## 👥 Realtime API

### WebSocket Events

#### cell_update
Hücre güncellendiğinde yayınlanır.

```json
{
    "event": "cell_update",
    "data": {
        "cell_id": 123,
        "project_id": 1,
        "work_date": "2026-02-15"
    }
}
```

#### cell_lock
Hücre kilitlendiğinde/açıldığında yayınlanır.

#### voice_message
Ses mesajı gönderildiğinde yayınlanır.

---

## 📝 Tasks API

### GET /api/tasks
Görev listesini getirir.

### POST /api/tasks
Yeni görev oluşturur.

### PUT /api/tasks/{task_id}
Görevi günceller.

### POST /api/tasks/{task_id}/comment
Göreve yorum ekler.

---

## 🚗 Vehicles API

### GET /api/vehicles
Araç listesini getirir.

### POST /api/vehicles
Yeni araç ekler.

### PUT /api/vehicles/{vehicle_id}
Araç bilgilerini günceller.

---

## 👤 Users API (Admin)

### GET /api/admin/users
Kullanıcı listesini getirir (sadece admin).

### POST /api/admin/users
Yeni kullanıcı oluşturur.

### PUT /api/admin/users/{user_id}
Kullanıcı bilgilerini günceller.

### DELETE /api/admin/users/{user_id}
Kullanıcıyı pasif yapar (soft delete).

---

## 📬 Error Responses

Tüm hata yanıtları aşağıdaki formatta döner:

```json
{
    "ok": false,
    "error": "Hata mesajı"
}
```

### HTTP Durum Kodları

| Kod | Açıklama |
|-----|----------|
| 200 | Başarılı |
| 400 | Geçersiz istek |
| 401 | Kimlik doğrulama gerekli |
| 403 | Yetkisiz erişim |
| 404 | Kaynak bulunamadı |
| 500 | Sunucu hatası |

---

## 🔄 Rate Limiting

API istekleri için rate limiting uygulanmaktadır:
- 100 istek / dakika / kullanıcı

---

## 📚 Ek Kaynaklar

- [Deployment Rehberi](DEPLOYMENT_GUIDE.md)
- [Mimari Dökümantasyonu](ARCHITECTURE.md)
- [Güvenlik Rehberi](SECURITY_GUIDELINES.md)
