# 🚀 Mail Şablon Sistemi Kaldırma Planı

**Tarih:** 09.02.2026  
**Durum:** ✅ TAMAMLANDI (09.02.2026)  
**Hedef:** Mail şablon sistemini tamamen kaldırıp, sabit ve kişiselleştirilmiş HTML mail şablonları oluşturmak.

---

## 📋 ÖZET

Mail şablonları sistemi gereksiz karmaşıklık oluşturdu. Bu plan ile:
1. MailTemplate modeli ve ilgili route'lar kaldırılacak
2. Admin panelindeki şablon yönetimi kaldırılacak
3. Sabit, kişiselleştirilmiş HTML şablonları utils.py'de fonksiyon olarak tanımlanacak
4. Mail gönderimler doğrudan bu sabit fonksiyonları kullanacak

---

## 🎯 AŞAMA 1: KALDIRMA İŞLEMLERİ

### 1.1 Model Temizliği
| Dosya | Değişiklik | Durum |
|-------|------------|-------|
| `models.py:358-367` | `MailTemplate` sınıfını yorum satırına al (silme) | [x] |

### 1.2 Import Temizliği
| Dosya | Satır | Değişiklik | Durum |
|-------|-------|------------|-------|
| `app.py:61` | `from models import ...MailTemplate...` | MailTemplate'i import'tan kaldır | [x] |
| `app.py:920-969` | MailTemplate seed kodları | Yorum satırına al | [x] |
| `routes/admin.py:3` | `from models import MailLog, MailTemplate` | MailTemplate'i kaldır | [x] |
| `services/mail_service.py:9` | `from models import MailTemplate` | import'u kaldır | [x] |
| `utils.py:1118-1136` | `_get_default_mail_template()`, `_render_mail_template()` | Fonksiyonları kaldır | [x] |

### 1.3 Route Temizliği (routes/admin.py)
| Satır | Route/Fonksiyon | İşlem | Durum |
|-------|-----------------|-------|-------|
| 541-914 | `TEMPLATE_VARIABLES`, `DEFAULT_TEMPLATES` | Yorum satırına al | [x] |
| 916-932 | `_ensure_template()` | Yorum satırına al | [x] |
| 934-960 | `api_list_templates()` | Yorum satırına al | [x] |
| 963-976 | `api_get_template_variables()` | Yorum satırına al | [x] |
| 979-1000 | `api_get_template()` | Yorum satırına al | [x] |
| 1003-1025 | `api_update_template()` | Yorum satırına al | [x] |
| 1027-1087 | `api_preview_mail_render()` | Yorum satırına al | [x] |
| 1089-1152 | `api_test_send_mail_endpoint()` | Yeniden tasarla (sabit şablonla) | [x] |
| 1155-1171 | `api_reset_template()` | Yorum satırına al | [x] |

### 1.4 MailService Temizliği (services/mail_service.py)
| Satır | Fonksiyon | İşlem | Durum |
|-------|-----------|-------|-------|
| 61-63 | `get_template()` | Kaldır | [x] |
| 65-75 | `update_template()` | Kaldır | [x] |
| 77-92 | `preview_template()` | Kaldır | [x] |
| 177-227 | `send_template()` | Kaldır (artık `send()` kullanılacak) | [x] |

### 1.5 Template Dosyaları
| Dosya | İşlem | Durum |
|-------|-------|-------|
| `templates/mail_templates.html` | Sil | [x] |
| `templates/mail_template_edit.html` | Sil | [x] |
| `templates/mail_settings.html` | Şablon sekmesini kaldır (satır 417-536) | [x] |

### 1.6 JavaScript Temizliği
| Dosya | Satır | İşlem | Durum |
|-------|-------|-------|-------|
| `static/app.js:5329-5459` | `_loadJobMailTemplates()`, `JOB_MAIL_TEMPLATES` | Kaldır | [x] |


---

## 🎯 AŞAMA 2: YENİ SABİT ŞABLONLAR

### 2.1 utils.py'ye Eklenecek Şablon Fonksiyonları

