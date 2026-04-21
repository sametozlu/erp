# 📧 Mail Şablon Sistemi - Detaylı Görev Dokümanı

## 🎯 Genel Bakış

| Özellik | Değer |
|---------|-------|
| **Versiyon** | v1.0 |
| **Durum** | Planlama Aşamasında |
| **Öncelik** | Yüksek |
| **Tahmini Süre** | 4-6 saat |

---

## 📋 Görev Kapsamı

### 1. Mevcut Durum Analizi

#### 📁 Sistemde Bulunan Mail Şablonları

| # | Şablon Adı | Dosya/Konum | Açıklama |
|---|------------|-------------|----------|
| 1 | `weekly` | `routes/admin.py` - DEFAULT_TEMPLATES | Haftalık Plan Maili |
| 2 | `team` | `routes/admin.py` - DEFAULT_TEMPLATES | Ekip Plan Maili |
| 3 | `job` | `routes/admin.py` - DEFAULT_TEMPLATES | İş Atama Maili |
| 4 | `task` | `routes/admin.py` - DEFAULT_TEMPLATES | Görev Bildirimi |
| 5 | `DEFAULT_JOB_MAIL_*` | `utils.py` | İş detaylı mail (hücre bazlı) |
| 6 | `DEFAULT_BULK_TEAM_MAIL_*` | `utils.py` | Toplu ekip maili |

#### 🔧 Mevcut API Endpoints

```
GET    /api/mail/templates              → Tüm şablonları listele
GET    /api/mail/templates/<type>       → Tek şablon getir
PUT    /api/mail/templates/<type>       → Şablon güncelle
POST   /api/mail/templates/<type>       → Şablon güncelle (alternatif)
POST   /api/mail/templates/<type>/reset → Varsayılana sıfırla
```

#### 📊 Mevcut Veritabanı Yapısı

**MailTemplate Model** (`models.py:357-366`):
```python
class MailTemplate(db.Model):
    id                → Integer, primary_key
    name              → String(120), unique, NOT NULL
    subject_template  → Text, NOT NULL
    heading_template  → Text, nullable
    intro_template    → Text, nullable
    body_template     → Text, NOT NULL
    is_default        → Boolean, NOT NULL
    created_at        → DateTime
    updated_at        → DateTime
```

---

## 🎯 Kullanıcı Talepleri

### ✅ Talep 1: Tüm Maillerin Şeklini Düzenleme
> "Sistemde ki tüm maillerin şeklini düzenlemek istiyorum"

**Detaylar:**
- [ ] Header/Footer stillerini özelleştirilebilir yap
- [ ] Renk şemalarını tema ile uyumlu hale getir
- [ ] Font, boyut, padding gibi CSS değerlerini değiştir
- [ ] Logo ve kurumsal bilgileri eklenebilir yap

### ✅ Talep 2: Şablon Seçimi ve Önizleme
> "Sistemde gönderilen tüm mailleri seçeneklere koysun ve var olan görüntüyü eklesin üzerindne düzeltme yapmamı sağlayacak bir sitem olsun"

**Detaylar:**
- [ ] Mevcut gönderilen maillerin listesini göster
- [ ] Her mail türü için ayrı şablon seçenekleri sun
- [ ] Canlı önizleme penceresi ekle
- [ ] Gerçek veri ile önizleme yapabil
- [ ] HTML editörü ile düzenleme yapabil

---

## 🔧 Yapılacak İşler

### 📌 Aşama 1: Analiz ve Planlama (30 dk)

- [ ] **A1.1** Mevcut `email_base.html` şablonunu analiz et
- [ ] **A1.2** `utils.py` içindeki mail fonksiyonlarını incele
- [ ] **A1.3** `routes/admin.py` template API'sini gözden geçir
- [ ] **A1.4** Hangi maillerin hangi şablonu kullandığını haritala

### 📌 Aşama 2: Şablon Seçim Arayüzü (1 saat)

