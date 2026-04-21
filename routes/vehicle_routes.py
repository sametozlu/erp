"""
Araç Yönetimi API Routes
Haftalık araç atama sistemi ve araç geçmişi için API endpoints
"""
from flask import Blueprint, jsonify, request
from datetime import date, timedelta
from extensions import db
from models import Vehicle, VehicleAssignment, Person, Team, Project

vehicle_bp = Blueprint("vehicle", __name__, url_prefix="/api/vehicle")


def get_week_start(d: date = None) -> date:
    """Pazartesi gününü hesapla (hafta başlangıcı)"""
    if d is None:
        d = date.today()
    return d - timedelta(days=d.weekday())


def get_week_end(week_start: date) -> date:
    """Pazar gününü hesapla (hafta sonu)"""
    return week_start + timedelta(days=6)


def get_current_user():
    """Mevcut kullanıcıyı al"""
    from flask_login import current_user
    try:
        if current_user and current_user.is_authenticated:
            return current_user
    except Exception:
        pass
    return None


# ---------- HAFTALIK ATAMA API ----------

@vehicle_bp.get("/assignments")
def get_vehicle_assignments():
    """
    Haftalık araç atamalarını getir
    Query params:
      - week_start: YYYY-MM-DD (opsiyonel, varsayılan: bu hafta)
      - vehicle_id: int (opsiyonel, belirli bir araç için)
      - person_id: int (opsiyonel, belirli bir personel için)
    """
    try:
        week_start_str = request.args.get("week_start", "")
        if week_start_str:
            week_start = date.fromisoformat(week_start_str)
        else:
            week_start = get_week_start()
        
        vehicle_id = request.args.get("vehicle_id", type=int)
        person_id = request.args.get("person_id", type=int)
        
        query = VehicleAssignment.query.filter(
            VehicleAssignment.week_start == week_start,
            VehicleAssignment.is_active == True
        )
        
        if vehicle_id:
            query = query.filter(VehicleAssignment.vehicle_id == vehicle_id)
        
        if person_id:
            query = query.filter(
                db.or_(
                    VehicleAssignment.person_id == person_id,
                    VehicleAssignment.secondary_person_id == person_id
                )
            )
        
        assignments = query.all()
        
        result = []
        for a in assignments:
            result.append({
                "id": a.id,
                "vehicle_id": a.vehicle_id,
                "vehicle_plate": a.vehicle.plate if a.vehicle else None,
                "vehicle_brand": a.vehicle.brand if a.vehicle else None,
                "person_id": a.person_id,
                "person_name": a.person.full_name if a.person else None,
                "secondary_person_id": a.secondary_person_id,
                "secondary_person_name": a.secondary_person.full_name if a.secondary_person else None,
                "team_id": a.team_id,
                "team_name": a.team.name if a.team else None,
                "project_id": a.project_id,
                "week_start": a.week_start.isoformat(),
                "week_end": a.week_end.isoformat(),
                "notes": a.notes,
                "is_active": a.is_active
            })
        
        return jsonify({
            "ok": True,
            "week_start": week_start.isoformat(),
            "week_end": get_week_end(week_start).isoformat(),
            "assignments": result,
            "count": len(result)
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@vehicle_bp.post("/assignments")
def create_vehicle_assignment():
    """
    Yeni araç ataması oluştur
    Body:
      - vehicle_id: int (zorunlu)
      - person_id: int (zorunlu)
      - secondary_person_id: int (opsiyonel)
      - week_start: YYYY-MM-DD (opsiyonel, varsayılan: bu hafta)
      - team_id: int (opsiyonel)
      - project_id: int (opsiyonel)
      - notes: str (opsiyonel)
    """
    try:
        data = request.get_json() or {}
        
        vehicle_id = data.get("vehicle_id")
        person_id = data.get("person_id")
        
        if not vehicle_id or not person_id:
            return jsonify({"ok": False, "error": "vehicle_id ve person_id zorunlu"}), 400
        
        # Araç ve personel kontrolü
        vehicle = Vehicle.query.get(vehicle_id)
        if not vehicle:
            return jsonify({"ok": False, "error": "Araç bulunamadı"}), 404
        
        person = Person.query.get(person_id)
        if not person:
            return jsonify({"ok": False, "error": "Personel bulunamadı"}), 404
        
        # Hafta hesapla
        week_start_str = data.get("week_start", "")
        if week_start_str:
            week_start = date.fromisoformat(week_start_str)
            # Pazartesi'ye yuvarla
            week_start = get_week_start(week_start)
        else:
            week_start = get_week_start()
        
        week_end = get_week_end(week_start)
        
        # Aynı hafta aynı araç için mevcut atama var mı?
        existing = VehicleAssignment.query.filter_by(
            vehicle_id=vehicle_id,
            week_start=week_start,
            is_active=True
        ).first()
        
        if existing:
            return jsonify({
                "ok": False, 
                "error": f"Bu araç {week_start.isoformat()} haftası için zaten {existing.person.full_name} kişisine atanmış"
            }), 409
        
        # İkincil kişi kontrolü
        secondary_person_id = data.get("secondary_person_id")
        if secondary_person_id:
            secondary_person = Person.query.get(secondary_person_id)
            if not secondary_person:
                return jsonify({"ok": False, "error": "İkincil personel bulunamadı"}), 404
        
        # Atama oluştur
        user = get_current_user()
        assignment = VehicleAssignment(
            vehicle_id=vehicle_id,
            person_id=person_id,
            secondary_person_id=secondary_person_id if secondary_person_id else None,
            week_start=week_start,
            week_end=week_end,
            team_id=data.get("team_id"),
            project_id=data.get("project_id"),
            notes=data.get("notes", "").strip() or None,
            created_by_user_id=user.id if user else None,
            is_active=True
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        return jsonify({
            "ok": True,
            "message": f"{vehicle.plate} aracı {person.full_name} kişisine atandı",
            "assignment_id": assignment.id,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@vehicle_bp.put("/assignments/<int:assignment_id>")
def update_vehicle_assignment(assignment_id: int):
    """
    Araç atamasını güncelle (ikinci kişi ekleme vb.)
    """
    try:
        assignment = VehicleAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({"ok": False, "error": "Atama bulunamadı"}), 404
        
        data = request.get_json() or {}
        
        # İkincil kişi güncelleme
        if "secondary_person_id" in data:
            secondary_id = data.get("secondary_person_id")
            if secondary_id:
                secondary_person = Person.query.get(secondary_id)
                if not secondary_person:
                    return jsonify({"ok": False, "error": "İkincil personel bulunamadı"}), 404
                assignment.secondary_person_id = secondary_id
            else:
                assignment.secondary_person_id = None
        
        # Notlar güncelleme
        if "notes" in data:
            assignment.notes = data.get("notes", "").strip() or None
        
        db.session.commit()
        
        return jsonify({
            "ok": True,
            "message": "Atama güncellendi"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@vehicle_bp.delete("/assignments/<int:assignment_id>")
def delete_vehicle_assignment(assignment_id: int):
    """
    Araç atamasını iptal et (soft delete)
    """
    try:
        assignment = VehicleAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({"ok": False, "error": "Atama bulunamadı"}), 404
        
        assignment.is_active = False
        db.session.commit()
        
        return jsonify({
            "ok": True,
            "message": "Atama iptal edildi"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------- GEÇMİŞ VE TOOLTIP API ----------

@vehicle_bp.get("/<int:vehicle_id>/history")
def get_vehicle_history(vehicle_id: int):
    """
    Araç geçmişini getir (önceki hafta tooltip için)
    """
    try:
        vehicle = Vehicle.query.get(vehicle_id)
        if not vehicle:
            return jsonify({"ok": False, "error": "Araç bulunamadı"}), 404
        
        # Önceki hafta
        current_week_start = get_week_start()
        prev_week_start = current_week_start - timedelta(days=7)
        
        prev_assignment = VehicleAssignment.query.filter_by(
            vehicle_id=vehicle_id,
            week_start=prev_week_start
        ).first()
        
        # Mevcut hafta ataması
        current_assignment = VehicleAssignment.query.filter_by(
            vehicle_id=vehicle_id,
            week_start=current_week_start,
            is_active=True
        ).first()
        
        result = {
            "ok": True,
            "vehicle": {
                "id": vehicle.id,
                "plate": vehicle.plate,
                "brand": vehicle.brand,
                "model": vehicle.model
            },
            "current_week": {
                "week_start": current_week_start.isoformat(),
                "week_end": get_week_end(current_week_start).isoformat(),
                "assignment": None
            },
            "previous_week": {
                "week_start": prev_week_start.isoformat(),
                "week_end": get_week_end(prev_week_start).isoformat(),
                "assignment": None
            }
        }
        
        if current_assignment:
            result["current_week"]["assignment"] = {
                "person_name": current_assignment.person.full_name if current_assignment.person else None,
                "secondary_person_name": current_assignment.secondary_person.full_name if current_assignment.secondary_person else None,
                "team_name": current_assignment.team.name if current_assignment.team else None,
                "notes": current_assignment.notes
            }
        
        if prev_assignment:
            result["previous_week"]["assignment"] = {
                "person_name": prev_assignment.person.full_name if prev_assignment.person else None,
                "secondary_person_name": prev_assignment.secondary_person.full_name if prev_assignment.secondary_person else None,
                "team_name": prev_assignment.team.name if prev_assignment.team else None,
                "notes": prev_assignment.notes
            }
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@vehicle_bp.get("/weekly-summary")
def get_weekly_summary():
    """
    Haftalık araç özeti - tüm araçların atama durumu
    """
    try:
        week_start_str = request.args.get("week_start", "")
        if week_start_str:
            week_start = date.fromisoformat(week_start_str)
        else:
            week_start = get_week_start()
        
        # Tüm araçlar
        vehicles = Vehicle.query.filter(
            db.or_(Vehicle.status == "available", Vehicle.status == None)
        ).order_by(Vehicle.plate).all()
        
        # Bu hafta aktif atamalar
        assignments = VehicleAssignment.query.filter_by(
            week_start=week_start,
            is_active=True
        ).all()
        
        assignment_map = {a.vehicle_id: a for a in assignments}
        
        result = []
        for v in vehicles:
            a = assignment_map.get(v.id)
            result.append({
                "vehicle_id": v.id,
                "plate": v.plate,
                "brand": v.brand,
                "model": v.model,
                "is_assigned": a is not None,
                "assigned_to": a.person.full_name if a and a.person else None,
                "secondary_person": a.secondary_person.full_name if a and a.secondary_person else None,
                "assignment_id": a.id if a else None
            })
        
        assigned_count = sum(1 for r in result if r["is_assigned"])
        
        return jsonify({
            "ok": True,
            "week_start": week_start.isoformat(),
            "week_end": get_week_end(week_start).isoformat(),
            "total_vehicles": len(result),
            "assigned_count": assigned_count,
            "available_count": len(result) - assigned_count,
            "vehicles": result
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------- HAFTALIK SIFIRLAMA ----------

def archive_expired_assignments():
    """
    Geçmiş hafta atamalarını arşivle (is_active=False)
    Bu fonksiyon scheduler tarafından çağrılır
    """
    try:
        today = date.today()
        current_week = get_week_start(today)
        
        # Geçmiş hafta atamalarını pasif yap
        expired = VehicleAssignment.query.filter(
            VehicleAssignment.week_end < today,
            VehicleAssignment.is_active == True
        ).all()
        
        for a in expired:
            a.is_active = False
        
        db.session.commit()
        return len(expired)
    except Exception as e:
        db.session.rollback()
        raise e


def register_vehicle_routes(app):
    """Blueprint'i uygulamaya kaydet"""
    app.register_blueprint(vehicle_bp)