```python
# ============== SABİT MAİL ŞABLONLARI ==============

def _get_priority_color(priority_label: str) -> str:
    """Öncelik seviyesine göre renk döndür"""
    colors = {
        "Kritik": "#dc2626",
        "Yüksek": "#f97316", 
        "Orta": "#eab308",
        "Düşük": "#22c55e",
        "Çok Düşük": "#64748b",
    }
    return colors.get(priority_label, "#64748b")

def _get_status_color(status: str) -> str:
    """Durum için renk döndür"""
    colors = {
        "İlk Giriş": "#3b82f6",
        "Devam Ediyor": "#f59e0b", 
        "Beklemede": "#8b5cf6",
        "İş Halledildi": "#22c55e",
        "Reddedildi": "#ef4444",
        "İptal": "#ef4444",
    }
    return colors.get(status, "#64748b")

def render_email_base(
    subject: str,
    header_title: str,
    header_subtitle: str,
    recipient_name: str,
    action_message: str,
    main_content: str = "",
    action_button: str = "",
    action_by: str = "Sistem",
) -> Tuple[str, str]:
    """
    Tüm mailler için tek bir wrapper fonksiyonu.
    Returns: (subject, html_body)
    """
    system_name = "Netmon Proje Takip"
    company_name = "Netmon"
    
    html = f'''<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin:0; padding:0; background-color:#f0f4f8; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  
  <!-- Header Banner -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);">
    <tr>
      <td style="padding: 24px 0; text-align: center;">
        <h1 style="color: #ffffff; margin: 0; font-size: 26px; font-weight: 700;">{header_title}</h1>
        <p style="color: rgba(255,255,255,0.85); margin: 10px 0 0 0; font-size: 14px;">{header_subtitle}</p>
      </td>
    </tr>
  </table>

  <!-- Main Content -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr>
      <td style="padding: 28px 16px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
          
          <!-- Personal Greeting -->
          <tr>
            <td style="padding: 28px 28px 16px 28px;">
              <p style="margin: 0; font-size: 16px; color: #1e3a5f;">
                Merhaba <strong style="color: #1e40af;">{recipient_name}</strong>,
              </p>
            </td>
          </tr>

          <!-- Action Message -->
          <tr>
            <td style="padding: 0 28px;">
              <div style="background-color: #f0f9ff; border-left: 4px solid #3b82f6; padding: 16px 20px; border-radius: 0 10px 10px 0;">
                <p style="margin: 0; font-size: 15px; color: #1e40af; line-height: 1.5;">{action_message}</p>
              </div>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding: 24px 28px;">{main_content}</td>
          </tr>

          <!-- Action Button -->
          {action_button}

          <!-- Footer Info -->
          <tr>
            <td style="padding: 20px 28px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; border-radius: 0 0 12px 12px;">
              <p style="margin: 0 0 6px 0; font-size: 12px; color: #64748b;">
                📧 Bu mail <strong>{system_name}</strong> tarafından otomatik olarak gönderilmiştir.
              </p>
              <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                👤 İşlemi gerçekleştiren: <strong>{action_by}</strong>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>

  <!-- Footer -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr>
      <td style="padding: 24px; text-align: center;">
        <p style="margin: 0; font-size: 12px; color: #94a3b8;">{company_name}</p>
      </td>
    </tr>
  </table>
</body>
</html>'''

    return subject, html
```

### 2.2 Mail Türleri ve Fonksiyonları

| Mail Türü | Fonksiyon Adı | Durum |
|-----------|---------------|-------|
| Görev Oluşturuldu | `render_task_created_email()` | [ ] |
| Görev Atandı | `render_task_assigned_email()` | [ ] |
| Durum Değişti | `render_task_status_changed_email()` | [ ] |
| Yorum Eklendi | `render_task_comment_email()` | [ ] |
| Hatırlatma | `render_task_reminder_email()` | [ ] |
| Süre Doldu | `render_task_deadline_expired_email()` | [ ] |
| Haftalık Plan | `render_weekly_plan_email()` | [ ] |
| Ekip Raporu | `render_team_report_email()` | [ ] |
| İş Atama | `render_job_assignment_email()` | [ ] |
| Test Maili | `render_test_email()` | [ ] |

---

## 🎯 AŞAMA 3: MAİL GÖNDERİM KODLARINI GÜNCELLEME

### 3.1 routes/tasks.py Güncelleme
| Satır | Mevcut Kod | Yeni Kod | Durum |
|-------|------------|----------|-------|
| 192 | `MailService.send_template()` | `email_base.html` + `MailService.send()` | [x] |

