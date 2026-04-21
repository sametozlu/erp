# Harita Modülü Teknik Geliştirme Spesifikasyonu

## 📋 Genel Bakış

**Doküman Türü:** Teknik Spesifikasyon
**Proje:** V12 Rota Planlayıcı Harita Modülü
**Versiyon:** 1.0
**Tarih:** 2026-02-01
**Hazırlayan:** V12 Geliştirme Ekibi

---

## 1. Mevcut Durum Analizi

### 1.1 Kullanılan Teknolojiler

```json
{
  "frontend": {
    "map_library": "Leaflet 1.9.4",
    "tile_provider": "OpenStreetMap",
    "routing": "OSRM (router.project-osrm.org)",
    "vehicle_tracking": "Arvento API",
    "styling": "Tailwind CSS + Custom CSS",
    "clustering": "Leaflet.markercluster 1.4.1"
  },
  "backend": {
    "framework": "Flask",
    "database": "SQLite",
    "api_endpoints": ["/api/jobs_for_map", "/api/routes_team"]
  }
}
```

### 1.2 Mevcut Sorunlar

| Sorun ID | Açıklama | Etki | Öncelik |
|----------|----------|------|---------|
| PERF-001 | Marker yükleme main thread'de blocking | UI donması | Kritik |
| PERF-002 | OSRM istekleri rate limit'e takılıyor | Rota hesaplama hatası | Yüksek |
| PERF-003 | Tüm araçlar tek seferde yükleniyor | Yüksek bellek kullanımı | Orta |
| UX-001 | Loading overlay yetersiz bilgilendirme | Kullanıcı belirsizliği | Orta |
| UX-002 | Mobilde panel taşması | Kullanılamaz görünüm | Orta |
| ERR-001 | API hatalarında retry mekanizması yok | Başarısız işlemler | Yüksek |
| ERR-002 | Offline mode desteği yok | Bağlantı kesilince çökme | Orta |

---

## 2. Geliştirme Gereksinimleri

### 2.1 Performans Optimizasyonu (PERF-001)

**Hedef:** Ana thread'i bloke etmeden marker yükleme

#### 2.1.1 Web Worker Implementasyonu

**Dosya:** `static/map-worker.js`

```javascript
// static/map-worker.js
// Harita verisi işleme worker'ı

self.onmessage = async function(e) {
  const { type, data } = e.data;

  switch (type) {
    case 'PROCESS_MARKERS':
      const markers = await processJobMarkers(data.jobs);
      self.postMessage({ type: 'MARKERS_READY', data: markers });
      break;

    case 'CALCULATE_ROUTE':
      const route = await calculateOptimizedRoute(data.points);
      self.postMessage({ type: 'ROUTE_READY', data: route });
      break;

    case 'CLUSTER_MARKERS':
      const clusters = await clusterMarkers(data.markers, data.zoom);
      self.postMessage({ type: 'CLUSTERS_READY', data: clusters });
      break;
  }
};

async function processJobMarkers(jobs) {
  // Marker verilerini işle
  return jobs.map(job => ({
    id: job.id,
    lat: job.lat,
    lng: job.lon,
    city: job.city,
    team_id: job.team_id,
    popup: createPopupContent(job)
  }));
}

async function calculateOptimizedRoute(points) {
  // 2-opt veya nearest neighbor TSP approximation
  const optimized = await tspOptimize(points);
  return optimized;
}

async function clusterMarkers(markers, zoom) {
  // Grid-based clustering
  const grid = createGrid(markers, zoom);
  return grid;
}
```

**Kullanım (main thread):**

```javascript
// static/app.js - ensureMap fonksiyonu güncellemesi
let mapWorker = null;

function initMapWorker() {
  if (mapWorker) return;
  mapWorker = new Worker('/static/map-worker.js');
  
  mapWorker.onmessage = function(e) {
    const { type, data } = e.data;
    switch (type) {
      case 'MARKERS_READY':
        renderMarkers(data);
        break;
      case 'ROUTE_READY':
        renderRoute(data);
        break;
    }
  };
}

async function loadJobMarkers() {
  // ... existing code ...
  
  // Worker'a gönder
  initMapWorker();
  mapWorker.postMessage({
    type: 'PROCESS_MARKERS',
    data: { jobs: data.all_jobs }
  });
}
```

