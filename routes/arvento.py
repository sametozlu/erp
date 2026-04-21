"""
Arvento API Routes

Bu modül Arvento araç takip entegrasyonu için API endpoint'lerini sağlar.
- /api/arvento/settings - Ayarları görüntüle/kaydet
- /api/arvento/vehicles - Araç konumlarını al
- /api/arvento/test - Bağlantı testi
"""

from flask import Blueprint, jsonify, request, session
from functools import wraps
import logging

log = logging.getLogger('arvento')

arvento_bp = Blueprint('arvento', __name__, url_prefix='/api/arvento')


def _login_required(f):
    """Login gerektirir"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'ok': False, 'error': 'Oturum açmanız gerekiyor'}), 401
        return f(*args, **kwargs)
    return decorated


def _admin_required(f):
    """Admin yetkisi gerektirir"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'ok': False, 'error': 'Oturum açmanız gerekiyor'}), 401
        if not session.get('is_admin') and session.get('role') not in ['planner', 'planlayici', 'planlayıcı']:
            return jsonify({'ok': False, 'error': 'Bu işlem için yetkiniz yok'}), 403
        return f(*args, **kwargs)
    return decorated


@arvento_bp.route('/settings', methods=['GET'])
@_admin_required
def get_settings():
    """
    Arvento ayarlarını getir (maskelenmiş).
    Hassas bilgiler maskelenerek döndürülür.
    """
    from services.arvento_service import get_masked_credentials, has_arvento_credentials
    
    try:
        masked = get_masked_credentials()
        return jsonify({
            'ok': True,
            'has_credentials': has_arvento_credentials(),
            'settings': {
                'username': masked.get('username', ''),
                'pin1': masked.get('pin1', ''),
                'pin2': masked.get('pin2', ''),
                'language': masked.get('language', 'TR')
            }
        })
    except Exception as e:
        log.error(f"Failed to get Arvento settings: {type(e).__name__}")
        return jsonify({'ok': False, 'error': 'Ayarlar yüklenemedi'}), 500


@arvento_bp.route('/settings', methods=['POST'])
@_admin_required
def save_settings():
    """
    Arvento ayarlarını kaydet.
    Tüm hassas bilgiler şifrelenerek saklanır.
    """
    from services.arvento_service import save_arvento_settings
    
    try:
        data = request.get_json() or {}
        
        username = (data.get('username') or '').strip()
        pin1 = (data.get('pin1') or '').strip()
        pin2 = (data.get('pin2') or '').strip()
        language = (data.get('language') or 'TR').strip().upper()
        
        # Validation
        if not username:
            return jsonify({'ok': False, 'error': 'Kullanıcı adı gerekli'}), 400
        if not pin1:
            return jsonify({'ok': False, 'error': 'PIN1 gerekli'}), 400
        if not pin2:
            return jsonify({'ok': False, 'error': 'PIN2 gerekli'}), 400
        
        if language not in ['TR', 'EN', 'RO', 'RU']:
            language = 'TR'
        
        # Kaydet
        save_arvento_settings(username, pin1, pin2, language)
        
        log.info(f"Arvento settings saved by user {session.get('user_id')}")
        
        return jsonify({
            'ok': True,
            'message': 'Ayarlar başarıyla kaydedildi'
        })
    
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    except Exception as e:
        log.error(f"Failed to save Arvento settings: {type(e).__name__}")
        return jsonify({'ok': False, 'error': 'Ayarlar kaydedilemedi'}), 500


@arvento_bp.route('/test', methods=['POST'])
@_admin_required
def test_connection():
    """
    Arvento bağlantısını test et.
    Kaydedilmiş kimlik bilgileriyle servise bağlanmayı dener.
    """
    from services.arvento_service import test_connection as _test_connection, has_arvento_credentials
    
    try:
        if not has_arvento_credentials():
            return jsonify({
                'ok': False,
                'error': 'Önce Arvento kimlik bilgilerini kaydedin'
            }), 400
        
        success, message = _test_connection()
        
        return jsonify({
            'ok': success,
            'message': message
        })
    
    except Exception as e:
        log.error(f"Connection test failed: {type(e).__name__}")
        return jsonify({'ok': False, 'error': 'Bağlantı testi başarısız'}), 500


