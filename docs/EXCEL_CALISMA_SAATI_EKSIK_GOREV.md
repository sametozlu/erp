# Excel Export - Çalışma Saati ve Detayı Eksiklik Görevi

## Problem Tanımı

Plan tablosunu Excel olarak indirirken:
- **Çalışma detayı** eksik görünüyor
- **Çalışma saati** bilgisi gösterilmiyor

Timesheet (Zimmet) Excel export'unda da:
- **Çalışma saati** bilgisi eksik (sadece mesai var, normal çalışma saati yok)

## Mevcut Durum Analizi

### Plan Excel Export (`/plan/export/excel`)

Mevcut Excel yapısı:
- Sütunlar: İL, PROJE, SORUMLU, Gün1, Gün2, ... Gün7
- Her gün hücresinde: Alt proje, Personel, Not

**Sorun**: Çalışma saati ve çalışma detayı hücre içinde yazmıyor.

### Timesheet Excel Export (`/timesheet/excel`)

Mevcut Excel yapısı:
- Sütunlar: Personel, Firma, Seviye, Gün1, Gün2, ... Gün7, Toplam Mesai
- Her gün hücresinde: Şehir, Proje, Alt Proje, Mesai, Önemli Not

**Sorun**: Normal çalışma saati hiç gösterilmiyor (sadece mesai var).

## Yapılması Gerekenler

**Önemli:** Yeni sütun EKLENMEYECEK. Mevcut hücrelerin içine bilgi eklenecek. Excel tablo formatında kalacak.

### 1. Plan Excel Export Düzeltmesi

Dosya: [`routes/planner.py`](routes/planner.py:1024)

Mevcut hücre içeriği (satır 1140-1163):
```python
if cell:
    parts = []
    # Alt proje bilgisi
    if cell.subproject_id:
        ...
    # Personel
    if ass_map.get(cell.id):
        parts.append(", ".join(ass_map[cell.id]))
    # Not
    if cell.note:
        parts.append(f"Not: {cell.note}")
    cell_text = " | ".join(parts) if parts else "-"
```

**Eklenmesi gerekenler:**
1. **Çalışma Saati** - `calculate_hours_from_shift(cell.shift)` fonksiyonu ile hesapla ve ekle
   ```python
   hours = calculate_hours_from_shift(cell.shift)
   if hours > 0:
       parts.append(f"Saat: {hours}")
   ```

2. **Çalışma Detayı** - `cell.job_mail_body` alanını ekle
   ```python
   if cell.job_mail_body:
       parts.append(f"Detay: {cell.job_mail_body}")
   ```

**Not:** Excel tablo formatı korunacak, sütun sayısı değişmeyecek.

### 2. Timesheet Excel Export Düzeltmesi

Dosya: [`routes/planner.py`](routes/planner.py:8782)

Mevcut hücre içeriği (satır 8890-8913):
```python
if tasks:
    cell_parts = []
    for task in tasks:
        parts = []
        # Şehir
        if task["city"]:
            parts.append(task["city"])
        # Proje kodu ve adı
        if task["project_code"]:
            parts.append(f"{task['project_code']} {task['project_name']}")
        # Alt proje
        if task["subproject"]:
            parts.append(task["subproject"])
        # Mesai saati
        overtime = overtime_map.get((p.id, k), 0)
        if overtime and overtime > 0:
            parts.append(f"Mesai: +{overtime} saat")
        # Önemli not
        if task["important_note"]:
            parts.append(f"Not: {task['important_note']}")
        cell_parts.append(" | ".join(parts))
```

**Eklenmesi gerekenler:**
1. **Normal Çalışma Saati** - `calculate_hours_from_shift(task["shift"])` ile hesapla ve ekle
   ```python
   work_hours = calculate_hours_from_shift(task["shift"])
   if work_hours and work_hours > 0:
       parts.append(f"Çalışma: {work_hours} saat")
   ```

**Not:** Excel tablo formatı korunacak, sütun sayısı değişmeyecek.

## Teknik Detaylar

### Çalışma Saati Hesaplama Fonksiyonu

Mevcut fonksiyon: [`routes/planner.py:1381`](routes/planner.py:1381)

```python
def calculate_hours_from_shift(shift_value: str) -> float:
    """
    Çalışma saatlerinden toplam saat hesapla.
    - "08:30 - 18:00" -> 8.5 saat
    - "08:30 - 18:00 YOL" -> 8.5 saat
    - "00:00 - 06:00" -> 8.5 saat
    - "08:30 - 12:30" -> 4 saat
    - "13:30 - 18:00" -> 4.5 saat
    """
```

Bu fonksiyon zaten var, sadece Excel export'larda kullanılmıyor.

### PlanCell Modeli İlgili Alanlar

[`models.py:130`](models.py:130) - PlanCell modeli:
- [`shift`](models.py:136): Vardiya bilgisi ("08:30 - 18:00")
- [`job_mail_body`](models.py:139): İş detay maili metni (çalışma detayı)
- [`note`](models.py:138): Not alanı
- [`important_note`](models.py:143): Önemli not

## Örnek Çıktı

### Plan Excel - Hücre İçeriği Örneği:

**Mevcut:**
```
Alt Proje Adı | Personel1, Personel2 | Not: İş notu
```

**Düzeltilmiş:**
```
Alt Proje Adı | Personel1, Personel2 | Saat: 8.5 | Detay: İş detay metni | Not: İş notu
```

### Timesheet Excel - Hücre İçeriği Örneği:

**Mevcut:**
```
İstanbul | 123 Proje Adı | Alt Proje | Mesai: +2 saat | Not: Önemli not
```

**Düzeltilmiş:**
```
İstanbul | 123 Proje Adı | Alt Proje | Çalışma: 8.5 saat | Mesai: +2 saat | Not: Önemli not
```

## Değişiklik Listesi

### Plan Export Excel (`routes/planner.py`)

| Satır | Değişiklik |
|-------|------------|
| ~1154-1162 | Çalışma saati ve çalışma detayı bilgilerini hücre içine ekle |

### Timesheet Export Excel (`routes/planner.py`)

| Satır | Değişiklik |
|-------|------------|
| ~8890-8913 | Normal çalışma saati bilgisini hücre içine ekle |

## Öncelik

**Yüksek** - Kullanıcılar Excel export'ları kullandığında kritik bilgiler eksik görünüyor.

## Test Edilecek Senaryolar

1. Farklı vardiya formatları ("08:30 - 18:00", "00:00 - 06:00", "08:30 - 12:30")
2. Mesai olan ve olmayan günler
3. Çalışma detayı olan ve olmayan planlar
4. Personel ataması olan ve olmayan hücreler
