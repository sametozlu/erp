# Kapsamlı Mail Sistemi Geliştirme Görevi

## Görev Özeti

Mevcut dağınık mail sistemini **tek bir merkezi noktaya entegre etmek** ve tüm mail işlemlerini yönetilebilir hale getirmek.

---

## Mevcut Durum Analizi

### 1. Mevcut Mail Bileşenleri

#### 1.1 Modeller ([`models.py`](models.py))

**MailLog** (satır 227-267):
```python
class MailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    
    # İdentifikasyon
    mail_type = db.Column(db.String(50), nullable=True, index=True)  # weekly/team/job/bulk/test/project/task
    kind = db.Column(db.String(30), nullable=False, default="send", index=True)  # send/test/preview
    
    # Durum
    ok = db.Column(db.Boolean, nullable=False, default=False, index=True)
    error_code = db.Column(db.String(50), nullable=True)
    error = db.Column(db.Text, nullable=True)
    
    # İçerik - Alıcılar
    to_addr = db.Column(db.String(500), nullable=False, default="")
    cc_addr = db.Column(db.String(500), nullable=True)
    bcc_addr = db.Column(db.String(500), nullable=True)
    subject = db.Column(db.String(255), nullable=False, default="")
    body_preview = db.Column(db.Text, nullable=True)
    
    # İlişkili Veriler
    week_start = db.Column(db.Date, nullable=True, index=True)
    team_id = db.Column(db.Integer, nullable=True, index=True)
    team_name = db.Column(db.String(120), nullable=True)
    project_id = db.Column(db.Integer, nullable=True, index=True)
    job_id = db.Column(db.Integer, nullable=True, index=True)
    task_id = db.Column(db.Integer, nullable=True, index=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    
    # Meta
    meta_json = db.Column(db.Text, nullable=True)
    attachments_count = db.Column(db.Integer, nullable=False, default=0)
    body_size_bytes = db.Column(db.Integer, nullable=False, default=0)
    
    # Zaman Damgaları
    sent_at = db.Column(db.DateTime, nullable=True, index=True)
```

**MailTemplate** (satır 357-366):
```python
class MailTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    subject_template = db.Column(db.Text, nullable=False)
    heading_template = db.Column(db.Text, nullable=True)
    intro_template = db.Column(db.Text, nullable=True)
    body_template = db.Column(db.Text, nullable=False)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
```

#### 1.2 Mail Gönderim Fonksiyonları

**utils.py** ([`utils.py:824`](utils.py:824)):

`send_email_smtp()` - Ana SMTP gönderim fonksiyonu:
- SMTP host/port yapılandırması
- TLS/SSL desteği
- Attachment desteği (dosya ekleme)
- Retry mekanizması (3 deneme)
- CC/BCC desteği

`create_mail_log()` - ([`utils.py:918`](utils.py:918)):
- Kapsamlı loglama
- Meta veri kaydetme
- Attachment bilgisi
- Hata durumları
- Zaman damgası

#### 1.3 Routes'da Mail Gönderim Noktaları

| Dosya | Route | Mail Türü |
|-------|-------|-----------|
| [`routes/planner.py`](routes/planner.py:1686) | `send_job_mail` | İş Atama |
| [`routes/planner.py`](routes/planner.py:2051) | `publish_week` | Haftalık Plan |
| [`routes/planner.py`](routes/planner.py:3675) | `preview_job_mail` | İş Önizleme |
| [`routes/planner.py`](routes/planner.py:3782) | `send_bulk_team_report` | Toplu Ekip |
| [`routes/planner.py`](routes/planner.py:8094) | `preview_weekly_report` | Haftalık Önizleme |
| [`routes/planner.py`](routes/planner.py:8234) | `send_weekly_report` | Haftalık Rapor |
| [`routes/planner.py`](routes/planner.py:8374) | `preview_team_report` | Ekip Önizleme |
| [`routes/planner.py`](routes/planner.py:8466) | `send_team_report` | Ekip Raporu |
| [`routes/planner.py`](routes/planner.py:8604) | `send_weekly_personal` | Kişisel Haftalık |
| [`routes/planner.py`](routes/planner.py:8765) | `send_team_personal` | Kişisel Ekip |
| [`routes/tasks.py`](routes/tasks.py:76) | `send_task_email` | Görev Bildirimi |

#### 1.4 Mevcut Mail Türleri

```python
DEFAULT_TEMPLATES = {
    "weekly": "Haftalık Plan Maili",
    "team": "Ekip Plan Maili",
    "job": "İş Atama Maili",
    "task": "Görev Bildirimi",
    "cell": "İş Detayı (Hücre)",
    "bulk": "Toplu Bildirim"
}
```

#### 1.5 Admin Arayüzü ([`templates/mail_settings.html`](templates/mail_settings.html))

