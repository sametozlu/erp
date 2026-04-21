# Mail Sistemi Geliştirme - Detaylı Analiz

## 📋 Mevcut Durum Analizi

### 1. Mevcut Mail Sistemi

Sistemde üç farklı mail gönderim yöntemi var:

| Yöntem | Endpoint | Açıklama |
|--------|----------|----------|
| Tabloyu Mail Olarak Gönder | `/api/table/send-email` | Tüm tabloyu tek mail olarak gönderir |
| Haftalık Mailler | `/api/send_weekly_emails` | Her personele özel haftalık plan |
| Ekip Mailleri | `/api/send_team_emails` | Belirli bir ekibin planını gönderir |

### 2. Mevcut Mail İçeriği (Karmaşık)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Haftalık Plan - 2026-02-02                                              │
├─────────────────────────────────────────────────────────────────────────┤
│  Tarih   | İl    | Proje          | Vardiya | Araç | Ekip | İş Detay... │
├─────────────────────────────────────────────────────────────────────────┤
│  02.02   | Ankara| 9026-0001 TEST | 08:30-..| ...  | ...  | ...         │
│  03.02   | Ankara| 9026-0001 TEST | 08:30-..| ...  | ...  | ...         │
│  ...     | ...   | ...            | ...     | ...  | ...  | ...         │
│  08.02   | ...   | ...            | ...     | ...  | ...  | ...         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3. Mevcut Sorunlar

| Sorun | Açıklama |
|-------|----------|
| **Karmaşık Tablo** | 10 sütunlu tablo çok kalabalık |
| **Okunabilirlik** | Çok fazla bilgi tek sayfada |
| **Tüm Ekiplere Aynı** | Yönetim de personelle aynı maili alıyor |
| **Görsel** | Basit HTML tablo, modern değil |
| **Ek Dosya Listesi** | Sadece dosya adları, indirme linki yok |

## 🎯 Yeni Tasarım

### 1. İki Farklı Mail Türü

