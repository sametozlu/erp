# 📧 MAİL SİSTEMİ İYİLEŞTİRME GÖREVİ

## 📋 ÖZET

Bu görev, mevcut mail sisteminin üç ana alanda iyileştirilmesini kapsar:
1. **Maillerin Görsel Olarak Zenginleştirilmesi** - Daha gösterişli ve anlaşılır mail şablonları
2. **Asenkron Mail Kuyruğu Sistemi** - Sistemin mail gönderimi için beklemesini engelleyen yapı
3. **Personel Listesi Sayfa Uzantısı** - Liste kutusunun sayfanın sonuna kadar uzaması

---

## ✅ BÖLÜM 1: PERSONEL LİSTESİ SAYFA UZANTISI

### 📌 DURUM: TAMAMLANDI ✓

[`templates/people.html`](templates/people.html) dosyasında:

```css
section.card {
    min-height: calc(100vh - 120px);
    display: flex;
    flex-direction: column;
}

.tablewrap.people-table {
    flex: 1;
    min-height: 0;
    max-height: none; /* Scroll artık tablo içinde değil, card'ın içinde */
}
```

---

## 🎨 BÖLÜM 2: MAİL ŞABLONLARININ GÖRSEL OLARAK ZENGİNLEŞTİRİLMESİ

### 📌 MEVCUT DURUM ANALİZİ

**Şu anki mail şablonları (utils.py):**
- `render_task_created_email()` - Görev oluşturma
- `render_task_status_changed_email()` - Görev durumu değişimi
- `render_task_comment_email()` - Göreve yorum
- `render_task_reminder_email()` - Hatırlatma
- `render_task_deadline_expired_email()` - Süre bitimi
- `render_weekly_plan_email()` - Haftalık plan
- `render_team_report_email()` - Ekip raporu
- `render_job_assignment_email()` - İş atama
- `render_test_email()` - Test maili

### 🎯 YAPILACAK DEĞİŞİKLİKLER

#### 2.1 Ana Mail Şablon Yapısı (Base Template)

**Yeni oluşturulacak:** `templates/email_base.html` veya `utils.py` içinde `render_base_email()`

```python
def render_base_email(
    *,
    subject: str,
    preheader: str,
    heading: str,
    intro_text: str,
    body_html: str,
    action_url: str = None,
    action_text: str = None,
    footer_text: str = None,
    accent_color: str = "#3b82f6",  # Varsayılan mavi
    logo_url: str = None,
) -> str:
    """Tüm mailler için ortak base template"""
    
    return f"""
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>{subject}</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
    <style>
        /* Reset Styles */
        body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
        table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
        img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
        body {{ height: 100% !important; margin: 0 !important; padding: 0 !important; width: 100% !important; }}
        
        /* Mobile Responsive */
        @media screen and (max-width: 600px) {{
            .email-container {{ width: 100% !important; max-width: 100% !important; }}
            .mobile-padding {{ padding: 16px !important; }}
            .mobile-stack {{ display: block !important; width: 100% !important; }}
            .hide-mobile {{ display: none !important; }}
        }}
        
        /* Button Styles */
        .btn {{
            display: inline-block;
            padding: 14px 28px;
            background: {accent_color};
            color: #ffffff !important;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 16px;
            text-align: center;
        }}
        
        /* Card Styles */
        .card {{
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            overflow: hidden;
        }}
        
        /* Status Badge */
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-success {{ background: #dcfce7; color: #166534; }}
        .badge-warning {{ background: #fef3c7; color: #92400e; }}
        .badge-danger {{ background: #fee2e2; color: #991b1b; }}
        .badge-info {{ background: #dbeafe; color: #1e40af; }}
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    
    <!-- Preheader (Görünmeyen önizleme metni) -->
    <div style="display: none; max-height: 0; overflow: hidden; mso-hide: all;">
        {preheader}
    </div>
    
    <!-- Email Wrapper -->
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f3f4f6;">
        <tr>
            <td align="center" style="padding: 20px 10px;">
                
                <!-- Logo (Varsa) -->
                {f'''
                <div style="margin-bottom: 20px;">
                    <img src="{logo_url}" alt="Logo" width="120" style="display: block; border: 0;">
                </div>
                ''' if logo_url else ''}
                
                <!-- Main Container -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" class="email-container" style="max-width: 600px; width: 100%;">
                    <tr>
                        <td class="card mobile-padding" style="background: #ffffff; padding: 32px;">
                            
                            <!-- Heading -->
                            <h1 style="margin: 0 0 16px 0; color: #1f2937; font-size: 24px; font-weight: 700; line-height: 1.3;">
                                {heading}
                            </h1>
                            
                            <!-- Intro Text -->
                            <p style="margin: 0 0 24px 0; color: #6b7280; font-size: 16px; line-height: 1.6;">
                                {intro_text}
                            </p>
                            
                            <!-- Body Content -->
                            <div style="margin-bottom: 24px;">
                                {body_html}
                            </div>
                            
                            <!-- Action Button -->
                            {f'''
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td align="center">
                                        <a href="{action_url}" class="btn" target="_blank">
                                            {action_text}
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            ''' if action_url else ''}
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px; text-align: center;">
                            <p style="margin: 0; color: #9ca3af; font-size: 13px;">
                                {footer_text or 'Bu mail otomatik olarak gönderilmiştir.'}
                            </p>
                        </td>
                    </tr>
                    
                </table>
                
                <!-- Unsubscribe Link (Optional) -->
                <div style="margin-top: 16px;">
                    <a href="#" style="color: #9ca3af; font-size: 12px; text-decoration: underline;">
                        Mail almak istemiyorsanız tıklayın
                    </a>
                </div>
                
            </td>
        </tr>
    </table>
    
</body>
</html>
"""
```