- [ ] **A2.1** Mail Settings sayfasına "Şablonlar" tabi genişlet
  - Mevcut: 4 tab (SMTP, Log, Şablonlar, Önizleme)
  - Hedef: Her mail türü için ayrı seçim

- [ ] **A2.2** Şablon seçim modalı oluştur
  ```
  ┌─────────────────────────────────────────────┐
  │  Mail Türü Seçin                           │
  ├─────────────────────────────────────────────┤
  │  ○ Haftalık Plan Maili (weekly)           │
  │  ○ Ekip Plan Maili (team)                  │
  │  ○ İş Atama Maili (job)                    │
  │  ○ Görev Bildirimi (task)                  │
  │  ○ İş Detaylı Mail (cell)                  │
  │  ○ Toplu Ekip Maili (bulk)                  │
  └─────────────────────────────────────────────┘
  ```

- [ ] **A2.3** Seçilen şablonun alanlarını göster
  - Subject (Konu)
  - Heading (Başlık)
  - Intro (Giriş)
  - Body (İçerik)

### 📌 Aşama 3: Önizleme Sistemi (1.5 saat)

- [ ] **A3.1** "Test Mail Gönder" butonu ekle
  - Admin kendine test maili gönderebilmeli
  - Seçilen şablonu gerçek olarak gönderebilmeli

- [ ] **A3.2** Iframe tabanlı önizleme
  - Mevcut: `mailPreviewModal` iframe
  - Genişlet: Veri ile doldurulmuş önizleme

- [ ] **A3.3** Jinja2 değişkenlerini highlight et
  ```
  {{ person_name }}     → Kullanıcı adı
  {{ week_start }}       → Hafta başlangıcı
  {{ team_name }}       → Ekip adı
  {{ project_name }}    → Proje adı
  ```

### 📌 Aşama 4: HTML Editör Entegrasyonu (1 saat)

- [ ] **A4.1** SimpleMDE/Marked editör kurulumu
  - Güvenlik: HTML sanitization
  - Mail güvenliği için HTML escape

- [ ] **A4.2** Şablon alanlarını editöre bağla
  - Subject (text input)
  - Heading (text input)
  - Intro (textarea)
  - Body (WYSIWYG editor)

- [ ] **A4.3** Değişiklikleri kaydetme
  - Otomatik kaydetme seçeneği
  - Manuel kaydetme butonu
  - İptal etme

### 📌 Aşama 5: Varsayılan Şablon Yönetimi (30 dk)

- [ ] **A5.1** Şablonu varsayılana sıfırla
  - API endpoint hazır: `/api/mail/templates/<type>/reset`
  - UI: "Varsayılana Sıfırla" butonu

- [ ] **A5.2** Versiyon kontrolü
  - Değişiklik tarihi
  - Kim tarafından değiştirildi

- [ ] **A5.3** Şablon export/import
  - JSON olarak dışa aktar
  - JSON olarak içe aktar

---

## 📁 Değiştirilecek Dosyalar

| # | Dosya | Değişiklik Türü | Açıklama |
|---|-------|-----------------|----------|
| 1 | `templates/mail_settings.html` | Genişletme | Şablon seçim UI |
| 2 | `routes/admin.py` | API Genişletme | Yeni endpoints |
| 3 | `models.py` | Model Genişletme | Şablon metadata |
| 4 | `utils.py` | Şablon Genişletme | Varsayılan şablonlar |
| 5 | `templates/email_base.html` | Genişletme | Özelleştirilebilir yapı |
| 6 | `static/js/mail_settings.js` | Yeni | Şablon yönetim JS |

---

## 🎨 Tasarım Önerileri

### Şablon Editörü Layout

