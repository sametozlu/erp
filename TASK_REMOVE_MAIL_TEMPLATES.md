# 🚀 Mail Sistemi Yenileme Görevi

## 🎯 Hedef

Mail şablon sistemini tamamen kaldırıp, **sabit ve kişiselleştirilmiş HTML mail şablonları** tasarlamak. Tüm mail gönderimleri tek bir tutarlı yapıda olacak.

---

## 📋 Görev Listesi

### Aşama 1: Şablon Sistemi Temizliği [ ]

#### 1.1 Model Temizliği
- [ ] [`MailTemplate`](models.py:358) modelini **devre dışı bırak** (silme, sadece kullanımdan kaldır)
- [ ] Şablon ile ilgili tüm route'ları **yorum satırı** yap
- [ ] Admin panelinden şablon yönetimini **gizle/sil**

#### 1.2 Kod Temizliği
| Dosya | Temizlenecek Kod |
|-------|------------------|
| [`services/mail_service.py`](services/mail_service.py) | Tüm `MailTemplate` referansları |
| [`routes/admin.py`](routes/admin.py) | Şablon CRUD operasyonları |
| [`routes/planner.py`](routes/planner.py) | Şablon kullanan tüm fonksiyonlar |
| [`utils.py`](utils.py) | `_render_mail_template()`, `_get_default_mail_template()` |
| [`models.py`](models.py) | `heading_template`, `intro_template` alanları |

#### 1.3 Template Dosyaları
- [ ] [`templates/mail_templates.html`](templates/mail_templates.html) → **Sil**
- [ ] [`templates/mail_template_edit.html`](templates/mail_template_edit.html) → **Sil**
- [ ] [`templates/email_base.html`](templates/email_base.html) → **Yeniden tasarla**

---

### Aşama 2: Yeni Sabit Mail Şablonları Tasarımı [ ]

#### 2.1 Ana Mail Wrapper (Yeni email_base.html)

```html
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ subject }}</title>
  <!--[if mso]>
  <style type="text/css">body, table, td {font-family: Arial, sans-serif !important;}</style>
  <![endif]-->
</head>
<body style="margin:0; padding:0; background-color:#f0f4f8; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;">
  <!-- Header Banner -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);">
    <tr>
      <td style="padding: 20px 0; text-align: center;">
        <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700;">
          📋 {{ header_title }}
        </h1>
        <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0 0; font-size: 14px;">
          {{ header_subtitle }}
        </p>
      </td>
    </tr>
  </table>

  <!-- Main Content -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr>
      <td style="padding: 24px 16px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
          
          <!-- Personal Greeting -->
          <tr>
            <td style="padding: 24px 24px 16px 24px;">
              <p style="margin: 0; font-size: 16px; color: #1e3a5f;">
                Merhaba <strong>{{ recipient_name }}</strong>,
              </p>
            </td>
          </tr>

          <!-- Action Message -->
          <tr>
            <td style="padding: 0 24px;">
              <div style="background-color: #f0f9ff; border-left: 4px solid #3b82f6; padding: 16px; border-radius: 0 8px 8px 0;">
                {{ action_message }}
              </div>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding: 24px;">
              {{ main_content }}
            </td>
          </tr>

          <!-- Details Grid -->
          {{ details_grid }}

          <!-- Action Button -->
          {{ action_button }}

          <!-- Footer Info -->
          <tr>
            <td style="padding: 20px 24px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; border-radius: 0 0 12px 12px;">
              <p style="margin: 0 0 8px 0; font-size: 12px; color: #64748b;">
                📧 Bu mail <strong>{{ system_name }}</strong> tarafından otomatik olarak gönderilmiştir.
              </p>
              <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                👤 İşlemi gerçekleştiren: {{ action_by }}
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
        <p style="margin: 0; font-size: 12px; color: #94a3b8;">
          {{ company_name }} • {{ company_address }}
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
```

---

### Aşama 3: Görev Mailleri (Yeni Tasarım) [ ]

#### 3.1 Görev Oluşturuldu Maili