#### 2.2 Görev Bildirim Maili - Zenginleştirilmiş Şablon

**Yeni:** `render_task_notification_email()`

```python
def render_task_notification_email(
    *,
    task_title: str,
    task_description: str,
    task_status: str,
    task_priority: str,
    assigned_to: str,
    assigned_by: str,
    project_name: str,
    due_date: str,
    task_url: str = None,
    comment: str = None,
) -> tuple[str, str]:
    """Görev bildirimi için zenginleştirilmiş mail şablonu"""
    
    # Badge renkleri
    status_colors = {
        'pending': ('warning', 'Beklemede'),
        'in_progress': ('info', 'Devam Ediyor'),
        'completed': ('success', 'Tamamlandı'),
        'problem': ('danger', 'Sorun'),
    }
    status_class, status_text = status_colors.get(task_status, ('info', task_status))
    
    priority_colors = {
        'high': ('danger', '🔴 Yüksek'),
        'medium': ('warning', '🟡 Orta'),
        'low': ('info', '🔵 Düşük'),
    }
    priority_class, priority_text = priority_colors.get(task_priority, ('info', task_priority))
    
    # İçerik
    body_html = f"""
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-bottom: 20px;">
        <tr>
            <td style="padding: 16px; background: #f9fafb; border-radius: 8px; border-left: 4px solid {accent_color};">
                <h3 style="margin: 0 0 8px 0; color: #1f2937; font-size: 16px; font-weight: 600;">
                    {task_title}
                </h3>
                <p style="margin: 0; color: #6b7280; font-size: 14px; line-height: 1.5;">
                    {task_description}
                </p>
            </td>
        </tr>
    </table>
    
    <!-- Task Details Grid -->
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-bottom: 20px;">
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <span style="color: #6b7280; font-size: 13px;">📊 Durum</span><br>
                <span class="badge badge-{status_class}">{status_text}</span>
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <span style="color: #6b7280; font-size: 13px;">⚡ Öncelik</span><br>
                <span class="badge badge-{priority_class}">{priority_text}</span>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <span style="color: #6b7280; font-size: 13px;">👤 Atayan</span><br>
                <strong style="color: #1f2937; font-size: 14px;">{assigned_by}</strong>
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <span style="color: #6b7280; font-size: 13px;">📅 Bitiş Tarihi</span><br>
                <strong style="color: #1f2937; font-size: 14px;">{due_date}</strong>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px;" colspan="2">
                <span style="color: #6b7280; font-size: 13px;">📁 Proje</span><br>
                <strong style="color: #1f2937; font-size: 14px;">{project_name}</strong>
            </td>
        </tr>
    </table>
    """
    
    if comment:
        body_html += f"""
        <!-- Yorum Kutusu -->
        <div style="background: #eff6ff; border-radius: 8px; padding: 16px; margin-top: 16px; border-left: 4px solid #3b82f6;">
            <p style="margin: 0 0 8px 0; color: #1e40af; font-size: 13px; font-weight: 600;">
                💬 Yeni Yorum
            </p>
            <p style="margin: 0; color: #1f2937; font-size: 14px; line-height: 1.5;">
                {comment}
            </p>
        </div>
        """
    
    subject = f"📋 Görev: {task_title}"
    intro_text = f"{assigned_by} size yeni bir görev atadı. Detaylar aşağıda:"
    
    return subject, render_base_email(
        subject=subject,
        preheader=f"Görev atandı: {task_title}",
        heading="📋 Yeni Görev Bildirimi",
        intro_text=intro_text,
        body_html=body_html,
        action_url=task_url,
        action_text="Görevi Görüntüle",
        accent_color="#3b82f6",
        footer_text="Netmon Proje Takip Sistemi",
    )
```

