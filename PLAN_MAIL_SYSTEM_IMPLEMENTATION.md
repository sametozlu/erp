# Mail Sistemi Onarım ve İyileştirme Planı

`TASK_MAIL_SYSTEM_ANALYSIS.md` dosyasındaki analizlere dayanarak oluşturulan uygulama planı aşağıdadır.

## 1. Durum Tespiti
*   **Veritabanı:** `app.db` üzerinde "malformed" hatası raporlanmış. Bu durum veri kaybı riski taşır. Öncelikli olarak kontrol edilmeli.
*   **MailLog Modeli:** Kod tarafında `MailLog` modelinde `team_id` alanı var (models.py:250), ancak veritabanı tablosunda bu sütun fiziksel olarak oluşmamış olabilir.
*   **Kod Hataları:** `utils.py` içinde `Environment` import hatası raporlanmış.

## 2. Uygulama Adımları

### AŞAMA 1: Güvenlik ve Bütünlük (Öncelikli)
1.  **Yedekleme:** Mevcut `app.db` ve `planner.db` dosyalarının yedeği (`.backup` uzantılı olarak) alınacak.
2.  **Sağlık Taraması:** `PRAGMA integrity_check` komutu ile veritabanı dosyalarının bozuk olup olmadığı test edilecek.
3.  **Onarım (Gerekirse):** Eğer bozukluk tespit edilirse, veriler dump edilip yeni bir dosyaya aktarılarak onarılacak.

### AŞAMA 2: Veritabanı Şema Güncellemesi
1.  **MailLog Kontrolü:** `MailLog` tablosunda `team_id` sütununun varlığı kontrol edilecek.
2.  **Sütun Ekleme:** Eğer sütun yoksa, `ALTER TABLE mail_log ADD COLUMN team_id INTEGER;` SQL komutuyla eklenecek.
3.  **İndeksleme:** Performans için `team_id` üzerine indeks eklenecek.

### AŞAMA 3: Kod İyileştirmeleri
1.  **Import Düzeltmesi:** `utils.py` dosyasındaki `jinja2` importları gözden geçirilecek ve olası isim çakışmaları (shadowing) giderilecek.
2.  **Hata Yönetimi:** `create_mail_log` fonksiyonunda model uyumsuzluklarına karşı `try-except` blokları güçlendirilecek.

### AŞAMA 4: Test ve Doğrulama
1.  **Test Maili:** Sistemin uçtan uca çalışıp çalışmadığını görmek için test maili gönderilecek.
2.  **Kuyruk Kontrolü:** `/admin/mail-queue` sayfası üzerinden bekleyen ve gönderilen maillerin durumu kontrol edilecek.

## 3. Onay
Bu planı onayladığınızda, işlemlere AŞAMA 1'den başlayarak sırasıyla devam edeceğim.
