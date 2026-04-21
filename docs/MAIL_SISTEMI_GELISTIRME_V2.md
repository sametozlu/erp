# Mail Sistemi Geliştirme Görevi v2

## Genel Bakış

Bu görev, mevcut mail sisteminin iyileştirilmesi ve standardize edilmesini hedeflemektedir. Sistemde farklı türlerde mailler gönderilmektedir ancak:
- Her mail türü için farklı HTML şablonları kullanılmaktadır
- Merkezi bir şablon yönetimi bulunmamaktadır
- Log kayıtları sınırlıdır ve standardize edilmemiştir
- Mail ayarları sayfasında kapsamlı bir sekme yapısı eksiktir

---

## 1. Mail Şablonlarının Standartlaştırılması

### 1.1 Mevcut Mail Türleri

Sistemde aşağıdaki mail türleri gönderilmektedir:

| Tür | Açıklama | Mevcut Dosya |
|-----|----------|--------------|
| **weekly** | Haftalık plan maili | `/api/send_weekly_emails` |
| **team** | Ekip bazlı plan maili | `/api/send_team_emails` |
| **job** | İş atama maili | `/api/send_job_email` |
| **bulk_team** | Toplu ekip maili | `/api/mail/send_bulk` |
| **test** | SMTP test maili | `/mail/settings/test` |
| **preview** | Önizleme maili | Çeşitli preview endpointleri |
| **project_added** | Yeni proje eklendi | `/api/project_added_email` |
| **subproject_added** | Alt proje eklendi | Planner route |
| **task_created** | Görev oluşturuldu | `/api/tasks` |
| **task_assigned** | Görev atandı | `/api/tasks` |
| **task_feedback** | Göreve geri bildirim | `/api/tasks` |
| **task_status_changed** | Görev durumu değişti | `/api/tasks` |

### 1.2 Standart Mail Bileşenleri

Tüm maillerde aşağıdaki bileşenler standart olmalıdır:

```
┌─────────────────────────────────────────┐
│           EMAIL BASE TEMPLATE            │
├─────────────────────────────────────────┤
│  1. Header (Logo + Company Name)         │
│  2. Title/Subject                        │
│  3. Intro Text                          │
│  4. Main Content (Dynamic Content)      │
│  5. Action Button (Opsiyonel)           │
│  6. Footer (Company Info + Disclaimer)  │
└─────────────────────────────────────────┘
```

### 1.3 Yapılacaklar

1. **Tüm mail şablonlarını tek bir `email_base.html` şablonunda birleştir**
2. **Outlook uyumlu HTML kurallarını uygula**:
   - Tablo tabanlı layout
   - Inline CSS (harici CSS kullanma)
   - Fixed width container (600px önerilen)
   - Arial/Helvetica font family
   - Background-color kullan, gradient kullanma
   - Border-radius yerine border kullan
3. **Renk şemasını standardize et**:
   - Primary: #3b82f6 (Blue)
   - Secondary: #64748b (Gray)
   - Success: #22c55e (Green)
   - Warning: #f59e0b (Orange)
   - Danger: #ef4444 (Red)

---

## 2. Mail Ayarları Sayfasına Sekmeler Ekleme

### 2.1 Yeni Sekme Yapısı

Mail Ayarları sayfasına aşağıdaki sekmeler eklenecektir:

```
┌──────────────────┬──────────────────────┬──────────────────────┬──────────────────────┐
│  SMTP Ayarları   │  Varsayılan Şablon   │  Gönderim Logları    │  Önizleme            │
├──────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│  Host, Port,     │  Tüm mail türleri   │  Son 100 gönderim    │  Örnek mailler       │
│  User, Password,  │  için şablon        │  ve durumları        │  gösterimi           │
│  From, CC, BCC   │  özelleştirme        │                      │                      │
└──────────────────┴──────────────────────┴──────────────────────┴──────────────────────┘
```

### 2.2 Sekme 1: SMTP Ayarları (Mevcut)

```
Alanlar:
├── Host: smtp.sunucu.com
├── Port: 465/587
├── Kullanıcı: email@sunucu.com
├── Şifre: ••••••••
├── Gönderen (From): "İsim <email@sunucu.com>"
├── CC: cc@sunucu.com
├── BCC: bcc@sunucu.com
├── SSL/TLS: [x] SSL [ ] TLS
└── Test Mail: [input] [Gönder Butonu]
```

### 2.3 Sekme 2: Varsayılan Şablonlar

Her mail türü için şablon özelleştirme:

```
Mail Türü Seçici:
├── Haftalık Plan Maili
├── Ekip Plan Maili
├── İş Atama Maili
├── Toplu Ekip Maili
├── Görev Bildirimleri
└── Proje Bildirimleri

Şablon Alanları:
├── Konu (Subject): "Haftalık Plan - {{week_start}}"
├── Başlık (Heading): "Haftalık İş Planınız"
├── Giriş Metni (Intro): "Merhaba {{person_name}},"
└── İçerik: [Rich Text Editor]
```

### 2.4 Sekme 3: Gönderim Logları

```
Filtreleme:
├── Tarih Aralığı: [____] - [____]
├── Mail Türü: [Tümü v]
├── Durum: [Tümü v] (Başarılı/Başarısız)
└── Arama: [___________]

Tablo Başlıkları:
├── Tarih/Saat
├── Tür
├── Alıcı
├── Konu
├── Durum
├── Hata (varsa)
└── İşlem

Eylemler:
├── Excel İndir
└── Detay Göster
```

### 2.5 Sekme 4: Önizleme

```
Önizleme Alanı:
├── Mail Türü Seç: [Haftalık Plan v]
├── Tarih Seç: [____]
└── [Önizleme Oluştur]

Canlı Önizleme:
├── Desktop Görünümü
├── Mobil Görünümü
└── Raw HTML

Test Gönderimi:
├── Alıcı Email: [___________]
└── [Test Gönder]
```

---

## 3. Kapsamlı Mail Log Sistemi

### 3.1 Genişletilmiş MailLog Modeli

```python
class MailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    # İdentifikasyon
    mail_type = db.Column(db.String(50), nullable=False)  # weekly/team/job/bulk/test/project/task
    kind = db.Column(db.String(30), nullable=False)  # send/test/preview

    # Durum
    ok = db.Column(db.Boolean, nullable=False, default=False)
    error_code = db.Column(db.String(50), nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    # İçerik
    to_addr = db.Column(db.String(500), nullable=False)  # JSON array
    cc_addr = db.Column(db.String(500), nullable=True)
    bcc_addr = db.Column(db.String(500), nullable=True)
    subject = db.Column(db.String(255), nullable=False)
    body_preview = db.Column(db.Text, nullable=True)  # İlk 1000 karakter

    # İlişkili Veriler
    week_start = db.Column(db.Date, nullable=True)
    team_id = db.Column(db.Integer, nullable=True)
    team_name = db.Column(db.String(120), nullable=True)
    project_id = db.Column(db.Integer, nullable=True)
    job_id = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, nullable=True)  # Gönderen kullanıcı

    # Meta
    meta_json = db.Column(db.Text, nullable=True)  # Ek bilgiler
    attachments_count = db.Column(db.Integer, default=0)
    body_size_bytes = db.Column(db.Integer, default=0)

    # Zaman Damgası
    sent_at = db.Column(db.DateTime, nullable=True)
```

### 3.2 Loglanacak Bilgiler

Her mail gönderiminde:

```
✓ Zaman Damgası
  - created_at: Log oluşturulma
  - sent_at: Mail gönderilme (varsa)

✓ Alıcı Bilgileri
  - to_addr: Ana alıcı (JSON array)
  - cc_addr: CC alıcıları
  - bcc_addr: BCC alıcıları
  - recipient_count: Toplam alıcı sayısı

✓ İçerik
  - subject: Mail konusu
  - body_preview: İçerik önizleme (ilk 1000 karakter)
  - body_size_bytes: İçerik boyutu
  - attachments_count: Ek sayısı

✓ İlişkili Kayıtlar
  - mail_type: Mail türü
  - week_start: İlgili hafta
  - team_id/team_name: İlgili ekip
  - project_id: İlgili proje
  - job_id: İlgili iş/görev
  - user_id: Gönderen kullanıcı

✓ Durum
  - ok: Başarılı mı
  - error_code: Hata kodu
  - error_message: Hata mesajı

✓ Meta
  - meta_json: Ek JSON verileri
```

### 3.3 Log Görüntüleme Sayfası

```
URL: /reports/mail-log

Özellikler:
├── Tarih Filtresi
├── Tür Filtresi
├── Durum Filtresi
├── Arama (to_addr, subject)
├── Sayfalama
├── Excel İndirme
└── Detay Modalı

Detay Modalı:
├── Log ID ve Tarih
├── Mail Türü ve Türü
├── Gönderen Kullanıcı
├── Alıcı Listesi (tümü)
├── Konu
├── İçerik Önizleme
├── Ekler
├── Durum ve Hata (varsa)
├── Meta Verileri
└── İlişkili Kayıt Linkleri
```