#### 1.1 Yönetim Maili (Tüm Tablo)
**Kime:** Yönetim, planlayıcılar
**İçerik:** Tüm projeler, tüm ekipler, tüm işler

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📅 Haftalık İş Planı - 02-08 Şubat 2026                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  📊 ÖZET                                                              │
│  ├── Toplam İş: 45                                                     │
│  ├── Aktif Ekip: 8                                                     │
│  └── Tamamlanan: 12                                                    │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 📋 Ekip Bazlı Özet                                                 │ │
│  │ ┌─────────────┬───────────┬────────┬────────┐                    │ │
│  │ │ Ekip Adı    │ Personel  │ İş Say │ Notlar │                    │ │
│  │ ├─────────────┼───────────┼────────┼────────┤                    │ │
│  │ │ Ekip A      │ 3 kişi    │ 12 iş  │ Tüm gün │                    │ │
│  │ │ Ekip B      │ 4 kişi    │ 15 iş  │ YOL var │                    │ │
│  │ │ Ekip C      │ 2 kişi    │ 8 iş   │ -       │                    │ │
│  │ └─────────────┴───────────┴────────┴────────┘                    │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 📍 Günlük Dağılım                                                 │ │
│  │                                                                   │ │
│  │  📅 02.02 Pazartesi                                               │ │
│  │  ├── Ekip A: TEST-001, TEST-002 (2 iş)                           │ │
│  │  ├── Ekip B: TEST-003, TEST-004, TEST-005 (3 iş)                 │ │
│  │  └── Ekip C: TEST-006 (1 iş)                                     │ │
│  │                                                                   │ │
│  │  📅 03.02 Salı                                                    │ │
│  │  ├── Ekip A: TEST-007, TEST-008 (2 iş)                           │ │
│  │  └── ...                                                         │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  📎 Ek Dosyalar:                                                       │
│  ├── Tüm Projeler.xlsx                                                 │
│  └── Haftalık Rapor.pdf                                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 1.2 Ekip Maili (Sadece O Ekip)
**Kime:** Ekip üyeleri
**İçerik:** Sadece kendi işleri, detaylı bilgi

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📅 Haftalık İş Planınız - 02-08 Şubat 2026                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  👋 Merhaba [Ad Soyad],                                                │
│                                                                         │
│  Bu hafta size atanan işler aşağıdadır:                                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 📋 Günlük İşleriniz                                               │ │
│  │                                                                   │ │
│  │  📅 Pazartesi, 02 Şubat                                           │ │
│  │  ┌─────────────────────────────────────────────────────────────┐  │ │
│  │  │ 🏢 [TEST-001] Ankara - Test Projesi                         │  │ │
│  │  │    ⏰ 08:30 - 18:00  🚗 Araç: 06 ABC 12                     │  │ │
│  │  │    📝 Kabin kurulum ve konfigürasyon                         │  │ │
│  │  │    📎 Ek: LLD_Dokumani.pdf  📎 Ek: Tutanak.xlsx              │  │ │
│  │  └─────────────────────────────────────────────────────────────┘  │ │
│  │  ┌─────────────────────────────────────────────────────────────┐  │ │
│  │  │ 🏢 [TEST-002] Ankara - Test Projesi                         │  │ │
│  │  │    ⏰ 13:00 - 18:00  🚗 Araç: 06 ABC 12                     │  │ │
│  │  │    📝 Test işlemleri                                         │  │ │
│  │  └─────────────────────────────────────────────────────────────┘  │ │
│  │                                                                   │ │
│  │  📅 Salı, 03 Şubat                                                │ │
│  │  ┌─────────────────────────────────────────────────────────────┐  │ │
│  │  │ 🏢 [TEST-003] Eskişehir - Bakım                            │  │ │
│  │  │    ⏰ 08:30 - 18:00  🚗 Araç: 06 DEF 34                     │  │ │
│  │  │    📝 Preventif bakım                                         │  │ │
│  │  └─────────────────────────────────────────────────────────────┘  │ │
│  │                                                                   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ⚠️  Önemli Notlar:                                                     │
│  ├── Pazartesi akşamı Ankara'ya dönüş gerekli                         │
│  └── Salı sabahı erken çıkış                                          │
│                                                                         │
│  📞 Acil durum: 0532 XXX XX XX                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2. Mail Template Yapısı

```
templates/
├── email_base.html           # Ana şablon (mevcut)
├── email_weekly_summary.html # Yönetim özet şablonu (YENİ)
├── email_team_detail.html    # Ekip detay şablonu (YENİ)
└── email_components.html     # Ortak bileşenler (YENİ)
```

### 3. Backend Değişiklikleri

#### 3.1 Yeni API Endpoints

| Endpoint | Metod | Açıklama |
|----------|-------|----------|
| `/api/mail/send_full_table` | POST | Yönetim için tüm tablo |
| `/api/mail/send_team_detail` | POST | Ekip için detaylı mail |
| `/api/mail/preview_summary` | GET | Özet mail önizleme |
| `/api/mail/preview_team_detail` | GET | Ekip maili önizleme |

#### 3.2 Yeni Mail Servis Fonksiyonu

```python
def generate_weekly_summary_html(week_start: date) -> str:
    """Yönetim için haftalık özet HTML üretir"""
    # Ekip bazlı özet
    # Günlük dağılım
    # İstatistikler
    pass

def generate_team_detail_html(week_start: date, team_name: str) -> str:
    """Ekip için detaylı HTML üretir"""
    # Personel bazlı işler
    # Günlük iş listesi
    # Detaylı bilgiler
    pass
```

### 4. Frontend Değişiklikleri

#### 4.1 Yeni Mail Gönderim Modalı

