"""
Arvento Araç Takip Servisi

Bu modül Arvento web servisine (https://ws.arvento.com/v1/report.asmx) bağlanarak
araçların anlık konumlarını çeker ve ekip bilgileriyle eşleştirir.

Güvenlik:
- Kimlik bilgileri AES-256 ile şifrelenir
- Şifreleme anahtarı ortam değişkeninde tutulur
- Kimlik bilgileri asla log'lara yazılmaz
"""

import os
import re
import logging
import base64
import json
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
import requests
import xml.etree.ElementTree as ET
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import current_app

log = logging.getLogger('arvento')

# =================== ENCRYPTION ===================

def _get_encryption_key() -> bytes:
    """
    Ortam değişkeninden şifreleme anahtarını al.
    Yoksa, instance klasöründe güvenli bir anahtar oluştur ve sakla.
    """
    key_env = os.getenv('ARVENTO_ENCRYPTION_KEY')
    if key_env:
        # Base64 encoded key from environment
        try:
            return base64.urlsafe_b64decode(key_env.encode())
        except Exception:
            pass
    
    # Fallback: instance klasöründe sakla
    key_file = os.path.join(current_app.instance_path, '.arvento_key')
    if os.path.exists(key_file):
        try:
            with open(key_file, 'rb') as f:
                return f.read()
        except Exception:
            pass
    
    # Yeni anahtar oluştur
    new_key = Fernet.generate_key()
    os.makedirs(current_app.instance_path, exist_ok=True)
    with open(key_file, 'wb') as f:
        f.write(new_key)
    
    # Dosya izinlerini kısıtla (Linux/macOS)
    try:
        os.chmod(key_file, 0o600)
    except Exception:
        pass
    
    return new_key


