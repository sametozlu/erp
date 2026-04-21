# Görev Süresi Bitim Bildirimi ve Yanıp Sönme Görevi

## Problem Tanımı

**http://127.0.0.1:5000/tasks/** sayfasında:

1. **Halledilmeyen ve süresi geçen görevler:** "Gün" yazısı yanıp sönmesi isteniyor
2. **Süresi geçen görevler:** İlgili kişiye otomatik mail atılması isteniyor

## Mevcut Durum Analizi

### Mevcut "Gün" (Kalan Süre) Gösterimi

Dosya: [`templates/tasks.html`](templates/tasks.html:4237-4243)

Mevcut kod:
```javascript
const daysLeft = getDaysLeft(t.target_date, t.closed_at);
let daysBadge = '-';
if (daysLeft !== null) {
    let badgeClass = 'days-left-ok';
    if (daysLeft < 0) badgeClass = 'days-left-critical';  // Süresi geçmiş
    else if (daysLeft <= 2) badgeClass = 'days-left-warn';  // 2 gün veya az kalmış

    const dayText = daysLeft < 0 ? `${Math.abs(daysLeft)} Gün Geçti` : `${daysLeft} Gün`;
    daysBadge = `<span class="days-left-badge ${badgeClass}">${dayText}</span>`;
}
```

Mevcut CSS (satır 1567-1585):
```css
.days-left-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}

.days-left-ok {
    background: var(--status-success);
    color: white;
}

.days-left-warn {
    background: var(--status-warning);
    color: white;
}

.days-left-critical {
    background: var(--status-danger);
    color: white;
}
```

**Sorun:** Süresi geçen görevler için sadece kırmızı arka plan var, yanıp sönme (blinking) yok.

### Mevcut Mail Sistemi

Dosya: [`routes/tasks.py`](routes/tasks.py:76-349)

Mevcut `send_task_email` fonksiyonu şu durumlarda mail gönderiyor:
- Görev oluşturulduğunda (`created`)
- Görev atandığında (`assigned`)
- Durum değiştiğinde (`status_changed`)
- Yorum eklendiğinde (`comment`)
- Görev güncellendiğinde (`updated`)

**Sorun:** Görev süresi (target_date) geçtiğinde otomatik mail gönderilmiyor.

## Yapılması Gerekenler

### 1. "Gün" Yazısı Yanıp Sönme Efekti

#### 1.1 CSS Eklenmesi

[`templates/tasks.html`](templates/tasks.html:1567) dosyasına CSS ekle:

```css
/* Yanıp sönme animasyonu */
@keyframes blink-animation {
    0% { opacity: 1; }
    50% { opacity: 0.4; }
    100% { opacity: 1; }
}

.days-left-blink {
    animation: blink-animation 1s infinite;
}
```

#### 1.2 JavaScript Güncellemesi

[`templates/tasks.html`](templates/tasks.html:4237-4243) dosyasında:

```javascript
const daysLeft = getDaysLeft(t.target_date, t.closed_at);
let daysBadge = '-';
if (daysLeft !== null) {
    let badgeClass = 'days-left-ok';
    let blinkClass = '';
    
    if (daysLeft < 0) {
        badgeClass = 'days-left-critical';
        blinkClass = 'days-left-blink';  // Süresi geçmişse yanıp sön
    } else if (daysLeft <= 2) {
        badgeClass = 'days-left-warn';
    }

    const dayText = daysLeft < 0 ? `${Math.abs(daysLeft)} Gün Geçti` : `${daysLeft} Gün`;
    daysBadge = `<span class="days-left-badge ${badgeClass} ${blinkClass}">${dayText}</span>`;
}
```

### 2. Süre Bitim Maili Gönderimi

#### 2.1 Yeni Mail Türü Ekleme

[`routes/tasks.py`](routes/tasks.py:76) dosyasına `send_task_email` fonksiyonuna yeni event_type ekle:

```python
elif event_type == "deadline_expired":
    subject = f"[SÜRE BİTTİ] {task.task_no} - {task.subject}"
    action_text = f"Görevin süresi doldu. Lütfen görevi tamamlayın veya yeni bir süre belirleyin."
```

#### 2.2 Scheduled Task / Cron Job

Görev süresi dolduğunda mail göndermek için bir mekanizma kurulmalı.

**Seçenek A: Flask-APScheduler Kullanımı**

