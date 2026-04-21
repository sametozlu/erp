# ARVENTO ARAÇ TAKİP WEB SERVİSLERİ - METOT ANALİZİ

## 📋 GENEL BİLGİLER

**Web Servis Adresi:**
- Arvento sunucuları: `http://ws.arvento.com/v1/report.asmx`
- Dış sunucular: `http://[Arvento-Server-IP]/Service/Report.asmx`

**Kullanım Kısıtları:**
- Kullanıcı başına günlük request limiti: **100,000 adet**
- Konum bilgisi verisi alan metotlar için: **Maksimum 10 cihaz ve 1 gün limit**
- Sorgular minimum **30 saniye** periyotlarla yapılabilir
- Maksimum çekilebilecek data sayısı: **100,000 adet**

**Ortak Parametreler:**
- `Username`: Kullanıcı adı
- `PIN1`, `PIN2`: Güvenlik pin kodları
- `StartDate`, `EndDate`: Tarih formatı `MMddyyyyHHmmss` (örn: 07202007235959)
- `Compress`: "1" ise sonuç sıkıştırılmış byte array döner
- `MinuteDif`: GMT zaman dilimine olan dakika farkı (Türkiye için: 120)
- `Locale`: Dil kodu (Türkçe: "0", İngilizce: "1", Romence: "2", Rusça: "3")
- `Node`: Cihaz numarası
- `Group`: Araç grubu adı
- `Language`: Dil seçeneği

---

## 🔍 METOTLARIN DETAYLI ANALİZİ

### 1. **AddUserMapObject**
**Ne İşe Yarar:**
- Verilen koordinatları merkez olarak baz alarak belirlenen yarıçapta **Bölge/Bina Tanımlar**
- Dairesel bölge oluşturur

**Parametreler:**
- `ObjectName`: Bölge/Bina adı
- `ObjectGroup`: Bölge grubu
- `ObjectCode`: Bölge kodu
- `ObjectType`: Bölge tipi
- `LongitudeX`: Boylam (X koordinatı)
- `LatitudeY`: Enlem (Y koordinatı)
- `Radius`: Yarıçap (metre cinsinden)
- `ImageName`: Görsel adı

**Proje İçin Gerekli mi?** ⚠️ **OPSİYONEL**
- Eğer projede belirli bölgelere giriş/çıkış takibi yapılacaksa gerekli
- Şu anki projede bölge tanımlama özelliği yok

---

### 2. **AddUserMapObjects**
**Ne İşe Yarar:**
- **Poligon Bölge/Bina Tanımlar**
- Dairesel değil, çokgen şeklinde bölge oluşturur

**Parametreler:**
- `Points`: Koordinat dizisi
  - Format: `"LongitudeX(0);LatitudeY(0);LongitudeX(1);LatitudeY(1);...;LongitudeX(n);LatitudeY(n)"`

**Proje İçin Gerekli mi?** ⚠️ **OPSİYONEL**
- Daha esnek bölge tanımlama için kullanılabilir
- Şu anki projede bölge tanımlama özelliği yok

---

### 3. **BuildingListReport**
**Ne İşe Yarar:**
- Tanımlı **Bina/bölge listesini** oluşturur
- Sistemde kayıtlı tüm bölgeleri listeler

**Proje İçin Gerekli mi?** ⚠️ **OPSİYONEL**
- Bölge yönetimi yapılacaksa gerekli
- Şu anki projede bölge listesi özelliği yok

---

### 4. **VehicleProgramReport**
**Ne İşe Yarar:**
- Araç **program durumu raporunu** oluşturur
- Cihazın üzerinde bulunan program (konfigürasyon) durumlarını listeler
- Hız alarmı, rölanti alarmı, duraklama alarmı gibi ayarları gösterir

**Parametreler:**
- `chkAllVehicles`: "1" ise tüm araçların program durumlarını listeler
- `ProgrammingVehicles`: Programlanacak araçlar

**Dönen Bilgiler:**
- Hız alarmı limitleri
- Rölanti alarmı süreleri
- Duraklama alarmı süreleri
- Hareket alarmı durumu
- Yön değişimine göre programlama

**Proje İçin Gerekli mi?** ❌ **GEREKSİZ**
- Araç konfigürasyon yönetimi projenin kapsamında değil
- Sadece konum takibi yeterli

---

### 5. **GeneralReport**
**Ne İşe Yarar:**
- **Genel rapor** oluşturur
- Araçların belirli bir tarih aralığındaki konum, hız, mesafe bilgilerini verir
- En temel raporlama metodu