def _get_fernet() -> Fernet:
    """Fernet şifreleme nesnesi döndür"""
    key = _get_encryption_key()
    return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    """Değeri şifrele ve base64 olarak döndür"""
    if not plaintext:
        return ""
    try:
        fernet = _get_fernet()
        encrypted = fernet.encrypt(plaintext.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    except Exception as e:
        log.error(f"Encryption failed: {type(e).__name__}")
        raise ValueError("Şifreleme başarısız")


def decrypt_value(encrypted_b64: str) -> str:
    """Base64 şifreli değeri çöz"""
    if not encrypted_b64:
        return ""
    try:
        fernet = _get_fernet()
        encrypted = base64.urlsafe_b64decode(encrypted_b64.encode('utf-8'))
        decrypted = fernet.decrypt(encrypted)
        return decrypted.decode('utf-8')
    except Exception as e:
        log.error(f"Decryption failed: {type(e).__name__}")
        raise ValueError("Şifre çözme başarısız")


# =================== ARVENTO SETTINGS ===================

_SETTINGS_FILE = 'arvento_settings.enc.json'


def _get_settings_path() -> str:
    """Ayar dosyasının yolunu döndür"""
    return os.path.join(current_app.instance_path, _SETTINGS_FILE)


def load_arvento_settings() -> Dict[str, Any]:
    """
    Arvento ayarlarını yükle (şifrelenmiş)
    Dönen dict: username, pin1, pin2, language (şifreli değerler)
    """
    path = _get_settings_path()
    if not os.path.exists(path):
        return {}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to load Arvento settings: {type(e).__name__}")
        return {}


def save_arvento_settings(username: str, pin1: str, pin2: str, language: str = "TR"):
    """
    Arvento ayarlarını şifreleyerek kaydet.
    Tüm hassas bilgiler AES-256 ile şifrelenir.
    """
    os.makedirs(current_app.instance_path, exist_ok=True)
    
    data = {
        'username': encrypt_value(username) if username else '',
        'pin1': encrypt_value(pin1) if pin1 else '',
        'pin2': encrypt_value(pin2) if pin2 else '',
        'language': language or 'TR',  # Dil şifrelenmez
        'updated_at': datetime.now().isoformat()
    }
    
    path = _get_settings_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Dosya izinlerini kısıtla
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    
    log.info("Arvento settings saved successfully")


def get_decrypted_credentials() -> Dict[str, str]:
    """
    Şifresi çözülmüş Arvento kimlik bilgilerini döndür.
    Bu fonksiyon sadece backend içinde kullanılmalı!
    Dönen bilgiler asla log'lanmamalı veya frontend'e gönderilmemeli.
    """
    settings = load_arvento_settings()
    if not settings:
        return {}
    
    try:
        return {
            'username': decrypt_value(settings.get('username', '')),
            'pin1': decrypt_value(settings.get('pin1', '')),
            'pin2': decrypt_value(settings.get('pin2', '')),
            'language': settings.get('language', 'TR')
        }
    except Exception as e:
        log.error(f"Failed to decrypt credentials: {type(e).__name__}")
        return {}


def has_arvento_credentials() -> bool:
    """Arvento kimlik bilgileri kayıtlı mı?"""
    settings = load_arvento_settings()
    return bool(settings.get('username') and settings.get('pin1') and settings.get('pin2'))


def get_masked_credentials() -> Dict[str, str]:
    """
    Frontend için maskelenmiş kimlik bilgileri.
    Sadece son 4 karakter görünür.
    """
    try:
        creds = get_decrypted_credentials()
    except Exception:
        return {'username': '', 'pin1': '', 'pin2': '', 'language': 'TR'}
    
    def mask(val: str) -> str:
        if not val:
            return ''
        if len(val) <= 4:
            return '*' * len(val)
        return '*' * (len(val) - 4) + val[-4:]
    
    return {
        'username': mask(creds.get('username', '')),
        'pin1': mask(creds.get('pin1', '')),
        'pin2': mask(creds.get('pin2', '')),
        'language': creds.get('language', 'TR')
    }


# =================== ARVENTO API CLIENT ===================

ARVENTO_BASE_URL = "https://ws.arvento.com/v1/report.asmx"

# Dil kodları
LANGUAGE_CODES = {
    'TR': '0',
    'EN': '1',
    'RO': '2',
    'RU': '3'
}


def _format_arvento_date(dt: datetime) -> str:
    """Arvento tarih formatı: MMddyyyyHHmmss"""
    return dt.strftime('%m%d%Y%H%M%S')


def _parse_vehicle_status_xml(xml_text: str) -> List[Dict[str, Any]]:
    """
    GetVehicleStatus yanıtını parse et.
    Her araç için: plate, lat, lng, last_update, speed, ignition vs.
    """
    vehicles = []
    
    try:
        # XML namespace'leri temizle
        xml_text = re.sub(r'\sxmlns[^"]*"[^"]*"', '', xml_text)
        root = ET.fromstring(xml_text)
        
        # Araç elementlerini bul (farklı yapılar için)
        for vehicle_elem in root.iter():
            # Vehicle veya Data elementlerini ara
            if vehicle_elem.tag in ('Vehicle', 'Data', 'VehicleData', 'Row'):
                vehicle = _extract_vehicle_data(vehicle_elem)
                if vehicle and vehicle.get('plate'):
                    vehicles.append(vehicle)
        
        # Alternatif: Table/Row yapısı
        if not vehicles:
            for row in root.findall('.//Row'):
                vehicle = _extract_vehicle_data_from_row(row)
                if vehicle and vehicle.get('plate'):
                    vehicles.append(vehicle)
        
        # Alternatif: string içinde data parse
        if not vehicles:
            vehicles = _parse_arvento_string_response(xml_text)
    
    except ET.ParseError as e:
        log.error(f"XML parse error: {e}")
        # String response dene
        vehicles = _parse_arvento_string_response(xml_text)
    
    return vehicles


def _extract_vehicle_data(elem: ET.Element) -> Dict[str, Any]:
    """Element'ten araç verisi çıkar"""
    def get_text(tag_name: str) -> str:
        child = elem.find(tag_name)
        if child is not None and child.text:
            return child.text.strip()
        # Attribute olarak kontrol et
        return elem.get(tag_name, '') or elem.get(tag_name.lower(), '') or ''
    
    plate = get_text('Plate') or get_text('plate') or get_text('PLATE') or get_text('Vehicle') or get_text('DeviceName')
    lat_str = get_text('Latitude') or get_text('latitude') or get_text('Lat') or get_text('Y')
    lng_str = get_text('Longitude') or get_text('longitude') or get_text('Lng') or get_text('Long') or get_text('X')
    
    if not plate:
        return {}
    
    try:
        lat = float(lat_str) if lat_str else None
        lng = float(lng_str) if lng_str else None
    except ValueError:
        lat, lng = None, None
    
    # Tarihi parse et
    date_str = get_text('LastUpdate') or get_text('DateTime') or get_text('Date') or get_text('Time')
    last_update = _parse_arvento_datetime(date_str) if date_str else None
    
    # Hız
    speed_str = get_text('Speed') or get_text('speed') or '0'
    try:
        speed = float(speed_str)
    except ValueError:
        speed = 0.0
    
    # Kontak durumu
    ignition_str = get_text('Ignition') or get_text('IgnitionStatus') or get_text('Kontak') or ''
    ignition = ignition_str.lower() in ('1', 'true', 'on', 'açık')
    
    return {
        'plate': plate,
        'lat': lat,
        'lng': lng,
        'last_update': last_update.isoformat() if last_update else None,
        'speed': speed,
        'ignition': ignition,
        'raw_ignition': ignition_str
    }


def _extract_vehicle_data_from_row(row: ET.Element) -> Dict[str, Any]:
    """Row elementinden araç verisi çıkar (tablo formatı için)"""
    cells = row.findall('Cell') or row.findall('TD') or list(row)
    if len(cells) < 3:
        return {}
    
    # Tipik sıralama: Plate, Date, Lat, Lng, Speed...
    try:
        plate = cells[0].text.strip() if cells[0].text else ''
        lat = float(cells[2].text) if len(cells) > 2 and cells[2].text else None
        lng = float(cells[3].text) if len(cells) > 3 and cells[3].text else None
        
        return {
            'plate': plate,
            'lat': lat,
            'lng': lng,
            'last_update': None,
            'speed': 0,
            'ignition': False
        }
    except Exception:
        return {}


def _parse_arvento_string_response(text: str) -> List[Dict[str, Any]]:
    """
    Arvento'nun string formatında döndüğü yanıtları parse et.
    Format: "Plate|Date|Lat|Lng|Speed|..." şeklinde olabilir
    """
    vehicles = []
    
    # Muhtemel delimiters
    for delimiter in ['|', ';', '\t', ',']:
        lines = text.strip().split('\n')
        for line in lines:
            parts = line.split(delimiter)
            if len(parts) >= 4:
                try:
                    # Plaka genellikle ilk sütun
                    plate = parts[0].strip()
                    if not plate or plate.isdigit() or len(plate) < 3:
                        continue
                    
                    # Lat/Lng bulmaya çalış (float değerler)
                    lat, lng = None, None
                    for i, p in enumerate(parts[1:], 1):
                        try:
                            val = float(p.strip())
                            if 35 < val < 45:  # Türkiye enlem aralığı
                                lat = val
                            elif 25 < val < 45:  # Türkiye boylam aralığı
                                lng = val
                        except ValueError:
                            continue
                    
                    if lat and lng:
                        vehicles.append({
                            'plate': plate,
                            'lat': lat,
                            'lng': lng,
                            'last_update': None,
                            'speed': 0,
                            'ignition': False
                        })
                except Exception:
                    continue
        
        if vehicles:
            break
    
    return vehicles


def _parse_arvento_datetime(date_str: str) -> Optional[datetime]:
    """Arvento tarih formatlarını datetime'a çevir"""
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # ISO 8601 with timezone (e.g., 2026-01-24T21:02:30+03:00)
    # Python 3.7+ fromisoformat supports this
    try:
        # Remove timezone for simpler handling (convert to naive datetime)
        if '+' in date_str:
            date_str_no_tz = date_str.split('+')[0]
            return datetime.fromisoformat(date_str_no_tz)
        elif date_str.endswith('Z'):
            return datetime.fromisoformat(date_str.replace('Z', ''))
        else:
            return datetime.fromisoformat(date_str)
    except (ValueError, AttributeError):
        pass
    
    # Legacy formats
    formats = [
        '%m/%d/%Y %H:%M:%S',
        '%d/%m/%Y %H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%d.%m.%Y %H:%M:%S',
        '%m%d%Y%H%M%S'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def get_vehicle_status() -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Arvento'dan tüm araçların anlık konumlarını çek.
    
    Returns:
        (success: bool, message: str, vehicles: List[Dict])
    """
    creds = get_decrypted_credentials()
    if not creds or not creds.get('username'):
        return False, "Arvento kimlik bilgileri ayarlanmamış", []
    
    # Language parametresi (TR, EN, RO, RU)
    language = creds.get('language', 'TR')
    
    # Önce HTTP GET ile dene (daha basit ve güvenilir)
    try:
        success, message, vehicles = _get_vehicle_status_http_get(creds, language)
        if success:
            return success, message, vehicles
        log.warning(f"HTTP GET failed, trying SOAP: {message}")
    except Exception as e:
        log.warning(f"HTTP GET exception: {type(e).__name__}")
    
    # SOAP ile dene
    return _get_vehicle_status_soap(creds, language)


def _get_vehicle_status_http_get(creds: dict, language: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """HTTP GET metoduyla araç durumlarını al"""
    url = "https://ws.arvento.com/v1/report.asmx/GetVehicleStatus"
    
    params = {
        'Username': creds['username'],
        'PIN1': creds['pin1'],
        'PIN2': creds['pin2'],
        'Language': language
    }
    
    try:
        response = requests.get(
            url,
            params=params,
            timeout=30,
            verify=True
        )
        
        log.info(f"Arvento HTTP GET status: {response.status_code}")
        
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}", []
        
        vehicles = _parse_dataset_xml(response.text)
        
        if vehicles:
            log.info(f"Arvento HTTP GET: {len(vehicles)} araç konumu alındı")
            return True, f"{len(vehicles)} araç konumu alındı", vehicles
        else:
            # XML'i logla (debug için)
            log.warning(f"Arvento: Araç verisi bulunamadı. Response length: {len(response.text)}")
            return False, "Araç verisi bulunamadı veya XML parse hatası", []
    
    except requests.exceptions.Timeout:
        return False, "Timeout - Arvento servisi yanıt vermedi", []
    except requests.exceptions.RequestException as e:
        return False, f"Bağlantı hatası: {type(e).__name__}", []


def _get_vehicle_status_soap(creds: dict, language: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """SOAP metoduyla araç durumlarını al"""
    
    # Doğru SOAP Body (Arvento belgelerine göre)
    # Namespace: http://www.arvento.com/ (ws değil www!)
    soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetVehicleStatus xmlns="http://www.arvento.com/">
      <Username>{_escape_xml(creds['username'])}</Username>
      <PIN1>{_escape_xml(creds['pin1'])}</PIN1>
      <PIN2>{_escape_xml(creds['pin2'])}</PIN2>
      <Language>{_escape_xml(language)}</Language>
    </GetVehicleStatus>
  </soap:Body>
</soap:Envelope>"""
    
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '"http://www.arvento.com/GetVehicleStatus"'
    }
    
    try:
        response = requests.post(
            ARVENTO_BASE_URL,
            data=soap_body.encode('utf-8'),
            headers=headers,
            timeout=30,
            verify=True
        )
        
        log.info(f"Arvento SOAP status: {response.status_code}")
        
        if response.status_code != 200:
            return False, f"SOAP HTTP {response.status_code}", []
        
        vehicles = _parse_soap_response(response.text)
        
        if vehicles:
            log.info(f"Arvento SOAP: {len(vehicles)} araç konumu alındı")
            return True, f"{len(vehicles)} araç konumu alındı", vehicles
        else:
            log.warning("Arvento SOAP: Araç verisi bulunamadı")
            return False, "Araç verisi bulunamadı", []
    
    except requests.exceptions.Timeout:
        log.error("Arvento SOAP: İstek zaman aşımına uğradı")
        return False, "Arvento servisi yanıt vermedi (timeout)", []
    
    except requests.exceptions.RequestException as e:
        log.error(f"Arvento SOAP request failed: {type(e).__name__}")
        return False, f"Arvento bağlantı hatası: {type(e).__name__}", []
    
    except Exception as e:
        log.error(f"Arvento SOAP error: {type(e).__name__}: {e}")
        return False, f"Beklenmeyen hata: {type(e).__name__}", []


def _parse_dataset_xml(xml_text: str) -> List[Dict[str, Any]]:
    """
    DataSet formatındaki XML'i parse et.
    HTTP GET ve POST yanıtları bu formatta döner.
    
    Arvento XML yapısı:
    - DataSet > diffgram > tblVehicleStatus > dtVehicleStatus (her araç için)
    - Device_x0020_No: Cihaz numarası / plaka
    - Latitude, Longitude: Koordinatlar
    - Speed: Hız
    - GMT_x0020_Date_x002F_Time: Tarih
    """
    vehicles = []
    
    try:
        root = ET.fromstring(xml_text)
        
        # Iterate over all elements and find dtVehicleStatus
        for elem in root.iter():
            # Get local name (without namespace prefix)
            local_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if local_name == 'dtVehicleStatus':
                vehicle = _extract_arvento_vehicle_ns(elem)
                if vehicle and vehicle.get('plate'):
                    vehicles.append(vehicle)
        
        # Fallback: try Table elements if no dtVehicleStatus found
        if not vehicles:
            for elem in root.iter():
                local_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if local_name in ('Table', 'Table1'):
                    vehicle = _extract_arvento_vehicle_ns(elem)
                    if vehicle and vehicle.get('plate'):
                        vehicles.append(vehicle)
        
        log.info(f"Parsed {len(vehicles)} vehicles from DataSet XML")
        
    except ET.ParseError as e:
        log.error(f"DataSet XML parse error: {e}")
    except Exception as e:
        log.error(f"DataSet parse error: {type(e).__name__}: {e}")
    
    return vehicles


def _extract_arvento_vehicle_ns(elem: ET.Element) -> Dict[str, Any]:
    """
    Arvento dtVehicleStatus elementinden araç verisi çıkar.
    Namespace-aware: child element'lerin namespace prefix'lerini temizler.
    """
    def get_child_text(tag_names: list) -> str:
        for child in elem:
            # Get local name without namespace
            child_local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if child_local in tag_names and child.text:
                return child.text.strip()
        return ''
    
    # Device No (Cihaz numarası veya plaka)
    plate = get_child_text([
        'Device_x0020_No', 'DeviceNo', 'Device No',
        'Plaka', 'PLAKA', 'Plate', 'PLATE',
        'VehicleName', 'Vehicle'
    ])
    
    if not plate:
        return {}
    
    # Koordinatlar
    lat_str = get_child_text(['Latitude', 'LATITUDE', 'Lat', 'Enlem'])
    lng_str = get_child_text(['Longitude', 'LONGITUDE', 'Lng', 'Long', 'Boylam'])
    
    try:
        lat = float(lat_str.replace(',', '.')) if lat_str else None
        lng = float(lng_str.replace(',', '.')) if lng_str else None
    except ValueError:
        lat, lng = None, None
    
    # Tarih
    date_str = get_child_text([
        'GMT_x0020_Date_x002F_Time', 'GMTDateTime', 'GMT Date/Time',
        'DateTime', 'Date', 'Tarih', 'LastUpdate'
    ])
    last_update = _parse_arvento_datetime(date_str) if date_str else None
    
    # Hız
    speed_str = get_child_text(['Speed', 'SPEED', 'Hiz', 'HIZ'])
    try:
        speed = float(speed_str.replace(',', '.')) if speed_str else 0.0
    except ValueError:
        speed = 0.0
    
    # Adres ve şehir bilgisi
    address = get_child_text(['Address', 'Adres'])
    city = get_child_text(['City', 'Sehir', 'İl'])
    town = get_child_text(['Town', 'Ilce', 'İlçe'])
    
    # Yükseklik
    height_str = get_child_text(['Height', 'Yukseklik'])
    try:
        height = float(height_str.replace(',', '.')) if height_str else None
    except ValueError:
        height = None
    
    # Cihaz güç seviyesi
    power_str = get_child_text(['Device_x0020_Power_x0020_Level', 'DevicePowerLevel', 'Power'])
    try:
        power = float(power_str.replace(',', '.')) if power_str else None
    except ValueError:
        power = None
    
    # Kontak durumu - güç seviyesi > 13V veya hız > 0
    ignition = speed > 0 or (power is not None and power > 13.5)
    
    return {
        'plate': plate,
        'lat': lat,
        'lng': lng,
        'last_update': last_update.isoformat() if last_update else None,
        'speed': speed,
        'ignition': ignition,
        'address': address,
        'city': city,
        'town': town,
        'height': height,
        'power_level': power
    }


def _extract_arvento_vehicle(elem: ET.Element) -> Dict[str, Any]:
    """
    Arvento dtVehicleStatus elementinden araç verisi çıkar.
    Özel alan isimleri: Device_x0020_No, GMT_x0020_Date_x002F_Time vb.
    """
    def get_text(tag_names: list) -> str:
        for tag in tag_names:
            child = elem.find(tag)
            if child is not None and child.text:
                return child.text.strip()
        return ''
    
    # Device No (Cihaz numarası veya plaka)
    plate = get_text([
        'Device_x0020_No', 'DeviceNo', 'Device No',
        'Plaka', 'PLAKA', 'Plate', 'PLATE',
        'VehicleName', 'Vehicle'
    ])
    
    if not plate:
        return {}
    
    # Koordinatlar
    lat_str = get_text(['Latitude', 'LATITUDE', 'Lat', 'Enlem'])
    lng_str = get_text(['Longitude', 'LONGITUDE', 'Lng', 'Long', 'Boylam'])
    
    try:
        lat = float(lat_str.replace(',', '.')) if lat_str else None
        lng = float(lng_str.replace(',', '.')) if lng_str else None
    except ValueError:
        lat, lng = None, None
    
    # Tarih (GMT_x0020_Date_x002F_Time formatı)
    date_str = get_text([
        'GMT_x0020_Date_x002F_Time', 'GMTDateTime', 'GMT Date/Time',
        'DateTime', 'Date', 'Tarih', 'LastUpdate'
    ])
    last_update = _parse_arvento_datetime(date_str) if date_str else None
    
    # Hız
    speed_str = get_text(['Speed', 'SPEED', 'Hiz', 'HIZ'])
    try:
        speed = float(speed_str.replace(',', '.')) if speed_str else 0.0
    except ValueError:
        speed = 0.0
    
    # Adres ve şehir bilgisi
    address = get_text(['Address', 'Adres'])
    city = get_text(['City', 'Sehir', 'İl'])
    town = get_text(['Town', 'Ilce', 'İlçe'])
    
    # Yükseklik
    height_str = get_text(['Height', 'Yukseklik'])
    try:
        height = float(height_str.replace(',', '.')) if height_str else None
    except ValueError:
        height = None
    
    # Cihaz güç seviyesi (kontak durumu için gösterge olabilir)
    power_str = get_text(['Device_x0020_Power_x0020_Level', 'DevicePowerLevel', 'Power'])
    try:
        power = float(power_str.replace(',', '.')) if power_str else None
    except ValueError:
        power = None
    
    # Kontak durumu - güç seviyesi > 13V genellikle motor çalışıyor demek
    # veya hız > 0 ise kesinlikle hareket ediyor
    ignition = speed > 0 or (power is not None and power > 13.5)
    
    return {
        'plate': plate,
        'lat': lat,
        'lng': lng,
        'last_update': last_update.isoformat() if last_update else None,
        'speed': speed,
        'ignition': ignition,
        'address': address,
        'city': city,
        'town': town,
        'height': height,
        'power_level': power
    }


def _parse_soap_response(xml_text: str) -> List[Dict[str, Any]]:
    """SOAP yanıtını parse et"""
    vehicles = []
    
    try:
        # Namespace'leri temizle
        clean_xml = re.sub(r'\sxmlns[^"]*"[^"]*"', '', xml_text)
        root = ET.fromstring(clean_xml)
        
        # GetVehicleStatusResult içindeki DataSet'i bul
        for result in root.iter('GetVehicleStatusResult'):
            # İçindeki tüm Table'ları bul
            for table in result.iter('Table'):
                vehicle = _extract_vehicle_from_table(table)
                if vehicle and vehicle.get('plate'):
                    vehicles.append(vehicle)
            
            # Table1, Table2 vs. dene
            if not vehicles:
                for i in range(10):
                    for table in result.iter(f'Table{i}'):
                        vehicle = _extract_vehicle_from_table(table)
                        if vehicle and vehicle.get('plate'):
                            vehicles.append(vehicle)
        
        # diffgram içinde ara
        if not vehicles:
            for diffgram in root.iter('diffgram'):
                for elem in diffgram.iter():
                    if 'Table' in elem.tag or elem.tag in ('Row', 'Vehicle', 'VehicleData'):
                        vehicle = _extract_vehicle_from_table(elem)
                        if vehicle and vehicle.get('plate'):
                            vehicles.append(vehicle)
        
    except ET.ParseError as e:
        log.error(f"SOAP XML parse error: {e}")
    except Exception as e:
        log.error(f"SOAP parse error: {type(e).__name__}: {e}")
    
    return vehicles


def _extract_vehicle_from_table(elem: ET.Element) -> Dict[str, Any]:
    """Table elementinden araç verisi çıkar"""
    def get_text(tag_names: list) -> str:
        for tag in tag_names:
            child = elem.find(tag)
            if child is not None and child.text:
                return child.text.strip()
            # Case insensitive arama
            for c in elem:
                if c.tag.lower() == tag.lower() and c.text:
                    return c.text.strip()
        return ''
    
    # Plaka alanları (farklı isimler olabilir)
    plate = get_text(['Plaka', 'PLAKA', 'Plate', 'PLATE', 'plate', 'DeviceName', 'VehicleName', 'Vehicle', 'Arac', 'ARAC'])
    
    if not plate:
        return {}
    
    # Koordinatlar
    lat_str = get_text(['Enlem', 'ENLEM', 'Latitude', 'LATITUDE', 'Lat', 'LAT', 'Y', 'y'])
    lng_str = get_text(['Boylam', 'BOYLAM', 'Longitude', 'LONGITUDE', 'Lng', 'LNG', 'Long', 'X', 'x'])
    
    try:
        lat = float(lat_str.replace(',', '.')) if lat_str else None
        lng = float(lng_str.replace(',', '.')) if lng_str else None
    except ValueError:
        lat, lng = None, None
    
    # Tarih
    date_str = get_text(['Tarih', 'TARIH', 'DateTime', 'DATE', 'Date', 'Time', 'LastUpdate', 'GuncellemeTarihi', 'SonKonum'])
    last_update = _parse_arvento_datetime(date_str) if date_str else None
    
    # Hız
    speed_str = get_text(['Hiz', 'HIZ', 'Speed', 'SPEED', 'speed', 'Km', 'KM'])
    try:
        speed = float(speed_str.replace(',', '.')) if speed_str else 0.0
    except ValueError:
        speed = 0.0
    
    # Kontak
    ignition_str = get_text(['Kontak', 'KONTAK', 'Ignition', 'IGNITION', 'IgnitionStatus', 'Motor'])
    ignition = ignition_str.lower() in ('1', 'true', 'on', 'açık', 'acik', 'evet', 'yes', 'open')
    
    # Yön (derece)
    direction_str = get_text(['Yon', 'YON', 'Direction', 'DIRECTION', 'Heading', 'Bearing'])
    try:
        direction = float(direction_str.replace(',', '.')) if direction_str else None
    except ValueError:
        direction = None
    
    return {
        'plate': plate,
        'lat': lat,
        'lng': lng,
        'last_update': last_update.isoformat() if last_update else None,
        'speed': speed,
        'ignition': ignition,
        'direction': direction,
        'raw_ignition': ignition_str
    }


def _escape_xml(value: str) -> str:
    """XML için güvenli escape"""
    if not value:
        return ''
    return (value
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))


