# Güvenlik Rehberi

## Netmon Proje Takip Sistemi - Güvenlik Yönergeleri

**Versiyon:** 2.0  
**Son Güncelleme:** 2026-02-02

---

## 📋 Genel Güvenlik Prensipleri

1. **Defense in Depth** - Çok katmanlı güvenlik
2. **Least Privilege** - Minimum yetki prensibi
3. **Secure by Default** - Varsayılan olarak güvenli
4. **Fail Secure** - Hata durumunda güvenli kalma

---

## 🔐 Kimlik Doğrulama

### Password Hashing

Sistem `pbkdf2:sha256` algoritması ile şifreleme kullanır:

```python
from werkzeug.security import generate_password_hash

# Şifre hash'leme
password_hash = generate_password_hash(password, method='pbkdf2:sha256')
```

### Şifre Politikası

Önerilen minimum gereksinimler:

| Kural | Değer |
|-------|-------|
| Minimum uzunluk | 8 karakter |
| Büyük harf | En az 1 |
| Küçük harf | En az 1 |
| Rakam | En az 1 |
| Özel karakter | Önerilir |

### Session Yönetimi

```python
# Güvenli session ayarları
app.config['SESSION_COOKIE_SECURE'] = True      # Sadece HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True    # JavaScript erişimi yok
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'   # CSRF koruması
app.config['PERMANENT_SESSION_LIFETIME'] = 3600 # 1 saat
```

---

## 🛡️ CSRF Koruması

Tüm state-changing isteklerde CSRF token kontrolü yapılır:

### Backend Kontrolü

```python
@app.before_request
def _csrf_protect_unsafe_methods():
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
        if not token or token != session.get('csrf_token'):
            abort(403, 'CSRF token mismatch')
```

### Frontend Kullanımı

```javascript
// CSRF token'ı header'a ekle
fetch('/api/endpoint', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': document.getElementById('csrfToken').value
    },
    body: JSON.stringify(data)
});
```

---

## 🔒 Input Validation

### SQL Injection Koruması

SQLAlchemy ORM kullanarak parameterized queries:

```python
# ✅ Güvenli
user = User.query.filter_by(username=username).first()

# ❌ Güvensiz (KULLANMAYIN)
# db.execute(f"SELECT * FROM user WHERE username = '{username}'")
```

### XSS Koruması

Jinja2 template'lerinde otomatik escape:

```html
<!-- Güvenli: Otomatik escape -->
<p>{{ user_input }}</p>

<!-- Dikkatli kullanın: raw HTML -->
<p>{{ trusted_html | safe }}</p>
```

### File Upload Güvenliği

```python
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Dosya adını güvenli hale getir
from werkzeug.utils import secure_filename
safe_filename = secure_filename(uploaded_file.filename)
```

---

## 👥 Yetkilendirme (Authorization)

### Role-Based Access Control (RBAC)

| Rol | Açıklama | Yetkiler |
|-----|----------|----------|
| `admin` | Sistem yöneticisi | Tüm işlemler |
| `planner` | Planlayıcı | Plan oluşturma/düzenleme |
| `field` | Saha personeli | Geri bildirim, kendi işlerini görme |
| `user` | Normal kullanıcı | Okuma yetkisi |
| `gözlemci` | Gözlemci | Sadece okuma |

### Decorator Kullanımı

```python
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user or not user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/users')
@admin_required
def admin_users():
    # Sadece admin erişebilir
    pass
```

---

## 🔑 Secret Key Yönetimi

### Environment Variables

```bash
# .env dosyası (git'e EKLEMEYİN)
SECRET_KEY=your-super-secret-key-minimum-32-characters-long
SMTP_PASS=your-smtp-password
```

### Production Gereksinimleri

```python
# SECRET_KEY zorunlu kontrolü
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise ValueError("SECRET_KEY environment variable is required in production")
```

### Güçlü Key Oluşturma

```bash
# Python ile
python -c "import secrets; print(secrets.token_hex(32))"

# OpenSSL ile
openssl rand -hex 32
```

---

## 🌐 HTTPS Yapılandırması

### Zorunlu HTTPS

```python
# Production'da HTTP'yi HTTPS'e yönlendir
@app.before_request
def force_https():
    if not request.is_secure and not app.debug:
        return redirect(request.url.replace('http://', 'https://', 1), code=301)
```

### Security Headers

```python
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response
```

---

## 📝 Logging ve Audit

### Güvenlik Logları

```python
import logging

security_logger = logging.getLogger('security')

# Başarısız giriş denemeleri
security_logger.warning(f"Failed login attempt for user: {username} from IP: {request.remote_addr}")

# Yetkisiz erişim denemeleri
security_logger.warning(f"Unauthorized access attempt by user {user.id} to {request.path}")
```

### Log Formatı

```
[2026-02-02 15:30:45] WARNING security: Failed login attempt for user: admin from IP: 192.168.1.100
```

---

## 🚨 Güvenlik Kontrol Listesi

### Deployment Öncesi

- [ ] `SECRET_KEY` environment variable olarak ayarlandı
- [ ] Debug mode kapalı (`app.debug = False`)
- [ ] HTTPS yapılandırıldı
- [ ] Database backup planı hazır
- [ ] Log rotation ayarlandı
- [ ] Rate limiting aktif

### Periyodik Kontroller

- [ ] Bağımlılık güncellemeleri (haftalık)
- [ ] Log inceleme (günlük)
- [ ] Backup testi (aylık)
- [ ] Güvenlik taraması (aylık)

---

## 🔄 Güvenlik Güncellemeleri

### Bağımlılık Güncelleme

```bash
# Güvenlik açığı taraması
pip-audit

# Güncellemeleri kontrol et
pip list --outdated

# Güncelleme yap
pip install --upgrade package_name
```

### CVE Takibi

- [NVD (National Vulnerability Database)](https://nvd.nist.gov/)
- [Snyk Vulnerability DB](https://snyk.io/vuln)
- [GitHub Security Advisories](https://github.com/advisories)

---

## 📚 Ek Kaynaklar

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/latest/security/)
- [API Dokümantasyonu](API_DOKUMENTASYON.md)
- [Deployment Rehberi](DEPLOYMENT_GUIDE.md)
- [Mimari Dökümantasyonu](ARCHITECTURE.md)
