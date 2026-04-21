# Plan Sayfası Senkronizasyon İyileştirme Görevi

## 📋 Genel Bakış

**Proje:** Saha Planlama Sistemi (V12)
**Sayfa:** http://127.0.0.1:5000/plan
**Görev ID:** PLAN-SYNC-001
**Öncelik:** Yüksek
**Durum:** Tamamlandı ✅

---

## 🎯 Problem Tanımı

### Mevcut Durum (Sorunlu)

Plan sayfasında bir değişiklik yapıldığında (hücre güncelleme, iş taşıma, iş atama, iş silme, iş iptal etme vb.), tüm kullanıcılarda senkronizasyon sağlanması için **sayfa yenileniyor**.

Bu durum şu sıkıntıları oluşturuyor:

1. **Scroll Pozisyonu Sıfırlanması**: Tablo yenilendiğinde sayfa en başa atıyor ve kullanıcı çalıştığı hücreyi kaybediyor
2. **Kullanıcı Deneyimi Kesintisi**: Çalışma akışı sürekli kesiliyor
3. **Verimlilik Kaybı**: Her değişiklikte en son çalışılan satıra tekrar gitmek gerekiyor
4. **Kendi Değişikliklerinde de Sorun**: Kullanıcı kendi yaptığı değişikliklerde bile aynı sorunla karşılaşıyor

### Örnek Senaryolar

| Senaryo | Mevcut Davranış | İstenen Davranış |
|---------|-----------------|------------------|
| İş taşıma (tarih değiştirme) | Sayfa yenileniyor, scroll başa atıyor | Sadece ilgili hücreler güncelleniyor |
| İş silme/iptal | Sayfa yenileniyor | Sadece hücre güncelleniyor |
| İş güncelleme | Bazı durumlarda sayfa yenileniyor | DOM güncelleme yeterli |
| Yeni iş ekleme | Sayfa yenileniyor | Sadece tabloya satır ekleniyor |
| Personel atama | Sayfa yenileniyor | Sadece hücre güncelleniyor |

---

## 🔍 Mevcut Sistem Analizi

### Backend (routes/realtime.py)

Socket.IO üzerinden yayınlanan olaylar:

```python
# Mevcut socket olayları
- cell_locked / cell_unlocked      # Hücre kilitleme
- cell_updated                     # Hücre güncelleme (✅ Kısmi DOM güncelleme mevcut)
- cell_cancelled / cell_restored   # İş iptal/geri yükleme
- task_moved                       # İş taşıma (❌ Sayfa yenileme yapıyor)
- overtime_added / deleted         # Mesai işlemleri
```

### Frontend (static/js/realtime.js)

**`cell_updated` olayı** (satır 791-838):
- Kullanıcı düzenleme yapıyorsa güncellemeleri sıraya alıyor
- Düzenleme yoksa doğrudan DOM güncellemesi yapıyor ✅

**`task_moved` olayı** (satır 1484):
```javascript
setTimeout(() => window.reloadWithScroll ? window.reloadWithScroll() : window.location.reload(), 800);
```
❌ **Sorun**: Tam sayfa yenileme yapıyor

### Frontend (static/js/editing-state.js)

- Kullanıcının düzenleme yapıp yapmadığını izliyor
- Düzenleme sırasında gelen güncellemeleri sıraya alıyor
- Çok fazla güncelleme olduğunda sayfa yenileme yapıyor

---

## ✅ Gereksinimler

### 1. Zorunlu Gereksinimler

| # | Gereksinim | Açıklama |
|---|------------|----------|
| R1 | **Senkronizasyon** | Tablodaki değişiklikler tüm kullanıcılarda anında görünmeli |
| R2 | **Scroll Koruma** | Sayfa yenilemeleri scroll pozisyonunu bozmamalı |
| R3 | **DOM Güncelleme** | Mümkün olan her yerde tam sayfa yenileme yerine granular DOM güncellemesi |
| R4 | **Akıcı Deneyim** | Kullanıcı çalışması kesintiye uğramamalı |
| R5 | **Görsel Geri Bildirim** | Değişiklikler görsel olarak işaretlenmeli (highlight, toast vb.) |

### 2. Kapsam - İşlem Türleri

Aşağıdaki işlemler için senkronizasyon implementasyonu gerekiyor:

| # | İşlem | Mevcut Durum | Hedef Durum |
|---|-------|--------------|-------------|
| 2.1 | **Yeni iş ekleme** | Sayfa yenileme | DOM satır ekleme (Gelecek faz) |
| 2.2 | **İş taşıma** (tarih değiştirme) | Sayfa yenileme | DOM hücre taşıma ✅ |
| 2.3 | **İş atama** (personel ekleme/çıkarma) | Kısmi güncelleme | Tam DOM güncelleme ✅ |
| 2.4 | **İş silme** | Sayfa yenileme | DOM hücre temizleme ✅ |
| 2.5 | **İş güncelleme** (not, araç, vardiya) | Kısmi güncelleme | Tam DOM güncelleme ✅ |
| 2.6 | **İş iptal etme** | DOM güncelleme ✅ | Mevcut durumu koru |
| 2.7 | **İş geri yükleme** | DOM güncelleme ✅ | Mevcut durumu koru |