```
┌────────────────────────────────────────────────────────────┐
│ 📧 Mail Şablonları                              [Yardım]   │
├────────────────────────────────────────────────────────────┤
│  [weekly]  [team]  [job]  [task]  [cell]  [bulk]          │
├────────────────────────────────────────────────────────────┤
│  Konu:                                                  │
│  ┌────────────────────────────────────────────────────┐  │
│  │ [{{ project_code }}] {{ site_code }} - İş Ataması │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Başlık:                                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Yeni İş Ataması                                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Giriş:                                                 │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Merhaba {{ person_name }},                         │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  İçerik:                                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  │  │
│  │ WYSIWYG Editor burada                             │  │
│  │ ...                                                │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │ 💾 Kaydet    │ │ 🔄 Sıfırla   │ │ 👁️ Önizle       │ │
│  └──────────────┘ └──────────────┘ └──────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

---

## 📋 Test Senaryoları

### ✅ Pozitif Testler

| # | Test | Beklenen Sonuç |
|---|------|----------------|
| 1 | Şablon düzenleme açılır | Tüm alanlar görünür |
| 2 | Değişkenler render edilir | `{{ person_name }}` → "Ahmet" |
| 3 | Kaydetme başarılı | Toast mesajı gösterir |
| 4 | Varsayılana sıfırlama | Orijinal değerler gelir |
| 5 | Önizleme açılır | Iframe içinde render edilmiş HTML |
| 6 | Test mail gönderilir | Mail gelir |

### ❌ Negatif Testler

| # | Test | Beklenen Sonuç |
|---|------|----------------|
| 1 | Geçersiz HTML kaydetme | Hata mesajı, kayıt başarısız |
| 2 | Boş alan bırakma | Zorunlu alan uyarısı |
| 3 | Yetkisiz erişim | 403 Forbidden |

---

## 🚀 Geliştirme Adımları

### Adım 1: Mevcut Kodu Analiz Et
```bash
# Dosyaları incele
grep -n "mail" templates/mail_settings.html
grep -n "DEFAULT_" routes/admin.py
grep -n "template" models.py
```

### Adım 2: Development Ortamını Hazırla
```bash
# Python virtual environment
source .venv/Scripts/activate

# Flask server başlat
python app.py
```

### Adım 3: İteratif Geliştirme
1. UI bileşenlerini oluştur
2. API ile bağla
3. Test et
4. Sonraki bileşene geç

---

## 📊 Başarı Kriterleri

| Kriter | Metrik | Hedef |
|--------|--------|-------|
| Kullanılabilirlik | Şablon düzenleme süresi | < 2 dakika |
| Performans | Sayfa yüklenme süresi | < 500ms |
| Güvenlik | XSS vulnerability | 0 |
| Erişilebilirlik | Tüm form alanları label ile | %100 |

---

## 📅 Zaman Çizelgesi

| Aşama | Süre | Toplam |
|-------|------|--------|
| Analiz | 30 dk | 0:30 |
| Şablon Seçim UI | 1 saat | 1:30 |
| Önizleme Sistemi | 1.5 saat | 3:00 |
| HTML Editör | 1 saat | 4:00 |
| Varsayılan Yönetimi | 30 dk | 4:30 |
| Test ve Düzeltmeler | 1 saat | 5:30 |

**Toplam Tahmini Süre: ~6 saat**

---

## 🔗 İlgili Dokümanlar

- [Mail Sistemi Geliştirme V2](MAIL_SISTEMI_GELISTIRME_V2.md)
- [API Dokümantasyonu](API_DOKUMENTASYON.md)
- [Mail Log Sistemi Analizi](MAIL_LOG_SISTEMI_ANALIZI.md)
- [Mevcut Mail Settings UI](templates/mail_settings.html)

---

## ❓ Sorular ve Belirsizlikler

1. **Q: Kaç farklı mail türü olacak?**
   - A: Mevcut 6 tür + gelecekte eklenebilir

2. **Q: Tema renkleri maile uygulanacak mı?**
   - A: Evet, header/footer renkleri tema uyumlu olmalı

3. **Q: Şablon versiyonlaması gerekiyor mu?**
   - A: Şimdilik hayır, sonradan eklenebilir

---

## 📝 Notlar

- Güvenlik için tüm HTML inputları sanitize edilmeli
- Jinja2 template injection'a karşı önlem alınmalı
- Mail gönderiminde hata yönetimi güçlendirilmeli
