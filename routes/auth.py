from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, current_app, jsonify
from extensions import db
from models import User, Firma, Seviye, Person, Team, RolePermission
from utils import login_required, admin_required, planner_or_admin_required, kivanc_required, _csrf_verify, _is_valid_email_address, _rate_limit, _touch_user_activity, get_current_user, ONLINE_WINDOW
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)

def init_users():
    """Initialize default users if they don't exist"""
    users_data = [
        {"username": "kivanc", "password": "kivanc", "is_admin": True, "is_super_admin": True, "role": "admin", "email": "kivancozcan@netmon.com.tr", "full_name": "Kıvanç Özcan"},
        {"username": "burak", "password": "burak", "is_admin": False, "is_super_admin": False, "role": "user", "email": "burakgul@netmon.com.tr", "full_name": "Burak Gül"},
        {"username": "gizem", "password": "gizem", "is_admin": False, "is_super_admin": False, "role": "user", "email": "gizelolmezboyukucar@netmon.com.tr", "full_name": "Gizem Ölmez Boyukucar"},
    ]
    
    # Önce tüm kullanıcıları kontrol et - Kıvanc dışındaki super admin'leri normal yap
    all_users = User.query.all()
    for user in all_users:
        if user.username != 'kivanc' and user.email != 'kivancozcan@netmon.com.tr':
            if hasattr(user, 'is_super_admin') and user.is_super_admin:
                user.is_super_admin = False
                db.session.commit()
    
    for u_data in users_data:
        existing = User.query.filter_by(username=u_data["username"]).first()
        if existing:
            # Update existing user
            if not existing.email:
                existing.email = u_data["email"]
            if not existing.full_name:
                existing.full_name = u_data["full_name"]
            # Ensure is_active is set (default to True for existing users)
            if not hasattr(existing, 'is_active') or existing.is_active is None:
                existing.is_active = True
            # Kıvanc'ı super admin yap, diğerlerini normal yap
            if u_data["username"] == "kivanc" or u_data["email"] == "kivancozcan@netmon.com.tr":
                existing.is_super_admin = True
            else:
                existing.is_super_admin = False
        else:
            # Create new user
            user = User(
                username=u_data["username"],
                is_admin=u_data["is_admin"],
                is_super_admin=u_data.get("is_super_admin", False),
                role=u_data["role"],
                email=u_data["email"],
                full_name=u_data["full_name"],
                is_active=True
            )
            user.set_password(u_data["password"])
            db.session.add(user)
    db.session.commit()

# ===================== ROUTES =====================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip() or "ip"
        if not _rate_limit(f"login:ip:{ip}", limit=20, window_seconds=300):
            flash("Çok fazla giriş denemesi. Biraz sonra tekrar deneyin.", "danger")
            return render_template("login.html")

        if not _csrf_verify(request.form.get("csrf_token", "")):
            flash("Güvenlik doğrulaması başarısız (CSRF). Sayfayı yenileyip tekrar deneyin.", "danger")
            return render_template("login.html")
        login_id = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if login_id:
            if not _rate_limit(f"login:ip_user:{ip}:{login_id.lower()}", limit=8, window_seconds=300):
                flash("Çok fazla giriş denemesi. Biraz sonra tekrar deneyin.", "danger")
                return render_template("login.html")
        
        if not login_id or not password:
            flash("Email/kullanıcı adı ve şifre gereklidir.", "danger")
            return render_template("login.html")
        
        if "@" in login_id:
            user = User.query.filter_by(email=login_id).first()
        else:
            user = User.query.filter_by(username=login_id).first()
        
        if user and user.check_password(password):
            if hasattr(user, "is_active") and not bool(user.is_active):
                flash("Hesabınız pasif. Yönetici ile görüşün.", "danger")
                return render_template("login.html")
            session['user_id'] = user.id
            session['username'] = user.email
            session['is_admin'] = user.is_admin
            session['is_super_admin'] = bool(getattr(user, 'is_super_admin', False))
            session['role'] = user.role
            session['full_name'] = user.full_name
            if request.form.get("remember"):
                session.permanent = True
            try:
                now = datetime.now()
                if _touch_user_activity(user, now=now):
                    session["_last_seen_touch_ts"] = now.timestamp()
            except Exception:
                pass
            flash(f"Hoş geldiniz, {user.full_name or user.email}!", "success")
            if (user.role or "").strip().lower() == "field":
                return redirect(url_for('planner.portal_home'))
            return redirect(url_for('planner.plan_week'))
        else:
            flash("Email veya şifre hatalı.", "danger")
    
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Başarıyla çıkış yapıldı.", "success")
    return redirect(url_for('auth.login'))