---

## 🛠️ Teknik Çözüm Planı

### 1. Backend Değişiklikleri

#### 1.1 Socket Payload'larını Genişletme

Tüm socket olayları için zenginleştirilmiş payload döndürülmeli:

```python
# Örnek: task_moved olayı için yeni payload
socketio.emit("task_moved", {
    "source_cell_id": source_cell.id,
    "target_cell_id": target_cell.id,
    "project_id": project_id,
    "old_date": old_date.isoformat(),
    "new_date": new_date.isoformat(),
    "moved_by": user.full_name,
    "moved_by_id": user.id,
    # Yeni alanlar - frontend için
    "cell_data": {
        "shift": target_cell.shift,
        "note": target_cell.note,
        "vehicle_info": target_cell.vehicle_info,
        "team_id": target_cell.team_id,
        "status": target_cell.status,
        "person_ids": [a.person_id for a in target_cell.assignments]
    }
}, room="plan_updates", namespace="/")
```

#### 1.2 Yeni API Endpoint'leri

Frontend'in granular güncelleme yapabilmesi için:

```
GET /api/cell/data/<cell_id>
- Hücre verilerini ve ilişkili verileri döndürür
```

### 2. Frontend Değişiklikleri

#### 2.1 Granular Update Fonksiyonu

```javascript
// static/js/realtime.js dosyasına eklenecek

/**
 * Hücreyi DOM'da güncelle (tam sayfa yenileme olmadan)
 */
function updateCellDOM(cellId, data) {
    const cell = getCellEl(cellId);
    if (!cell) {
        console.warn('Hücre bulunamadı:', cellId);
        return false;
    }

    // Shift güncelleme
    if (data.shift !== undefined) {
        const timeDiv = cell.querySelector('.cell-time');
        if (timeDiv) timeDiv.textContent = data.shift;
        cell.setAttribute('data-shift', data.shift || '');
    }

    // Note güncelleme
    if (data.note !== undefined) {
        cell.setAttribute('data-note', data.note || '');
        const noteDiv = cell.querySelector('.cell-note');
        if (noteDiv) noteDiv.textContent = data.note || '';
    }

    // Vehicle güncelleme
    if (data.vehicle_info !== undefined) {
        cell.setAttribute('data-vehicle', data.vehicle_info || '');
        const vehicleDiv = cell.querySelector('.cell-vehicle');
        if (vehicleDiv) vehicleDiv.textContent = data.vehicle_info || '';
    }

    // Status güncelleme
    if (data.status !== undefined) {
        cell.setAttribute('data-status', data.status);
        if (data.status === 'cancelled') {
            cell.classList.add('is-cancelled');
        } else {
            cell.classList.remove('is-cancelled');
        }
    }

    // Personel atamaları güncelleme
    if (data.person_ids !== undefined) {
        updateCellPersonnel(cell, data.person_ids);
    }

    return true;
}

/**
 * İş taşıma işlemini DOM'da gerçekleştir
 */
function moveTaskDOM(sourceCellId, targetCellId, data) {
    const sourceCell = getCellEl(sourceCellId);
    const targetCell = getCellEl(targetCellId);

    if (!sourceCell || !targetCell) {
        console.warn('Kaynak veya hedef hücre bulunamadı');
        return false;
    }

    // Kaynak hücreyi temizle
    clearCellDOM(sourceCell);

    // Hedef hücreyi güncelle
    updateCellDOM(targetCellId, data);

    // Görsel efekt
    targetCell.style.backgroundColor = '#86efac'; // Yeşil highlight
    setTimeout(() => {
        targetCell.style.backgroundColor = '';
    }, 2000);

    return true;
}
```

#### 2.2 Socket Event Handler'larını Güncelleme

```javascript
// static/js/realtime.js

// task_moved olayı için yeni handler
socket.on('task_moved', (data) => {
    if (data.moved_by_id === getCurrentUserId()) {
        // Kendi yaptığımız taşıma - zaten işlemi yaptık
        return;
    }

    // EditingStateManager ile düzenleme durumu kontrolü
    if (window.EditingStateManager && window.EditingStateManager.isEditing()) {
        // Düzenleme aktif - sıraya al
        window.EditingStateManager.queueTaskMove({
            source_cell_id: data.source_cell_id,
            target_cell_id: data.target_cell_id,
            cell_data: data.cell_data
        });
    } else {
        // DOM güncelleme
        moveTaskDOM(data.source_cell_id, data.target_cell_id, data.cell_data);
    }

    // Toast bildirim
    showToast(`${data.moved_by} işi taşıdı`, 'info');
});
```

