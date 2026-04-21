---
description: Gerçek zamanlı özellikler ve gelişmiş fonksiyonlar için uygulama planı
---

# Gerçek Zamanlı Özellikler - Uygulama Durumu

## ✅ Tamamlanan Özellikler

### 1. Veritabanı Modelleri (models.py)
- [x] `CellLock` - Hücre kilitleme (optimistic locking)
- [x] `CellCancellation` - İş iptal kaydı
- [x] `CellVersion` - Hücre versiyonlama (çakışma çözümü için)
- [x] `TeamOvertime` - Mesai kaydı
- [x] `VoiceMessage` - Ses mesajları (PTT)
- [x] `UserSettings` - Kullanıcı ayarları
- [x] `TableSnapshot` - Tablo snapshot'ı (mail gönderimi için)
- [x] `PlanCell.status` - İptal durumu alanı
- [x] `PlanCell.version` - Versiyon numarası

### 2. Backend API'leri (routes/realtime.py)
- [x] Hücre Kilitleme:
  - `POST /api/cell/lock` - Hücreyi kilitle
  - `POST /api/cell/unlock` - Kilidi kaldır
  - `GET /api/cell/locks` - Aktif kilitleri listele
- [x] Çakışma Çözümü:
  - `POST /api/cell/save-with-version` - Versiyonlu kaydetme
- [x] Tarih Taşıma:
  - `PUT /api/update-task-date` - İşi başka tarihe taşı
- [x] İptal Mekanizması:
  - `POST /api/cell/cancel` - İşi iptal et
  - `POST /api/cell/restore` - İptal edilen işi geri yükle
- [x] Mesai Sistemi:
  - `POST /api/overtime/add` - Mesai ekle
  - `GET /api/overtime/list` - Mesai listesi
  - `DELETE /api/overtime/<id>` - Mesai sil
- [x] Kullanıcı Ayarları:
  - `GET /api/settings` - Ayarları getir
  - `POST /api/settings` - Ayarları kaydet
- [x] Ses Mesajları (PTT):
  - `POST /api/voice/send` - Ses mesajı gönder
  - `GET /api/voice/history` - Ses mesajı geçmişi
  - `POST /api/voice/<id>/heard` - Dinlendi işaretle
- [x] Tablo Mail Gönderimi:
  - `POST /api/table/snapshot` - Snapshot oluştur
  - `POST /api/table/send-email` - E-posta ile gönder
- [x] Socket.IO Event Handler'ları:
  - `join_plan_updates` - Plan güncellemeleri odasına katıl
  - `leave_plan_updates` - Odadan ayrıl
  - `cell_editing_start/end` - Düzenleme bildirimleri

### 3. Frontend JavaScript (static/js/realtime.js)
- [x] Socket.IO bağlantısı
- [x] Hücre kilitleme/kilit kaldırma
- [x] Çakışma algılama ve gösterim
- [x] İptal mekanizması UI
- [x] Tarih taşıma modalı
- [x] Mesai giriş modalı
- [x] Push-to-Talk ses kaydı
- [x] Tam ekran modu
- [x] Kullanıcı ayarları modalı
- [x] Toast bildirimleri
- [x] Hücre vurgulama animasyonları

### 4. CSS Stilleri (static/style.css)
- [x] Kilit göstergeleri (.lock-indicator, .editing-indicator)
- [x] İptal edilen işler (.is-cancelled)
- [x] Mesai göstergesi (.overtime-indicator)
- [x] Animasyonlar (fade-in, fade-out, highlight)
- [x] Tam ekran modu (.fullscreen-mode)
- [x] PTT butonu (.ptt-button)
- [x] Toast bildirimleri (.realtime-toast)
- [x] Ses oynatıcı (.voice-player)
- [x] Aksiyon butonları (.cell-actions)

### 5. Template Güncellemeleri
- [x] base.html - realtime.js eklendi
- [x] plan.html - Yeni aksiyon butonları:
  - İşi İptal Et
  - İşi Taşı
  - Mesai Ekle
  - Tam Ekran
  - Ayarlar
  - Tabloyu Gönder (mail)

## 📝 Kullanım Kılavuzu

### Hücre Kilitleme
1. Bir hücreye tıkladığınızda otomatik olarak kilit oluşturulur
2. Kilit 60 saniye geçerlidir ve düzenleme süresince yenilenir
3. Başka kullanıcı düzenlemeye çalışırsa uyarı alır

### İş İptal Etme
1. Tabloda bir hücre seçin
2. "İşi İptal Et" butonuna tıklayın
3. İsteğe bağlı iptal nedeni girin
4. İptal edilen işler açık kırmızı arka planla ve üstü çizili olarak gösterilir

### İş Taşıma
1. Taşımak istediğiniz hücreyi seçin
2. "İşi Taşı" butonuna tıklayın
3. Yeni tarihi seçin
4. Tüm personel atamaları ve detaylar yeni tarihe taşınır

### Mesai Girişi
1. Mesai eklemek istediğiniz hücreyi seçin
2. "⏰ Mesai" butonuna tıklayın
3. Süre ve açıklama girin
4. Mesai olan hücreler saat simgesiyle işaretlenir

### Tam Ekran Modu
- "⛶ Tam Ekran" butonuna tıklayın veya F11 tuşuna basın
- Menüler gizlenir, sadece tablo görünür
- Çıkmak için ESC veya tekrar F11

### Kullanıcı Ayarları
- "⚙️ Ayarlar" butonuyla ayarlar panelini açın
- Tam ekran kısayol tuşunu değiştirin
- Bildirim tercihlerini ayarlayın
- PTT tuşunu seçin

### Tablo Mail Gönderimi
1. "📧 Tabloyu Gönder" butonuna tıklayın
2. Alıcı e-posta adreslerini virgülle ayırarak girin
3. Tablo anlık görüntüsü e-posta olarak gönderilir

### Sesli İletişim (PTT)
1. Chat sayfasında mikrofon butonunu basılı tutun
2. Konuşun, bırakınca ses mesajı gönderilir
3. Alıcı otomatik olarak sesi duyar (ayarlara bağlı)

## 🔧 Teknik Notlar

### Veritabanı Migrasyonu
Yeni tablolar ve alanlar ilk uygulama başlatıldığında otomatik oluşturulur (`ensure_schema()` fonksiyonu).

### Socket.IO Odaları
- `plan_updates` - Tüm plan güncellemeleri için
- `user_{id}` - Kullanıcıya özel bildirimler
- `chat_team_{id}` - Ekip sohbeti

### CSRF Koruması
Tüm POST/PUT/DELETE istekleri CSRF token gerektirir.

### Dosya Yükleme
Ses dosyaları `uploads/voice/` klasörüne kaydedilir.
