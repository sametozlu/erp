---
description: V12 Harita Modülü Modernizasyon ve İyileştirme - Uygulama Planı
---

# V12 HARİTA MODÜLÜ MODERNİZASYON PLANI

**Kaynak Rapor:** `docs/MAP_MODERNIZASYON_RAPORU.md`
**Durum:** 🚀 Başlatıldı
**Başlangıç:** 1 Şubat 2026

Bu plan, Harita Modülü Modernizasyon Raporu'nda onaylanan 4 aşamalı geliştirme sürecini takip eder.

---

## 📅 Aşama 1: Temel Altyapı (ÖNCELİKLİ)
*Hedef: Sistemi daha güvenilir hale getirmek ve kullanıcı bilgilendirmesini iyileştirmek.*

### 🛠️ 1.1 Yeniden Deneme Mekanizması (Retry Logic)
- [x] `RetryHelper` sınıfı oluşturulacak (JS)
  - [x] Üstel geri çekilme (Exponential backoff) stratejisi
  - [x] Yapılandırılabilir deneme sayısı ve bekleme süreleri
  - [x] 5xx hataları ve ağ hataları için otomatik tetikleme

### 💾 1.2 Rota Önbellekleme (Routing Cache)
- [x] `RoutingCache` yapısı kurulacak
  - [x] Bellek içi (In-memory) önbellek (Map yapısı)
  - [x] `localStorage` tabanlı kalıcı önbellek (Haftalık veriler için)
  - [x] Cache invalidation stratejisi

### 📊 1.3 Kullanıcı Bilgilendirme (Loading UX)
- [x] `LoadingManager` sınıfı oluşturulacak
- [x] UI Bileşenleri eklenecek:
  - [x] Detaylı Progress Bar (Yüzdelik göstergeli)
  - [x] Durum metinleri ("Veriler alınıyor...", "İşaretçiler oluşturuluyor...")
  - [x] Hata durumunda kullanıcı dostu mesajlar

---

## ⚡ Aşama 2: Performans Optimizasyonları
*Hedef: Harita donmalarını engellemek ve büyük veri setlerini yönetmek.*

### 🧵 2.1 Web Worker Entegrasyonu
- [x] `map-worker.js` oluşturulacak
- [x] Ana thread'den Worker'a taşınacak işlemler:
  - [x] Marker verilerinin işlenmesi (Parsing)
  - [x] Kümeleme (Clustering) hesaplamaları
  - [x] Rota verilerinin düzenlenmesi

### 👁️ 2.2 Viewport Bazlı Yükleme (Araçlar İçin)
- [x] Backend: `bbox` (Bounding Box) parametresi alan yeni endpointler
- [x] Frontend: Harita hareket ettikçe sadece görünen alanı yükleme mantığı
- [x] Throttling mekanizması (Gereksiz istekleri önlemek için)

---

## 📱 Aşama 3: Kullanıcı Deneyimi ve Mobil
*Hedef: Tablet ve telefonlarda kusursuz deneyim.*

### 📲 3.1 Responsive Tasarım
- [x] Mobil uyumlu layout (CSS/Tailwind)
  - [x] Sol panel yerine mobilde alttan açılan menü (Bottom Sheet)
  - [x] Genişletilmiş harita alanı

### 👆 3.2 Dokunmatik Optimizasyon
- [x] Buton boyutlarının büyütülmesi (>44px)
- [x] Marker dokunma alanlarının genişletilmesi
- [x] Pinch-to-zoom ve kaydırma iyileştirmeleri

---

## 🔌 Aşama 4: İleri Özellikler & Offline Mod
*Hedef: İnternet kesintilerinde çalışabilirlik.*

### 🗄️ 4.1 Çevrimdışı Veri (IndexedDB)
- [x] `OfflineManager` sınıfı oluşturuldu (`static/js/offline/offline-manager.js`)
- [x] İşler, Rotalar ve Araçlar için object store yapısı
- [x] `app.js` entegrasyonu (LoadJobs, DrawAllRoutes, DrawSingleRoute)

### 📡 4.2 Service Worker
- [x] `sw.js` oluşturuldu (Genel asset cache için)
- [x] Service Worker kaydı (`app.js` içine eklendi)
- [ ] Background sync (Gelecek geliştirme)

---

## 🗃️ Arşivlenen Görevler (Eski Plan)
*(Önceki plandan kalan ve tamamlanmamış işler buraya taşınmıştır)*

- [ ] Rotaların tüm haftalık işleri desteklemesi (Aşama 2 ile birleştirilecek)