#### 2.3 EditingStateManager Güncelleme

```javascript
// static/js/editing-state.js

// Yeni fonksiyonlar ekle
function queueTaskMove(moveData) {
    state.pendingTaskMoves = state.pendingTaskMoves || [];
    state.pendingTaskMoves.push({
        ...moveData,
        queuedAt: Date.now()
    });
    state.hasPendingUpdates = true;
    showPendingUpdateIndicator();
}

function applyPendingTaskMoves() {
    if (!state.pendingTaskMoves || state.pendingTaskMoves.length === 0) return;

    state.pendingTaskMoves.forEach(move => {
        moveTaskDOM(move.source_cell_id, move.target_cell_id, move.cell_data);
    });

    state.pendingTaskMoves = [];
    state.hasPendingUpdates = false;
    hidePendingUpdateIndicator();
}
```

#### 2.4 Yeni Satır Ekleme İçin DOM Güncelleme

```javascript
// Plan tablosuna yeni satır ekleme
function addJobRowDOM(projectData, cellData) {
    const tbody = document.getElementById('planTbody');
    if (!tbody) return false;

    // Yeni satır HTML'i oluştur
    const newRow = createJobRowHTML(projectData, cellData);

    // Tabloya ekle (en sona veya uygun pozisyona)
    tbody.insertAdjacentHTML('beforeend', newRow);

    // Scroll değil, smooth scroll ile göster
    newRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    return true;
}
```

---

## 📁 Değiştirilecek Dosyalar

| Dosya | Değişiklik Türü | Açıklama |
|-------|-----------------|----------|
| `routes/realtime.py` | Modifikasyon | Socket payload'larını genişletme |
| `static/js/realtime.js` | Modifikasyon | Socket event handler'larını güncelleme, yeni DOM fonksiyonları |
| `static/js/editing-state.js` | Modifikasyon | Task move queue fonksiyonları ekleme |
| `static/app.js` | Opsiyonel | Yardımcı fonksiyonlar (varsa) |

---

## 🧪 Test Senaryoları

### Unit Testler

1. **updateCellDOM fonksiyonu testi**
   - Farklı data kombinasyonları ile test
   - Eksik hücre durumu testi

2. **moveTaskDOM fonksiyonu testi**
   - Kaynak ve hedef hücre aynı olduğunda
   - Hedef hücre mevcut değilse

3. **EditingStateManager queue testi**
   - Çoklu güncelleme sıralaması
   - Sıra temizleme

### Integration Testler

1. **Senkronizasyon Testi**
   - 2 farklı tarayıcı/sekme aç
   - Birinde işlem yap
   - Diğerinde anlık güncelleme kontrol et

2. **Scroll Koruma Testi**
   - Sayfayı aşağı kaydır
   - İşlem yap
   - Scroll pozisyonunu kontrol et

3. **Editing State Testi**
   - Düzenleme modunda iken gelen güncelleme
   - Düzenleme bittiğinde sıradaki güncellemelerin uygulanması

---

## 📊 Başarı Kriterleri

| # | Kriter | Hedef | Ölçüm Metodu |
|---|--------|-------|--------------|
| 1 | Scroll kaybı oranı | %0 | Kullanıcı şikayetleri |
| 2 | Ortalama sayfa yenileme sayısı | < 1/gün | Log analizi |
| 3 | Senkronizasyon gecikmesi | < 500ms | Socket event timing |
| 4 | DOM güncelleme başarı oranı | %100 | Console log kontrolü |

---

## ⚠️ Riskler ve Önlemler

| Risk | Önlem |
|------|-------|
| DOM yapısı değişirse fonksiyonlar bozulabilir | Selector'ları merkezi yönet |
| Büyük tablolarda DOM güncelleme yavaş olabilir | Virtual scrolling değerlendir |
| Conflict durumları | Versiyon kontrolü güçlendir |
| Socket bağlantı kopması | Fallback polling mekanizması |

---

## 📅 Tahmini Süre

| Aşama | Süre |
|-------|------|
| Analiz ve tasarım | 2 saat |
| Backend değişiklikleri | 3 saat |
| Frontend değişiklikleri | 6 saat |
| Test | 3 saat |
| **Toplam** | **14 saat** |

---

## 🔗 İlgili Dosyalar

- [`routes/realtime.py`](routes/realtime.py) - Backend real-time API'leri
- [`static/js/realtime.js`](static/js/realtime.js) - Frontend socket işleyicileri
- [`static/js/editing-state.js`](static/js/editing-state.js) - Düzenleme durumu yönetimi
- [`static/app.js`](static/app.js) - Ana uygulama fonksiyonları
- [`templates/plan.html`](templates/plan.html) - Plan sayfası şablonu

---

## 📝 Değişiklik Logu

| Versiyon | Tarih | Değişiklik | Yapan |
|----------|-------|------------|-------|
| 1.0 | 2026-02-02 | Görev dokümanı oluşturuldu | - |