```python
def render_task_created_email(task, recipient_name, action_by):
    """Yeni görev atandığında gönderilen mail"""
    
    priority_colors = {
        "Kritik": "#dc2626",
        "Yüksek": "#f97316", 
        "Orta": "#eab308",
        "Düşük": "#22c55e",
        "Çok Düşük": "#64748b",
    }
    priority_color = priority_colors.get(task.priority_label, "#64748b")
    
    subject = f"📋 Yeni Görev Atandı: {task.task_no} - {task.subject}"
    
    # Detay Grid
    details_grid = f"""
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top: 16px;">
      <tr>
        <td style="padding: 8px 0;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
            <tr>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 33%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">📌 Görev No</div>
                <div style="font-size: 14px; font-weight: 600; color: #1e3a5f;">{task.task_no}</div>
              </td>
              <td style="width: 4%;"></td>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 33%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">📁 Tip</div>
                <div style="font-size: 14px; font-weight: 600; color: #1e3a5f;">{task.task_type}</div>
              </td>
              <td style="width: 4%;"></td>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 30%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">⚡ Öncelik</div>
                <div style="font-size: 14px; font-weight: 600;">
                  <span style="background: {priority_color}; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-size: 12px;">{task.priority_label}</span>
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding: 8px 0;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
            <tr>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 50%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">📅 Hedef Tarih</div>
                <div style="font-size: 14px; font-weight: 600; color: #1e3a5f;">{task.target_date.strftime('%d.%m.%Y') if task.target_date else 'Belirtilmemiş'}</div>
              </td>
              <td style="width: 4%;"></td>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 46%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">👤 Oluşturan</div>
                <div style="font-size: 14px; font-weight: 600; color: #1e3a5f;">{task.created_by_name}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    """
    
    # Açıklama
    description_html = ""
    if task.description:
        description_html = f"""
        <tr>
          <td style="padding: 16px 0;">
            <div style="background: #fffbeb; border: 1px solid #fcd34d; padding: 16px; border-radius: 8px;">
              <div style="font-size: 12px; color: #92400e; font-weight: 600; margin-bottom: 8px;">📝 Açıklama</div>
              <div style="font-size: 14px; color: #451a03; line-height: 1.6;">{task.description.replace(chr(10), '<br>')}</div>
            </div>
          </td>
        </tr>
        """
    
    # Proje Bilgisi
    project_html = ""
    if task.project_codes:
        project_html = f"""
        <tr>
          <td style="padding: 8px 0;">
            <div style="background: #f0fdf4; border: 1px solid #86efac; padding: 12px 16px; border-radius: 8px;">
              <span style="font-size: 12px; color: #166534;">🏢 Proje: <strong>{task.project_codes}</strong></span>
            </div>
          </td>
        </tr>
        """
    
    # Buton
    action_button = f"""
    <tr>
      <td style="padding: 24px; text-align: center;">
        <a href="{settings.SYSTEM_URL}/gorev/{task.id}" 
           style="display: inline-block; background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); color: #ffffff; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">
          👁 Görevi Görüntüle
        </a>
      </td>
    </tr>
    """
    
    return render_email_template(
        subject=subject,
        header_title="📋 Yeni Görev Atandı",
        header_subtitle=f"Görev No: {task.task_no}",
        recipient_name=recipient_name,
        action_message=f"Size yeni bir görev atandı. Görevi inceleyip gerekli aksiyonları alabilirsiniz.",
        main_content=project_html + details_grid + description_html,
        action_button=action_button,
        action_by=action_by,
    )
```

#### 3.2 Görev Durumu Değişti Maili

```python
def render_task_status_changed_email(task, old_status, new_status, recipient_name, changed_by, comment=None):
    """Görev durumu değiştiğinde gönderilen mail"""
    
    status_colors = {
        "Yeni": "#3b82f6",
        "Devam Ediyor": "#f59e0b", 
        "Beklemede": "#8b5cf6",
        "Tamamlandı": "#22c55e",
        "İptal": "#ef4444",
    }
    status_color = status_colors.get(new_status, "#64748b")
    
    subject = f"🔄 Görev Durumu Güncellendi: {task.task_no}"
    
    # Durum Değişimi Grid
    status_change_html = f"""
    <tr>
      <td style="padding: 16px 0;">
        <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); padding: 20px; border-radius: 12px; text-align: center;">
          <div style="font-size: 12px; color: #92400e; margin-bottom: 8px;">Eski Durum</div>
          <div style="font-size: 16px; font-weight: 700; color: #78350f; margin-bottom: 12px;">{old_status}</div>
          <div style="font-size: 20px; color: #92400e; margin-bottom: 12px;">⬇️</div>
          <div style="font-size: 12px; color: #166534; margin-bottom: 8px;">Yeni Durum</div>
          <div style="font-size: 16px; font-weight: 700; color: #166534;">
            <span style="background: {status_color}; color: #ffffff; padding: 6px 16px; border-radius: 6px;">{new_status}</span>
          </div>
        </div>
      </td>
    </tr>
    """
    
    # Yorum varsa
    comment_html = ""
    if comment:
        comment_html = f"""
        <tr>
          <td style="padding: 16px 0;">
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 16px; border-radius: 8px;">
              <div style="font-size: 12px; color: #64748b; margin-bottom: 8px;">💬 {changed_by} yazdı:</div>
              <div style="font-size: 14px; color: #1e293b; line-height: 1.5; font-style: italic;">"{comment}"</div>
            </div>
          </td>
        </tr>
        """
    
    return render_email_template(
        subject=subject,
        header_title="🔄 Durum Güncellemesi",
        header_subtitle=f"Görev: {task.task_no} - {task.subject}",
        recipient_name=recipient_name,
        action_message=f"Görevin durumu <strong>{old_status}</strong> → <strong>{new_status}</strong> olarak güncellendi.",
        main_content=status_change_html + comment_html,
        action_by=changed_by,
    )
```

