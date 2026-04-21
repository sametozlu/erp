# Mail Sistemi Geliştirme - Görev Planı

## Görev Özeti
Mevcut karmaşık mail sistemini iki farklı tipe ayırmak:
1. **Yönetim Maili**: Tüm tabloyu özet formatında, istatistiklerle
2. **Ekip Maili**: Sadece o ekibin işlerini detaylı format

## Todo Listesi

### 1. Backend - Mail Servis Fonksiyonları
- [ ] `generate_weekly_summary_html(week_start)` fonksiyonu yaz
  - [ ] Ekip bazlı özet istatistikleri hesapla
  - [ ] Günlük dağılım bilgisi
  - [ ] Toplam iş sayısı, tamamlanan, bekleyen
- [ ] `generate_team_detail_html(week_start, team_name)` fonksiyonu yaz
  - [ ] Personel bazlı iş listesi
  - [ ] Günlük iş detayları
  - [ ] Araç, not, dosya bilgileri
- [ ] `get_weekly_stats()` yardımcı fonksiyonu yaz

### 2. Backend - Template Dosyaları
- [ ] `templates/email_weekly_summary.html` oluştur
  - [ ] Özet istatistik kartı
  - [ ] Ekip bazlı özet tablosu
  - [ ] Günlük dağılım bölümü
  - [ ] Excel/PDF indirme linkleri
- [ ] `templates/email_team_detail.html` oluştur
  - [ ] Personel selamlama
  - [ ] Günlük iş kartları
  - [ ] Önemli notlar bölümü
  - [ ] Acil durum bilgisi
- [ ] `templates/email_components.html` oluştur
  - [ ] Ortak kart stili
  - [ ] İkon helper'ları
  - [ ] Renk kodları

### 3. Backend - API Endpoints
- [ ] `/api/mail/send_full_table` endpointi
  - [ ] POST data: week_start, options
  - [ ] Yönetim email listesi
  - [ ] Özet HTML üret
  - [ ] Mail gönder
