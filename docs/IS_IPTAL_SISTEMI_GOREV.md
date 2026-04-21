# İş İptal Sistemi - Görev Planı

## Görev Özeti
İş iptal işlemini hücreye sağ tıklamadan, iş detay modalının içinden yapılabilir hale getirmek. İptal sırasında not ve dosya eklenebilmeli, iptal geri alınabilmeli.

## Todo Listesi

### 1. Veritabanı Modeli Güncelleme
- [ ] CellCancellation modeline file alanları ekle (file_path, file_name, file_type)
- [ ] Migration dosyası oluştur
- [ ] Veritabanını güncelle

### 2. Backend API Güncelleme
- [ ] `/api/cell/cancel` endpointini dosya upload destekleyecek şekilde güncelle
- [ ] Dosya upload fonksiyonu ekle
- [ ] Dosya kaydetme path'ini belirle (instance/uploads/cancellations/)
- [ ] `/api/cell/restore` endpointini dosya silme destekleyecek şekilde güncelle

### 3. Frontend - İş Detay Modalı Güncelleme
- [ ] cellModal'a "İş İptal Et" butonu ekle (sağ üst köşede, Sil/Kapat/Kaydet yanına)
- [ ] İptal formu section'ı ekle (hidden başlangıçta, butona basınca açılır)
- [ ] İptal bilgisi section'ı ekle (iptal edilmiş işler için, read-only)
- [ ] Dosya upload alanı ekle (drag & drop destekli)
- [ ] "İptal Kaldır" butonu ekle

### 4. Frontend - JavaScript Güncelleme
- [ ] İptal butonu click handler'ı yaz (formu göster)
- [ ] Dosya upload handler'ı yaz (drag & drop)
- [ ] İptal API call'ı yaz (FormData kullanarak dosya ile birlikte)
- [ ] İptal kaldır API call'ı yaz
- [ ] Modal'da iptal durumuna göre UI güncelleme fonksiyonu yaz
- [ ] İptal bilgisi section'ını doldurma fonksiyonu yaz

### 5. Context Menu ve Tablo Görünümü Güncelleme
- [ ] Sağ tık menüsündeki "İşi İptal Et" seçeneğini kaldır
- [ ] "İptal Nedenini Göster" seçeneğini koru (varsa)
- [ ] **Tablo hücrelerinde iptal gösterimi ekle:**
  - [ ] CSS ile `is-cancelled` class'ı için strikethrough (üzeri çizili) stili
  - [ ] Metin rengi kırmızı (#dc2626)
  - [ ] Arka plan açık kırmızı (#fef2f2)
  - [ ] İptal icon'u (❌) ekle
- [ ] İptal geri alınınca normal görünüme dönüş

### 6. Dosya Yönetimi
- [ ] Cancellation dosyaları için uploads klasörü oluştur
- [ ] Dosya silme fonksiyonu yaz (iptal geri alınınca)
- [ ] Dosya güvenlik kontrolü (tip, boyut)

### 7. Test
- [ ] İptal işlemini test et (not ile)
- [ ] Dosya upload'u test et
- [ ] İptal geri almayı test et (dosya siliniyor mu?)
- [ ] Çakışma durumlarını test et
- [ ] Responsive görünümü test et

---

## Teknik Detaylar

### API Endpoint Güncellemesi

**POST /api/cell/cancel**
```json
{
  "cell_id": 123,
  "reason": "İptal nedeni",
  "csrf_token": "...",
  "file": "multipart/form-data"
}
```

**POST /api/cell/restore**
```json
{
  "cell_id": 123,
  "csrf_token": "..."
}
```

### Modal Yapısı

```html
<div id="cellModal">
  <!-- Mevcut header -->
  <div class="rowline">
    <button onclick="clearCell()">Sil</button>
    <button onclick="closeCellModal()">Kapat</button>
    <button onclick="saveCell()">Kaydet</button>
    <button id="btnCancelJob" onclick="showCancelForm()">İş İptal Et</button>
  </div>
  
  <!-- Mevcut form alanları -->
  <form id="modalForm">...</form>
  
  <!-- YENİ: İptal Formu (hidden) -->
  <div id="cancelFormSection" style="display:none;">
    <h4>İş İptal Et</h4>
    <textarea id="cancelReason" required></textarea>
    <input type="file" id="cancelFile">
    <button onclick="submitCancel()">İptal Et</button>
    <button onclick="hideCancelForm()">Vazgeç</button>
  </div>
  
  <!-- YENİ: İptal Bilgisi (iptal edilmiş işler için, hidden) -->
  <div id="cancellationInfoSection" style="display:none;">
    <h4>İptal Bilgisi</h4>
    <p>İptal Tarihi: <span id="cancelDate"></span></p>
    <p>İptal Eden: <span id="canceledBy"></span></p>
    <p>Neden: <span id="cancelReasonDisplay"></span></p>
    <p>Dosya: <a id="cancelFileLink" href="#">Dosya</a></p>
    <button id="btnRemoveCancellation" onclick="removeCancellation()">İptal Kaldır</button>
  </div>
</div>
```

### JavaScript Fonksiyonları

```javascript
// İptal formunu göster
function showCancelForm() {
    document.getElementById('cancelFormSection').style.display = 'block';
    document.getElementById('cancellationInfoSection').style.display = 'none';
}

// İptal formunu gizle
function hideCancelForm() {
    document.getElementById('cancelFormSection').style.display = 'none';
    document.getElementById('cancelReason').value = '';
    document.getElementById('cancelFile').value = '';
}

// İptal et
async function submitCancel() {
    const reason = document.getElementById('cancelReason').value.trim();
    if (!reason) {
        showToast('İptal nedeni zorunludur', 'warning');
        return;
    }
    
    const formData = new FormData();
    formData.append('cell_id', active.id);
    formData.append('reason', reason);
    formData.append('csrf_token', csrfToken);
    
    const fileInput = document.getElementById('cancelFile');
    if (fileInput.files.length > 0) {
        formData.append('file', fileInput.files[0]);
    }
    
    const res = await fetch('/api/cell/cancel', {
        method: 'POST',
        body: formData
    });
    
    if (res.ok) {
        showToast('İş iptal edildi', 'success');
        closeCellModal();
        refreshCell(active.id);
    }
}

// İptal kaldır
async function removeCancellation() {
    const res = await fetch('/api/cell/restore', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            cell_id: active.id,
            csrf_token: csrfToken
        })
    });
    
    if (res.ok) {
        showToast('İptal kaldırıldı', 'success');
        closeCellModal();
        refreshCell(active.id);
    }
}
```

---

## Bağımlılıklar
- Mevcut `/api/cell/cancel` endpointi
- Mevcut `/api/cell/restore` endpointi
- Mevcut cellModal yapısı
- Mevcut dosya upload sistemi (dropzone)

## Notlar
- İptal işlemi sırasında dosya ekleme zorunlu değil
- Mevcut sağ tık menüsündeki "İşi İptal Et" seçeneği kaldırılacak
- "İptal Nedenini Göster" seçeneği korunabilir