**Değiştirilecek Dosyalar:**
- `static/app.js` - `loadJobMarkers()` fonksiyonu
- `static/app.js` - `drawSingleTeamRoute()` fonksiyonu
- `static/map-worker.js` - YENİ DOSYA

---

### 2.2 Routing Cache Sistemi (PERF-002)

**Hedef:** OSRM rate limit sorununu çöz ve hızlandır

#### 2.2.1 Multi-layer Cache Mimarisi

```javascript
// static/routing-cache.js
class RoutingCache {
  constructor() {
    this.memoryCache = new Map();        // Session cache
    this.localStorageCache = new Map();  // Persistent cache (7 gün)
    this.redisCache = null;              // Server-side cache (opsiyonel)
  }

  async getDistance(a, b) {
    const key = this.getKey(a, b);
    
    // 1. Memory cache kontrolü
    if (this.memoryCache.has(key)) {
      return this.memoryCache.get(key);
    }

    // 2. Local storage kontrolü
    const cached = this.localStorageCache.get(key);
    if (cached && this.isValid(cached)) {
      this.memoryCache.set(key, cached);
      return cached;
    }

    // 3. API çağrısı
    const result = await this.callOSRM(a, b);
    
    // Cache'e kaydet
    this.memoryCache.set(key, result);
    this.localStorageCache.set(key, {
      data: result,
      timestamp: Date.now()
    });

    return result;
  }

  getKey(a, b) {
    return `${a.lat.toFixed(5)},${a.lon.toFixed(5)}|${b.lat.toFixed(5)},${b.lon.toFixed(5)}`;
  }

  isValid(cacheEntry) {
    const sevenDays = 7 * 24 * 60 * 60 * 1000;
    return (Date.now() - cacheEntry.timestamp) < sevenDays;
  }

  async callOSRM(a, b) {
    const url = `https://router.project-osrm.org/route/v1/driving/${a.lon},${a.lat};${b.lon},${b.lat}?overview=false`;
    
    // Rate limit koruması
    await this.respectRateLimit();
    
    try {
      const res = await fetch(url);
      const js = await res.json();
      if (js.routes && js.routes[0]) {
        return {
          km: js.routes[0].distance / 1000,
          hours: js.routes[0].duration / 3600
        };
      }
    } catch (e) {
      console.error('OSRM error:', e);
    }
    
    // Fallback: Haversine
    return this.haversineFallback(a, b);
  }

  haversineFallback(a, b) {
    const R = 6371;
    const dLat = (b.lat - a.lat) * Math.PI / 180;
    const dLon = (b.lon - a.lon) * Math.PI / 180;
    const lat1 = a.lat * Math.PI / 180;
    const lat2 = b.lat * Math.PI / 180;
    
    const h = Math.sin(dLat/2)**2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon/2)**2;
    const km = 2 * R * Math.asin(Math.sqrt(h));
    
    return { km: km * 1.3, hours: km / 60 };
  }

  // Token bucket rate limiting
  tokens = 100;
  lastRefill = Date.now();
  
  async respectRateLimit() {
    const now = Date.now();
    const refillRate = 50; // tokens per second
    
    this.tokens = Math.min(100, this.tokens + (now - this.lastRefill) / 1000 * refillRate);
    this.lastRefill = now;
    
    if (this.tokens < 1) {
      const waitTime = (1 - this.tokens) / refillRate * 1000;
      await new Promise(r => setTimeout(r, waitTime));
    }
    
    this.tokens--;
  }
}

window.routingCache = new RoutingCache();
```

**Değiştirilecek Dosyalar:**
- `static/app.js` - `osrmDistanceDuration()` fonksiyonu
- `static/routing-cache.js` - YENİ DOSYA

---

### 2.3 Viewport-Based Araç Yükleme (PERF-003)

**Hedef:** Sadece görünür alandaki araçları yükle

```javascript
// static/app.js - loadArventoVehicles güncellemesi
let lastViewport = null;
let vehicleThrottleTimer = null;

function initViewportTracking() {
  _map.on('moveend', () => {
    if (vehicleThrottleTimer) return;
    
    vehicleThrottleTimer = setTimeout(() => {
      vehicleThrottleTimer = null;
      handleViewportChange();
    }, 300);
  });
}

