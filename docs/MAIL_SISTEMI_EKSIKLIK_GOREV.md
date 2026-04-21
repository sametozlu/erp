# Mail Sistemi V2 - Eksiklikleri Giderme Görevi

## 📋 Görev Özeti

Bu görev, Mail Sistemi Geliştirme V2'deki eksik özellikleri tamamlamayı hedefler.

---

## 🎯 Tamamlanacak Görevler

### Görev 1: Tema Uyumluluğu Düzeltmesi

**Dosya:** `templates/mail_settings.html`

**Yapılacaklar:**
- [ ] Satır 57-58: Sabit renkleri tema değişkenlerine çevir
- [ ] `.status-ok` sınıfını tema uyumlu yap
- [ ] `.status-err` sınıfını tema uyumlu yap

**Değişiklik:**
```css
/* ÖNCE */
.status-ok { background: #dcfce7; color: #166534; }
.status-err { background: #fee2e2; color: #991b1b; }

/* SONRA */
.status-ok { 
  background: var(--status-success-bg); 
  color: var(--status-success-text); 
}
.status-err { 
  background: var(--status-danger-bg); 
  color: var(--status-danger-text); 
}
```

**Tahmini Süre:** 15 dakika

---

### Görev 2: Şablon Yönetimi API Endpointleri

**Dosya:** `routes/admin.py`

**Yapılacaklar:**
- [ ] `GET /api/mail/templates` - Şablonları listele
- [ ] `GET /api/mail/templates/<type>` - Tek şablon getir
- [ ] `PUT /api/mail/templates/<type>` - Şablon güncelle
- [ ] `POST /api/mail/templates/<type>/reset` - Varsayılana sıfırla

**API Yanıt Formatı:**
```json
{
  "ok": true,
  "templates": [
    {
      "type": "weekly",
      "name": "Haftalık Plan Maili",
      "subject": "Haftalık Plan - {{week_start}}",
      "heading": "Haftalık İş Planınız",
      "intro": "Merhaba {{person_name}},",
      "content": "..."
    }
  ]
}
```

**Tahmini Süre:** 2 saat

---

### Görev 3: Şablon Yönetimi UI

**Dosya:** `templates/mail_settings.html`

**Yapılacaklar:**
- [ ] "Şablonlar (Yakında)" sekmesini aktif et
- [ ] Mail türü seçici ekle
- [ ] Şablon alanlarını düzenlenebilir yap
- [ ] Kaydet/Sıfırla butonları ekle

**UI Yapısı:**
```html
<!-- SEKME 3: ŞABLONLAR -->
<div id="tab-templates" class="tab-pane">
  <div class="template-selector">
    <select id="template-type" class="input">
      <option value="weekly">Haftalık Plan Maili</option>
      <option value="team">Ekip Plan Maili</option>
      <option value="job">İş Atama Maili</option>
      <option value="task">Görev Bildirimi</option>
    </select>
  </div>
  
  <div class="template-fields">
    <label>Konu (Subject)
      <input class="input" id="template-subject" type="text">
    </label>
    <label>Başlık (Heading)
      <input class="input" id="template-heading" type="text">
    </label>
    <label>Giriş Metni (Intro)
      <textarea class="input" id="template-intro"></textarea>
    </label>
    <label>İçerik
      <textarea class="input" id="template-content" rows="10"></textarea>
    </label>
  </div>
  
  <div class="template-actions">
    <button class="btn primary" onclick="saveTemplate()">Kaydet</button>
    <button class="btn secondary" onclick="resetTemplate()">Varsayılana Sıfırla</button>
  </div>
</div>
```

**Tahmini Süre:** 4 saat

---

### Görev 4: Önizleme Sistemi

**Dosya:** `templates/mail_settings.html`

**Yapılacaklar:**
- [ ] "Önizleme (Yakında)" sekmesini aktif et
- [ ] Mail türü seçici ekle
- [ ] Tarih seçici ekle
- [ ] Canlı önizleme alanı ekle
- [ ] Mobil/Desktop görünüm toggle ekle
- [ ] Test mail gönderme özelliği ekle