**Parametreler:**
- `StartDate`, `EndDate`: Tarih aralığı
- `Node` veya `Group`: Cihaz veya grup seçimi
- `ShowIgnition`: Kontak durumu gösterilsin mi
- `ShowMaxSpeed`: Maksimum hız gösterilsin mi
- `ShowAlarmCounts`: Alarm sayıları gösterilsin mi

**Dönen Bilgiler:**
- Konum bilgileri (enlem, boylam)
- Tarih/saat
- Hız
- Mesafe
- Kontak durumu
- Alarm bilgileri

**Proje İçin Gerekli mi?** ✅ **GEREKLİ - YÜKSEK ÖNCELİK**
- Araçların geçmiş konum bilgilerini almak için temel metot
- Plan sayfasında araçların nerede olduğunu göstermek için gerekli
- Harita üzerinde rota çizmek için kullanılabilir

---

### 6. **GeneralReport2**
**Ne İşe Yarar:**
- **GeneralReport'un gelişmiş versiyonu**
- Daha detaylı bilgiler içerir
- Mesafe hesaplamaları dahil

**Kısıtlamalar:**
- Maksimum 10 cihaz ve 1 gün limit
- Minimum 30 saniye periyot

**Proje İçin Gerekli mi?** ✅ **GEREKLİ - YÜKSEK ÖNCELİK**
- GeneralReport'dan daha detaylı bilgi verir
- Mesafe hesaplamaları önemli (yakıt maliyeti, rota optimizasyonu)

---

### 7. **GeneralReport2ReturnObject**
**Ne İşe Yarar:**
- **GeneralReport2'nin object döndüren versiyonu**
- XML yerine structured object döner
- Programatik kullanım için daha uygun

**Proje İçin Gerekli mi?** ✅ **GEREKLİ - ORTA ÖNCELİK**
- XML parse etmek yerine direkt object almak daha kolay
- Python/Flask entegrasyonu için uygun

---

### 8. **GeneralReportReturnObject**
**Ne İşe Yarar:**
- **GeneralReport'un object döndüren versiyonu**
- XML yerine structured object döner

**Proje İçin Gerekli mi?** ✅ **GEREKLİ - ORTA ÖNCELİK**
- GeneralReport2ReturnObject tercih edilebilir (daha detaylı)

---

### 9. **GeneralReportWithDistance**
**Ne İşe Yarar:**
- **Mesafe bilgisi içeren genel rapor**
- Araçların kat ettiği toplam mesafeyi hesaplar
- Yakıt maliyeti hesaplamaları için kullanılabilir

**Kısıtlamalar:**
- Maksimum 10 cihaz ve 1 gün limit
- Minimum 30 saniye periyot

**Proje İçin Gerekli mi?** ✅ **GEREKLİ - ORTA ÖNCELİK**
- Mesafe takibi önemli (maliyet hesaplamaları)
- Rota optimizasyonu için gerekli

---

### 10. **GeneralReportWithDistanceReturnObject**
**Ne İşe Yarar:**
- **GeneralReportWithDistance'in object döndüren versiyonu**
- Mesafe bilgisi + structured object

**Proje İçin Gerekli mi?** ✅ **GEREKLİ - ORTA ÖNCELİK**
- Mesafe + kolay parse kombinasyonu

---

### 11. **SpeedReport**
**Ne İşe Yarar:**
- **Hız raporu** oluşturur
- Araçların belirli bir tarih aralığındaki hız bilgilerini verir
- Hız limiti aşımı tespiti için kullanılır

**Kısıtlamalar:**
- Maksimum 10 cihaz ve 1 gün limit
- Minimum 30 saniye periyot

**Proje İçin Gerekli mi?** ⚠️ **OPSİYONEL**
- Hız takibi güvenlik açısından önemli
- Ancak projenin temel ihtiyacı değil
- İleride eklenebilir

---

### 12. **GetVehicleStatus** ⭐ **EN ÖNEMLİ**
**Ne İşe Yarar:**
- **Tüm araçların son konum bilgilerini** öğrenmek için kullanılır
- Anlık konum takibi için ideal
- En sık kullanılan metot

**Özellikler:**
- Tüm araçların son durumunu tek sorguda getirir
- Performanslı
- Anlık takip için optimize edilmiş

**Proje İçin Gerekli mi?** ✅ **GEREKLİ - ÇOK YÜKSEK ÖNCELİK**
- Plan sayfasında araçların anlık konumlarını göstermek için **MUTLAKA GEREKLİ**
- Harita üzerinde araçları işaretlemek için kullanılmalı
- En önemli metot!

