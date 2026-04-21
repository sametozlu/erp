# UX ve Mail Sistemi İyileştirme Planı

Bu belge, kullanıcının talep ettiği üç ana iyileştirme maddesi için teknik analiz ve uygulama adımlarını içerir.

## 1. Personel Listesi Sayfa Düzeni
**Hedef:** Personel listesinin (tablo) sayfanın altına kadar uzanması ve sayfa içinde kaydırma (scroll) yapılması, sayfa yapısının bozulmaması.

**Mevcut Durum:**
- `people.html` dosyasında `.tablewrap` elementinde `max-height: 650px` kısıtlaması var.
- Sayfa yapısı Flexbox kullanıyor ancak yükseklik hesaplamaları statik değerlere (`calc(100vh - 120px)`) dayanıyor.

**Yapılacaklar:**
1.  **CSS Düzenlemesi:** `people.html` içindeki CSS güncellenecek.
    - `section.card`: `flex: 1; display: flex; flex-direction: column; overflow: hidden;` özellikleri ile ana kapsayıcı yapılacak.
    - `.tab-content`: `flex: 1; display: flex; flex-direction: column; overflow: hidden;` yapılacak.
    - `.tablewrap`: `flex: 1; overflow-y: auto; max-height: none;` yapılarak kalan tüm alanı kaplaması sağlanacak.
    - `thead`: Tablo başlığının sabit kalması (`position: sticky; top: 0;`) sağlanarak kullanıcı deneyimi artırılacak.

## 2. Mail Tasarımı İyileştirmesi
**Hedef:** Maillerin daha modern, şık ve anlaşılır olması.

**Mevcut Durum:**
- `email_base.html` basit bir gri arka plan ve beyaz kutu yapısına sahip.
- Tipografi ve boşluklar standart.

**Yapılacaklar:**
1.  **Modern Şablon:** `email_base.html` yeniden tasarlanacak.
    - **Header:** Kurumsal renklerin olduğu şık bir üst baner.
    - **Card Layout:** İçeriğin gölgeli ve yuvarlak hatlı bir kart içinde sunulması.
    - **Typography:** `Segoe UI`, `Roboto`, `Helvetica Neue` gibi modern font yığınları.
    - **CTA Butonları:** Aksiyon gerektiren durumlar (örn. "Onayla", "Görüntüle") için belirgin buton stilleri.
    - **Footer:** Daha sade ve bilgilendirici alt bilgi alanı.
2.  **İçerik Render Fonksiyonları:** `utils.py` içindeki mail HTML oluşturma blokları (`render_template` çağrıları) yeni şablona uygun hale getirilecek (gerekirse).

## 3. Asenkron Mail Kuyruğu (Mail Queue)
**Hedef:** İşlemlerin hızlanması için mail gönderiminin arka plana alınması ve sırayla gönderilmesi.

**Mevcut Durum:**
- `MailService.send()` metodu senkron çalışıyor. Kullanıcı bir işlem yaptığında SMTP sunucusuna bağlanıp mail atılana kadar bekliyor.
- Hata durumunda işlem yavaşlıyor veya kullanıcıya hata dönüyor.

**Yapılacaklar:**
1.  **Veritabanı Modeli (`models.py`):**
    - `MailQueue` tablosu oluşturulacak.
    - Alanlar: `id`, `recipients` (JSON/Text), `subject`, `html_content`, `status` (pending, processing, sent, failed), `created_at`, `sent_at`, `error_message`, `retry_count`.
2.  **Servis Güncellemesi (`services/mail_service.py`):**
    - `send()` metodu artık mail göndermeyecek, `MailQueue` tablosuna kayıt ekleyecek.
    - Yeni `process_queue()` metodu eklenecek: Bekleyen (`pending`) kayıtları alıp tek tek göndermeyi deneyecek. Başarılı olanları `sent`, hatalıları `failed` yapacak.
3.  **Arka Plan İşçisi (`app.py`):**
    - Uygulama başladığında (`app.py` içinde) ayrı bir `Thread` başlatılacak.
    - Bu thread sonsuz bir döngüde (belirli aralıklarla, örn. 10 saniye) `MailService.process_queue()` metodunu çağıracak.
    - **Not:** V12 mimarisi (Flask) için basit threading çözümü en pratik ve az bağımlılık gerektiren yöntemdir. Celery/Redis gibi ağır çözümlere gerek yok.

## Uygulama Sırası
1.  `models.py`: `MailQueue` modelini ekle.
2.  `services/mail_service.py`: Kuyruk yapısına geçir.
3.  `app.py`: Background thread başlat.
4.  `email_base.html`: Tasarımı yenile.
5.  `people.html`: CSS düzeltmelerini uygula.