async function handleViewportChange() {
  const bounds = _map.getBounds();
  const currentViewport = {
    north: bounds.getNorth(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    west: bounds.getWest()
  };

  // Eğer viewport çok değişmediyse ignore et
  if (lastViewport && isViewportSimilar(lastViewport, currentViewport)) {
    return;
  }

  lastViewport = currentViewport;

  // Sadece viewport içindeki araçları getir
  await loadVehiclesInViewport(currentViewport);
}

async function loadVehiclesInViewport(viewport) {
  const url = `/api/arvento/vehicles?bbox=${viewport.south},${viewport.west},${viewport.north},${viewport.east}`;
  const res = await fetch(url);
  const data = await res.json();
  
  if (data.vehicles) {
    updateVehicleMarkers(data.vehicles);
  }
}

// Backend endpoint eklenmeli
// routes/arvento.py
@app.route('/api/arvento/vehicles')
@login_required
def api_vehicles_in_viewport():
    bbox = request.args.get('bbox')  # south,west,north,east
    south, west, north, east = map(float, bbox.split(','))
    
    vehicles = Vehicle.query.filter(
        Vehicle.lat >= south,
        Vehicle.lat <= north,
        Vehicle.lon >= west,
        Vehicle.lon <= east
    ).all()
    
    return jsonify({
        'vehicles': [v.to_dict() for v in vehicles]
    })
```

**Değiştirilecek Dosyalar:**
- `static/app.js` - `loadArventoVehicles()` fonksiyonu
- `routes/arvento.py` - YENİ endpoint

---

### 2.4 Gelişmiş Loading UX (UX-001)

**Hedef:** Kullanıcıya net bilgilendirme

```html
<!-- templates/map.html - Loading overlay güncellemesi -->
<div id="mapLoadingOverlay" class="map-loading-overlay">
  <div class="map-loading-content">
    <div class="map-loading-icon">
      <svg class="animate-spin" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
        <path d="M12 2a10 10 0 0 1 10 10" stroke-opacity="0.75"></path>
      </svg>
    </div>
    
    <div class="map-loading-text" id="mapLoadingText">Hazırlanıyor...</div>
    
    <div class="map-progress-container">
      <div class="map-progress-bar">
        <div class="map-progress-fill" id="mapProgressFill"></div>
      </div>
      <div class="map-progress-info">
        <span id="mapProgressPercent">0%</span>
        <span id="mapProgressStatus">Başlangıç</span>
      </div>
    </div>
    
    <div class="map-loading-details" id="mapLoadingDetails">
      <!-- Detaylı progres bilgisi -->
    </div>
  </div>
</div>
```

```javascript
// static/app.js - Loading overlay helper
class LoadingOverlay {
  constructor() {
    this.overlay = document.getElementById('mapLoadingOverlay');
    this.text = document.getElementById('mapLoadingText');
    this.fill = document.getElementById('mapProgressFill');
    this.percent = document.getElementById('mapProgressPercent');
    this.status = document.getElementById('mapProgressStatus');
    this.details = document.getElementById('mapLoadingDetails');
  }

  start(message = 'İşleniyor...') {
    this.overlay.classList.add('active');
    this.text.textContent = message;
    this.update(0, 'Başlangıç', '');
  }

  update(percent, status, details = '') {
    this.fill.style.width = `${percent}%`;
    this.percent.textContent = `${percent.toFixed(0)}%`;
    this.status.textContent = status;
    if (details) {
      this.details.innerHTML = `<div class="loading-detail">${details}</div>`;
    }
  }

  success(message = 'Tamamlandı!') {
    this.update(100, '✓', message);
    setTimeout(() => this.hide(), 1500);
  }

  error(message) {
    this.text.textContent = 'Hata!';
    this.status.textContent = '✗';
    this.details.innerHTML = `<div class="loading-error">${message}</div>`;
    setTimeout(() => this.hide(), 3000);
  }

  hide() {
    this.overlay.classList.remove('active');
  }
}

// Kullanım
const mapLoader = new LoadingOverlay();

async function loadJobMarkers() {
  const week = _byId("mapWeek")?.value;
  const teamId = _byId("singleTeamSelect")?.value || '';

  if (!week) {
    toast("Lütfen hafta seçin.");
    return;
  }

  mapLoader.start('Veriler alınıyor...');

  try {
    // Fetch data
    mapLoader.update(20, 'API çağrısı', 'Hafta: ' + week);
    const url = `/api/jobs_for_map?week_start=${encodeURIComponent(week)}${teamId ? `&team_id=${teamId}` : ''}`;
    const res = await fetch(url);
    const data = await res.json();

    if (!data.ok) {
      mapLoader.error(data.error || "Veri alınamadı");
      return;
    }

    mapLoader.update(40, 'İşleniyor', `${data.all_jobs.length} iş bulundu`);

    // Worker'a gönder
    initMapWorker();
    mapWorker.postMessage({
      type: 'PROCESS_MARKERS',
      data: { jobs: data.all_jobs }
    });

  } catch (e) {
    console.error(e);
    mapLoader.error(e.message);
  }
}
```

**Değiştirilecek Dosyalar:**
- `templates/map.html` - Loading overlay HTML
- `static/app.js` - Loading helper class
- `static/style.css` - Loading styles

---

### 2.5 Responsive Mobil Düzen (UX-002)

**Hedef:** Mobil cihazlarda kullanılabilir arayüz

```css
/* static/style.css - Responsive map styles */

/* Mobile breakpoint */
@media (max-width: 768px) {
  #map-wrapper {
    height: calc(100vh - 56px);
  }

  /* Sidebar'ı collapsible yap */
  .absolute.top-4.left-4 {
    left: 0;
    right: 0;
    bottom: 80px; /* Bottom panel için yer */
    top: auto;
    width: 100%;
    z-index: [600, 800];
  }

  /* Kartları collapsible yap */
  #map-wrapper .bg-white\/95 {
    border-radius: 0;
    border-left: none;
    border-right: none;
    margin: 0 4px;
  }

  /* Bottom panel daha kompakt */
  .absolute.bottom-8 {
    bottom: 0;
    left: 0;
    right: 0;
    max-width: 100%;
    width: 100%;
  }

  /* Mobile menu button */
  #mobileMapMenuBtn {
    display: flex;
    position: fixed;
    bottom: 80px;
    right: 16px;
    z-index: 900;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: linear-gradient(135deg, #3b82f6, #2563eb);
    color: white;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    align-items: center;
    justify-content: center;
  }

  /* Hide non-essential controls on mobile */
  .hidden.mobile\:hidden {
    display: none;
  }
}