---

### 13. **GeneralReport (reportv2.asmx)**
**Ne İşe Yarar:**
- **v2 API'deki genel rapor**
- Daha yeni versiyon, daha iyi performans
- report.asmx'ten farklı endpoint

**Proje İçin Gerekli mi?** ✅ **GEREKLİ - YÜKSEK ÖNCELİK**
- v2 API daha güncel, tercih edilmeli

---

### 14. **GeneralReportExtended (reportv2.asmx)**
**Ne İşe Yarar:**
- **Genişletilmiş genel rapor**
- Daha fazla detay içerir
- v2 API'nin gelişmiş versiyonu

**Proje İçin Gerekli mi?** ✅ **GEREKLİ - YÜKSEK ÖNCELİK**
- Daha detaylı bilgi için kullanılabilir

---

## 📊 PROJE İÇİN ÖNCELİK SIRALAMASI

### 🔴 **ÇOK YÜKSEK ÖNCELİK (Mutlaka Gerekli)**
1. **GetVehicleStatus** - Anlık araç konumları için
2. **GeneralReport2** veya **GeneralReportExtended** - Geçmiş konum verileri için

### 🟡 **YÜKSEK ÖNCELİK (Önerilen)**
3. **GeneralReport2ReturnObject** - Kolay parse için
4. **GeneralReportWithDistance** - Mesafe takibi için

### 🟢 **ORTA ÖNCELİK (İleride Eklenebilir)**
5. **SpeedReport** - Hız takibi için
6. **AddUserMapObject** - Bölge tanımlama için

### ⚪ **DÜŞÜK ÖNCELİK (Gereksiz)**
7. **VehicleProgramReport** - Konfigürasyon yönetimi (proje kapsamında değil)
8. **BuildingListReport** - Bölge listesi (şu an gerekli değil)

---

## 🎯 ÖNERİLER VE ENTEGRASYON PLANI

### 1. **İlk Aşama - Temel Entegrasyon**
```python
# Öncelikli metotlar:
- GetVehicleStatus: Anlık konum takibi
- GeneralReport2: Geçmiş konum verileri
```

**Kullanım Senaryoları:**
- Plan sayfasında araçların anlık konumlarını göster
- Harita sayfasında araçları işaretle
- Haftalık rota çizimi için geçmiş konum verilerini kullan

### 2. **İkinci Aşama - Gelişmiş Özellikler**
```python
# Ek metotlar:
- GeneralReportWithDistance: Mesafe takibi
- SpeedReport: Hız takibi (güvenlik)
```

**Kullanım Senaryoları:**
- Yakıt maliyeti hesaplama
- Rota optimizasyonu
- Güvenlik raporları

### 3. **Üçüncü Aşama - Bölge Yönetimi (Opsiyonel)**
```python
# Opsiyonel metotlar:
- AddUserMapObject: Bölge tanımlama
- BuildingListReport: Bölge listesi
```

**Kullanım Senaryoları:**
- Belirli bölgelere giriş/çıkış takibi
- Geofencing (sanal çit) özellikleri

---

## 🔧 TEKNİK UYGULAMA ÖNERİLERİ

### 1. **Web Servis Client Oluşturma**
```python
# arvento_client.py
import requests
from datetime import datetime
from typing import Optional, Dict, List

class ArventoClient:
    def __init__(self, username: str, pin1: str, pin2: str, server_url: str):
        self.username = username
        self.pin1 = pin1
        self.pin2 = pin2
        self.server_url = server_url.rstrip('/')
    
    def format_date(self, dt: datetime) -> str:
        """MMddyyyyHHmmss formatına çevir"""
        return dt.strftime('%m%d%Y%H%M%S')
    
    def get_vehicle_status(self) -> Dict:
        """GetVehicleStatus - Anlık araç konumları"""
        url = f"{self.server_url}/v1/report.asmx/GetVehicleStatus"
        params = {
            'Username': self.username,
            'PIN1': self.pin1,
            'PIN2': self.pin2,
            'Compress': '0',
            'Language': '0'  # Türkçe
        }
        response = requests.get(url, params=params)
        return response.text  # XML döner
    
    def general_report2(self, start_date: datetime, end_date: datetime, 
                       node: Optional[str] = None, group: Optional[str] = None) -> Dict:
        """GeneralReport2 - Geçmiş konum verileri"""
        url = f"{self.server_url}/v1/report.asmx/GeneralReport2"
        params = {
            'Username': self.username,
            'PIN1': self.pin1,
            'PIN2': self.pin2,
            'StartDate': self.format_date(start_date),
            'EndDate': self.format_date(end_date),
            'Compress': '0',
            'Language': '0',
            'MinuteDif': '120',  # Türkiye GMT+2
            'Locale': 'tr'
        }
        if node:
            params['Node'] = node
        elif group:
            params['Group'] = group
        
        response = requests.get(url, params=params)
        return response.text  # XML döner
```