#### 3.3 Göreve Yorum Eklendi Maili

```python
def render_task_comment_email(task, comment_text, comment_by, recipient_name):
    """Göreve yorum eklendiğinde gönderilen mail"""
    
    subject = f"💬 Yeni Yorum: {task.task_no}"
    
    comment_html = f"""
    <tr>
      <td style="padding: 20px 0;">
        <div style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-left: 4px solid #3b82f6; padding: 20px; border-radius: 0 12px 12px 0;">
          <div style="font-size: 12px; color: #1e40af; margin-bottom: 8px;">
            <span style="background: rgba(255,255,255,0.5); padding: 4px 10px; border-radius: 4px;">💬 {comment_by}</span>
          </div>
          <div style="font-size: 15px; color: #1e3a8a; line-height: 1.6; font-style: italic;">
            "{comment_text}"
          </div>
        </div>
      </td>
    </tr>
    """
    
    return render_email_template(
        subject=subject,
        header_title="💬 Yeni Yorum Eklendi",
        header_subtitle=f"Görev: {task.task_no}",
        recipient_name=recipient_name,
        action_message=f"{comment_by} görevinize yeni bir yorum ekledi.",
        main_content=comment_html,
        action_by=comment_by,
    )
```

#### 3.4 Görev Hatırlatma Maili

```python
def render_task_reminder_email(task, days_left, recipient_name):
    """Görev hatırlatma maili"""
    
    urgency_color = "#ef4444" if days_left <= 1 else "#f59e0b" if days_left <= 3 else "#22c55e"
    
    subject = f"⏰ Hatırlatma: {task.task_no} - {days_left} gün kaldı"
    
    reminder_html = f"""
    <tr>
      <td style="padding: 20px 0;">
        <div style="background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); padding: 24px; border-radius: 12px; text-align: center;">
          <div style="font-size: 48px; margin-bottom: 12px;">⏰</div>
          <div style="font-size: 18px; font-weight: 700; color: #991b1b; margin-bottom: 8px;">
            Hedef Tarihe {days_left} Gün Kaldı!
          </div>
          <div style="font-size: 14px; color: #7f1d1d;">
            Görevinizi tamamlamak için acele edin.
          </div>
        </div>
      </td>
    </tr>
    """
    
    return render_email_template(
        subject=subject,
        header_title="⏰ Görev Hatırlatması",
        header_subtitle=f"{task.task_no}",
        recipient_name=recipient_name,
        action_message=f"Görevinizin hedef tarihi yaklaşıyor. Lütfen görevi gözden geçirin.",
        main_content=reminder_html,
        action_by="Sistem",
    )
```

---

### Aşama 4: Planlama Mailleri [ ]

#### 4.1 Haftalık Plan Maili