/* Tablet */
@media (min-width: 769px) and (max-width: 1024px) {
  .absolute.top-4.left-4 {
    width: 280px;
  }
}
```

```html
<!-- templates/map.html - Mobile menu button -->
<button id="mobileMapMenuBtn" class="hidden md:hidden" onclick="toggleMobileMapMenu()">
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <line x1="3" y1="12" x2="21" y2="12"></line>
    <line x1="3" y1="6" x2="21" y2="6"></line>
    <line x1="3" y1="18" x2="21" y2="18"></line>
  </svg>
</button>

<div id="mobileMapMenu" class="hidden fixed inset-0 bg-black/50 z-[900] md:hidden">
  <div class="bg-white absolute bottom-0 left-0 right-0 rounded-t-2xl p-4 animate-slide-up">
    <div class="w-12 h-1 bg-slate-300 rounded-full mx-auto mb-4"></div>
    <!-- Panel contents here -->
  </div>
</div>
```

**Değiştirilecek Dosyalar:**
- `templates/map.html` - Mobile button ve menu
- `static/style.css` - Responsive media queries

---

### 2.6 Retry Mekanizması (ERR-001)

**Hedef:** Geçici hatalarda otomatik tekrar deneme

```javascript
// static/retry-helper.js
class RetryHelper {
  static async execute(fn, options = {}) {
    const {
      maxRetries = 3,
      initialDelay = 1000,
      maxDelay = 10000,
      backoff = 2,
      retryOn = [500, 502, 503, 504, 'ECONNRESET', 'ETIMEDOUT']
    } = options;

    let lastError;
    let delay = initialDelay;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (e) {
        lastError = e;
        
        const shouldRetry = retryOn.some(code => 
          e.status === code || e.message?.includes(code) || e.code === code
        );

        if (!shouldRetry || attempt === maxRetries) {
          throw e;
        }

        console.warn(`Attempt ${attempt + 1} failed, retrying in ${delay}ms...`, e);
        
        await new Promise(r => setTimeout(r, delay));
        delay = Math.min(delay * backoff, maxDelay);
      }
    }