- [ ] `/api/mail/send_team_detail` endpointi
  - [ ] POST data: week_start, team_name
  - [ ] Ekip email listesi (TeamMailConfig'den)
  - [ ] Detay HTML üret
  - [ ] Her personele özel mail
- [ ] `/api/mail/preview_summary` endpointi
  - [ ] GET: week_start
  - [ ] HTML önizleme döndür
- [ ] `/api/mail/preview_team_detail` endpointi
  - [ ] GET: week_start, team_name
  - [ ] HTML önizleme döndür

### 4. Frontend - Mail Modalı
- [ ] Yeni mail gönderim modalı tasarımı (plan.html)
  - [ ] Mail türü seçimi (radio: Yönetim/Ekip)
  - [ ] İçerik türü seçimi (radio: Özet/Detaylı)
  - [ ] Hafta seçici
  - [ ] Önizleme butonu
  - [ ] Gönder butonu
- [ ] Modal CSS stilleri
  - [ ] Responsive tasarım
  - [ ] Kart stili
  - [ ] İkon stilleri

### 5. Frontend - JavaScript
- [ ] `openMailModal()` fonksiyonu
- [ ] Mail türü değişiklik handler'ı
- [ ] `previewMail()` fonksiyonu
- [ ] `sendMail()` fonksiyonu
  - [ ] Loading state
  - [ ] Error handling
  - [ ] Toast bildirim
- [ ] `closeMailModal()` fonksiyonu

### 6. Entegrasyon
- [ ] Mevcut "Tablo Gönder" butonunu yeni modal'a bağla
- [ ] Excel export fonksiyonunu mail'e ekle
- [ ] PDF export fonksiyonunu mail'e ekle

### 7. Test
- [ ] Yönetim maili içeriğini kontrol et
- [ ] Ekip maili içeriğini kontrol et
- [ ] Attachment'ların doğru eklenmesi
- [ ] Responsive görünüm (mobil)
- [ ] Outlook uyumluluğu
- [ ] Hata durumları (mail server hatası, eksik veri)

---

## Teknik Detaylar

### API: Send Full Table

```python
@planner_bp.post("/api/mail/send_full_table")
@login_required
@planner_or_admin_required
def api_mail_send_full_table():
    data = request.get_json()
    week_start = parse_date(data.get("week_start"))
    include_excel = data.get("include_excel", True)
    include_pdf = data.get("include_pdf", False)
    
    # Yönetim email listesi
    recipients = get_management_emails()
    
    # Özet HTML üret
    html = generate_weekly_summary_html(week_start)
    
    # Excel/PDF attachment'ları hazırla
    attachments = []
    if include_excel:
        attachments.append(generate_weekly_excel(week_start))
    
    # Mail gönder
    for recipient in recipients:
        send_email_smtp(recipient, subject, html, attachments)
    
    return jsonify({"ok": True, "sent": len(recipients)})
```

### API: Send Team Detail

```python
@planner_bp.post("/api/mail/send_team_detail")
@login_required
@planner_or_admin_required
def api_mail_send_team_detail():
    data = request.get_json()
    week_start = parse_date(data.get("week_start"))
    team_name = data.get("team_name")
    
    # Ekip email listesi
    recipients = get_team_emails(team_name)
    
    # Detay HTML üret (her personel için ayrı)
    results = []
    for person in get_team_personnel(team_name):
        html = generate_team_detail_html(week_start, team_name, person)
        send_email_smtp(person.email, subject, html)
        results.append({"email": person.email, "sent": True})
    
    return jsonify({"ok": True, "results": results})
```

### Template: email_team_detail.html

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; background: #f8fafc; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; padding: 24px; border-radius: 12px 12px 0 0; }
        .content { background: white; padding: 24px; border-radius: 0 0 12px 12px; }
        .day-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
        .job-card { background: #f8fafc; border-radius: 6px; padding: 12px; margin: 8px 0; }
        .job-header { display: flex; justify-content: space-between; font-weight: bold; }
        .job-details { margin-top: 8px; font-size: 14px; color: #64748b; }
        .footer { text-align: center; padding: 20px; color: #64748b; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📅 Haftalık İş Planınız</h1>
            <p>{{ week_start }} - {{ week_end }}</p>
        </div>
        <div class="content">
            <p>Merhaba {{ person.full_name }},</p>
            <p>Bu hafta size atanan işler aşağıdadır:</p>
            
            {% for day in days %}
            <div class="day-card">
                <h3>📅 {{ day.date }} - {{ day.day_name }}</h3>
                {% for job in day.jobs %}
                <div class="job-card">
                    <div class="job-header">
                        <span>🏢 [{{ job.project_code }}] {{ job.project_name }}</span>
                        <span>⏰ {{ job.shift }}</span>
                    </div>
                    <div class="job-details">
                        <p>📍 {{ job.region }} 🚗 {{ job.vehicle }}</p>
                        <p>📝 {{ job.note }}</p>
                        {% if job.files %}
                        <p>📎 Ek: {{ job.files }}</p>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endfor %}
            
            {% if important_notes %}
            <div class="day-card" style="border-color: #f59e0b; background: #fffbeb;">
                <h3>⚠️ Önemli Notlar</h3>
                <ul>
                    {% for note in important_notes %}
                    <li>{{ note }}</li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}
        </div>
        <div class="footer">
            <p>📞 Acil durum: {{ emergency_phone }}</p>
        </div>
    </div>
</body>
</html>
```

---

## Bağımlılıklar
- Mevcut `send_email_smtp()` fonksiyonu
- Mevcut `create_mail_log()` fonksiyonu
- Mevcut `TeamMailConfig` modeli
- Mevcut Excel export fonksiyonları

## Notlar
- Yeni sistem mevcut sisteme paralel çalışacak
- Eski mailler silinmeyecek, kullanıcı tercihine göre seçilecek
- Attachment boyutu kontrol edilmeli (mail server limiti)