@arvento_bp.route('/vehicles', methods=['GET'])
@_login_required
def get_vehicles():
    """
    Araç konumlarını al ve ekip bilgileriyle eşleştir.
    Harita sayfasından çağrılır.
    
    Dönen veri:
    - vehicles: [{plate, lat, lng, last_update, speed, ignition, team_id, team_name, matched, address, city}, ...]
    """
    from services.arvento_service import get_vehicles_with_locations, has_arvento_credentials
    
    try:
        if not has_arvento_credentials():
            return jsonify({
                'ok': False,
                'error': 'Arvento ayarları yapılmamış. Lütfen yöneticiye başvurun.',
                'vehicles': []
            }), 400
        
        success, message, vehicles = get_vehicles_with_locations()
        
        if not success:
            return jsonify({
                'ok': False,
                'error': message,
                'vehicles': []
            }), 500
        
        # Hassas bilgileri temizle (sadece gerekli alanları gönder)
        # Ekip üyeleri için utils'den import
        from utils import get_team_members_names
        
        # Bbox parameters
        try:
            min_lat = float(request.args.get('min_lat')) if request.args.get('min_lat') else None
            max_lat = float(request.args.get('max_lat')) if request.args.get('max_lat') else None
            min_lng = float(request.args.get('min_lng')) if request.args.get('min_lng') else None
            max_lng = float(request.args.get('max_lng')) if request.args.get('max_lng') else None
        except ValueError:
            min_lat = max_lat = min_lng = max_lng = None

        safe_vehicles = []
        for v in vehicles:
            # Lat/Lng validation
            try:
                v_lat = float(v.get('lat'))
                v_lng = float(v.get('lng'))
            except (ValueError, TypeError):
                v_lat = v_lng = None

            # Filter by bbox if provided
            if min_lat is not None and max_lat is not None and min_lng is not None and max_lng is not None:
                if v_lat is None or v_lng is None:
                    continue
                if not (min_lat <= v_lat <= max_lat and min_lng <= v_lng <= max_lng):
                    continue

            team_id = v.get('team_id')
            team_members = []
            
            # Ekip ID varsa üyeleri getir
            if team_id:
                try:
                    team_members = get_team_members_names(team_id)
                except Exception:
                    team_members = []
            
            safe_vehicles.append({
                'plate': v.get('plate', ''),
                'device_no': v.get('device_no', ''),
                'lat': v_lat,
                'lng': v_lng,
                'last_update': v.get('last_update'),
                'speed': v.get('speed', 0),
                'ignition': v.get('ignition', False),
                'team_id': team_id,
                'team_name': v.get('team_name'),
                'team_members': team_members,
                'matched': v.get('matched', False),
                'address': v.get('address', ''),
                'city': v.get('city', ''),
                'town': v.get('town', ''),
                'unregistered': v.get('unregistered', False),
            })
        
        return jsonify({
            'ok': True,
            'message': message,
            'vehicles': safe_vehicles,
            'count': len(safe_vehicles),
            'matched_count': sum(1 for v in safe_vehicles if v['matched'])
        })
    
    except Exception as e:
        log.error(f"Failed to get vehicles: {type(e).__name__}: {e}")
        return jsonify({
            'ok': False,
            'error': 'Araç konumları alınamadı',
            'vehicles': []
        }), 500


@arvento_bp.route('/vehicles/refresh', methods=['POST'])
@_login_required
def refresh_vehicles():
    """
    Araç konumlarını yenile.
    POST olarak çağrılır (rate limiting için ayrı endpoint).
    """
    return get_vehicles()


# =================== DEVICE MANAGEMENT ===================

@arvento_bp.route('/devices', methods=['GET'])
@_admin_required
def list_devices():
    """
    Tüm Arvento cihazlarını listele.
    Yönetim ekranı için kullanılır.
    """
    from services.arvento_service import get_all_arvento_devices
    
    try:
        devices = get_all_arvento_devices()
        return jsonify({
            'ok': True,
            'devices': devices,
            'count': len(devices)
        })
    except Exception as e:
        log.error(f"Failed to list devices: {type(e).__name__}")
        return jsonify({'ok': False, 'error': 'Cihazlar listelenemedi'}), 500