@auth_bp.route("/admin/users")
@login_required
@planner_or_admin_required
def admin_users():
    q = (request.args.get("q") or "").strip().lower()
    users_q = User.query
    if q:
        like = f"%{q}%"
        users_q = users_q.filter(or_(User.email.like(like), User.full_name.like(like)))
    users = users_q.order_by(User.email.asc()).all()
    teams = Team.query.order_by(Team.name.asc()).all()
    now = datetime.now()
    online_cutoff = now - ONLINE_WINDOW
    current_user = get_current_user()
    is_kivanc = False
    if current_user:
        if hasattr(current_user, 'is_super_admin') and current_user.is_super_admin:
            is_kivanc = True
        elif current_user.email == 'kivancozcan@netmon.com.tr' or current_user.username == 'kivanc':
            is_kivanc = True
    
    # Fetch role permissions
    permissions_dict = {}
    try:
        perms = RolePermission.query.all()
        for perm in perms:
            if perm.role not in permissions_dict:
                permissions_dict[perm.role] = {}
            permissions_dict[perm.role][perm.permission_key] = perm.can_access
    except Exception:
        permissions_dict = {}
    
    active_tab = request.args.get('tab', '')
    
    return render_template("admin_users.html", users=users, teams=teams, q=q, now=now, 
                           online_cutoff=online_cutoff, is_kivanc=is_kivanc, 
                           permissions_dict=permissions_dict, active_tab=active_tab)

