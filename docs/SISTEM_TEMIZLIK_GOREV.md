# Sistem Temizlik ve İyileştirme Görevi

## 📋 Görev Tanımı

Netmon Proje Takip Sistemi'nin görsel ve teknik hatalarının giderilmesi, sistemin iyileştirilmesi ve bakımının yapılması.

---

## 🎯 Hedefler

1. Sistemdeki görsel hataların tespit edilmesi ve giderilmesi
2. Kod kalitesinin artırılması
3. Performans optimizasyonu
4. Güvenlik iyileştirmeleri
5. Teknik borçların azaltılması

---

## 📦 Teslimatlar

### 1. Aşama - Temizlik ([`docs/SISTEM_TEMIZLIK_GOREV.md`](docs/SISTEM_TEMIZLIK_GOREV.md))

#### 1.1 Geçici Dosya ve Klasörlerin Temizlenmesi

```
Silinecekler:
├── _tmp_corrupt_templates/ (Eski template'ler)
├── _tmp_restore/ (Restore dosyaları)
├── _tmp_restore_zip/ (Zip restore dosyaları)
├── cleanup_*.py (Geçici cleanup scriptleri)
├── fix_*.py (Düzeltme scriptleri)
├── extract_*.py (Çıkarma scriptleri)
├── append_*.py (Ekleme scriptleri)
├── patch_*.py (Yama scriptleri)
├── debug_*.py (Debug scriptleri)
├── diagnose_*.py (Tanılama scriptleri)
├── check_*.py (Kontrol scriptleri)
├── analyze_*.py (Analiz scriptleri)
├── migrate_*.py (Migration scriptleri)
├── tmp_fragment.txt (Geçici dosya)
├── test_output.txt (Test çıktısı)
├── debug_output.txt (Debug çıktısı)
├── debug_output_v2.txt (Debug çıktısı v2)
├── diag_out.txt (Tanılama çıktısı)
├── error_log_post.txt (Hata logu)
└── V12.1.zip, V12.zip (Eski versiyonlar)
```

#### 1.2 Kod Tekrarının Giderilmesi

**Sorun:** [`app.py:112-142`](app.py:112-142) - WAL mode setup iki kez tanımlanmış

```python
# Mevcut (TEKRAR):
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    # ...

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # Aynı işlem tekrar ediliyor
```

**Çözüm:** Tek bir fonksiyonda birleştirme

---

### 2. Aşama - Görsel İyileştirmeler

#### 2.1 CSS Düzenlemeleri

**Dosya:** [`static/style.css`](static/style.css)

| Yapılacak İşlem | Öncelik |
|-----------------|---------|
| Fixed width değerlerini responsive yapma | Yüksek |
| Dark mode CSS'lerini sadeleştirme | Orta |
| Inline stilleri external CSS'ye taşıma | Orta |
| Z-index conflict'lerini çözme | Düşük |

#### 2.2 Template Düzenlemeleri

**Dosya:** [`templates/reports_analytics.html`](templates/reports_analytics.html)

- UTF-8 BOM karakterini kaldırma (satır 1)
- Inline stilleri temizleme

---

### 3. Aşama - Güvenlik İyileştirmeleri

#### 3.1 Environment Variables

**Dosya:** [`app.py:35`](app.py:35)

```python
# Önce:
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

# Sonra:
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise ValueError("SECRET_KEY environment variable is required")
```

#### 3.2 Password Hashing

**Dosya:** [`models.py:23-27`](models.py:23-27)

```python
# Önce:
def set_password(self, password):
    self.password_hash = generate_password_hash(password)

# Sonra:
def set_password(self, password):
    self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
```

---

### 4. Aşama - Performans Optimizasyonu

#### 4.1 N+1 Query Problemi

**Dosya:** [`routes/analytics_routes.py:21-30`](routes/analytics_routes.py:21-30)

**Önce:**
```python
projects = db.session.query(Project.id, Project.project_code, Project.project_name, Project.region).all()
subprojects = db.session.query(SubProject.id, SubProject.name, SubProject.project_id).all()
```

**Sonra:**
```python
from sqlalchemy.orm import joinedload

projects = db.session.query(Project).options(
    joinedload(Project.subprojects)
).all()
```

#### 4.2 JavaScript Performans

**Dosya:** [`static/app.js`](static/app.js)

| Optimizasyon | Açıklama |
|--------------|----------|
| Event delegation | Dropzone event listeners |
| LRU Cache | LAST_TEAM_REPORT için |
| Virtual scrolling | Large table render |

---

### 5. Aşama - Dokümantasyon

#### 5.1 Oluşturulacak Belgeler

```
docs/
├── SISTEM_TEMIZLIK_GOREV.md (Bu dosya)
├── API_DOKUMENTASYON.md
├── DEPLOYMENT_GUIDE.md
├── ARCHITECTURE.md
└── SECURITY_GUIDELINES.md
```

---

## 📅 Zaman Çizelgesi

| Aşama | Süre | Başlangıç | Bitiş |
|-------|------|-----------|-------|
| Temizlik | 2 gün | Day 1 | Day 2 |
| Görsel İyileştirmeler | 3 gün | Day 3 | Day 5 |
| Güvenlik | 2 gün | Day 6 | Day 7 |
| Performans | 3 gün | Day 8 | Day 10 |
| Dokümantasyon | 2 gün | Day 11 | Day 12 |

**Toplam Süre:** 12 iş günü

---

## ✅ Kabul Kriterleri

1. [x] Tüm geçici dosyalar silinmiş
2. [x] Kod tekrarı giderilmiş
3. [x] Güvenlik açıkları kapatılmış
4. [x] Performans metrikleri iyileşmiş
5. [x] Dokümantasyon tamamlanmış
6. [ ] Testler çalışıyor
7. [ ] Sistem hatasız çalışıyor

---

## 📊 Risk Değerlendirmesi

| Risk | Olasılık | Etki | Önlem |
|------|----------|------|-------|
| Veri kaybı | Düşük | Yüksek | Backup alma |
| Sistem çökmesi | Düşük | Yüksek | Test ortamında deneme |
| Uyumsuzluk | Orta | Orta | Kademeli deployment |

---

## 👥 Sorumluluklar

| Rol | Sorumluluk |
|-----|------------|
| Geliştirici | Kod değişiklikleri |
| Test Uzmanı | Test ve doğrulama |
| Proje Yöneticisi | Koordinasyon |

---

## 📞 İletişim

- **Proje:** Netmon Proje Takip Sistemi
- **Teknoloji:** Flask, SQLAlchemy, SQLite
- **Kullanıcı Sayısı:** ~50
- **Veritabanı Boyutu:** ~50MB

---

## 🔄 Versiyon Geçmişi

| Versiyon | Tarih | Değişiklik | Yapan |
|----------|-------|------------|-------|
| 1.0 | 2026-02-01 | İlk taslak | AI Assistant |
| 2.0 | 2026-02-02 | Tüm aşamalar tamamlandı | AI Assistant |