#### 2.3 Haftalık Plan Maili - Zenginleştirilmiş Şablon

```python
def render_weekly_plan_email(
    *,
    person_name: str,
    week_start: str,
    week_end: str,
    jobs: list,
    total_jobs: int,
    completion_rate: float,
) -> tuple[str, str]:
    """Haftalık plan maili için zenginleştirilmiş şablon"""
    
    # İş listesini HTML tabloya çevir
    jobs_html = """
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 16px;">
        <thead>
            <tr style="background: #f3f4f6;">
                <th style="padding: 12px; text-align: left; font-size: 12px; color: #6b7280; font-weight: 600;">TARİH</th>
                <th style="padding: 12px; text-align: left; font-size: 12px; color: #6b7280; font-weight: 600;">İŞ</th>
                <th style="padding: 12px; text-align: left; font-size: 12px; color: #6b7280; font-weight: 600;">PROJE</th>
                <th style="padding: 12px; text-align: center; font-size: 12px; color: #6b7280; font-weight: 600;">DURUM</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for job in jobs[:10]:  # En fazla 10 iş göster
        status_colors = {
            'pending': ('warning', 'Beklemede'),
            'completed': ('success', '✓'),
            'problem': ('danger', '⚠️'),
        }
        status_class, status_text = status_colors.get(job.get('status', 'pending'), ('info', '-'))
        
        jobs_html += f"""
            <tr style="border-bottom: 1px solid #e5e7eb;">
                <td style="padding: 12px; font-size: 13px; color: #1f2937;">{job.get('date', '-')}</td>
                <td style="padding: 12px; font-size: 13px; color: #1f2937; font-weight: 500;">{job.get('title', '-')}</td>
                <td style="padding: 12px; font-size: 13px; color: #6b7280;">{job.get('project', '-')}</td>
                <td style="padding: 12px; text-align: center;">
                    <span class="badge badge-{status_class}">{status_text}</span>
                </td>
            </tr>
        """
    
    if len(jobs) > 10:
        jobs_html += f"""
            <tr>
                <td colspan="4" style="padding: 12px; text-align: center; color: #6b7280; font-size: 13px;">
                    ...ve {len(jobs) - 10} iş daha
                </td>
            </tr>
        """
    
    jobs_html += """
        </tbody>
    </table>
    """
    
    # Özet kutusu
    summary_html = f"""
    <div style="display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 120px; background: linear-gradient(135deg, #3b82f6, #2563eb); border-radius: 12px; padding: 20px; color: white;">
            <div style="font-size: 28px; font-weight: 700;">{total_jobs}</div>
            <div style="font-size: 13px; opacity: 0.9;">Toplam İş</div>
        </div>
        <div style="flex: 1; min-width: 120px; background: linear-gradient(135deg, #10b981, #059669); border-radius: 12px; padding: 20px; color: white;">
            <div style="font-size: 28px; font-weight: 700;">{completion_rate:.0f}%</div>
            <div style="font-size: 13px; opacity: 0.9;">Tamamlanma</div>
        </div>
    </div>
    """
    
    body_html = summary_html + jobs_html
    
    subject = f"📅 Haftalık Plan - {week_start} / {week_end}"
    
    return subject, render_base_email(
        subject=subject,
        preheader=f"Bu hafta {total_jobs} işiniz var. Tamamlanma oranınız: {completion_rate}%",
        heading=f"📅 {person_name} - Haftalık İş Planınız",
        intro_text=f"{week_start} - {week_end} tarihleri arasındaki iş planınız aşağıdadır.",
        body_html=body_html,
        action_url=None,
        accent_color="#10b981",
        footer_text="Netmon Proje Takip Sistemi",
    )
```