@auth_bp.route("/admin/users/add", methods=["GET", "POST"])
@login_required
@admin_required
def admin_user_add():
    if request.method == "POST":
        if not _csrf_verify(request.form.get("csrf_token", "")):
            flash("Güvenlik doğrulaması başarısız (CSRF).", "danger")
            return redirect(url_for('auth.admin_user_add'))
        username = (request.form.get("username") or "").strip() or None
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        role = request.form.get("role", "user").strip()
        team_id = int(request.form.get("team_id", 0) or 0)
        is_admin = request.form.get("is_admin") == "1"
        is_active = request.form.get("is_active") == "1"
        
        if not email or not password:
            flash("Email ve şifre zorunludur.", "danger")
            return redirect(url_for('auth.admin_user_add'))

        if not username:
            base = (email.split("@", 1)[0] if "@" in email else email).strip().lower()
            base = re.sub(r"[^a-z0-9_\\.\\-]+", "_", base).strip("._-") or "user"
            candidate = base
            suffix = 1
            while User.query.filter_by(username=candidate).first() is not None:
                suffix += 1
                candidate = f"{base}{suffix}"
            username = candidate
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Bu email zaten kullanılıyor.", "danger")
            return redirect(url_for('auth.admin_user_add'))

        if username:
            existing_un = User.query.filter_by(username=username).first()
            if existing_un:
                flash("Bu kullanıcı adı zaten kullanılıyor.", "danger")
                return redirect(url_for('auth.admin_user_add'))
        
        user = User(
            username=username,
            email=email,
            full_name=full_name if full_name else None,
            role=role,
            is_admin=is_admin,
            is_active=is_active,
            team_id=(team_id if team_id else None)
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Kullanıcı eklendi.", "success")
        return redirect(url_for('auth.admin_users'))
    
    teams = Team.query.order_by(Team.name.asc()).all()
    return render_template("admin_user_add.html", teams=teams)

@auth_bp.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def admin_user_edit(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == "POST":
        if not _csrf_verify(request.form.get("csrf_token", "")):
            flash("Güvenlik doğrulaması başarısız (CSRF).", "danger")
            return redirect(url_for('auth.admin_user_edit', user_id=user_id))
        new_username = (request.form.get("username") or "").strip() or None
        new_role = request.form.get("role", "user").strip()
        new_is_admin = request.form.get("is_admin") == "1"
        new_is_active = request.form.get("is_active") == "1"
        new_password = request.form.get("password", "").strip()
        new_email = request.form.get("email", "").strip()
        new_full_name = request.form.get("full_name", "").strip()
        new_team_id = int(request.form.get("team_id", 0) or 0)
        
        if not new_email:
            flash("Email zorunludur.", "danger")
            return redirect(url_for('auth.admin_user_edit', user_id=user_id))
        
        # Check if email already exists for another user
        existing_user = User.query.filter(User.email == new_email, User.id != user_id).first()
        if existing_user:
            flash("Bu email başka bir kullanıcı tarafından kullanılıyor.", "danger")
            return redirect(url_for('auth.admin_user_edit', user_id=user_id))

        if not new_username:
            new_username = user.username

        if new_username:
            existing_un = User.query.filter(User.username == new_username, User.id != user_id).first()
            if existing_un:
                flash("Bu kullanıcı adı başka bir kullanıcı tarafından kullanılıyor.", "danger")
                return redirect(url_for('auth.admin_user_edit', user_id=user_id))
        
        # Admin kendisini admin'den çıkaramaz
        if user.id == session['user_id'] and not new_is_admin:
            flash("Kendi admin yetkinizi kaldıramazsınız.", "danger")
            return redirect(url_for('auth.admin_user_edit', user_id=user_id))
        
        # Kullanıcı kendisini pasif yapamaz
        if user.id == session['user_id'] and not new_is_active:
            flash("Kendinizi pasif yapamazsınız.", "danger")
            return redirect(url_for('auth.admin_user_edit', user_id=user_id))
        
        user.role = new_role
        user.is_admin = new_is_admin
        user.is_active = new_is_active
        user.username = new_username
        user.email = new_email
        user.full_name = new_full_name if new_full_name else None
        user.team_id = (new_team_id if new_team_id else None)
        
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        flash("Kullanıcı güncellendi.", "success")
        return redirect(url_for('auth.admin_users'))
    
    teams = Team.query.order_by(Team.name.asc()).all()
    return render_template("admin_user_edit.html", user=user, teams=teams)

@auth_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@kivanc_required
def admin_user_delete(user_id):
    user = User.query.get_or_404(user_id)
    
    if not _csrf_verify(request.form.get("csrf_token", "")):
        flash("Güvenlik doğrulaması başarısız (CSRF).", "danger")
        return redirect(url_for('auth.admin_users'))
    
    # Kendi kendini silmesini engelle
    current_user = get_current_user()
    if current_user and current_user.id == user_id:
        flash("Kendi hesabınızı silemezsiniz.", "danger")
        return redirect(url_for('auth.admin_users'))
    
    # Kıvanc kullanıcısını silmeyi engelle
    if user.username == 'kivanc' or user.email == 'kivancozcan@netmon.com.tr':
        flash("Bu kullanıcı silinemez.", "danger")
        return redirect(url_for('auth.admin_users'))
    
    try:
        # Soft delete: Kullanıcıyı pasife al ve bilgilerini değiştir
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        user.is_active = False
        user.username = f"del_{timestamp}_{user.username}"
        user.email = f"del_{timestamp}_{user.email}"
        user.password_hash = "deleted" # Şifreyi geçersiz kıl
        
        db.session.commit()
        flash("Kullanıcı silindi (Pasife alındı).", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Kullanıcı silinirken hata oluştu: {str(e)}", "danger")
    
    return redirect(url_for('auth.admin_users'))


@auth_bp.route("/admin/permissions/update", methods=["POST"])
@login_required
@admin_required
def admin_permissions_update():
    """Update role permissions"""
    if not _csrf_verify(request.form.get("csrf_token", "")):
        flash("Güvenlik doğrulaması başarısız (CSRF).", "danger")
        return redirect(url_for('auth.admin_users', tab='permissions'))
    
    current_user = get_current_user()
    
    # Rollere ait izinler
    roles = ['admin', 'planner', 'field', 'user', 'gözlemci']
    permissions = ['reports_analytics', 'admin_users', 'tasks_management', 'planner', 'chat']
    
    try:
        for role in roles:
            for perm_key in permissions:
                # Formdan değeri al
                form_key = f"perm_{role}_{perm_key}"
                can_access = request.form.get(form_key) == "1"
                
                # Mevcut kaydı bul veya yeni oluştur
                existing = RolePermission.query.filter_by(role=role, permission_key=perm_key).first()
                
                if existing:
                    existing.can_access = can_access
                    existing.updated_at = datetime.now()
                    existing.updated_by_user_id = current_user.id if current_user else None
                else:
                    # Eğer varsayılan izinden farklıysa kaydet (admin ve planner için varsayılan True)
                    rp = RolePermission(
                        role=role,
                        permission_key=perm_key,
                        can_access=can_access,
                        updated_by_user_id=current_user.id if current_user else None
                    )
                    db.session.add(rp)
        
        db.session.commit()
        flash("Rol izinleri başarıyla güncellendi.", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"İzinler güncellenirken hata oluştu: {str(e)}", "danger")
    
    return redirect(url_for('auth.admin_users', tab='permissions'))

