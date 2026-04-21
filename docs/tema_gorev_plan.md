## Tema Çalışmaları - Teknik Görev Planı

### 1) Tek Kaynaklı Tema Altyapısı
- `templates/base.html` ve `templates/login.html` içindeki inline THEME JSON + FOUC snippet’ini kaldır; preload aşamasında yalnızca `static/js/theme/theme-transition.js` çalışsın.
- Tema verisini ve uygulamasını `theme-manager.js` + `theme-selector.js` üzerinden yükle; `<script>` ve `<link>` sırası: `css/theme-system.css` → `css/glass-effects.css` → `style.css` → `theme-transition.js` → `theme-manager.js` → `theme-selector.js`.
- `static/dark-theme.css` referansını kapat; gerekli override’ları `css/theme-system.css` içindeki ilgili `data-theme` bloklarına taşı.

### 2) Token Konsolidasyonu ve Refaktör
- `static/style.css` ve sayfa içi `<style>` bloklarındaki hex/hard-coded renkleri `theme-system.css` semantik token’larıyla değiştir (`--bg*`, `--text*`, `--accent*`, `--status*`, `--border*`, `--glass-*`).
- `templates/tasks.html` durum renkleri ve `[data-theme="dark"]` özel bloklarını tek set token tabanına indir; satır hover/selection renklerini `--table-row-*` token’larına bağla.
- `static/app.js`’teki “Force Cyan/Blue theme” gibi tema zorlamalarını kaldır veya token’lara yönlendir.

### 3) Tema Seçici Bileşeni ve Kalıcılık
- Tema seçici markup’ını partial’a (`templates/partials/theme_selector.html`) taşı; `theme-selector.js` ile data-driven render et, inline HTML üretimini kaldır.
- `ThemeManager`’a `/api/settings` entegrasyonu ekle: ilk yüklemede GET ile `UserSettings.theme` oku, değişiklikte POST ile kaydet. `localStorage` anahtarlarını API ile senkronize et; eski `darkMode` fallback’ini temizle.

### 4) Cam/Glass ve Karanlık Tema Temizliği
- `static/css/glass-effects.css`’teki tema bazlı renkleri `--glass-*` token’larına bağla; tema başına ayrı renk yazımı kalmasın.
- `static/dark-theme.css` içeriğini `css/theme-system.css` altındaki `pure-black`/`dark` bloklarına kat; dosyayı devre dışı bırak.

### 5) Bileşen Standardizasyonu
- Buton varyantlarını (primary/secondary/ghost/text/danger) `--accent-primary` ve türevleriyle hover/active/focus’ta güncelle; radius/shadow değerlerini token’laştır.
- Modal/Dialog/Drawer overlay opaklıklarını `--bg-overlay` ve `--glass-*` ile tekilleştir; kart gölgeleri ve radius’ları tema başına gerekirse override et.

### 6) Sayfa Bazlı Temizlik
- `templates/login.html`: ana tema modülüne bağla, kendi FOUC ve inline tema verisini kaldır, tüm renkleri token’la değiştir.
- Plan/görev/harita/chat sayfalarında inline renkleri token’lara çevir (öncelik: `templates/tasks.html`, `templates/plan.html`, varsa `templates/board.html`, `static/app.js` UI parçaları).

### 7) Tema Seti Genişletme
- Yeni tema eklerken aynı anda güncelle: `css/theme-system.css`, `js/theme/theme-data.js`, selector ikon/preview tanımları. Status ve glass/border/shadow/radius varyantlarını belirle.

### 8) Doğrulama ve Test
- FOUC/CLS: `ThemeTransition`’ın preload’da çalıştığını ve geçişte `theme-transitioning` sınıfının zamanında kalktığını kontrol et.
- Smoke test: login → dashboard/plan → görev detay → modal akışını her tema için çalıştır.
- WCAG kontrast kontrolü: primary button, nav link, tablo header; scrollbar ve input stilleri tema geçişinde tutarlı mı bak.

### 9) Dokümantasyon
- `docs/` altına kısa “Tema ekleme/değiştirme rehberi” ve “token sözlüğü” ekle; API senkron adımlarını özetle.
