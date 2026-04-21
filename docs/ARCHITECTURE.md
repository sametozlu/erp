# Sistem Mimarisi

## Netmon Proje Takip Sistemi - Mimari Dökümantasyonu

**Versiyon:** 2.0  
**Son Güncelleme:** 2026-02-02

---

## 📋 Genel Bakış

Netmon Proje Takip Sistemi, saha operasyonlarını yönetmek için tasarlanmış bir web uygulamasıdır. Flask tabanlı backend, SQLite veritabanı ve real-time WebSocket iletişimi kullanır.

---

## 🏗️ Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Browser   │  │   Mobile    │  │   PWA       │              │
│  │  (Desktop)  │  │  (WebView)  │  │ (Installed) │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                       │
│         └────────────────┼────────────────┘                      │
│                          ▼                                        │
│              ┌───────────────────────┐                           │
│              │   Service Worker      │                           │
│              │   (Offline Support)   │                           │
│              └───────────┬───────────┘                           │
└──────────────────────────┼──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       APPLICATION LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Nginx (Reverse Proxy)                 │    │
│  │   - SSL Termination                                      │    │
│  │   - Static File Serving                                  │    │
│  │   - WebSocket Proxy                                      │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Flask Application                      │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │   Auth   │ │   API    │ │  Admin   │ │ Planner  │   │    │
│  │  │ Blueprint│ │Blueprint │ │Blueprint │ │Blueprint │   │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │  Tasks   │ │ Analytics│ │ Realtime │ │  Chat    │   │    │
│  │  │Blueprint │ │Blueprint │ │Blueprint │ │Blueprint │   │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Flask-SocketIO                          │    │
│  │   - Real-time Events                                     │    │
│  │   - Push-to-Talk (PTT)                                   │    │
│  │   - Live Notifications                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                SQLAlchemy ORM                            │    │
│  │   - Model Definitions                                    │    │
│  │   - Query Builder                                        │    │
│  │   - Connection Pooling                                   │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  SQLite Database                         │    │
│  │   - WAL Mode (Concurrent Reads)                          │    │
│  │   - Foreign Keys Enabled                                 │    │
│  │   - Automatic Migrations                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  File Storage                            │    │
│  │   - /instance/uploads (Attachments)                      │    │
│  │   - /instance/logs (Application Logs)                    │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📦 Modül Yapısı

```
V12/
├── app.py                    # Ana uygulama dosyası
├── extensions.py             # Flask extension'ları (db, socketio)
├── models.py                 # SQLAlchemy model tanımları
├── utils.py                  # Yardımcı fonksiyonlar
│
├── routes/                   # Blueprint'ler
│   ├── auth.py              # Kimlik doğrulama
│   ├── api.py               # Genel API endpoint'leri
│   ├── admin.py             # Admin paneli
│   ├── planner.py           # Plan yönetimi
│   ├── analytics_routes.py  # İstatistik ve raporlar
│   ├── realtime.py          # WebSocket olayları
│   ├── tasks.py             # Görev takip sistemi
│   ├── chat.py              # Mesajlaşma
│   └── arvento.py           # Araç takip entegrasyonu
│
├── services/                 # İş mantığı servisleri
│   ├── analytics_service.py # İstatistik hesaplamaları
│   ├── analytics_helpers.py # Yardımcı fonksiyonlar
│   └── mail_service.py      # E-posta gönderimi
│
├── templates/                # Jinja2 template'leri
│   ├── base.html            # Ana şablon
│   ├── plan.html            # Planlama sayfası
│   ├── reports_analytics.html
│   └── ...
│
├── static/                   # Statik dosyalar
│   ├── style.css            # Ana CSS
│   ├── app.js               # Ana JavaScript
│   ├── sw.js                # Service Worker
│   └── js/                  # Modüler JavaScript
│       ├── offline/         # Offline destek
│       ├── ui/              # UI bileşenleri
│       └── networking/      # Ağ işlemleri
│
└── docs/                     # Dokümantasyon
    ├── API_DOKUMENTASYON.md
    ├── DEPLOYMENT_GUIDE.md
    ├── ARCHITECTURE.md
    └── SECURITY_GUIDELINES.md
```

