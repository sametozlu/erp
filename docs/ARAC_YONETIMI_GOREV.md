# Araç Yönetim Sistemi Geliştirme Görevleri

## Genel Bakış
Bu belge, araç yönetim sisteminde tespit edilen hataların ve yeni özellik taleplerinin detaylı bir açıklamasını içermektedir.

---

## Mevcut Hatalar (Bug Fixes)

### Hata 1: Araçlar Sekmesinde Hata
**URL:** http://127.0.0.1:5000/tools

**Açıklama:** Araçlar sekmesi açıldığında beklenmeyen bir hata oluşuyor. Sayfa düzgün yüklenmiyor veya araçlar görüntülenemiyor.

**Beklenen Davranış:** Araçlar sekmesi sorunsuz açılmalı ve tüm araçlar listelenmeli.

**Öncelik:** Yüksek

---

### Hata 2: İş Detayı Kısmına Tüm Araçlar Gelmiyor
**URL:** http://127.0.0.1:5000/plan

**Açıklama:** Plan sayfasındaki "İş Detayı" (Job Details) bölümünde araç seçimi yapılmak istendiğinde, mevcut araçların tamamı listelenmiyor. Bazı araçlar eksik kalıyor.

**Beklenen Davranış:** Sistemdeki tüm araçlar (aktif araçlar) İş Detayı bölümündeki araç seçim listesinde görünmeli.

**Öncelik:** Yüksek

**İlgili Dosyalar:**
- `routes/planner.py` - araç listeleme endpoint'leri
- `templates/plan.html` - araç seçim UI bileşeni
- `static/js/map/vehicle-manager.js` - araç yönetim JavaScript kodu

---

### Hata 3: "Tüm Araçları Gör" Butonu Çalışmıyor
**URL:** http://127.0.0.1:5000/plan

**Açıklama:** Plan sayfasında veya araçlar sayfasında bulunan "Tüm Araçları Gör" (Show All Vehicles) butonu tıklandığında herhangi bir işlem yapmıyor.

**Beklenen Davranış:** Butona tıklandığında gizli araçlar görünür hale gelmeli veya tüm araçların olduğu bir görünüm açılmalı.

**Öncelik:** Orta

**İlgili Dosyalar:**
- `templates/plan.html` - buton ve olay işleyici
- `static/js/map/vehicle-manager.js` - JavaScript olay işleyicileri

---

### Hata 4: Araç Güncelleme Hatası - "Araç Kullanıyor"
**URL:** http://127.0.0.1:5000/plan

**Açıklama:** Bir araca ait bilgiler girildikten sonra, başka bir güncelleme yapılıp "Kaydet" butonuna basıldığında "Araç kullanıyor" hatası veriyor ve değişiklikler kaydedilmiyor.

**Senaryo:**
1. Araç seçilir
2. Bilgiler girilir
3. Başka bir alan güncellenir (tarih, personel vb.)
4. Kaydet denir
5. Hata: "Araç kullanıyor" mesajı çıkıyor

**Beklenen Davranış:** Araç zaten seçili olsa bile, kullanıcı başka alanları güncelleyip kaydedebilmeli. Sistem, aynı aracın tekrar seçilmesini engellememeli.

**Öncelik:** Yüksek

**İlgili Dosyalar:**
- `routes/planner.py` - kaydetme endpoint'leri ve doğrulama mantığı
- `models.py` - veritabanı modelleri

---

### Hata 5: Araçlar Kısmında Tüm Araçlar Yok
**URL:** http://127.0.0.1:5000/tools

**Açıklama:** Araçlar ana sayfasında (veya ilgili bölümde) sistemdeki araçların tamamı görüntülenmiyor. Bazı araçlar eksik.

**Beklenen Davranış:** Tüm araçlar (aktif kayıtlar) listelenmeli.

**Öncelik:** Yüksek

---

## Yeni Özellik Talepleri (New Features)

### Özellik 1: Haftalık Araç Atama Sistemi
**Açıklama:** Araçlar haftalık olarak atanmalı ve her yeni haftada atamalar sıfırlanmalıdır.

**Detaylar:**
- Bir haftalık periyot tanımlanmalı (örneğin Pazartesi - Pazar)
- Araç atamaları bu periyot boyunca geçerli olmalı
- Yeni hafta başladığında tüm araç atamaları otomatik sıfırlanmalı
- Sıfırlama işlemi sırasında geçmiş atama kayıtları arşivlenmeli

**Teknik Gereksinimler:**
- Veritabanında haftalık atama tablosu oluşturulmalı
- Otomatik sıfırlama için cron job veya scheduler eklenmeli
- Haftalık raporlama özelliği düşünülmeli

**Öncelik:** Yüksek

**İlgili Dosyalar:**
- `models.py` - yeni veritabanı modelleri
- `routes/planner.py` - haftalık atama endpoint'leri
- `app.py` - scheduler/background job yapılandırması

---

### Özellik 2: Önceki Hafta Araç Atama Baloncuğu
**Açıklama:** Araçlar bölümünde, her aracın üzerine gelindiğinde (hover) veya tıklandığında, bir önceki hafta o aracın kimde olduğunu gösteren bir bilgi baloncuğu (tooltip/popup) görüntülenmelidir.