---

## 🔄 BÖLÜM 3: ASENKRON MAİL KUYRUĞU SİSTEMİ

### 📌 MEVCUT DURUM ANALİZİ

**Sorun:** Mevcut sistemde mail gönderimi **senkron** (eşzamanlı) yapılıyor:
```
Kullanıcı işlem yapar → Sunucu mail gönderene kadar bekler → Mail gönderilir → Sayfa yüklenir
```

Bu sorunlara yol açıyor:
1. Sayfa yavaş yükleniyor (özellikle toplu maillerde)
2. Timeout hataları
3. Kullanıcı deneyimi kötü
4. Sunucu kaynakları tükeniyor

### 🎯 YENİ SİSTEM MİMARİSİ

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Kullanıcı     │     │   Web Sunucusu  │     │   Mail Worker   │
│   (Browser)     │     │   (Flask)       │     │   (Background)  │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                        │
         │  1. İşlem Yap         │                        │
         │──────────────────────▶│                        │
         │                       │  2. Kuyruğa Ekle      │
         │                       │──────────────────────▶│
         │                       │                        │
         │                       │  3. "İşlem Tamamlandı"│◀───────────────────────
         │◀──────────────────────│                        │
         │                       │                        │  4. Mail Gönder
         │                       │                        │──────────────────────▶
         │                       │                        │    (SMTP)
```

### 3.1 Veritabanı: Mail Queue Tablosu

**Oluşturulacak migration:** `migration_create_mail_queue.py`

```python
from extensions import db
from datetime import datetime

class MailQueue(db.Model):
    """Asenkron mail kuyruğu"""
    
    __tablename__ = 'mail_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Mail bilgileri
    mail_type = db.Column(db.String(50), nullable=False, index=True)
    subject = db.Column(db.String(500), nullable=False)
    html_body = db.Column(db.Text, nullable=False)
    text_body = db.Column(db.Text)
    
    # Alıcılar
    recipients = db.Column(db.Text, nullable=False)  # JSON: ["a@x.com", "b@x.com"]
    cc = db.Column(db.Text)  # JSON
    bcc = db.Column(db.Text)  # JSON
    
    # Ekler
    attachments = db.Column(db.Text)  # JSON
    
    # Durum
    STATUS_CHOICES = ['pending', 'processing', 'sent', 'failed', 'cancelled']
    status = db.Column(db.String(20), default='pending', index=True)
    
    # Zamanlama
    scheduled_at = db.Column(db.DateTime, index=True)  # Planlanan zaman
    sent_at = db.Column(db.DateTime)
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    
    # Hata yönetimi
    error_message = db.Column(db.Text)
    error_code = db.Column(db.String(50))
    
    # Bağlam
    context_json = db.Column(db.Text)  # JSON: {task_id, project_id, user_id...}
    
    # Zaman damgaları
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    logs = db.relationship('MailLog', backref='queue_item', lazy='dynamic')
```

### 3.2 Queue Service

**Yeni dosya:** `services/mail_queue_service.py`

```python
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from extensions import db
from models import MailQueue
from utils import send_email_smtp, create_mail_log

log = logging.getLogger(__name__)