```python
def render_weekly_plan_email(person, week_start, week_end, plans, action_by="Sistem"):
    """Haftalık iş planı maili"""
    
    subject = f"📅 Haftalık Planınız - {week_start} / {week_end}"
    
    # Plan özeti
    plans_html = ""
    for day, day_plans in plans.items():
        day_date, day_name = day
        plans_html += f"""
        <tr>
          <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0;">
            <strong>{day_date} {day_name}</strong>
          </td>
          <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0;">
            {day_plans}
          </td>
        </tr>
        """
    
    content = f"""
    <tr>
      <td style="padding: 16px 0;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background: #f8fafc; border-radius: 8px;">
          <thead>
            <tr style="background: #1e3a5f;">
              <th style="padding: 12px 16px; color: #ffffff; text-align: left;">Tarih</th>
              <th style="padding: 12px 16px; color: #ffffff; text-align: left;">İşler</th>
            </tr>
          </thead>
          <tbody>
            {plans_html}
          </tbody>
        </table>
      </td>
    </tr>
    """
    
    return render_email_template(
        subject=subject,
        header_title="📅 Haftalık İş Planınız",
        header_subtitle=f"{week_start} - {week_end}",
        recipient_name=person.full_name,
        action_message="Haftalık iş planınız aşağıda sunulmuştur. Planınızı inceleyip hazırlıklarınızı yapabilirsiniz.",
        main_content=content,
        action_by=action_by,
    )
```

#### 4.2 Ekip Raporu Maili

```python
def render_team_report_email(team, date_range, jobs_summary, action_by):
    """Ekip raporu maili"""
    
    subject = f"👥 Ekip Raporu - {team.name} - {date_range}"
    
    summary_html = f"""
    <tr>
      <td style="padding: 16px 0;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
          <tr>
            <td style="background: #f0fdf4; padding: 16px; border-radius: 8px; text-align: center; width: 33%;">
              <div style="font-size: 24px; font-weight: 700; color: #166534;">{jobs_summary['total']}</div>
              <div style="font-size: 12px; color: #166534;">Toplam İş</div>
            </td>
            <td style="width: 2%;"></td>
            <td style="background: #eff6ff; padding: 16px; border-radius: 8px; text-align: center; width: 33%;">
              <div style="font-size: 24px; font-weight: 700; color: #1e40af;">{jobs_summary['completed']}</div>
              <div style="font-size: 12px; color: #1e40af;">Tamamlanan</div>
            </td>
            <td style="width: 2%;"></td>
            <td style="background: #fef3c7; padding: 16px; border-radius: 8px; text-align: center; width: 32%;">
              <div style="font-size: 24px; font-weight: 700; color: #92400e;">{jobs_summary['pending']}</div>
              <div style="font-size: 12px; color: #92400e;">Bekleyen</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    """
    
    return render_email_template(
        subject=subject,
        header_title="👥 Ekip Raporu",
        header_subtitle=f"{team.name}",
        recipient_name=team.manager_name,
        action_message=f"{date_range} dönemine ait ekip raporu aşağıdadır.",
        main_content=summary_html,
        action_by=action_by,
    )
```

---

### Aşama 5: Tek Yardımcı Fonksiyon [ ]

```python
# utils.py - Yeni render_email_template fonksiyonu

def render_email_template(
    subject: str,
    header_title: str,
    header_subtitle: str,
    recipient_name: str,
    action_message: str,
    main_content: str = "",
    action_button: str = "",
    action_by: str = "Sistem",
    details_grid: str = "",
) -> Tuple[str, str]:
    """
    Tüm mailler için tek bir wrapper fonksiyonu.
    
    Returns:
        (subject, html_body)
    """
    
    # Logo ve şirket bilgisi config'den alınır
    company_name = current_app.config.get("COMPANY_NAME", "V12 Sistem")
    company_address = current_app.config.get("COMPANY_ADDRESS", "")
    system_name = current_app.config.get("SYSTEM_NAME", "Görev Takip Sistemi")
    system_url = current_app.config.get("SYSTEM_URL", "https://v12.sistem.com")
    
    html = f"""
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <!--[if mso]>
  <style type="text/css">body, table, td {{font-family: Arial, sans-serif !important;}}</style>
  <![endif]-->
</head>
<body style="margin:0; padding:0; background-color:#f0f4f8; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;">
  
  <!-- Header Banner -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);">
    <tr>
      <td style="padding: 24px 0; text-align: center;">
        <h1 style="color: #ffffff; margin: 0; font-size: 26px; font-weight: 700;">
          {header_title}
        </h1>
        <p style="color: rgba(255,255,255,0.85); margin: 10px 0 0 0; font-size: 14px;">
          {header_subtitle}
        </p>
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
                <p style="margin: 0; font-size: 15px; color: #1e40af; line-height: 1.5;">
                  {action_message}
                </p>
              </div>
            </td>
          </tr>

          <!-- Details Grid -->
          {details_grid}

          <!-- Main Content -->
          {main_content}

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
        <p style="margin: 0; font-size: 12px; color: #94a3b8;">
          {company_name} • {company_address}
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
    """
    
    return subject, html
```