# =================== PLATE MATCHING ===================

def normalize_plate(plate: str) -> str:
    """
    Plakayı normalize et: boşlukları, tireleri kaldır, büyük harfe çevir.
    Örnek: "34 ABC 123" -> "34ABC123"
    """
    if not plate:
        return ''
    return re.sub(r'[\s\-_]+', '', plate.upper().strip())


def match_vehicles_with_teams(vehicles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Arvento araçlarını sistemdeki ekip bilgileriyle eşleştir.
    
    Eşleştirme kuralı:
    1. Vehicle tablosundaki plate ile Arvento plakasını karşılaştır (normalize edilmiş)
    2. Vehicle'a bağlı Team'i bul
    3. Eşleşme yoksa team_id = None, team_name = "Ekip bilgisi bulunamadı"
    """
    from models import Vehicle, Team
    
    # Sistemdeki tüm araçları çek
    system_vehicles = Vehicle.query.all()
    
    # Normalize plate -> Vehicle mapping
    plate_to_vehicle = {}
    for v in system_vehicles:
        norm_plate = normalize_plate(v.plate)
        plate_to_vehicle[norm_plate] = v
    
    # Araç -> Ekip mapping (Team.vehicle_id üzerinden)
    vehicle_id_to_team = {}
    teams = Team.query.filter(Team.vehicle_id.isnot(None)).all()
    for t in teams:
        vehicle_id_to_team[t.vehicle_id] = t
    
    result = []
    for v in vehicles:
        # Artık 'plate' alanı ArventoDevice'dan gelen gerçek plaka
        arvento_plate = v.get('plate', '')
        norm_arvento_plate = normalize_plate(arvento_plate)
        
        matched_vehicle = plate_to_vehicle.get(norm_arvento_plate)
        
        if matched_vehicle:
            # Eşleşme bulundu
            team = vehicle_id_to_team.get(matched_vehicle.id)
            
            result.append({
                **v,
                'system_vehicle_id': matched_vehicle.id,
                'system_plate': matched_vehicle.plate,
                'team_id': team.id if team else None,
                'team_name': team.name if team else None,
                'matched': True
            })
        else:
            # Eşleşme bulunamadı
            result.append({
                **v,
                'system_vehicle_id': None,
                'system_plate': None,
                'team_id': None,
                'team_name': None,
                'matched': False
            })
    
    matched_count = sum(1 for v in result if v['matched'])
    log.info(f"Plaka eşleştirme: {matched_count}/{len(result)} araç eşleşti")
    
    return result


def get_vehicles_with_locations() -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Ana fonksiyon: Araç konumlarını al, plakalarla eşleştir ve ekip bilgileriyle birleştir.
    Frontend'e gönderilecek hazır veri döner.
    
    1. Arvento'dan cihaz numaraları ile konum verisi çekilir
    2. ArventoDevice tablosundan cihaz->plaka eşleştirmesi yapılır
    3. Pasif cihazlar filtrelenir
    4. Vehicle tablosundan sistem araç eşleştirmesi yapılır
    5. Team tablosundan ekip bilgisi eklenir
    """
    from models import ArventoDevice
    
    success, message, vehicles = get_vehicle_status()
    
    if not success:
        return False, message, []
    
    if not vehicles:
        return False, "Araç konumu bulunamadı", []
    
    # ArventoDevice tablosundan cihaz->plaka eşleştirmesini al
    device_map = {}  # device_no -> ArventoDevice
    for ad in ArventoDevice.query.all():
        device_map[ad.device_no] = ad
    
    # Cihaz numarasını plaka ile değiştir ve pasif olanları filtrele
    filtered_vehicles = []
    for v in vehicles:
        device_no = v.get('plate', '')  # Arvento'dan gelen aslında device_no
        
        arvento_device = device_map.get(device_no)
        
        if arvento_device:
            # Pasif cihazları atla
            if not arvento_device.is_active:
                continue
            
            # Cihaz numarası yerine plakalı sürüm
            v_with_plate = {
                **v,
                'device_no': device_no,
                'plate': arvento_device.plate,  # Gerçek plaka
                'arvento_device_id': arvento_device.id,
            }
            filtered_vehicles.append(v_with_plate)
        else:
            # Eşleştirme bulunamadı - yine de göster ama device_no ile
            v_with_plate = {
                **v,
                'device_no': device_no,
                'plate': device_no,  # Plaka bulunamadı, cihaz numarasını göster
                'arvento_device_id': None,
                'unregistered': True,  # Kayıtsız cihaz işareti
            }
            filtered_vehicles.append(v_with_plate)
    
    log.info(f"Arvento: {len(vehicles)} araç geldi, {len(filtered_vehicles)} aktif")
    
    # Ekip eşleştirmesi yap
    matched_vehicles = match_vehicles_with_teams(filtered_vehicles)
    
    return True, message, matched_vehicles


# =================== ARVENTO DEVICE MANAGEMENT ===================

def get_all_arvento_devices() -> List[Dict[str, Any]]:
    """
    Tüm Arvento cihazlarını listele (yönetim ekranı için).
    """
    from models import ArventoDevice, Vehicle, Team
    
    devices = ArventoDevice.query.order_by(ArventoDevice.plate.asc()).all()
    
    # Vehicle -> Team mapping
    vehicle_to_team = {}
    for t in Team.query.filter(Team.vehicle_id.isnot(None)).all():
        vehicle_to_team[t.vehicle_id] = t
    
    result = []
    for d in devices:
        team = None
        system_vehicle = None
        
        if d.vehicle_id:
            system_vehicle = Vehicle.query.get(d.vehicle_id)
            team = vehicle_to_team.get(d.vehicle_id)
        
        result.append({
            'id': d.id,
            'device_no': d.device_no,
            'plate': d.plate,
            'is_active': d.is_active,
            'vehicle_id': d.vehicle_id,
            'system_plate': system_vehicle.plate if system_vehicle else None,
            'team_id': team.id if team else None,
            'team_name': team.name if team else None,
            'notes': d.notes or '',
            'updated_at': d.updated_at.isoformat() if d.updated_at else None,
        })
    
    return result


def update_arvento_device(device_id: int, **kwargs) -> Tuple[bool, str]:
    """
    Arvento cihaz ayarlarını güncelle.
    """
    from extensions import db
    from models import ArventoDevice
    
    device = ArventoDevice.query.get(device_id)
    if not device:
        return False, "Cihaz bulunamadı"
    
    if 'is_active' in kwargs:
        device.is_active = bool(kwargs['is_active'])
    
    if 'plate' in kwargs and kwargs['plate']:
        device.plate = kwargs['plate'].strip()
    
    if 'vehicle_id' in kwargs:
        device.vehicle_id = int(kwargs['vehicle_id']) if kwargs['vehicle_id'] else None
    
    if 'notes' in kwargs:
        device.notes = (kwargs['notes'] or '').strip()[:200]
    
    try:
        db.session.commit()
        log.info(f"ArventoDevice {device_id} updated")
        return True, "Cihaz güncellendi"
    except Exception as e:
        db.session.rollback()
        log.error(f"ArventoDevice update error: {type(e).__name__}")
        return False, "Güncelleme hatası"


def add_arvento_device(device_no: str, plate: str, **kwargs) -> Tuple[bool, str, int]:
    """
    Yeni Arvento cihazı ekle.
    """
    from extensions import db
    from models import ArventoDevice
    
    device_no = device_no.strip()
    plate = plate.strip()
    
    if not device_no or not plate:
        return False, "Cihaz numarası ve plaka zorunlu", 0
    
    # Mevcut kontrol
    existing = ArventoDevice.query.filter_by(device_no=device_no).first()
    if existing:
        return False, f"Bu cihaz numarası zaten kayıtlı: {existing.plate}", 0
    
    device = ArventoDevice(
        device_no=device_no,
        plate=plate,
        is_active=kwargs.get('is_active', True),
        vehicle_id=kwargs.get('vehicle_id'),
        notes=kwargs.get('notes', '')[:200] if kwargs.get('notes') else None
    )
    
    try:
        db.session.add(device)
        db.session.commit()
        log.info(f"ArventoDevice added: {device_no} -> {plate}")
        return True, "Cihaz eklendi", device.id
    except Exception as e:
        db.session.rollback()
        log.error(f"ArventoDevice add error: {type(e).__name__}")
        return False, "Ekleme hatası", 0


def delete_arvento_device(device_id: int) -> Tuple[bool, str]:
    """
    Arvento cihazını sil.
    """
    from extensions import db
    from models import ArventoDevice
    
    device = ArventoDevice.query.get(device_id)
    if not device:
        return False, "Cihaz bulunamadı"
    
    try:
        db.session.delete(device)
        db.session.commit()
        log.info(f"ArventoDevice deleted: {device_id}")
        return True, "Cihaz silindi"
    except Exception as e:
        db.session.rollback()
        log.error(f"ArventoDevice delete error: {type(e).__name__}")
        return False, "Silme hatası"


def sync_arvento_devices() -> Tuple[int, int]:
    """
    Arvento'dan gelen cihazları veritabanıyla senkronize et.
    Yeni cihazlar otomatik olarak (pasif) eklenir.
    
    Returns:
        (added_count, total_count)
    """
    from extensions import db
    from models import ArventoDevice
    
    success, message, vehicles = get_vehicle_status()
    if not success:
        return 0, 0
    
    # Mevcut cihaz numaralarını al
    existing = {d.device_no for d in ArventoDevice.query.all()}
    
    added = 0
    for v in vehicles:
        device_no = v.get('plate', '')  # Arvento'dan gelen device_no
        if device_no and device_no not in existing:
            # Yeni cihaz - pasif olarak ekle
            device = ArventoDevice(
                device_no=device_no,
                plate=device_no,  # Başlangıçta cihaz numarasını plaka olarak kullan
                is_active=False,  # Kullanıcı manuel aktif etmeli
                notes="Otomatik eklendi - plaka güncellenmeli"
            )
            db.session.add(device)
            existing.add(device_no)
            added += 1
    
    if added > 0:
        db.session.commit()
        log.info(f"Synced {added} new devices from Arvento")
    
    return added, len(existing)


def test_connection() -> Tuple[bool, str]:
    """
    Arvento bağlantısını test et.
    Kimlik bilgilerinin doğru olup olmadığını kontrol eder.
    """
    # Önce kimlik bilgilerini kontrol et
    creds = get_decrypted_credentials()
    if not creds or not creds.get('username'):
        return False, "Kimlik bilgileri bulunamadı veya çözülemedi"
    
    log.info(f"Testing Arvento connection for user: {creds.get('username', '')[:3]}***")
    
    success, message, vehicles = get_vehicle_status()
    
    if success:
        return True, f"Bağlantı başarılı! {len(vehicles)} araç bulundu."
    else:
        return False, message