```
┌─────────────────────────────────────────────────────────────┐
│  Mail Gönder                                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📧 Alıcı Türü:                                              │
│  ○ Tüm Tablo (Yönetim)                                       │
│  ● Ekip Bazlı (Personeller)                                  │
│                                                             │
│  ─────────────────────────────────────────────────────────── │
│                                                             │
│  📋 İçerik Türü:                                             │
│  ○ Özet (Sadece başlıklar ve sayılar)                        │
│  ● Detaylı (Tüm iş bilgileri)                                │
│                                                             │
│  ─────────────────────────────────────────────────────────── │
│                                                             │
│  📅 Hafta: [02-08 Şubat 2026  ▼]                             │
│                                                             │
│  ─────────────────────────────────────────────────────────── │
│                                                             │
│  📎 Ek Dosya: [Excel İndir]  [PDF İndir]                     │
│                                                             │
│  [Önizleme]  [Mail Gönder]  [İptal]                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5. Özet Karşılaştırma

| Özellik | Mevcut | Yeni |
|---------|--------|------|
| Mail Türü | Tek tip | 2 tip (Yönetim/Ekip) |
| İçerik | 10 sütun tablo | Özet + Detaylı |
| Görsel | Basit HTML | Modern, kart bazlı |
| Okunabilirlik | Düşük | Yüksek |
| Dosya Ekleri | Sadece ad | İndirme linki |
| Özet Bilgi | Yok | Var (istatistikler) |
| Günlük Dağılım | Tabloda gizli | Ayrı bölüm |

## 📝 Görev Listesi

### Görev 1: Backend - Mail Servis Fonksiyonları
- [ ] `generate_weekly_summary_html()` fonksiyonu yaz
- [ ] `generate_team_detail_html()` fonksiyonu yaz
- [ ] Yeni template dosyaları oluştur
- [ ] İstatistik hesaplama yardımcı fonksiyonları

### Görev 2: Backend - API Endpoints
- [ ] `/api/mail/send_full_table` endpointi
- [ ] `/api/mail/send_team_detail` endpointi
- [ ] Preview endpointleri
- [ ] Excel/PDF export entegrasyonu

### Görev 3: Frontend - Mail Modalı
- [ ] Yeni mail gönderim modalı tasarımı
- [ ] Mail türü seçimi (radio buttons)
- [ ] Hafta seçici
- [ ] Önizleme fonksiyonu

### Görev 4: Frontend - JavaScript
- [ ] Mail gönderim handler'ları
- [ ] Modal aç/kapa fonksiyonları
- [ ] Loading state'ler
- [ ] Toast bildirimleri

### Görev 5: Template'ler
- [ ] `email_weekly_summary.html` şablonu
- [ ] `email_team_detail.html` şablonu
- [ ] `email_components.html` bileşenleri
- [ ] Responsive CSS stilleri

### Görev 6: Test
- [ ] Yönetim maili testi
- [ ] Ekip maili testi
- [ ] Attachment testi
- [ ] Responsive görünüm testi

---

## 🎨 Tasarım Notları

### Renk Paleti
```css
:root {
    --email-bg: #f8fafc;
    --email-card-bg: #ffffff;
    --email-text: #1e293b;
    --email-text-muted: #64748b;
    --email-border: #e2e8f0;
    --email-primary: #3b82f6;
    --email-success: #22c55e;
    --email-warning: #f59e0b;
    --email-danger: #ef4444;
}
```

### Kart Stili
```css
.email-card {
    background: white;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    padding: 20px;
    margin-bottom: 16px;
}
```

---

## 📅 Tahmini Süre

| Görev | Tahmini Süre |
|-------|-------------|
| Backend Servis | 2 saat |
| API Endpoints | 1 saat |
| Frontend Modal | 2 saat |
| JavaScript | 1 saat |
| Template'ler | 2 saat |
| Test | 1 saat |
| **Toplam** | **~9 saat**

---

## ⚠️ Dikkat Edilmesi Gerekenler

1. **Eski Sistem Uyumluluğu**: Mevcut mailler çalışmaya devam etmeli
2. **Büyük Veri**: Çok fazla iş olan haftalarda performans
3. **Ek Dosya Boyutu**: Mail server limitleri
4. **Outlook Uyumluluğu**: CSS stilleri uyumlu olmalı
5. **Mobil Görünüm**: Responsive tasarım