**UI Yapısı:**
```html
<!-- SEKME 4: ÖNİZLEME -->
<div id="tab-preview" class="tab-pane">
  <div class="preview-controls">
    <select id="preview-type" class="input">
      <option value="weekly">Haftalık Plan</option>
      <option value="team">Ekip Planı</option>
      <option value="job">İş Atama</option>
    </select>
    <input type="date" id="preview-date" class="input">
    <button class="btn primary" onclick="generatePreview()">Önizleme Oluştur</button>
  </div>
  
  <div class="preview-tabs">
    <button class="tab-btn active" onclick="switchPreviewView('desktop')">Desktop</button>
    <button class="tab-btn" onclick="switchPreviewView('mobile')">Mobil</button>
    <button class="tab-btn" onclick="switchPreviewView('html')">HTML</button>
  </div>
  
  <div class="preview-container">
    <iframe id="preview-frame"></iframe>
  </div>
  
  <div class="preview-actions">
    <input type="email" id="preview-test-email" class="input" placeholder="Test maili alıcısı">
    <button class="btn secondary" onclick="sendTestMail()">Test Gönder</button>
  </div>
</div>
```

**Tahmini Süre:** 4 saat

---

### Görev 5: Excel Export Özelliği

**Dosya:** `templates/mail_settings.html` + `routes/admin.py`

**Yapılacaklar:**
- [ ] Log tablosuna "Excel İndir" butonu ekle
- [ ] Backend'de Excel export endpoint'i oluştur
- [ ] Excel dosyası formatını düzenle

**Backend Endpoint:**
```python
@admin_bp.get("/admin/mail-logs/export")
def export_mail_logs():
    """Excel export endpoint"""
    # Mevcut filtreleri al
    # Excel oluştur
    # Dosyayı döndür
```

**Frontend:**
```html
<button class="btn secondary" onclick="exportLogs()">
  📊 Excel İndir
</button>
```

**Tahmini Süre:** 2 saat

---

### Görev 6: cc_addr/bcc_addr Güvenli Atama

**Dosya:** `utils.py`

**Yapılacaklar:**
- [ ] Log verisi hazırlanırken None kontrolü yap

**Değişiklik:**
```python
# utils.py - create_mail_log fonksiyonu
log_data["cc_addr"] = cc_addrs if cc_addrs else None
log_data["bcc_addr"] = bcc_addrs if bcc_addrs else None
```

**Tahmini Süre:** 15 dakika

---

## 📅 Uygulama Planı

### Hafta 1: Temel Özellikler

| Gün | Görev | Çıktı |
|-----|-------|-------|
| 1 | Tema uyumluluğu | CSS değişkenleri |
| 1 | cc_addr/bcc_addr düzeltme | Güvenli atama |
| 2-3 | Şablon API | CRUD endpoint'leri |
| 4-5 | Şablon UI | Editör arayüzü |

### Hafta 2: Gelişmiş Özellikler

| Gün | Görev | Çıktı |
|-----|-------|-------|
| 1-2 | Önizleme sistemi | Canlı önizleme |
| 3 | Excel export | Download özelliği |
| 4 | Test ve düzeltmeler | Final testler |
| 5 | Dokümantasyon | Güncel doküman |

---

## ✅ Tamamlanma Kriterleri

1. Tema uyumlu CSS değişkenleri kullanılıyor
2. Şablonlar sekmesi aktif ve çalışıyor
3. Şablonlar kaydedilebiliyor ve varsayılana sıfırlanabiliyor
4. Önizleme sistemi çalışıyor
5. Excel export indirilebiliyor
6. Hata logları düzgün çalışıyor

---

## 🔗 İlgili Dokümanlar

- [Mail Sistemi Geliştirme V2](docs/MAIL_SISTEMI_GELISTIRME_V2.md)
- [Mail Sistemi V2 Kontrol Raporu](docs/MAIL_SISTEMI_GELISTIRME_V2_KONTROL.md)