class MailQueueService:
    """Mail kuyruğu yönetim servisi"""
    
    @staticmethod
    def enqueue(
        *,
        mail_type: str,
        recipients: List[str],
        subject: str,
        html_body: str,
        text_body: str = None,
        cc: List[str] = None,
        bcc: List[str] = None,
        attachments: List[Dict] = None,
        scheduled_at: datetime = None,
        context: Dict[str, Any] = None,
        priority: int = 0,  # 0=normal, 1=high, 2=urgent
    ) -> MailQueue:
        """
        Mail'i kuyruğa ekle.
        
        Args:
            mail_type: Mail türü (task_created, weekly, vb.)
            recipients: Alıcı listesi
            subject: Mail konusu
            html_body: HTML içerik
            text_body: Metin içerik (opsiyonel)
            cc: CC listesi
            bcc: BCC listesi
            attachments: Ek dosyalar
            scheduled_at: Planlanan gönderim zamanı
            context: Ek bağlam bilgileri
            priority: Öncelik (0=normal, 1=yüksek, 2=acil)
        
        Returns:
            MailQueue: Oluşturulan kuyruk öğesi
        """
        queue_item = MailQueue(
            mail_type=mail_type,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            recipients=json.dumps(recipients),
            cc=json.dumps(cc) if cc else None,
            bcc=json.dumps(bcc) if bcc else None,
            attachments=json.dumps(attachments) if attachments else None,
            scheduled_at=scheduled_at or datetime.utcnow(),
            context_json=json.dumps(context) if context else None,
            status='pending',
            priority=priority,
        )
        
        db.session.add(queue_item)
        db.session.commit()
        
        log.info(f"Mail queued: {mail_type} -> {len(recipients)} recipients, ID: {queue_item.id}")
        
        return queue_item
    
    @staticmethod
    def get_pending(limit: int = 100) -> List[MailQueue]:
        """Bekleyen mailleri getir"""
        return MailQueue.query.filter(
            MailQueue.status.in_(['pending', 'scheduled']),
            (MailQueue.scheduled_at <= datetime.utcnow()) | (MailQueue.scheduled_at.is_(None)),
        ).order_by(
            MailQueue.priority.desc(),
            MailQueue.created_at.asc()
        ).limit(limit).all()
    
    @staticmethod
    def process_queue_batch(batch_size: int = 20) -> Dict[str, int]:
        """
        Kuyruktan mailleri işle.
        
        Returns:
            Dict: {'sent': x, 'failed': y, 'remaining': z}
        """
        pending = MailQueueService.get_pending(batch_size)
        
        if not pending:
            return {'sent': 0, 'failed': 0, 'remaining': 0}
        
        sent_count = 0
        failed_count = 0
        
        for item in pending:
            try:
                MailQueueService.process_item(item)
                sent_count += 1
            except Exception as e:
                log.exception(f"Failed to process mail queue item {item.id}")
                failed_count += 1
        
        remaining = MailQueue.query.filter(
            MailQueue.status.in_(['pending', 'scheduled'])
        ).count()
        
        return {'sent': sent_count, 'failed': failed_count, 'remaining': remaining}
    
    @staticmethod
    def process_item(item: MailQueue) -> bool:
        """Tek bir mail öğesini işle"""
        # Durumu "processing" olarak güncelle
        item.status = 'processing'
        db.session.commit()
        
        try:
            # Alıcıları çözümle
            recipients = json.loads(item.recipients)
            cc = json.loads(item.cc) if item.cc else None
            bcc = json.loads(item.bcc) if item.bcc else None
            attachments = json.loads(item.attachments) if item.attachments else None
            context = json.loads(item.context_json) if item.context_json else None
            
            # SMTP ile gönder
            send_email_smtp(
                to_addr=", ".join(recipients),
                subject=item.subject,
                html_body=item.html_body,
                attachments=attachments,
                cc_addrs=", ".join(cc) if cc else None,
                bcc_addrs=", ".join(bcc) if bcc else None,
            )
            
            # Başarılı
            item.status = 'sent'
            item.sent_at = datetime.utcnow()
            db.session.commit()
            
            # Log oluştur
            create_mail_log(
                kind='send',
                ok=True,
                to_addr=item.recipients,
                subject=item.subject,
                mail_type=item.mail_type,
                body_preview=item.text_body or item.html_body[:200],
                body_html=item.html_body,
            )
            
            log.info(f"Mail sent successfully: {item.id} -> {len(recipients)} recipients")
            return True
            
        except Exception as e:
            # Hata yönetimi
            item.retry_count += 1
            item.error_message = str(e)
            
            if item.retry_count >= item.max_retries:
                item.status = 'failed'
                log.error(f"Mail {item.id} failed after {item.max_retries} retries")
            else:
                item.status = 'pending'  # Tekrar denenmek üzere
                item.scheduled_at = datetime.utcnow() + timedelta(seconds=30 * item.retry_count)
                log.warning(f"Mail {item.id} retry {item.retry_count}/{item.max_retries}")
            
            db.session.commit()
            
            # Hata logu
            create_mail_log(
                kind='send',
                ok=False,
                to_addr=item.recipients,
                subject=item.subject,
                mail_type=item.mail_type,
                error=item.error_message,
            )
            
            return False
    
    @staticmethod
    def cancel(queue_id: int) -> bool:
        """Mail iptal et"""
        item = MailQueue.query.get(queue_id)
        if item and item.status in ['pending', 'scheduled']:
            item.status = 'cancelled'
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def retry_failed(queue_id: int) -> bool:
        """Başarısız maili tekrar kuyruğa ekle"""
        item = MailQueue.query.get(queue_id)
        if item and item.status == 'failed':
            item.status = 'pending'
            item.retry_count = 0
            item.scheduled_at = datetime.utcnow()
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Kuyruk istatistikleri"""
        stats = {
            'pending': MailQueue.query.filter_by(status='pending').count(),
            'processing': MailQueue.query.filter_by(status='processing').count(),
            'sent': MailQueue.query.filter_by(status='sent').count(),
            'failed': MailQueue.query.filter_by(status='failed').count(),
        }
        stats['total'] = sum(stats.values())
        return stats
```

### 3.3 Flask Entegrasyonu

**Güncellenecek:** `app.py` veya `utils.py`

```python
# Mevcut send fonksiyonu yerine
def send_mail_async(
    *,
    mail_type: str,
    recipients: Union[str, List[str]],
    subject: str,
    html: str,
    cc: Union[str, List[str]] = None,
    bcc: Union[str, List[str]] = None,
    attachments: List[Dict] = None,
    context: Dict[str, Any] = None,
    priority: int = 0,
):
    """
    Mail'i kuyruğa ekle (async).
    
    Kullanım:
        send_mail_async(
            mail_type="task_created",
            recipients=["user@example.com"],
            subject="Yeni Görev",
            html="<p>...</p>",
        )
    """
    # String listeye çevir
    if isinstance(recipients, str):
        recipients = [x.strip() for x in recipients.split(",") if x.strip()]
    
    MailQueueService.enqueue(
        mail_type=mail_type,
        recipients=recipients,
        subject=subject,
        html_body=html,
        text_body=None,
        cc=cc,
        bcc=bcc,
        attachments=attachments,
        context=context,
        priority=priority,
    )
```

### 3.4 Background Worker

**Yeni dosya:** `workers/mail_worker.py`

```python
"""
Mail Queue Worker
-----------------
Bu script cron job veya supervisor ile çalıştırılmalı:
    python workers/mail_worker.py --daemon --interval 5