---

## 🗄️ Veritabanı Şeması

### Ana Tablolar

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    User      │       │   Project    │       │    Team      │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id           │       │ id           │       │ id           │
│ username     │       │ project_code │       │ name         │
│ password_hash│       │ project_name │       │ signature    │
│ role         │◄──────│ region       │◄──────│ vehicle_id   │
│ team_id      │       │ is_active    │       └──────────────┘
└──────────────┘       └──────────────┘              │
       │                      │                       │
       │                      ▼                       │
       │               ┌──────────────┐              │
       │               │  SubProject  │              │
       │               ├──────────────┤              │
       │               │ id           │              │
       │               │ project_id   │              │
       │               │ name         │              │
       │               │ code         │              │
       │               └──────────────┘              │
       │                      │                       │
       ▼                      ▼                       ▼
┌──────────────────────────────────────────────────────────┐
│                        PlanCell                           │
├──────────────────────────────────────────────────────────┤
│ id, project_id, work_date, shift, note, team_id          │
│ status, cancelled_at, cancellation_reason, version       │
└──────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐       ┌──────────────┐
│     Job      │       │ JobFeedback  │
├──────────────┤       ├──────────────┤
│ id           │◄──────│ id           │
│ cell_id      │       │ job_id       │
│ kanban_status│       │ outcome      │
│ is_published │       │ notes_text   │
└──────────────┘       └──────────────┘
```

### İlişkiler

| Tablo | İlişki | Açıklama |
|-------|--------|----------|
| User → Team | N:1 | Kullanıcı bir ekibe ait |
| Project → SubProject | 1:N | Proje birden çok alt proje içerir |
| PlanCell → CellAssignment | 1:N | Hücreye birden çok personel atanabilir |
| Job → JobFeedback | 1:N | İş için birden çok geri bildirim |
| Task → TaskLog | 1:N | Görev için birden çok log kaydı |

---

## 🔄 Real-time Akışı

```
┌─────────────┐                    ┌─────────────┐
│   Client A  │                    │   Client B  │
└──────┬──────┘                    └──────┬──────┘
       │                                   │
       │ 1. cell_update                    │
       ▼                                   │
┌──────────────────────────────────────────┴───────┐
│              Flask-SocketIO Server               │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌─────────────┐    ┌─────────────┐             │
│  │   Room:     │    │   Room:     │             │
│  │   team_1    │    │   team_2    │             │
│  └─────────────┘    └─────────────┘             │
│                                                  │
│  Events:                                         │
│  - cell_update    → Broadcast to room           │
│  - cell_lock      → Broadcast to room           │
│  - voice_message  → Broadcast to room           │
│  - notification   → Send to specific user       │
│                                                  │
└──────────────────────────────────────────────────┘
       │
       │ 2. broadcast (cell_update)
       ▼
┌─────────────┐
│   Client B  │ ← Receives update
└─────────────┘
```

---

## 🔐 Güvenlik Katmanları

1. **Session-based Authentication**
   - Flask-Login ile kullanıcı oturumu
   - Secure cookie flags

2. **CSRF Protection**
   - Tüm POST/PUT/DELETE isteklerinde token kontrolü

3. **Role-based Access Control (RBAC)**
   - admin, planner, field, user rolleri
   - Blueprint bazlı erişim kontrolü

4. **Input Validation**
   - SQLAlchemy parameterized queries
   - HTML escape for XSS prevention

---

## 📈 Performans Optimizasyonları

| Alan | Optimizasyon |
|------|--------------|
| Database | WAL mode, indexes, eager loading |
| Queries | joinedload() ile N+1 çözümü |
| Static Files | Nginx ile serve, cache headers |
| WebSocket | Room-based broadcasting |
| Frontend | Service Worker caching |

---

## 📚 Ek Kaynaklar

- [API Dokümantasyonu](API_DOKUMENTASYON.md)
- [Deployment Rehberi](DEPLOYMENT_GUIDE.md)
- [Güvenlik Rehberi](SECURITY_GUIDELINES.md)