---

## 4. Teknik Gereksinimler

### 4.1 Database Migration

```python
# Migration script: migration_enhanced_mail_logs.py

def upgrade():
    # Mevcut MailLog tablosunu genişlet
    op.add_column('mail_log', sa.Column('mail_type', sa.String(50), nullable=True))
    op.add_column('mail_log', sa.Column('error_code', sa.String(50), nullable=True))
    op.add_column('mail_log', sa.Column('cc_addr', sa.String(500), nullable=True))
    op.add_column('mail_log', sa.Column('bcc_addr', sa.String(500), nullable=True))
    op.add_column('mail_log', sa.Column('body_preview', sa.Text, nullable=True))
    op.add_column('mail_log', sa.Column('attachments_count', sa.Integer, default=0))
    op.add_column('mail_log', sa.Column('body_size_bytes', sa.Integer, default=0))
    op.add_column('mail_log', sa.Column('sent_at', sa.DateTime, nullable=True))
    op.add_column('mail_log', sa.Column('user_id', sa.Integer, nullable=True))

    # Mevcut verileri güncelle
    op.execute("UPDATE mail_log SET mail_type = kind WHERE mail_type IS NULL")
```

### 4.2 API Endpointleri

```
GET  /api/mail/settings          # Mail ayarlarını getir
POST /api/mail/settings          # Mail ayarlarını kaydet
POST /api/mail/settings/test     # Test mail gönder

GET  /api/mail/logs              # Logları listele (filtrelerle)
GET  /api/mail/logs/<id>         # Log detayı
GET  /api/mail/logs/<id>/resend  # Tekrar gönder

GET  /api/mail/templates         # Şablonları listele
PUT  /api/mail/templates/<id>    # Şablon güncelle
POST /api/mail/templates/<id>/reset  # Varsayılana sıfırla

POST /api/mail/preview           # Önizleme oluştur
POST /api/mail/send              # Mail gönder
```

### 4.3 Frontend Bileşenleri

```
Bileşenler:
├── MailSettingsTabs.vue          # Sekme yapısı
├── MailSettingsSMTP.vue         # SMTP ayarları formu
├── MailSettingsTemplates.vue    # Şablon editörü
├── MailSettingsLogs.vue         # Log tablosu
├── MailSettingsPreview.vue      # Önizleme bileşeni
├── MailLogTable.vue             # Log tablosu
├── MailLogDetailModal.vue       # Log detay modalı
├── MailTemplateEditor.vue       # Şablon editörü
└── MailPreviewWindow.vue        # Önizleme penceresi
```

---

## 5. Uygulama Adımları

### Adım 1: Database Migration
- [ ] MailLog tablosunu genişlet
- [ ] Yeni indeksleri oluştur
- [ ] Mevcut verileri güncelle

### Adım 2: Backend API
- [ ] Loglama fonksiyonlarını güncelle
- [ ] Yeni API endpointleri ekle
- [ ] Template rendering'i standardize et
- [ ] Error handling'i iyileştir

### Adım 3: Frontend - Mail Ayarları Sayfası
- [ ] Sekme yapısını oluştur
- [ ] SMTP Ayarları sekmesini güncelle
- [ ] Varsayılan Şablonlar sekmesini ekle
- [ ] Gönderim Logları sekmesini ekle
- [ ] Önizleme sekmesini ekle

### Adım 4: Log Görüntüleme Sayfası
- [ ] Gelişmiş filtreleme
- [ ] Detay modalı
- [ ] Excel export
- [ ] Sayfalama

### Adım 5: Test ve Entegrasyon
- [ ] Tüm mail türlerini test et
- [ ] Log kayıtlarını doğrula
- [ ] Performans testi
- [ ] Hata senaryolarını test et

---

## 6. Öncelikler

| Öncelik | İş | Açıklama |
|---------|-----|----------|
| P1 | Standart mail şablonu | Tüm mailler için ortak base template |
| P1 | Genişletilmiş log modeli | Kapsamlı log kayıtları |
| P2 | Sekme yapısı | Mail ayarlarına sekmeler |
| P2 | Log görüntüleme | Gelişmiş log ekranı |
| P3 | Template yönetimi | Admin şablon düzenleme |
| P3 | Önizleme sistemi | Canlı önizleme |

---

## 7. Notlar

- Mevcut `create_mail_log()` fonksiyonu güncellenecek
- Tüm mail gönderim noktaları güncellenmeli
- Büyük mailler için body_preview sınırlandırılmalı
- Log tablosu için partition düşünülmeli (büyüme durumunda)