Mevcut sekmeler:
1. **SMTP Ayarları** - Host, port, kullanıcı, şifre, TLS/SSL
2. **Gönderim Logları** - Filtreleme, sayfalama, detay görüntüleme
3. **Şablonlar & Önizleme** - Template düzenleme, canlı önizleme

---

## Tespit Edilen Eksiklikler

### 1. Merkezi Entegrasyon Eksikliği

**Sorun:** Her route'da ayrı `send_email_smtp` ve `create_mail_log` çağrısı var.
- Kod tekrarı
- Tutarsız davranış
- Yeni özellik eklemesi zor

### 2. Template Sisteminin Sınırlılıkları

**Sorun:** Sadece subject, heading, intro, body alanları var.
- Dinamik içerik (tablo, liste vb.) için destek yok
- Conditional content (koşullu içerik) yok
- Değişken genişletme sınırlı

### 3. Mail Görüntüleme Eksikliği

**Sorun:** Log tablosunda sadece özet bilgi var.
- Gerçek mail içeriği görüntülenemiyor
- Attachment dosyaları listelenmiyor
- Detaylı arama yok

### 4. Bildirim Sistemi Yetersiz

**Sorun:** Sadece hata durumunda admin bildirimi var.
- Başarılı gönderim bildirimi yok
- Scheduled mail bildirimi yok
- Toplu işlem bildirimi yok

### 5. Performans ve Güvenlik

**Sorun:** Büyük attachment'lar ve toplu gönderimler.
- Attachment boyutu kontrolü yok
- Rate limiting yok
- Queue sistemi yok

---

## Yapılması Gerekenler

### FASE 1: Merkezi Mail Servisi

#### 1.1 MailService Sınıfı Oluşturma

Dosya: `services/mail_service.py`

```python
class MailService:
    """Merkezi Mail Servisi"""
    
    @staticmethod
    def send(mail_type: str, recipients: list, subject: str, html: str, 
             attachments: list = None, cc: list = None, bcc: list = None,
             context: dict = None, user_id: int = None, **kwargs):
        """
        Merkezi mail gönderim fonksiyonu
        
        Args:
            mail_type: Mail türü (weekly, task, job, etc.)
            recipients: Alıcı listesi
            subject: Mail konusu
            html: Mail içeriği (HTML)
            attachments: Ek dosya listesi [{filename, data, content_type}]
            cc: CC alıcıları
            bcc: BCC alıcıları
            context: Template değişkenleri
            user_id: Gönderen kullanıcı ID
        """
        pass
    
    @staticmethod
    def send_template(mail_type: str, recipients: list, template_data: dict,
                      user_id: int = None, **kwargs):
        """Template kullanarak mail gönder"""
        pass
    
    @staticmethod
    def get_template(mail_type: str) -> MailTemplate:
        """Mail şablonu getir"""
        pass
    
    @staticmethod
    def update_template(mail_type: str, data: dict):
        """Mail şablonu güncelle"""
        pass
    
    @staticmethod
    def preview_template(mail_type: str, context: dict) -> str:
        """Template önizleme"""
        pass
```

#### 1.2 Mevcut Kodun Refactor Edilmesi

Tüm route'lardaki mail gönderimlerini `MailService` kullanacak şekilde güncelle:

```python
# ÖNCE (routes/planner.py)
send_email_smtp(recipient, subject, html_body, attachments=None)
create_mail_log(kind="send", ok=True, to_addr=recipient, subject=subject, ...)

# SONRA
MailService.send(
    mail_type="job",
    recipients=[recipient],
    subject=subject,
    html=html_body,
    attachments=attachments,
    user_id=current_user.id
)
```

### FASE 2: Gelişmiş Template Sistemi

#### 2.1 Dinamik Template Değişkenleri

```python
TEMPLATE_VARIABLES = {
    "weekly": {
        "week_start": "Hafta başlangıç tarihi",
        "week_end": "Hafta bitiş tarihi",
        "person_name": "Personel adı",
        "person_email": "Personel email",
        "team_name": "Ekip adı",
        "total_jobs": "Toplam iş sayısı",
        "jobs_table": "İşler tablosu (HTML)",
        "summary_stats": "Özet istatistikler",
    },
    "task": {
        "task_no": "Görev numarası",
        "task_subject": "Görev konusu",
        "task_description": "Görev açıklaması",
        "task_priority": "Önem derecesi",
        "target_date": "Hedef tarih",
        "days_left": "Kalan gün",
        "assigned_user": "Atanan kullanıcı",
        "created_by": "Oluşturan kullanıcı",
        "link_url": "Görev linki",
    },
    # ... diğer türler
}
```

#### 2.2 Koşullu Template Desteği

Template'lerde {% if %}, {% for %} gibi Jinja2 syntax desteği:

```html
<!-- Örnek: Görev maili -->
<h1>{{ task_subject }}</h1>

{% if days_left < 0 %}
<div style="background: #fee2e2; padding: 10px; color: #dc2626;">
    ⚠️ Bu görevin süresi {{ abs(days_left) }} gün geçti!
</div>
{% endif %}

<table>
{% for job in jobs %}
    <tr>
        <td>{{ job.project_name }}</td>
        <td>{{ job.shift }}</td>
        <td>{{ job.vehicle }}</td>
    </tr>
{% endfor %}
</table>
```

#### 2.3 Template Versiyonlama

```python
class MailTemplateVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("mail_template.id"))
    version = db.Column(db.Integer, nullable=False)
    subject_template = db.Column(db.Text)
    body_template = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by_user_id = db.Column(db.Integer)
```

### FASE 3: Gelişmiş Log Görüntüleme

#### 3.1 Mail Detay Sayfası

Yeni route: `/admin/mail-log/<log_id>`

```python
@admin_bp.get("/mail-log/<int:log_id>")
@admin_required
def view_mail_log(log_id: int):
    """Mail log detayını görüntüle"""
    log = MailLog.query.get_or_404(log_id)
    return render_template("mail_log_detail.html", log=log)
```

#### 3.2 Gelişmiş Arama ve Filtreleme

```python
@admin_bp.get("/api/mail/logs/search")
@admin_required
def search_mail_logs():
    """Gelişmiş mail log arama"""
    query = request.args.get("q", "")
    mail_type = request.args.get("type")
    status = request.args.get("status")  # ok, error
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    user_id = request.args.get("user_id")
    has_attachment = request.args.get("has_attachment")
    
    # Log sorgulama
    logs = MailLog.query.filter(...)
    
    return jsonify({"logs": [...], "count": total})
```

#### 3.3 Attachment İndirme

```python
@admin_bp.get("/api/mail/log/<int:log_id>/attachment/<filename>")
@admin_required
def download_mail_attachment(log_id: int, filename: str):
    """Mail ekini indir"""
    log = MailLog.query.get_or_404(log_id)
    # Attachment'ı bul ve döndür
```

### FASE 4: Bildirim ve İzleme Sistemi

#### 4.1 Mail Durumu Dashboard

```python
@admin_bp.get("/api/mail/stats")
@admin_required
def mail_stats():
    """Mail istatistikleri"""
    today = date.today()
    
    stats = {
        "today": {
            "sent": MailLog.query.filter_by(ok=True, sent_at=today).count(),
            "failed": MailLog.query.filter_by(ok=False).count(),
        },
        "this_week": {...},
        "by_type": {...},
        "top_recipients": [...],
        "error_summary": {...},
    }
    return jsonify(stats)
```

#### 4.2 Hata Otomatik Bildirimi

```python
# app.py - startup'da scheduler başlat
from apscheduler.schedulers.background import BackgroundScheduler

def check_failed_mails():
    """Başarısız mailleri kontrol et ve bildir"""
    failed_logs = MailLog.query.filter_by(ok=False).filter(
        MailLog.created_at >= datetime.now() - timedelta(hours=1)
    ).all()
    
    if failed_logs:
        notify_admins(
            event='mail_failure_alert',
            title=f"{len(failed_logs)} Mail Gönderimi Başarısız",
            body=f"Son 1 saatte {len(failed_logs)} mail gönderilemedi.",
            link_url="/admin/mail-settings#logs"
        )

scheduler = BackgroundScheduler()
scheduler.add_job(check_failed_mails, 'interval', minutes=30)
scheduler.start()
```

#### 4.3 Başarılı Gönderim Özeti

```python
def send_daily_summary():
    """Günlük mail gönderim özeti"""
    yesterday = date.today() - timedelta(days=1)
    
    stats = {
        "total_sent": MailLog.query.filter_by(ok=True, sent_at=yesterday).count(),
        "total_failed": MailLog.query.filter_by(ok=False, created_at=yesterday).count(),
        "by_type": {...},
        "top_errors": [...],
    }
    
    # Admin'e özet mail gönder
    send_email_smtp(
        to_addr=admin_email,
        subject=f"Günlük Mail Raporu - {yesterday}",
        html=render_template("daily_mail_summary.html", stats=stats)
    )
```

### FASE 5: Queue ve Performans

#### 5.1 Background Queue Sistemi

```python
from celery import Celery

celery_app = Celery('tasks', broker='redis://localhost:6379/0')

@celery_app.task(bind=True, max_retries=3)
def send_mail_task(self, mail_log_id: int):
    """Background mail gönderimi"""
    log = MailLog.query.get(mail_log_id)
    try:
        send_email_smtp(
            to_addr=log.to_addr,
            subject=log.subject,
            html=log.body_preview,  # veya tam içerik
        )
        log.ok = True
        log.sent_at = datetime.now()
    except Exception as e:
        log.ok = False
        log.error = str(e)
        raise self.retry(exc=e, countdown=60)
    finally:
        db.session.commit()
```

