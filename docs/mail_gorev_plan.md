## Mail Sistemi – Teknik Görev Planı

### 1) Şablon Birleştirme ve Görsel Tutarlılık
- Tüm gönderim kanallarını en az bir ortak base template’e (örn. `templates/email_base.html`) indir; `planner.py` / `realtime.py` / `tasks.py` / bulk & weekly mailler aynı layout + aynı tipografi/renkleri kullansın.
- Mevcut inline HTML’leri (özellikle tablo maili, görev bildirimi, proje ekleme maili) parçala: header, body, footer, CTA ve “otomatik mail” notu için ortak kısmi şablonlar (`templates/email/partials/*.html`).
- Outlook uyumluluğu için tablo yapısını tek bir CSS bloğuna topla; inline stil setini tek dosyada sakla (örn. `static/email/email-inline.css`) ve render’da inline eder hale getir.

### 2) Mail Ayar Ekranını Sekmeli Yapı + Önizleme
- `routes/admin.py /mail/settings` sayfasını sekmeli hale getir: Genel SMTP, Gönderim kuralları, Şablon seçimi, Varsayılan alıcılar/CC, Test & Önizleme.
- Her sekmede ilgili mail türleri için (görev bildirimi, plan tablosu, proje ekleme, haftalık/ekip maili, toplu mail) şunları ekle:
  - Şablon seçimi (listeden veya custom HTML ID’si).
  - Varsayılan başlık/subject formatı.
  - Özel alan (örn. footer metni, imza).
  - “Bu ayarlar hangi endpoint’i etkiler” bilgisi.
- Önizleme butonu: seçili şablon + dummy veri ile `/api/.../preview_*` endpoint’lerinden alınan HTML’i modalda göster; farklı alıcıya gönder test butonu ekle.

### 3) Gönderim Akışlarında Ayar Kullanımı
- `planner.py` / `realtime.py` / `tasks.py` mail gönderen fonksiyonları ayar sayfasındaki seçilen şablon ve subject kalıbını kullanacak şekilde refaktör et; fallback olarak mevcut defaultu koru.
- CC/BCC, from name, reply-to değerlerini ayarlardan çek; her gönderimde uygulandığını doğrula.

### 4) Loglama İyileştirmeleri
- `MailLog` kayıtlarına aşağıdaki alanları ekle: `template_id`, `kind` (send/preview/test/system), `cc`, `bcc`, `attachments`, `trigger`, `user_id`, `job_id/task_id/project_id` referansları, `duration_ms`, `smtp_error_code`, `smtp_error_message`.
- Tüm gönderim noktalarında `create_mail_log` çağrılarını bu alanlarla doldur; hatalarda `_mail_error_meta_from_exc` çıktısını `meta` içine yaz.
- Log tutarlılığı: preview ve test mailleri de loglansın; en az 2000 kayıt için rapor sayfası filtrelenebilir kalmalı.

### 5) Log Görselleştirme ve Filtreler
- `/reports/mail-log` sayfasına filtre barı ekle: tarih aralığı, mail türü, şablon, alıcı, durum (ok/fail), tetikleyici (kullanıcı/cron), ilgili entity (task/project/team/job).
- Liste sütunları: zaman, subject, to/cc/bcc, şablon, tür, durum, süre, hata kodu. Satıra tıkla → modal ile mail body preview (log meta veya body snapshot’tan).
- Excel/CSV export’ta yeni alanları dahil et.

### 6) Şablon Yönetimi ve Önizleme API’leri
- Mevcut `/admin/mail-templates` ekranını genişlet: şablon kategorisi (task/plan/weekly/bulk/system), sürüm açıklaması, son değiştiren.
- Yeni preview endpoint’leri: her mail türü için `.../preview_*` HTML + subject döndürsün; admin sayfasındaki modal bunları kullansın.

### 7) Teslim ve Test
- Birim/entegrasyon: mail ayar senaryosu (şablon seç → preview → send test) için happy path + invalid smtp + boş alıcı testleri.
- Manuel smoke: her mail türü için bir test alıcıya gönderim; UI’de önizleme görüntüleme; log ekranında görünürlük ve filtreler.
- Performans: log insert’lerinin kritik path’i yavaşlatmadığını ölç (duration_ms alanı ile).

### 8) Geçiş / Geriye Dönük Uyumluluk
- Eski ayar dosyasındaki (cfg) değerleri yeni alanlara map et; olmayanları varsayılanlarla doldur. Log şeması migration’ını veri kaybı olmadan yap; eski kayıtları “unknown” template_id ile işaretle.

### 9) Dokümantasyon
- `docs/` altına “Mail gönderim mimarisi” ve “Şablon ekleme/önizleme rehberi”; ayar sekmelerinin hangi endpoint’leri etkilediğini tablo halinde ekle.