### 2. **Veritabanı Entegrasyonu**
```python
# Vehicle modeline eklenebilir:
class Vehicle(db.Model):
    # ... mevcut alanlar ...
    arvento_device_id = db.Column(db.String(50), nullable=True)  # Arvento cihaz ID
    last_location_lat = db.Column(db.Float, nullable=True)  # Son konum - enlem
    last_location_lng = db.Column(db.Float, nullable=True)  # Son konum - boylam
    last_location_time = db.Column(db.DateTime, nullable=True)  # Son konum zamanı
    last_speed = db.Column(db.Float, nullable=True)  # Son hız
    is_online = db.Column(db.Boolean, default=False)  # Çevrimiçi mi?
```

### 3. **Background Task (Celery/APScheduler)**
```python
# Periyodik olarak araç konumlarını güncelle
@scheduler.task('interval', minutes=5)
def update_vehicle_locations():
    """Her 5 dakikada bir araç konumlarını güncelle"""
    client = ArventoClient(...)
    status = client.get_vehicle_status()
    # Parse XML ve veritabanını güncelle
```

### 4. **API Endpoint**
```python
@app.get("/api/arvento/vehicle_status")
@login_required
def api_arvento_vehicle_status():
    """Anlık araç konumlarını döndür"""
    client = ArventoClient(...)
    status = client.get_vehicle_status()
    return jsonify({"ok": True, "data": parse_xml(status)})

@app.get("/api/arvento/vehicle_history")
@login_required
def api_arvento_vehicle_history():
    """Araç geçmiş konum verilerini döndür"""
    start = parse_date(request.args.get('start_date'))
    end = parse_date(request.args.get('end_date'))
    vehicle_id = request.args.get('vehicle_id')
    
    client = ArventoClient(...)
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle or not vehicle.arvento_device_id:
        return jsonify({"ok": False, "error": "Araç bulunamadı"}), 404
    
    report = client.general_report2(start, end, node=vehicle.arvento_device_id)
    return jsonify({"ok": True, "data": parse_xml(report)})
```

---

## ⚠️ DİKKAT EDİLMESİ GEREKENLER

1. **Rate Limiting**: 
   - Günlük 100,000 request limiti var
   - Minimum 30 saniye periyot (konum verisi alan metotlar için)
   - Background task'larda dikkatli olunmalı

2. **XML Parsing**:
   - Tüm metotlar XML döndürür (Compress=0 ise)
   - `xml.etree.ElementTree` veya `lxml` kullanılabilir
   - Compress=1 ise önce decompress edilmeli

3. **Tarih Formatı**:
   - `MMddyyyyHHmmss` formatı kullanılmalı
   - Türkiye için `MinuteDif=120` (GMT+2)

4. **Hata Yönetimi**:
   - Web servis hatalarını yakalayın
   - Timeout ayarları yapın
   - Retry mekanizması ekleyin

5. **Güvenlik**:
   - PIN1 ve PIN2 bilgilerini environment variable'da saklayın
   - HTTPS kullanın
   - API key'leri güvenli tutun

---

## 📝 SONUÇ

**Projeniz için en önemli metotlar:**
1. ✅ **GetVehicleStatus** - Anlık konum takibi (MUTLAKA GEREKLİ)
2. ✅ **GeneralReport2** veya **GeneralReportExtended** - Geçmiş veriler (MUTLAKA GEREKLİ)
3. ✅ **GeneralReportWithDistance** - Mesafe takibi (ÖNERİLEN)

**İlk entegrasyon için:**
- GetVehicleStatus ile başlayın
- Plan sayfasında araç konumlarını gösterin
- Harita sayfasında araçları işaretleyin
- Sonra GeneralReport2 ile geçmiş verileri ekleyin

**İleride eklenebilir:**
- SpeedReport (hız takibi)
- Bölge yönetimi (AddUserMapObject)

Bu analiz projenizin ihtiyaçlarına göre hazırlanmıştır. Sorularınız varsa çekinmeyin!