#### 5.2 Rate Limiting

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="redis://localhost:6379/1"
)

@admin_bp.route("/api/mail/send", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def send_mail_api():
    """Rate limited mail gönderimi"""
```

---

## Yeni Template Türleri

### 1. Süre Bitim Maili (Deadline Expired)

```python
DEFAULT_TEMPLATES["deadline_expired"] = {
    "name": "deadline_expired",
    "subject": "[SÜRE BİTTİ] {{task_no}} - {{task_subject}}",
    "heading": "Görev Süresi Doldu",
    "intro": "Merhaba {{assigned_user_name}},",
    "content": """
    <div style="background: #fee2e2; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <h2 style="margin: 0 0 10px 0; color: #dc2626;">⚠️ Görev Süresi Doldu</h2>
        <p>Aşağıdaki görevin süresi geçmiştir:</p>
        <ul>
            <li><strong>Görev No:</strong> {{task_no}}</li>
            <li><strong>Konu:</strong> {{task_subject}}</li>
            <li><strong>Hedef Tarih:</strong> {{target_date}}</li>
            <li><strong>Geçen Süre:</strong> {{days_overdue}} gün</li>
        </ul>
    </div>
    <a href="{{link_url}}" style="background: #3b82f6; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none;">Görevi Görüntüle</a>
    """
}
```

### 2. Hatırlatma Maili (Reminder)

```python
DEFAULT_TEMPLATES["reminder"] = {
    "name": "reminder",
    "subject": "[HATIRLATMA] {{task_no}} - {{task_subject}}",
    "heading": "Görev Hatırlatması",
    "intro": "Merhaba {{assigned_user_name}},",
    "content": """
    <div style="background: #fef3c7; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <h2 style="margin: 0 0 10px 0; color: #d97706;">⏰ Görev Hatırlatması</h2>
        <p>Aşağıdaki görevin bitmesine <strong>{{days_left}} gün</strong> kaldı:</p>
        <ul>
            <li><strong>Görev No:</strong> {{task_no}}</li>
            <li><strong>Konu:</strong> {{task_subject}}</li>
            <li><strong>Hedef Tarih:</strong> {{target_date}}</li>
        </ul>
    </div>
    """
}
```

---

## Geliştirme Öncelikleri

### P0 - Kritik (İlk Sürüm)
1. [ ] `MailService` sınıfı oluşturma
2. [ ] Mevcut kodun `MailService`'e taşınması
3. [ ] Deadline expired template ekleme
4. [ ] Reminder template ekleme
5. [ ] Log detay sayfası

### P1 - Önemli (v2)
1. [ ] Gelişmiş arama/filtreleme
2. [ ] Attachment indirme
3. [ ] Mail stats dashboard
4. [ ] Otomatik hata bildirimi

### P2 - Normal (v3)
1. [ ] Background queue (Celery)
2. [ ] Rate limiting
3. [ ] Template versiyonlama
4. [ ] Koşullu template desteği

---

## Test Senaryoları

### Birim Testleri
- [ ] Mail gönderim fonksiyonu
- [ ] Template rendering
- [ ] Log kaydetme
- [ ] Hata durumları

### Entegrasyon Testleri
- [ ] Tüm mail türleri gönderimi
- [ ] Attachment ekleme
- [ ] CC/BCC desteği
- [ ] Retry mekanizması

### UI Testleri
- [ ] Template editor
- [ ] Log görüntüleme
- [ ] Arama/filtreleme
- [ ] Önizleme

---

## Bağımlılıklar

```python
# requirements.txt'ye eklenecek
celery>=5.0.0
redis>=4.0.0
flask-limiter>=3.0.0
```

---

## Geçiş Planı

### Adım 1: MailService Entegrasyonu
- Yeni `MailService` sınıfı oluştur
- Mevcut `send_email_smtp` ve `create_mail_log` çağrılarını değiştir
- Test et

### Adım 2: Yeni Template'ler
- Deadline expired template ekle
- Reminder template ekle
- Mail sistemi entegrasyonu

### Adım 3: UI İyileştirmeleri
- Log detay sayfası
- Gelişmiş arama
- Attachment indirme

### Adım 4: İzleme ve Bildirim
- Stats dashboard
- Hata bildirimi
- Günlük özet

---

## Riskler ve Önlemler

| Risk | Önlem |
|------|-------|
| Mevcut mailler bozulabilir | A/B test, geri dönüş planı |
| Performans düşüşü | Queue sistemi, caching |
| Template hataları | Version kontrolü, önizleme |
| SMTP hizmet kesintisi | Retry, alternatif SMTP |
