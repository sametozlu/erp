# Plan/Timesheet Sistemi Geliştirme Görevleri

## Mevcut Durum Analizi

### 1. Timesheet Excel (routes/planner.py:8734-8898)
**Mevcut Durum:**
- Personel bazlı haftalık rapor
- Şehir, proje kodu, alt proje, vardiya bilgisi içeriyor
- Emoji kullanımı mevcut (📍, ⏰, 🔸, ⚠️, 📝)
- Mesai (overtime) bilgisi var ama görsel olarak belirsiz

**Kullanıcı İsteği:**
- Vardiya kelimelerini kaldır
- Sadece şehir, günler ve çalışma detayı olsun
- Mesai saatleri işlensin (görünür şekilde)
- Tablo halinde, sade ve anlaşılır
- Simgeler gerek yok

---

### 2. Plan Excel (routes/planner.py:1024-1223)
**Mevcut Durum:**
- Haftalık plan Excel export
- "Vardiya: {shift}" formatında vardiya bilgisi
- "Araç: {vehicle_info}" formatında araç bilgisi
- "Not: {note}" formatında notlar
- Proje kodu, proje adı, sorumlu bilgileri

**Kullanıcı İsteği:**
- Vardiya yazısına gerek yok
- Çalışma saati, şehir ve çalışma detayı yeterli
- Tablo halinde, anlaşılır ve sade

---

### 3. Tablo Gönder Butonu (routes/realtime.py:1174-1280)
**Mevcut Durum:**
- `/api/table/snapshot` ile tablo HTML'i kaydediliyor
- `/api/table/send-email` ile mail gönderimi
- Kullanıcıdan manuel email adresi istiyor
- Tüm tabloyu gönderiyor

**Sorunlar:**
- Boş tablo geliyor (snapshot HTML'i tam yüklenmiyor olabilir)
- Ekipler şikayetçi - tablo formatı uygun değil
- Ekip bazlı mail atma özelliği yok

**Kullanıcı İsteği:**
- Düzgün tablo gelsin
- Sadece yazı olsun
- Ekip bazlı butonlar olsun (her ekip için ayrı mail adresi)
- Tıklanınca o ekibin işlerini tablodan kesip sadece o ekibe mail atsın

---

## Görev Detayları

### Görev 1: Timesheet Excel Düzenlemesi

**Dosya:** `routes/planner.py`
**Fonksiyon:** `timesheet_excel()` (satır 8737)

**Yapılacak Değişiklikler:**

1. Shift bilgisini kaldır (emoji + metin)
2. Mesai saatlerini belirgin şekilde göster (+{saat} saat mesai yerine)
3. Simgeleri kaldır (📍, ⏰, 🔸, ⚠️, 📝)
4. Tablo formatını sadeleştir

**Yeni Format:**
```
Personel | Firma | Seviye | 01.02 Pzt | 02.02 Sal | ... | Toplam Mesai
---------|-------|---------|-----------|-----------|-----|-------------
Ahmet Y. | ABC   | Müdür  | Ankara    | İstanbul  | ... | 4 saat
```

---

### Görev 2: Plan Excel Düzenlemesi

**Dosya:** `routes/planner.py`
**Fonksiyon:** `plan_export_excel()` (satır 1026)

**Yapılacak Değişiklikler:**

1. "Vardiya: {shift}" satırını kaldır
2. "Araç: {vehicle_info}" satırını kaldır
3. "Not: {note}" satırını basitleştir
4. Çalışma saatlerini göster (varsa)
5. Sadece şehir, proje ve çalışma detayı kalsın

**Yeni Format:**
```
İL  | PROJE           | SORUMLU | 01.02 Pzt | 02.02 Sal | ...
----|-----------------|---------|-----------|-----------|-----
ANK | 9025-006 ZTEE  | Mehmet  | Proje A   | Proje B   | ...
IST | 9025-007 XYZ   | Ali     | -         | Montaj    | ...
```

---

### Görev 3: Ekip Bazlı Mail Sistemi

**Dosya:** `routes/realtime.py`
**Fonksiyonlar:** `api_table_snapshot()`, `api_table_send_email()`

**Yapılacak Değişiklikler:**

1. Yeni endpoint: `/api/table/send-team-email`
   - `team_id` parametresi
   - `week_start` parametresi
   - Otomatik olarak TeamMailConfig'den email adreslerini al

2. Tabloyu ekip bazlı filtrele
   - Sadece o ekibin işlerini içeren tablo oluştur
   - HTML tabloyu temizle (gereksiz CSS class'ları kaldır)

3. Frontend değişiklikleri (templates/plan.html)
   - "Tablo Gönder" butonunun yanına ekip dropdown'ı ekle
   - Her ekip için ayrı buton veya dropdown seçeneği
   - Seçilen ekibin mail adresini otomatik doldur

---

### Görev 4: Boş Tablo Sorununu Çöz

**Olası Nedenler:**
1. `tablewrap` elementi doğru seçilmiyor olabilir
2. DOM yüklenmeden önce HTML alınıyor olabilir
3. CSS class'ları eksik geliyor olabilir

**Çözüm:**
1. Tablo HTML'ini direkt olarak backend'de oluştur (snapshot yerine)
2. Sade, inline CSS ile tablo oluştur
3. Email için optimize edilmiş HTML template kullan

---

## Teknik Notlar

### TeamMailConfig Model (models.py:120-127)
```python
class TeamMailConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)
    emails_json = db.Column(db.Text, nullable=False, default="[]")  # JSON list
    active = db.Column(db.Boolean, nullable=False, default=True)
```

Bu model zaten var, sadece kullanılmalı.

### Team Model (models.py:111-117)
```python
class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    signature = db.Column(db.String(400), nullable=False)
```

### PlanCell'de Ekip Bilgisi
`PlanCell.team_id` alanı ile hangi hücrenin hangi ekibe ait olduğu belirlenebilir.

---

## Öncelik Sırası

1. **Kritik:** Boş tablo sorununu çöz (çalışmayan özellik)
2. **Yüksek:** Timesheet Excel düzenlemesi (görsel çıktı önemli)
3. **Yüksek:** Plan Excel düzenlemesi
4. **Orta:** Ekip bazlı mail sistemi (yeni özellik)
5. **Düşük:** UI iyileştirmeleri

---

## Beklenen Çıktılar

### Timesheet Excel Örneği
```
╔══════════╦════════╦═════════╦══════════╦══════════╦══════════╦══════════╗
║ Personel ║ Firma  ║ Seviye  ║ 01.02 Pzt║ 02.02 Sal║ ...      ║ Toplam   ║
╠══════════╬════════╬═════════╬══════════╬══════════╬══════════╬══════════╣
║ Ahmet Y. ║ ABC    ║ Müdür   ║ Ankara   ║ İstanbul ║ ...      ║ 4 saat  ║
║ Mehmet K.║ XYZ    ║ Teknisyen║ -       ║ İzmir    ║ ...      ║ 2 saat  ║
╚══════════╩════════╩═════════╩══════════╩══════════╩══════════╩══════════╝
```

### Ekip Bazlı Mail Butonu UI
```
┌─────────────────────────────────────────────────────┐
│ [Excel] [Timesheet] [Ekip Gönder ▼]               │
├─────────────────────────────────────────────────────┤
│                    ▼ Ekip Seç                       │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 🔧 Elektrik Ekibi - elektrik@şirket.com         │ │
│ │ 🔧 Mekanik Ekibi - mekanik@şirket.com          │ │
│ │ 🔧 Yazılım Ekibi - yazilim@şirket.com          │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```