### 3.2 routes/planner.py Güncelleme
| Satır | Mevcut Kod | Yeni Kod | Durum |
|-------|------------|----------|-------|
| 1676 | `MailService.send_template()` | `email_base.html` + `MailService.send()` | [x] |
| 2054 | `MailService.send_template()` | `email_base.html` + `MailService.send()` | [x] |
| 3658 | `_render_inline_mail_templates()` | Daha önce kaldırılmış | [x] |
| 3729 | `_render_inline_mail_templates()` | Daha önce kaldırılmış | [x] |
| 8472 | `_render_inline_mail_templates()` | Daha önce kaldırılmış | [x] |
| 8602 | `_render_inline_mail_templates()` | Daha önce kaldırılmış | [x] |
| 8740 | `_render_inline_mail_templates()` | Daha önce kaldırılmış | [x] |

### 3.3 routes/admin.py Güncelleme
| Satır | Mevcut Kod | Yeni Kod | Durum |
|-------|------------|----------|-------|
| 191 | `MailService.send_template()` | `render_test_email()` + `MailService.send()` | [x] |

---

## 🎯 AŞAMA 4: ADMIN PANEL GÜNCELLEMESİ

### 4.1 mail_settings.html Değişiklikleri
- Şablonlar sekmesini kaldır (satır 261-262, 417-536) [x]
- Tab butonlarından "Şablonlar & Önizleme" kaldır [x]
- JavaScript'teki şablon fonksiyonlarını kaldır (satır 576-900+) [x]

### 4.2 Kaldırılacak Sayfalar
- `/admin/mail-templates` route'u yok zaten [x]
- `/api/mail/templates/*` route'ları kaldırılacak [x]

---

## 📊 UYGULAMA SIRASI

1. **utils.py**: Yeni `render_email_base()` ve mail şablon fonksiyonlarını ekle
2. **services/mail_service.py**: Template fonksiyonlarını kaldır, sadece `send()` bırak
3. **routes/tasks.py**: `send_template` → `render_*` + `send` olarak güncelle
4. **routes/planner.py**: Tüm mail gönderimlerini yeni sisteme geçir
5. **routes/admin.py**: Template API'lerini kaldır, test endpoint'ini güncelle
6. **mail_settings.html**: Şablonlar sekmesini kaldır
7. **models.py**: MailTemplate sınıfını yorum satırına al
8. **app.py**: MailTemplate import ve seed'lerini kaldır
9. **Template dosyalarını sil**: mail_templates.html, mail_template_edit.html

---

## ✅ TEST KONTROL LİSTESİ

- [ ] Görev oluşturma maili gönderildi
- [ ] Görev atama maili gönderildi
- [ ] Durum değişikliği maili gönderildi
- [ ] Yorum maili gönderildi
- [ ] Hatırlatma maili gönderildi
- [ ] Haftalık plan maili gönderildi
- [ ] Ekip raporu maili gönderildi
- [ ] Test maili gönderildi
- [ ] Tüm mailler kişiselleştirilmiş ve profesyonel görünüyor
- [ ] Mail logları doğru çalışıyor
- [ ] Admin paneli hatasız çalışıyor

---

## ⚠️ DİKKAT EDİLECEKLER

1. **Geriye Dönük Uyumluluk**: Eski log kayıtları okunabilir kalmalı
2. **Veritabanı**: MailTemplate tablosu silinmeyecek, sadece kullanılmayacak
3. **Test**: Her değişiklikten sonra mail gönderimi test edilmeli
4. **Yedek**: Değişiklik öncesi git commit alınmalı

---

## 📁 ETKİLENEN DOSYALAR

```
V12/
├── models.py                        # MailTemplate yorum satırına
├── app.py                           # Import ve seed temizliği
├── utils.py                         # Yeni şablon fonksiyonları ekle
├── services/mail_service.py         # Template fonksiyonlarını kaldır
├── routes/
│   ├── admin.py                     # Template API'leri kaldır
│   ├── tasks.py                     # Mail gönderimini güncelle
│   └── planner.py                   # Mail gönderimini güncelle
├── templates/
│   ├── mail_settings.html           # Şablon sekmesini kaldır
│   ├── mail_templates.html          # SİL
│   └── mail_template_edit.html      # SİL
└── static/
    └── app.js                       # Template yükleme kodlarını kaldır
```