---

### Aşama 6: Güncelleme Adımları [ ]

#### 6.1 routes/tasks.py Güncelleme

```python
# Eski kod:
# from services.mail_service import MailService
# MailService.send_template(...)

# Yeni kod:
from utils import render_email_template, send_task_email_direct

# send_task_email fonksiyonunu güncelle
def send_task_email(task, event_type="created", changed_by_user=None, extra_content=None):
    """Yeni sabit şablon ile görev maili gönder"""
    
    # ... alıcı belirleme mantığı ...
    
    # Render mail
    if event_type == "created":
        subject, html = render_task_created_email(task, recipient_name, changed_by_name)
    elif event_type == "status_changed":
        subject, html = render_task_status_changed_email(task, old_status, new_status, ...)
    # ... diğer türler ...
    
    # Log ve gönder
    create_mail_log(
        kind="send",
        ok=send_email_smtp(to_addr=recipient_email, subject=subject, html_body=html),
        to_addr=recipient_email,
        subject=subject,
        task_id=task.id,
        body_html=html,
        body_preview=html[:200],
    )
```

#### 6.2 routes/planner.py Güncelleme

```python
# Eski kod:
# subject, body_html = _render_inline_mail_templates(DEFAULT_JOB_MAIL_SUBJECT_TEMPLATE, ...)

# Yeni kod:
from utils import render_email_template

def api_send_job_email():
    # ...
    subject, html = render_job_email(...)
    # ...
```

---

### Aşama 7: Admin Panel Temizliği [ ]

#### 7.1 Kaldırılacak Sayfalar
- `/admin/mail-templates` → **Sil**
- `/admin/mail-template/add` → **Sil**
- `/admin/mail-template/edit/<id>` → **Sil**

#### 7.2 Gizlenecek Route'lar
```python
# routes/admin.py - Yorum satırı yap
# @admin_required
# def mail_templates_page():
#     ...

# @admin_required  
# def mail_template_edit_page(tpl_id):
#     ...

# @admin_required
# def api_mail_templates():
#     ...
```

#### 7.3 Mail Ayarları Sayfası Güncelleme
[`templates/mail_settings.html`](templates/mail_settings.html):
- Şablon ayarları bölümünü **kaldır**
- Sadece SMTP ayarları **tut**

---

## 📊 Yeni Mail Türleri Özeti

| Mail Türü | Konu Başlığı | Öncelik | Renk |
|-----------|---------------|----------|------|
| Görev Oluşturuldu | 📋 Yeni Görev Atandı | Yüksek | Mavi |
| Görev Atandı | 📋 Görev Atandı | Yüksek | Mavi |
| Durum Değişti | 🔄 Durum Güncellendi | Orta | Turuncu |
| Yorum Eklendi | 💬 Yeni Yorum | Düşük | Gri |
| Süre Doldu | ⚠️ Süre Doldu | Kritik | Kırmızı |
| Hatırlatma | ⏰ Hatırlatma | Orta | Turuncu |
| Haftalık Plan | 📅 Haftalık Plan | Normal | Mavi |
| Ekip Raporu | 👥 Ekip Raporu | Normal | Mavi |

---

## ✅ Kontrol Listesi

- [ ] Tüm `MailTemplate` referansları temizlendi
- [ ] Şablon sayfaları silindi
- [ ] Yeni `render_email_template` fonksiyonu eklendi
- [ ] Görev mailleri güncellendi (6 tür)
- [ ] Planlama mailleri güncellendi (2 tür)
- [ ] Admin paneli temizlendi
- [ ] Mail log sistemi çalışıyor
- [ ] SMTP ayarları test edildi
- [ ] Tüm mail türleri manuel test edildi

---

## ⚠️ Dikkat Edilmesi Gerekenler

1. **Geriye Dönük Uyumluluk**: Eski log kayıtları okunabilir kalmalı
2. **Test Ortamı**: Önce test ortamında tüm mailler kontrol edilmeli
3. **Kullanıcı Bildirimi**: Mail formatı değişikliği hakkında kullanıcılar bilgilendirilmeli
4. **Backup**: Değişiklik öncesi veritabanı yedeği alınmalı