veya crontab:
    * * * * * cd /path/to/app && python workers/mail_worker.py --once
"""

import sys
import time
import signal
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# Import Flask app
from app import app
from extensions import db
from services.mail_queue_service import MailQueueService


class MailWorker:
    """Mail kuyruğu işleyici"""
    
    def __init__(self, interval: int = 5, batch_size: int = 20):
        self.interval = interval  # Saniye
        self.batch_size = batch_size
        self.running = True
        self.processed = 0
        
        # Signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
    
    def shutdown(self, signum, frame):
        log.info("Shutdown signal received, finishing current batch...")
        self.running = False
    
    def run(self):
        log.info(f"Mail worker started. Interval: {self.interval}s, Batch: {self.batch_size}")
        log.info("Press Ctrl+C to stop.")
        
        with app.app_context():
            while self.running:
                try:
                    result = MailQueueService.process_queue_batch(self.batch_size)
                    
                    if result['sent'] > 0 or result['failed'] > 0:
                        log.info(f"Batch complete: sent={result['sent']}, failed={result['failed']}, remaining={result['remaining']}")
                    
                    self.processed += result['sent'] + result['failed']
                    
                except Exception as e:
                    log.exception(f"Error in processing loop: {e}")
                
                # Interval bekle
                for i in range(self.interval):
                    if not self.running:
                        break
                    time.sleep(1)
        
        log.info(f"Mail worker stopped. Total processed: {self.processed}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Mail Queue Worker')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--interval', type=int, default=5, help='Processing interval in seconds')
    parser.add_argument('--batch', type=int, default=20, help='Batch size')
    parser.add_argument('--once', action='store_true', help='Process one batch and exit')
    
    args = parser.parse_args()
    
    worker = MailWorker(interval=args.interval, batch_size=args.batch)
    
    if args.once:
        with app.app_context():
            result = MailQueueService.process_queue_batch(args.batch)
            print(f"Processed: sent={result['sent']}, failed={result['failed']}, remaining={result['remaining']}")
    elif args.daemon:
        worker.run()
    else:
        # Interactive mode
        print("Running single batch. Use --once for cron, --daemon for background.")
        with app.app_context():
            result = MailQueueService.process_queue_batch(args.batch)
            print(f"Processed: sent={result['sent']}, failed={result['failed']}, remaining={result['remaining']}")


if __name__ == '__main__':
    main()
```

### 3.5 API Endpoints

**Güncellenecek:** `routes/api.py` - Mail queue status endpoint

```python
@api.route('/mail/queue/stats')
def api_mail_queue_stats():
    """Kuyruk istatistiklerini getir"""
    stats = MailQueueService.get_stats()
    return jsonify({
        'ok': True,
        'stats': stats,
        'timestamp': datetime.utcnow().isoformat(),
    })


@api.route('/mail/queue/process', methods=['POST'])
def api_mail_queue_process():
    """Manuel olarak kuyruğu işle (test amaçlı)"""
    if not current_user.is_admin:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 403
    
    result = MailQueueService.process_queue_batch(20)
    return jsonify({
        'ok': True,
        'result': result,
    })
```

---

## 📊 KAYNAKLAR VE ÖNEM SIRASI

### Öncelik 1: Mail Queue Sistemi (En Önemli)
- [ ] `migration_create_mail_queue.py` - Veritabanı modeli
- [ ] `services/mail_queue_service.py` - Queue service
- [ ] `workers/mail_worker.py` - Background worker
- [ ] `utils.py` - Async send fonksiyonu güncelleme

### Öncelik 2: Zenginleştirilmiş Mail Şablonları
- [ ] `render_base_email()` - Ana template fonksiyonu
- [ ] `render_task_notification_email()` - Görev bildirimi
- [ ] `render_weekly_plan_email()` - Haftalık plan
- [ ] Diğer şablonların güncellenmesi

### Öncelik 3: Frontend İyileştirmeleri
- [ ] Mail log sayfasında kuyruk durumu gösterimi
- [ ] Gerçek zamanlı güncellemeler için WebSocket entegrasyonu
- [ ] Admin panelinde kuyruk yönetimi

---

## ✅ CHECKLIST

### Tamamlananlar
- [x] Personel listesi sayfa uzantısı (CSS flexbox ile)

### Yapılacaklar
#### Mail Queue Sistemi
- [ ] MailQueue model oluşturma
- [ ] MailQueueService implementasyonu
- [ ] Background worker scripti
- #### Mevcut kodun güncellenmesi
        - [ ] `utils.py` send_email_async()
        - [ ] `planner.py` içindeki mail gönderimleri
        - [ ] `admin.py` içindeki mail gönderimleri

#### Mail Şablonları
- [ ] Base email template fonksiyonu
- [ ] Görev bildirimi şablonu
- [ ] Haftalık plan şablonu
- [ ] Diğer şablonların güncellenmesi

---

## 📝 NOTLAR

1. **Cron/Supervisord Kurulumu:**
   ```bash
   # Crontab'a ekle (her dakika)
   * * * * * cd /path/to/app && python workers/mail_worker.py --once
   ```

2. **Systemd Service (Ubuntu/Debian):**
   ```ini
   # /etc/systemd/system/mail-worker.service
   [Unit]
   Description=Mail Queue Worker
   After=network.target
   
   [Service]
   User=www-data
   WorkingDirectory=/path/to/app
   ExecStart=/usr/bin/python workers/mail_worker.py --daemon --interval 5
   Restart=always
   
   [Install]
   WantedBy=multi-user.target
   ```

3. **Migration Çalıştırma:**
   ```bash
   flask db upgrade
   ```

4. **Test Etme:**
   ```bash
   # Worker'ı test modunda çalıştır
   python workers/mail_worker.py --once
   
   # Manuel tetikleme
   curl -X POST http://localhost:5000/api/mail/queue/process
   ```