**Detaylar:**
- Mouse hover veya tıklama ile baloncuk açılmalı
- Baloncuk içeriği:
  - Önceki hafta aracı kullanan personelin adı
  - Atama tarih aralığı
  - Gideceği yer/rota bilgisi (varsa)
- Baloncuk tasarımı temiz ve okunaklı olmalı
- Mobil cihazlarda uzun basma (long press) ile açılmalı

**Teknik Gereksinimler:**
- `models.py`'de geçmiş atama kayıtları tutulmalı
- API endpoint'i ile geçmiş veriler çekilmeli
- Frontend'de tooltip/popup bileşeni oluşturulmalı

**Öncelik:** Orta

**İlgili Dosyalar:**
- `models.py` - geçmiş atama modelleri
- `routes/planner.py` - geçmiş veri endpoint'leri
- `templates/plan.html` - tooltip UI bileşeni
- `static/js/map/vehicle-manager.js` - tooltip JavaScript mantığı
- `static/style.css` - tooltip stilleri

---

## Geliştirme Öncelik Sırası

| # | Görev | Tip | Öncelik | Durum |
|---|-------|-----|---------|-------|
| 1 | Hata 2 - İş Detayı araç listesi düzeltmesi | Bug Fix | Yüksek | ✅ Tamamlandı |
| 2 | Hata 4 - Araç kullanıyor hatası düzeltmesi | Bug Fix | Yüksek | ⏭️ Pas geçildi |
| 3 | Özellik 1 - Haftalık araç atama sistemi | New Feature | Yüksek | ✅ Tamamlandı |
| 4 | Hata 1 - Araçlar sekmesi hatası | Bug Fix | Yüksek | ✅ Tamamlandı |
| 5 | Hata 5 - Tüm araçların görünmesi | Bug Fix | Orta | ✅ Tamamlandı |
| 6 | Hata 3 - Tüm araçları gör butonu | Bug Fix | Orta | ✅ Tamamlandı |
| 7 | Özellik 2 - Önceki hafta baloncuğu | New Feature | Orta | ✅ API Hazır |

---

## Yapılan Değişiklikler (2026-02-02)

### 1. Araçlar Sekmesi Düzeltmesi
- **Dosya:** `templates/tools.html`
- **Değişiklik:** Gözlemci kullanıcılar artık araç listesini görebilir (sadece düzenleme/silme gizli)

### 2. İş Detayı Araç Listesi Düzeltmesi  
- **Dosya:** `static/app.js` - `renderVehicleSelect()` fonksiyonu
- **Değişiklik:** `assigned_team_id` filtresi kaldırıldı, tüm araçlar artık listelenebiliyor
- **Ek Özellik:** Başka ekibe atanmış araçlar `[Atanmış]` etiketi ve turuncu renk ile gösteriliyor

### 3. Haftalık Araç Atama Sistemi
- **Yeni Model:** `models.py` - `VehicleAssignment` sınıfı eklendi
  - `vehicle_id`, `person_id`, `secondary_person_id` (opsiyonel 2. kişi)
  - `week_start`, `week_end` (Pazartesi-Pazar)
  - `team_id`, `project_id`, `notes`
  - `is_active` (arşivleme için)

- **Yeni API Routes:** `routes/vehicle_routes.py`
  - `GET /api/vehicle/assignments` - Haftalık atamaları getir
  - `POST /api/vehicle/assignments` - Yeni atama oluştur
  - `PUT /api/vehicle/assignments/<id>` - Atama güncelle (2. kişi ekle)
  - `DELETE /api/vehicle/assignments/<id>` - Atama iptal et
  - `GET /api/vehicle/<id>/history` - Araç geçmişi (tooltip için)
  - `GET /api/vehicle/weekly-summary` - Haftalık özet

---

## Test Senaryoları

### Araç Listeleme Testi
1. Sistemdeki tüm araçları kontrol edin
2. Plan sayfasındaki İş Detayı bölümüne gidin
3. Araç seçim dropdown'unu açın
4. Tüm araçların listelendiğini doğrulayın

### Araç Güncelleme Testi
1. Bir plan oluşturun
2. Araç seçin
3. Tarih veya personel bilgilerini güncelleyin
4. Kaydet butonuna basın
5. Başarılı mesajı alın

### Haftalık Sıfırlama Testi
1. Bir aracı belirli bir personele atayın
2. Haftalık döngüyü simüle edin (veya bekleyin)
3. Atamanın sıfırlandığını doğrulayın
4. Geçmiş kaydın arşivlendiğini kontrol edin

### Baloncuk Testi
1. Araçlar sayfasına gidin
2. Herhangi bir aracın üzerine gelin
3. Önceki hafta bilgisinin görüntülendiğini doğrulayın

---

## Notlar
- Tüm değişiklikler mevcut veritabanı şeması ile uyumlu olmalı
- Geriye dönük uyumluluk korunmalı
- Kod değişiklikleri için pull request açılmalı
- Değişiklikler test ortamında doğrulanmalı

---

**Oluşturulma Tarihi:** 2026-02-02
**Son Güncelleme:** 2026-02-02