    throw lastError;
  }

  static withToast(fn, options = {}) {
    return RetryHelper.execute(fn, options).catch(e => {
      toast(`İşlem başarısız: ${e.message}`);
      throw e;
    });
  }
}

// Kullanım
async function loadJobMarkers() {
  const week = _byId("mapWeek")?.value;
  
  await RetryHelper.withToast(async () => {
    const url = `/api/jobs_for_map?week_start=${encodeURIComponent(week)}`;
    const res = await fetch(url);
    
    if (!res.ok) {
      throw { status: res.status, message: 'API hatası' };
    }
    
    return res.json();
  }, {
    maxRetries: 3,
    initialDelay: 500,
    backoff: 2
  });
}
```

**Değiştirilecek Dosyalar:**
- `static/retry-helper.js` - YENİ DOSYA
- `static/app.js` - API çağrılarında retry kullanımı

---

### 2.7 Offline Mode (ERR-002)

**Hedef:** İnternet bağlantısı olmadan da çalışabilme

```javascript
// static/offline-manager.js
class OfflineManager {
  constructor() {
    this.cacheName = 'v12-map-cache';
    this.dataCacheName = 'v12-map-data';
    this.isOnline = navigator.onLine;
    
    window.addEventListener('online', () => this.handleOnline());
    window.addEventListener('offline', () => this.handleOffline());
  }

  async init() {
    // Service Worker kaydet
    if ('serviceWorker' in navigator) {
      try {
        const registration = await navigator.serviceWorker.register('/sw.js');
        console.log('SW registered:', registration);
      } catch (e) {
        console.warn('SW registration failed:', e);
      }
    }

    // IndexedDB aç
    await this.openIndexedDB();
  }

  async openIndexedDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('V12MapDB', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains('jobs')) {
          db.createObjectStore('jobs', { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('routes')) {
          db.createObjectStore('routes', { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('vehicles')) {
          db.createObjectStore('vehicles', { keyPath: 'id' });
        }
      };
    });
  }

  async cacheJobs(jobs) {
    const tx = this.db.transaction('jobs', 'readwrite');
    const store = tx.objectStore('jobs');
    
    for (const job of jobs) {
      store.put({ ...job, cachedAt: Date.now() });
    }
  }

  async getCachedJobs(week) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('jobs', 'readonly');
      const store = tx.objectStore('jobs');
      const request = store.getAll();
      
      request.onsuccess = () => {
        const oneWeekAgo = Date.now() - (7 * 24 * 60 * 60 * 1000);
        const cached = request.result.filter(j => 
          j.cachedAt > oneWeekAgo && j.week === week
        );
        resolve(cached);
      };
      request.onerror = () => reject(request.error);
    });
  }

  async fetchWithOfflineFallback(url, options = {}) {
    if (this.isOnline) {
      try {
        const res = await fetch(url, options);
        return res;
      } catch (e) {
        console.warn('Network failed, using cache:', e);
      }
    }

    // Offline: cache'den getir
    if (url.includes('/api/jobs_for_map')) {
      const week = new URL(url, window.location.origin).searchParams.get('week_start');
      return this.getCachedJobs(week);
    }
  }

  handleOnline() {
    this.isOnline = true;
    toast('İnternet bağlantısı yeniden kuruldu');
    // Sync pending data
    this.syncPendingChanges();
  }

  handleOffline() {
    this.isOnline = false;
    toast('İnternet bağlantısı kesildi. Çevrimdışı mod aktif.');
  }

  async syncPendingChanges() {
    // Queue'daki değişiklikleri gönder
  }
}