```python
from apscheduler.schedulers.background import BackgroundScheduler

def check_expired_tasks():
    """Süresi dolan görevleri kontrol et ve mail gönder"""
    today = date.today()
    
    # Süresi dolmuş açık görevleri bul
    expired_tasks = Task.query.filter(
        Task.target_date < today,
        ~Task.status.in_(['Tamamlandı', 'Kapatıldı', 'İptal'])
    ).all()
    
    for task in expired_tasks:
        # Daha önce mail gönderilmiş mi kontrol et
        last_reminder = getattr(task, 'last_deadline_mail_at', None)
        if not last_reminder or last_reminder.date() < today:
            # Mail gönder
            send_task_email(task, "deadline_expired")
            # Son gönderim zamanını kaydet
            task.last_deadline_mail_at = datetime.now()
    
    db.session.commit()

# Scheduler başlat
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_expired_tasks, trigger="cron", hour=8, minute=0)  # Her gün saat 08:00'de çalış
scheduler.start()
```

**Seçenek B: Basit HTTP Trigger**

Her gün bir kez çalışacak bir endpoint:

```python
@tasks_bp.route("/api/check-deadlines", methods=["POST"])
@login_required
def check_deadlines():
    """Süresi dolan görevleri kontrol et ve mail gönder"""
    today = date.today()
    
    # Süresi dolmuş açık görevleri bul
    expired_tasks = Task.query.filter(
        Task.target_date < today,
        ~Task.status.in_(['Tamamlandı', 'Kapatıldı', 'İptal'])
    ).all()
    
    sent_count = 0
    for task in expired_tasks:
        # Son gönderim zamanını kontrol et
        last_mail = getattr(task, 'last_deadline_mail_at', None)
        
        # Bugün daha önce mail gönderilmediyse
        if not last_mail or last_mail.date() < today:
            send_task_email(task, "deadline_expired")
            task.last_deadline_mail_at = datetime.now()
            sent_count += 1
    
    db.session.commit()
    
    return jsonify({
        "ok": True,
        "message": f"{sent_count} göreve süre bitim maili gönderildi"
    })
```

Bu endpoint, harici bir cron job ile veya sistemde her gün bir kez tetiklenebilir.

#### 2.3 Model Güncellemesi (Gerekirse)

[`models.py`](models.py:716) Task modeline:

```python
class Task(db.Model):
    # ... mevcut alanlar ...
    
    # Yeni alanlar
    last_deadline_mail_at = db.Column(db.DateTime, nullable=True)  # Son süre bitim maili zamanı
```

### 3. Model Migration

Yeni alanı veritabanına eklemek için migration:

```python
# migration_add_deadline_mail_field.py
def run_migration():
    # Task tablosuna last_deadline_mail_at ekle
    try:
        db.session.execute(text("ALTER TABLE task ADD COLUMN last_deadline_mail_at DATETIME"))
        db.session.commit()
        print("Migration: last_deadline_mail_at alanı eklendi")
    except Exception as e:
        print(f"Migration hatası: {e}")
        db.session.rollback()
```

## Öncelik

**Yüksek** - Görev takibi için kritik özellikler.

## Test Edilecek Senaryolar

1. ✅ Süresi geçmiş görevlerde "Gün Geçti" yazısı yanıp sönüyor mu?
2. ✅ Yeni eklenen CSS animasyonu doğru çalışıyor mu?
3. ✅ Mail sistemi doğru alıcıya gidiyor mu?
4. ✅ Aynı göreve tekrar tekrar mail gidiyor mu (önleme mekanizması)?
5. ✅ Manuel tetikleme endpoint'i çalışıyor mu?

## Örnek Mail İçeriği

**Konu:** [SÜRE BİTTİ] NG0042 - Kablo Değişimi

**İçerik:**
> Görev Süresi Doldu
>
> Görev No: NG0042
> Görev: Kablo Değişimi
> Hedef Tarihi: 01.02.2026 (Geçmiş)
> Atanan Kişi: Ahmet Yılmaz
>
> Bu görevin süresi dolmuştur. Lütfen görevi tamamlayın veya yeni bir hedef tarih belirleyin.
>
> Görevi görüntülemek için tıklayın: [Link]

## Teknik Notlar

1. Mail sadece açık görevler için gönderilecek (Tamamlandı, Kapatıldı, İptal durumları için değil)
2. Aynı güne birden fazla mail gitmesini önlemek için `last_deadline_mail_at` alanı kullanılacak
3. Blinking efekti sadece süresi geçmiş görevler için aktif olacak
4. Animasyon 1 saniye aralıklarla yanıp sönecek