@arvento_bp.route('/devices/<int:device_id>', methods=['PUT', 'PATCH'])
@_admin_required
def update_device(device_id: int):
    """
    Arvento cihaz ayarlarını güncelle.
    """
    from services.arvento_service import update_arvento_device
    
    try:
        data = request.get_json() or {}
        
        kwargs = {}
        if 'is_active' in data:
            kwargs['is_active'] = data['is_active']
        if 'plate' in data:
            kwargs['plate'] = data['plate']
        if 'vehicle_id' in data:
            kwargs['vehicle_id'] = data['vehicle_id']
        if 'notes' in data:
            kwargs['notes'] = data['notes']
        
        success, message = update_arvento_device(device_id, **kwargs)
        
        if success:
            return jsonify({'ok': True, 'message': message})
        else:
            return jsonify({'ok': False, 'error': message}), 400
    
    except Exception as e:
        log.error(f"Failed to update device: {type(e).__name__}")
        return jsonify({'ok': False, 'error': 'Cihaz güncellenemedi'}), 500


@arvento_bp.route('/devices', methods=['POST'])
@_admin_required
def add_device():
    """
    Yeni Arvento cihazı ekle.
    """
    from services.arvento_service import add_arvento_device
    
    try:
        data = request.get_json() or {}
        
        device_no = (data.get('device_no') or '').strip()
        plate = (data.get('plate') or '').strip()
        
        if not device_no:
            return jsonify({'ok': False, 'error': 'Cihaz numarası gerekli'}), 400
        if not plate:
            return jsonify({'ok': False, 'error': 'Plaka gerekli'}), 400
        
        kwargs = {
            'is_active': data.get('is_active', True),
            'vehicle_id': data.get('vehicle_id'),
            'notes': data.get('notes', '')
        }
        
        success, message, device_id = add_arvento_device(device_no, plate, **kwargs)
        
        if success:
            return jsonify({'ok': True, 'message': message, 'device_id': device_id})
        else:
            return jsonify({'ok': False, 'error': message}), 400
    
    except Exception as e:
        log.error(f"Failed to add device: {type(e).__name__}")
        return jsonify({'ok': False, 'error': 'Cihaz eklenemedi'}), 500


@arvento_bp.route('/devices/<int:device_id>', methods=['DELETE'])
@_admin_required
def delete_device(device_id: int):
    """
    Arvento cihazını sil.
    """
    from services.arvento_service import delete_arvento_device
    
    try:
        success, message = delete_arvento_device(device_id)
        
        if success:
            return jsonify({'ok': True, 'message': message})
        else:
            return jsonify({'ok': False, 'error': message}), 400
    
    except Exception as e:
        log.error(f"Failed to delete device: {type(e).__name__}")
        return jsonify({'ok': False, 'error': 'Cihaz silinemedi'}), 500


@arvento_bp.route('/devices/sync', methods=['POST'])
@_admin_required
def sync_devices():
    """
    Arvento'dan gelen cihazları veritabanıyla senkronize et.
    Yeni cihazlar pasif olarak eklenir.
    """
    from services.arvento_service import sync_arvento_devices, has_arvento_credentials
    
    try:
        if not has_arvento_credentials():
            return jsonify({
                'ok': False,
                'error': 'Önce Arvento kimlik bilgilerini kaydedin'
            }), 400
        
        added, total = sync_arvento_devices()
        
        return jsonify({
            'ok': True,
            'message': f'{added} yeni cihaz eklendi',
            'added': added,
            'total': total
        })
    
    except Exception as e:
        log.error(f"Failed to sync devices: {type(e).__name__}")
        return jsonify({'ok': False, 'error': 'Senkronizasyon başarısız'}), 500


@arvento_bp.route('/devices/toggle-all', methods=['POST'])
@_admin_required
def toggle_all_devices():
    """
    Tüm cihazları aktif/pasif yap.
    """
    from extensions import db
    from models import ArventoDevice
    
    try:
        data = request.get_json() or {}
        is_active = bool(data.get('is_active', True))
        
        ArventoDevice.query.update({'is_active': is_active})
        db.session.commit()
        
        return jsonify({
            'ok': True,
            'message': f'Tüm cihazlar {"aktif" if is_active else "pasif"} yapıldı'
        })
    
    except Exception as e:
        log.error(f"Failed to toggle devices: {type(e).__name__}")
        return jsonify({'ok': False, 'error': 'İşlem başarısız'}), 500

