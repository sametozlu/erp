# Proje Kodu Otomatik Doldurma Görevi

## Genel Bakış
Bu görev, "Projeler" sayfasında "Proje Ekle" butonuna tıklandığında, proje kodu alanının son mevcut proje kodunun 1 fazlası otomatik olarak doldurulmasını sağlar. Kullanıcı bu değeri düzenleyebilir.

## Mevcut Durum
- `templates/projects.html` dosyasında `addProjectModal` modal'ı mevcut
- `openAddProjectModal()` fonksiyonu modal açıldığında form alanlarını temizliyor
- `routes/planner.py` dosyasında `projects_page()` route'u proje ekleme işlemini yönetiyor
- Projeler `Project` modelinde `project_code` alanı ile saklanıyor

## Yapılacaklar

### 1. Backend: Son Proje Kodunu Getiren API Endpoint

**Dosya:** `routes/planner.py`

**Yeni route ekle:**
```python
@planner_bp.route("/api/next-project-code", methods=["GET"])
@login_required
@observer_required
def api_next_project_code():
    """Son proje kodunu bulup bir sonraki kodunu döndürür"""
    # Sadece ana projeleri al (region == '-')
    last_project = Project.query.filter(Project.region == "-")\
        .order_by(Project.project_code.desc()).first()
    
    if not last_project:
        return jsonify({"next_code": "P-001"})
    
    current_code = last_project.project_code or ""
    
    # Kod formatını analiz et ve sonraki kodu hesapla
    import re
    
    # Format: "P-XXX" veya "XXXX-XXXX" gibi formatları destekle
    # Sayısal kısmı bul
    numeric_match = re.search(r'(\d+)$', current_code)
    
    if numeric_match:
        numeric_part = numeric_match.group(1)
        next_numeric = int(numeric_part) + 1
        
        # Aynı formatta yeni kod oluştur
        prefix = current_code[:len(current_code) - len(numeric_part)]
        next_code = f"{prefix}{next_numeric:0{len(numeric_part)}d}"
    else:
        # Format tanınmazsa basit bir ekleme yap
        next_code = f"{current_code}-1"
    
    return jsonify({"next_code": next_code})
```

### 2. Frontend: API'yi Çağır ve Input'u Doldur

**Dosya:** `templates/projects.html`

**`openAddProjectModal()` fonksiyonunu güncelle:**

```javascript
async function openAddProjectModal() {
  const modal = document.getElementById('addProjectModal');
  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('open');
    
    // Form alanlarını temizle
    document.getElementById('modal_project_name').value = '';
    document.getElementById('modal_responsible').value = '';
    document.getElementById('modal_karsi_firma_sorumlusu').value = '';
    document.getElementById('modal_is_active').value = '';
    
    // Son proje kodunu al ve input'a yaz
    try {
      const response = await fetch('/api/next-project-code');
      const data = await response.json();
      document.getElementById('modal_project_code').value = data.next_code || '';
    } catch (error) {
      console.error('Proje kodu alınamadı:', error);
      document.getElementById('modal_project_code').value = '';
    }
  }
}
```

### 3. Input Alanını Düzenlenebilir Tut

**Dosya:** `templates/projects.html`

**Modal'daki input HTML'i (zaten düzenlenebilir, sadece stil ekle):**

```html
<label>Proje Kodu 
  <input name="project_code" id="modal_project_code" required 
         placeholder="Örn: P-042"
         style="transition: border-color 0.2s;">
</label>
```

### 4. Stil İyileştirmesi (İsteğe Bağlı)

**Dosya:** `templates/projects.html`

**CSS ekle:**
```css
#modal_project_code:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-alpha);
}

#modal_project_code[value^="P-"] {
  font-family: monospace;
  letter-spacing: 1px;
}
```

## Test Senaryoları

1. **Boş veritabanı:** İlk proje eklendiğinde "P-001" veya benzeri bir kod önerilmeli
2. **Mevcut proje var:** Son proje kodunun 1 fazlası önerilmeli (örn: "P-041" -> "P-042")
3. **Farklı format:** "9026-0001" formatlı projelerde de doğru çalışmalı
4. **Manuel düzenleme:** Kullanıcı önerilen kodu değiştirebilmeli
5. **Mevcut kod çakışması:** Aynı kod varsa hata mesajı verilmeli

## Notlar

- Bu özellik sadece öneri sunar, zorunlu değildir
- Kullanıcı her zaman farklı bir kod girebilir
- Backend validation halihazırda benzersiz kod kontrolü yapıyor
- API endpoint'i sadece ana projeleri (region == '-') dikkate alır

## Tahmini Süre
- Backend API: 15 dakika
- Frontend entegrasyonu: 10 dakika
- Test: 5 dakika
- **Toplam: ~30 dakika**