window.offlineManager = new OfflineManager();
```

```javascript
// static/app.js - init içine ekle
document.addEventListener('DOMContentLoaded', () => {
  try {
    offlineManager.init();
  } catch (e) {
    console.warn('Offline mode init failed:', e);
  }
});
```

**Değiştirilecek Dosyalar:**
- `static/offline-manager.js` - YENİ DOSYA
- `static/app.js` - Offline manager init
- `static/sw.js` - Service Worker (opsiyonel)

---

## 3. Yeni Özellikler

### 3.1 Route Export (GPX/KML)

```javascript
// static/route-export.js
function exportRouteAsGPX(routeData, filename = 'rota.gpx') {
  let gpx = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="V12 Rota Planlayıcı">
  <trk>
    <name>${filename}</name>
    <trkseg>
`;

  routeData.points.forEach(point => {
    gpx += `      <trkpt lat="${point.lat}" lon="${point.lon}">
        <ele>0</ele>
        <time>${new Date().toISOString()}</time>
      </trkpt>
`;
  });

  gpx += `    </trkseg>
  </trk>
</gpx>`;

  downloadFile(gpx, filename, 'application/gpx+xml');
}

function exportRouteAsKML(routeData, filename = 'rota.kml') {
  let kml = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>${filename}</name>
    <Placemark>
      <name>Rota</name>
      <LineString>
        <coordinates>
`;

  routeData.points.forEach(point => {
    kml += `${point.lon},${point.lat},0 `;
  });

  kml += `        </coordinates>
      </LineString>
      <Style>
        <LineStyle>
          <color>ff3b82f6</color>
          <width>4</width>
        </LineStyle>
      </Style>
    </Placemark>
  </Document>
</kml>`;

  downloadFile(kml, filename, 'application/vnd.google-earth.kml+xml');
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

### 3.2 Route Animation

```javascript
// static/route-animation.js
class RouteAnimator {
  constructor(map, layer) {
    this.map = map;
    this.layer = layer;
    this.animationLayer = null;
    this.isAnimating = false;
  }

  async animateRoute(points, options = {}) {
    const {
      duration = 5000, // ms
      easing = 'linear',
      showMarker = true
    } = options;

    if (this.isAnimating) {
      this.stopAnimation();
    }

    this.isAnimating = true;
    this.animationLayer = L.layerGroup().addTo(this.map);

    const startTime = performance.now();
    const animatedMarker = showMarker ? this.createAnimatedMarker() : null;

    const animate = (currentTime) => {
      if (!this.isAnimating) return;

      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Easing function
      const easedProgress = this.ease(easing, progress);

      // Current position
      const currentPoint = this.getPointAtProgress(points, easedProgress);

      // Draw path up to current point
      this.drawAnimatedPath(points.slice(0, Math.floor(progress * points.length)));

      // Update marker position
      if (animatedMarker && currentPoint) {
        animatedMarker.setLatLng([currentPoint.lat, currentPoint.lon]);
      }

      // Continue animation
      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        this.isAnimating = false;
      }
    };

    requestAnimationFrame(animate);
  }

  ease(type, t) {
    const eases = {
      linear: t => t,
      easeInQuad: t => t * t,
      easeOutQuad: t => t * (2 - t),
      easeInOutQuad: t => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t
    };
    return (eases[type] || eases.linear)(t);
  }

  getPointAtProgress(points, progress) {
    if (points.length === 0) return null;
    const index = Math.min(
      Math.floor(progress * points.length),
      points.length - 1
    );
    return points[index];
  }

  drawAnimatedPath(points) {
    this.animationLayer.clearLayers();
    
    if (points.length < 2) return;

    const latlngs = points.map(p => [p.lat, p.lon]);
    
    L.polyline(latlngs, {
      color: '#0891b2',
      weight: 4,
      opacity: 0.8,
      smoothFactor: 1
    }).addTo(this.animationLayer);
  }

  createAnimatedMarker() {
    const icon = L.divIcon({
      className: 'animated-marker',
      html: '<div class="w-4 h-4 bg-cyan-600 rounded-full border-2 border-white shadow-lg animate-pulse"></div>',
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    });

    const marker = L.marker([0, 0], { icon }).addTo(this.animationLayer);
    return marker;
  }

  stopAnimation() {
    this.isAnimating = false;
    if (this.animationLayer) {
      this.map.removeLayer(this.animationLayer);
      this.animationLayer = null;
    }
  }
}
```

---

## 4. Dosya Yapısı Değişiklikleri

```
static/
├── app.js                    # Ana uygulama JS (güncellenecek)
├── style.css                 # Ana CSS (güncellenecek)
├── map-worker.js            # YENİ - Web Worker
├── routing-cache.js         # YENİ - Routing cache
├── offline-manager.js       # YENİ - Offline mode
├── retry-helper.js          # YENİ - Retry mekanizması
├── route-export.js          # YENİ - GPX/KML export
├── route-animation.js       # YENİ - Route animation
└── sw.js                    # YENİ - Service Worker (opsiyonel)

templates/
├── map.html                 # Güncellenecek
└── ...

routes/
├── arvento.py               # Güncellenecek
├── planner.py               # Güncellenecek
└── ...

docs/
├── MAP_IMPROVEMENTS_SPEC.md # Bu dosya
└── ...
```

---

## 5. Test Gereksinimleri

### 5.1 Unit Testler

```javascript
// tests/unit/routing-cache.test.js
describe('RoutingCache', () => {
  let cache;
  
  beforeEach(() => {
    cache = new RoutingCache();
  });
  
  test('getKey generates consistent keys', () => {
    const a = { lat: 41.0082, lon: 28.9784 };
    const b = { lat: 39.9208, lon: 32.8541 };
    const key1 = cache.getKey(a, b);
    const key2 = cache.getKey(a, b);
    expect(key1).toBe(key2);
  });
  
  test('haversineFallback calculates distance', () => {
    const a = { lat: 41.0082, lon: 28.9784 };
    const b = { lat: 39.9208, lon: 32.8541 };
    const result = cache.haversineFallback(a, b);
    expect(result.km).toBeGreaterThan(300);
    expect(result.km).toBeLessThan(500);
  });
});
```

### 5.2 Integration Testler

```javascript
// tests/integration/map.test.js
describe('Map Integration', () => {
  beforeEach(() => {
    cy.visit('/map');
  });
  
  it('loads markers successfully', () => {
    cy.intercept('/api/jobs_for_map*').as('loadJobs');
    
    cy.get('#mapWeek').type('2026-02-01');
    cy.get('#loadMarkersBtn').click();
    
    cy.wait('@loadJobs').then(() => {
      cy.get('.modern-marker').should('have.length.greaterThan', 0);
    });
  });
  
  it('shows loading overlay', () => {
    cy.intercept('/api/jobs_for_map*', { delay: 2000 }).as('slowLoad');
    
    cy.get('#loadMarkersBtn').click();
    cy.get('#mapLoadingOverlay').should('be.visible');
  });
});
```

---

## 6. Deployment Planı

### 6.1 Aşamalı Deployment

| Aşama | Değişiklik | Risk | Geri Alma |
|-------|------------|------|-----------|
| 1 | Routing Cache | Düşük | CSS class remove |
| 2 | Retry Helper | Düşük | JS comment out |
| 3 | Loading UX | Orta | Template revert |
| 4 | Web Worker | Orta | Feature flag |
| 5 | Offline Mode | Yüksek | SW unregister |

### 6.2 Feature Flag Sistemi

```javascript
// static/feature-flags.js
const FEATURE_FLAGS = {
  WEB_WORKER: false,  // Enable after testing
  OFFLINE_MODE: false,
  ROUTE_ANIMATION: true,
  GPX_EXPORT: true
};

function isFeatureEnabled(flag) {
  // Backend'den override al
  const overrides = window.FEATURE_FLAG_OVERRIDES || {};
  return overrides[flag] ?? FEATURE_FLAGS[flag];
}

// Kullanım
if (isFeatureEnabled('WEB_WORKER')) {
  initMapWorker();
}
```

---

## 7. Tahmini Geliştirme Süreleri

| Görev | Tahmini Süre | Öncelik |
|-------|--------------|---------|
| Routing Cache | 4 saat | Yüksek |
| Web Worker | 8 saat | Kritik |
| Loading UX | 4 saat | Orta |
| Retry Mechanism | 2 saat | Yüksek |
| Offline Mode | 6 saat | Orta |
| Responsive Düzen | 4 saat | Orta |
| Route Export | 3 saat | Düşük |
| Route Animation | 4 saat | Düşük |
| Test Yazımı | 8 saat | Orta |

**Toplam Tahmin:** ~43 saat geliştirme

---

## 8. Kabul Kriterleri

- [ ] Sayfa yükleme süresi < 3 saniye (LTE bağlantıda)
- [ ] 500+ marker'da UI donması yok
- [ ] API hatasında 3 kez otomatik retry
- [ ] Mobil viewport'da kayma yok
- [ ] GPX export tüm tarayıcılarda çalışıyor
- [ ] Unit test coverage > 70%
- [ ] E2E test senaryoları geçiyor

---

## 9. İletişim

**Proje Yöneticisi:** [İsim]
**Teknik Lider:** [İsim]
**İletişim:** [Email]

---

*Bu doküman V12 Harita Modülü geliştirme projesi için hazırlanmıştır.*
*Son güncelleme: 2026-02-01*
