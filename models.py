from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

from flask_login import UserMixin

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="user")  # admin/planner/field/user
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_super_admin = db.Column(db.Boolean, nullable=False, default=False)  # Sadece Kıvanc için
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    email = db.Column(db.String(120), nullable=False, unique=True)
    full_name = db.Column(db.String(120), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    last_seen = db.Column(db.DateTime, nullable=True, index=True)
    online_since = db.Column(db.DateTime, nullable=True, index=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Firma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    gender = db.Column(db.String(10), nullable=True)  # Erkek, Kadın
    email = db.Column(db.String(120), nullable=True)
    mail_recipient_name = db.Column(db.String(120), nullable=True)  # Mail atılacak kişi bilgileri

class Seviye(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    tc_no = db.Column(db.String(20))
    role = db.Column(db.String(80))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    firma_id = db.Column(db.Integer, db.ForeignKey("firma.id"), nullable=True)
    seviye_id = db.Column(db.Integer, db.ForeignKey("seviye.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, unique=True, index=True)
    durum = db.Column(db.String(20), nullable=False, default="Aktif")  # Aktif veya Pasif
    karsi_firma_sorumlusu = db.Column(db.String(120))  # Karşı Firma Sorumlusu
    
    firma = db.relationship("Firma")
    seviye = db.relationship("Seviye")
    user = db.relationship("User")


class Project(db.Model):
    __table_args__ = (db.UniqueConstraint("project_code", name="uq_project_project_code"),)
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(80), nullable=False)
    project_code = db.Column(db.String(80), nullable=False, index=True)
    project_name = db.Column(db.String(180), nullable=False)
    responsible = db.Column(db.String(120), nullable=False)
    karsi_firma_sorumlusu = db.Column(db.String(120))  # Karşı Firma Sorumlusu
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    notification_enabled = db.Column(db.Boolean, nullable=False, default=True)  # Yeni: Bildirim ayarı
    
    # Proje Başlangıç Dosyası (Initiation)
    initiation_file_path = db.Column(db.String(400), nullable=True)
    initiation_file_type = db.Column(db.String(30), nullable=True)
    initiation_file_name = db.Column(db.String(255), nullable=True)
    no_initiation_file = db.Column(db.Boolean, nullable=False, default=False)
    no_file_reason = db.Column(db.Text, nullable=True)


class SubProject(db.Model):
    __tablename__ = "sub_project"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False)
    code = db.Column(db.String(80), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    project = db.relationship("Project", backref=db.backref("subprojects", cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint("project_id", "code", name="uq_subproject_project_code"),)


class ProjectComment(db.Model):
    """Proje yorumları"""
    __tablename__ = "project_comment"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True, index=True)
    subproject_id = db.Column(db.Integer, db.ForeignKey("sub_project.id"), nullable=True, index=True)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    
    # Yeni: Dosya ekleri
    file_path = db.Column(db.String(400), nullable=True)
    file_type = db.Column(db.String(30), nullable=True) # image, document
    file_name = db.Column(db.String(255), nullable=True)
    
    project = db.relationship("Project", backref=db.backref("comments", cascade="all, delete-orphan"))
    subproject = db.relationship("SubProject", backref=db.backref("comments", cascade="all, delete-orphan"))
    created_by = db.relationship("User")
    
    __table_args__ = (
        db.Index("ix_project_comment_project_created", "project_id", "created_at"),
        db.Index("ix_project_comment_subproject_created", "subproject_id", "created_at"),
    )


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    signature = db.Column(db.String(400), nullable=False, unique=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.id"), nullable=True, index=True)

    vehicle = db.relationship("Vehicle")


class TeamMailConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False, unique=True, index=True)
    emails_json = db.Column(db.Text, nullable=False, default="[]")  # JSON list
    active = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, index=True)

    team = db.relationship("Team")


class PlanCell(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    subproject_id = db.Column(db.Integer, db.ForeignKey("sub_project.id"), nullable=True, index=True)

    shift = db.Column(db.String(20), nullable=True)          # Gündüz / Gündüz Yol / Gece
    vehicle_info = db.Column(db.String(120), nullable=True)
    note = db.Column(db.Text, nullable=True)
    job_mail_body = db.Column(db.Text, nullable=True)  # İş detay maili metni

    isdp_info = db.Column(db.String(200), nullable=True)
    po_info = db.Column(db.String(200), nullable=True)
    important_note = db.Column(db.Text, nullable=True)
    lld_hhd_path = db.Column(db.String(255), nullable=True)  # PDF/Word
    tutanak_path = db.Column(db.String(255), nullable=True)  # Excel
    lld_hhd_files = db.Column(db.Text, nullable=True)  # JSON list
    tutanak_files = db.Column(db.Text, nullable=True)  # JSON list

    photo_files = db.Column(db.Text, nullable=True)  # JSON list (images)
    qc_result = db.Column(db.Text, nullable=True)  # QC result text

    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True, index=True)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    team_name = db.Column(db.String(120), nullable=True)  # rapor için ekip adı
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    # İptal durumu için yeni alanlar
    status = db.Column(db.String(20), nullable=False, default="active", index=True)  # active/cancelled
    cancelled_at = db.Column(db.DateTime, nullable=True)  # İptal zamanı
    cancelled_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    cancellation_reason = db.Column(db.Text, nullable=True)  # İptal nedeni
    
    # Versiyon numarası - çakışma çözümü için
    version = db.Column(db.Integer, nullable=False, default=1)

    project = db.relationship("Project", backref=db.backref("cells", cascade="all, delete-orphan"))
    subproject = db.relationship("SubProject")
    team = db.relationship("Team", backref=db.backref("cells", cascade="all"))
    assigned_user = db.relationship("User", foreign_keys=[assigned_user_id])

    __table_args__ = (db.UniqueConstraint("project_id", "work_date", name="uq_project_day"),)


class CellAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cell_id = db.Column(db.Integer, db.ForeignKey("plan_cell.id"), nullable=False, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False, index=True)

    cell = db.relationship("PlanCell", backref=db.backref("assignments", cascade="all, delete-orphan"))
    person = db.relationship("Person")


class PersonDayStatus(db.Model):
    """
    Günlük personel durumu:
      available (boşta) / leave (izinli) / production (üretimde)
    """
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False, index=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="available")
    status_type_id = db.Column(db.Integer, db.ForeignKey("personnel_status_type.id"), nullable=True, index=True)
    note = db.Column(db.String(200), nullable=True)

    person = db.relationship("Person")
    status_type = db.relationship("PersonnelStatusType")

    __table_args__ = (db.UniqueConstraint("person_id", "work_date", name="uq_person_day"),)


class PersonnelStatusType(db.Model):
    """
    Personel durum tipleri (İzinli, Raporlu, Ofis, vb.)
    Her durum tipi bir alt proje ile ilişkilendirilebilir.
    """
    __tablename__ = "personnel_status_type"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)  # Örn: "İzinli", "Raporlu", "Ofis"
    code = db.Column(db.String(20), nullable=False, unique=True)  # Sistemde kullanılacak kod: leave, sick, office
    color = db.Column(db.String(20), nullable=True, default="#be123c")  # Görsel renk
    icon = db.Column(db.String(20), nullable=True, default="📋")  # Emoji veya ikon
    subproject_id = db.Column(db.Integer, db.ForeignKey("sub_project.id"), nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    visible_in_summary = db.Column(db.Boolean, nullable=False, default=True)  # Özet panelinde göster
    display_order = db.Column(db.Integer, nullable=False, default=0)  # Sıralama
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    subproject = db.relationship("SubProject")
    
    __table_args__ = (
        db.Index("ix_personnel_status_type_active_order", "is_active", "display_order"),
    )


class MailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    
    # İdentifikasyon
    mail_type = db.Column(db.String(50), nullable=True, index=True)  # weekly/team/job/bulk/test/project/task
    kind = db.Column(db.String(30), nullable=False, default="send", index=True)  # send/test/preview
    
    # Durum
    ok = db.Column(db.Boolean, nullable=False, default=False, index=True)
    error_code = db.Column(db.String(50), nullable=True)  # auth/timeout/recipient/config vb.
    error = db.Column(db.Text, nullable=True)  # Detaylı hata mesajı (geriye uyumluluk için korundu)
    
    # İçerik - Alıcılar
    to_addr = db.Column(db.String(500), nullable=False, default="")  # JSON array destekler
    cc_addr = db.Column(db.String(500), nullable=True)  # CC alıcıları
    bcc_addr = db.Column(db.String(500), nullable=True)  # BCC alıcıları
    subject = db.Column(db.String(255), nullable=False, default="")
    body_preview = db.Column(db.Text, nullable=True)  # İlk 1000 karakter
    body_html = db.Column(db.Text, nullable=True)  # Tam HTML içerik (görsel önizleme için)
    
    # İlişkili Veriler
    week_start = db.Column(db.Date, nullable=True, index=True)
    team_id = db.Column(db.Integer, nullable=True, index=True)
    team_name = db.Column(db.String(120), nullable=True)
    project_id = db.Column(db.Integer, nullable=True, index=True)
    job_id = db.Column(db.Integer, nullable=True, index=True)
    task_id = db.Column(db.Integer, nullable=True, index=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)  # Gönderen kullanıcı
    
    # Meta
    meta_json = db.Column(db.Text, nullable=True)  # Ek JSON verileri
    attachments_count = db.Column(db.Integer, nullable=False, default=0)
    body_size_bytes = db.Column(db.Integer, nullable=False, default=0)
    
    # Zaman Damgaları
    sent_at = db.Column(db.DateTime, nullable=True, index=True)  # Mail gerçekten gönderildi mi?
    
    __table_args__ = (
        db.Index("ix_mail_log_type_created", "mail_type", "created_at"),
        db.Index("ix_mail_log_ok_created", "ok", "created_at"),
    )

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    event = db.Column(db.String(30), nullable=False, index=True)  # new_assignment/feedback/mail_fail/sla
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=True)
    link_url = db.Column(db.String(255), nullable=True)
    job_id = db.Column(db.Integer, nullable=True, index=True)
    mail_log_id = db.Column(db.Integer, nullable=True, index=True)
    meta_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    read_at = db.Column(db.DateTime, nullable=True, index=True)

    user = db.relationship("User")

    __table_args__ = (
        db.Index("ix_notification_user_read_created", "user_id", "read_at", "created_at"),
    )


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    title = db.Column(db.String(200), nullable=False, default="Duyuru")
    body = db.Column(db.Text, nullable=False, default="")
    is_popup = db.Column(db.Boolean, nullable=False, default=False, index=True)

    audience_type = db.Column(db.String(20), nullable=False, default="all", index=True)  # all|team|user
    audience_id = db.Column(db.Integer, nullable=True, index=True)  # team_id or user_id (depending on audience_type)

    created_by = db.relationship("User")

    __table_args__ = (
        db.Index("ix_announcement_audience_created", "audience_type", "audience_id", "created_at"),
    )


class AnnouncementRead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey("announcement.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    announcement = db.relationship("Announcement")
    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("announcement_id", "user_id", name="uq_announcement_read"),
        db.Index("ix_announcement_read_user_announcement", "user_id", "announcement_id"),
    )



class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    team = db.relationship("Team")
    user = db.relationship("User")

    __table_args__ = (
        db.Index("ix_chat_message_team_created", "team_id", "created_at"),
    )


class ChatUserMessage(db.Model):
    __tablename__ = "chat_user_message"

    id = db.Column(db.Integer, primary_key=True)
    pair_key = db.Column(db.String(60), nullable=False, index=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    to_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    from_user = db.relationship("User", foreign_keys=[from_user_id])
    to_user = db.relationship("User", foreign_keys=[to_user_id])

    __table_args__ = (
        db.Index("ix_chat_user_message_pair_created", "pair_key", "created_at"),
    )


class MailTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    subject_template = db.Column(db.Text, nullable=False)
    heading_template = db.Column(db.Text, nullable=True)  # New field
    intro_template = db.Column(db.Text, nullable=True)    # New field
    body_template = db.Column(db.Text, nullable=False)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cell_id = db.Column(db.Integer, db.ForeignKey("plan_cell.id"), nullable=False, unique=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    subproject_id = db.Column(db.Integer, db.ForeignKey("sub_project.id"), nullable=True, index=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True, index=True)
    team_name = db.Column(db.String(120), nullable=True, index=True)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    is_published = db.Column(db.Boolean, nullable=False, default=False, index=True)
    published_at = db.Column(db.DateTime, nullable=True, index=True)
    published_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    shift = db.Column(db.String(40), nullable=True)
    vehicle_info = db.Column(db.String(120), nullable=True)
    note = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)  # pending/completed/problem
    kanban_status = db.Column(db.String(30), nullable=False, default="PLANNED", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    closed_at = db.Column(db.DateTime, nullable=True, index=True)

    cell = db.relationship("PlanCell")
    project = db.relationship("Project")
    subproject = db.relationship("SubProject")
    team = db.relationship("Team")
    assigned_user = db.relationship("User", foreign_keys=[assigned_user_id])
    published_by_user = db.relationship("User", foreign_keys=[published_by_user_id])


class JobAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False, index=True)

    job = db.relationship("Job", backref=db.backref("assignments", cascade="all, delete-orphan"))
    person = db.relationship("Person")

    __table_args__ = (db.UniqueConstraint("job_id", "person_id", name="uq_job_person"),)


class JobFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="completed")  # completed/problem
    note = db.Column(db.Text, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # Sprint 2 fields (field feedback submission)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    submitted_at = db.Column(db.DateTime, nullable=True, index=True)
    outcome = db.Column(db.String(20), nullable=True, index=True)  # completed/not_completed/issue
    isdp_status = db.Column(db.String(20), nullable=True)  # yes/no/error
    extra_work_text = db.Column(db.Text, nullable=True)
    notes_text = db.Column(db.Text, nullable=True)

    reviewed_at = db.Column(db.DateTime, nullable=True, index=True)
    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    review_status = db.Column(db.String(20), nullable=False, default="pending", index=True)  # pending/approved/rejected
    review_note = db.Column(db.Text, nullable=True)

    job = db.relationship("Job", backref=db.backref("feedback_rows", cascade="all, delete-orphan"))
    user = db.relationship("User", foreign_keys=[user_id])
    created_by_user = db.relationship("User", foreign_keys=[created_by_user_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_user_id])


class JobFeedbackMedia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feedback_id = db.Column(db.Integer, db.ForeignKey("job_feedback.id"), nullable=False, index=True)
    file_path = db.Column(db.String(400), nullable=False, index=True)
    file_type = db.Column(db.String(30), nullable=False, default="file")  # image/video/file
    original_name = db.Column(db.String(255), nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    feedback = db.relationship("JobFeedback", backref=db.backref("media", cascade="all, delete-orphan"))


class JobReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    answers_json = db.Column(db.Text, nullable=False, default="{}")  # JSON
    status_outcome = db.Column(db.String(20), nullable=False, default="not_completed", index=True)  # completed/not_completed/issue
    issue_type = db.Column(db.String(80), nullable=True)
    issue_note = db.Column(db.Text, nullable=True)
    extra_work_note = db.Column(db.Text, nullable=True)

    reviewed_at = db.Column(db.DateTime, nullable=True, index=True)
    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    job = db.relationship("Job")
    user = db.relationship("User", foreign_keys=[user_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_user_id])

class JobStatusHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False, index=True)
    from_status = db.Column(db.String(30), nullable=True)
    to_status = db.Column(db.String(30), nullable=False)
    note = db.Column(db.Text, nullable=True)
    changed_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    job = db.relationship("Job", backref=db.backref("status_history", cascade="all, delete-orphan"))
    changed_by = db.relationship("User")


class Vehicle(db.Model):
    """
    Araç/Tool bilgileri
    """
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20), nullable=False, unique=True)  # Plaka
    brand = db.Column(db.String(80), nullable=False)  # Marka
    model = db.Column(db.String(80), nullable=True)  # Model
    year = db.Column(db.Integer, nullable=True)  # Yıl
    vehicle_type = db.Column(db.String(50), nullable=True)  # Araç tipi (Araba, Kamyon, vb.)
    status = db.Column(db.String(50), nullable=True, default="available")  # Durum (available, maintenance, out_of_service)
    notes = db.Column(db.Text, nullable=True)  # Notlar
    capacity = db.Column(db.Integer, nullable=True)  # Kaç kişilik
    vodafone_approval = db.Column(db.Boolean, nullable=False, default=False)  # Vodafone onayı
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)


class VehicleAssignment(db.Model):
    """
    Haftalık Araç Atama Sistemi
    - Araçlar haftalık olarak personele atanır
    - Her Pazartesi yeni hafta başlar
    - Bir araç genellikle 1 kişiye atanır, isteğe bağlı 2. kişi de atanabilir
    - Hafta bitiminde atamalar arşivlenir (is_active=False)
    """
    __tablename__ = "vehicle_assignment"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.id"), nullable=False, index=True)
    
    # Birincil atama (zorunlu)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False, index=True)
    
    # İkincil atama (opsiyonel - talep edilirse iki kişiye atama)
    secondary_person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=True, index=True)
    
    # Hafta bilgisi (Pazartesi'den başlar)
    week_start = db.Column(db.Date, nullable=False, index=True)  # Pazartesi tarihi
    week_end = db.Column(db.Date, nullable=False)  # Pazar tarihi
    
    # Ekip ve proje bilgisi (opsiyonel)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True, index=True)
    
    # Meta bilgiler
    notes = db.Column(db.Text, nullable=True)  # Atama notları
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    
    # Durum
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)  # Aktif atama mı?
    
    # İlişkiler
    vehicle = db.relationship("Vehicle", backref=db.backref("assignments", cascade="all, delete-orphan"))
    person = db.relationship("Person", foreign_keys=[person_id])
    secondary_person = db.relationship("Person", foreign_keys=[secondary_person_id])
    team = db.relationship("Team")
    project = db.relationship("Project")
    created_by = db.relationship("User")
    
    # Unique constraint: Aynı hafta aynı araç sadece bir kez atanabilir
    __table_args__ = (
        db.UniqueConstraint("vehicle_id", "week_start", name="uq_vehicle_week"),
    )

class ArventoDevice(db.Model):
    """
    Arvento cihaz - plaka eşleştirmesi.
    Arvento'dan gelen cihaz numaraları burada plaka ile eşleştirilir.
    """
    __tablename__ = "arvento_device"
    id = db.Column(db.Integer, primary_key=True)
    device_no = db.Column(db.String(50), nullable=False, unique=True, index=True)  # Arvento cihaz numarası
    plate = db.Column(db.String(30), nullable=False, index=True)  # Plaka (ör: 06 BJ 8300)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)  # Haritada gösterilsin mi?
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.id"), nullable=True, index=True)  # Sistem araç eşleştirmesi
    notes = db.Column(db.String(200), nullable=True)  # Notlar
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    vehicle = db.relationship("Vehicle")


# ---------- REALTIME FEATURES ----------

class CellLock(db.Model):
    """
    Hücre bazlı kilitleme - Optimistic Locking için
    Bir kullanıcı hücreyi düzenlerken diğer kullanıcıların o hücreyi değiştirmesini engeller
    """
    __tablename__ = "cell_lock"
    id = db.Column(db.Integer, primary_key=True)
    cell_id = db.Column(db.Integer, db.ForeignKey("plan_cell.id"), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    locked_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)  # Kilit sona erme zamanı (60 saniye)
    
    cell = db.relationship("PlanCell", backref=db.backref("lock", uselist=False, cascade="all, delete-orphan"))
    user = db.relationship("User")


class CellCancellation(db.Model):
    """
    İş iptal kaydı - Kim, ne zaman iptal etti, neden
    """
    __tablename__ = "cell_cancellation"
    id = db.Column(db.Integer, primary_key=True)
    cell_id = db.Column(db.Integer, db.ForeignKey("plan_cell.id"), nullable=False, index=True)
    cancelled_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    cancelled_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    reason = db.Column(db.Text, nullable=True)  # İptal nedeni
    previous_status = db.Column(db.String(30), nullable=True)  # Önceki durum
    
    # Dosya ekleri
    file_path = db.Column(db.String(400), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    file_type = db.Column(db.String(30), nullable=True)
    
    cell = db.relationship("PlanCell", backref=db.backref("cancellations", cascade="all, delete-orphan"))
    cancelled_by = db.relationship("User")


class TeamOvertime(db.Model):
    """
    Ekip mesai kaydı - Hangi ekibe, hangi tarihte, ne kadar mesai
    """
    __tablename__ = "team_overtime"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True, index=True)
    cell_id = db.Column(db.Integer, db.ForeignKey("plan_cell.id"), nullable=True, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=True, index=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    duration_hours = db.Column(db.Float, nullable=False, default=0)  # Mesai süresi (saat)
    description = db.Column(db.Text, nullable=True)  # Açıklama
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    team = db.relationship("Team")
    cell = db.relationship("PlanCell", backref=db.backref("overtime_records", cascade="all, delete-orphan"))
    person = db.relationship("Person")
    created_by = db.relationship("User")
    
    __table_args__ = (
        db.Index("ix_team_overtime_team_date", "team_id", "work_date"),
        db.Index("ix_team_overtime_cell_date", "cell_id", "work_date"),
    )


class VoiceMessage(db.Model):
    """
    Ses mesajı - Push-to-Talk (PTT) için
    """
    __tablename__ = "voice_message"
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    to_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)  # Null = broadcast
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True, index=True)  # Ekibe gönderim
    audio_path = db.Column(db.String(400), nullable=False)  # Ses dosyası yolu
    duration_seconds = db.Column(db.Float, nullable=True)  # Süre (saniye)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    is_heard = db.Column(db.Boolean, nullable=False, default=False)  # Dinlendi mi?
    heard_at = db.Column(db.DateTime, nullable=True)
    
    from_user = db.relationship("User", foreign_keys=[from_user_id])
    to_user = db.relationship("User", foreign_keys=[to_user_id])
    team = db.relationship("Team")
    
    __table_args__ = (
        db.Index("ix_voice_message_to_user_created", "to_user_id", "created_at"),
        db.Index("ix_voice_message_team_created", "team_id", "created_at"),
    )


class UserSettings(db.Model):
    """
    Kullanıcı ayarları - Tam ekran kısayolu, tema, vb.
    """
    __tablename__ = "user_settings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True)
    # Tam ekran kısayol tuşu (örn: "F11", "Alt+S", "Ctrl+Shift+F")
    fullscreen_shortcut = db.Column(db.String(30), nullable=True, default="F11")
    # Tema tercihi
    theme = db.Column(db.String(20), nullable=True, default="light")  # light/dark/auto
    # Bildirim ayarları
    notifications_enabled = db.Column(db.Boolean, nullable=False, default=True)
    sound_enabled = db.Column(db.Boolean, nullable=False, default=True)
    # Push-to-Talk ayarları
    ptt_key = db.Column(db.String(30), nullable=True, default="Space")  # Basılı tutulacak tuş
    auto_play_voice = db.Column(db.Boolean, nullable=False, default=True)  # Ses mesajlarını otomatik çal
    # Diğer ayarlar JSON olarak
    extra_settings_json = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    user = db.relationship("User", backref=db.backref("settings", uselist=False, cascade="all, delete-orphan"))


class CellVersion(db.Model):
    """
    Hücre versiyonlama - Çakışma çözümü için
    Her değişiklikte version numarası artar
    """
    __tablename__ = "cell_version"
    id = db.Column(db.Integer, primary_key=True)
    cell_id = db.Column(db.Integer, db.ForeignKey("plan_cell.id"), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    data_json = db.Column(db.Text, nullable=False)  # JSON olarak hücre verisi
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    changed_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    change_type = db.Column(db.String(20), nullable=False, default="update")  # create/update/delete
    
    cell = db.relationship("PlanCell", backref=db.backref("versions", cascade="all, delete-orphan"))
    changed_by = db.relationship("User")
    
    __table_args__ = (
        db.Index("ix_cell_version_cell_version", "cell_id", "version"),
    )


class TableSnapshot(db.Model):
    """
    Tablo snapshot'ı - Mail gönderimi için
    """
    __tablename__ = "table_snapshot"
    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.Date, nullable=False, index=True)
    html_content = db.Column(db.Text, nullable=False)  # HTML formatında tablo
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    sent_at = db.Column(db.DateTime, nullable=True)  # Mail gönderim zamanı
    recipients_json = db.Column(db.Text, nullable=True)  # Alıcı listesi JSON
    
    created_by = db.relationship("User")


# ========== GÖREV TAKİP SİSTEMİ ==========

class Task(db.Model):
    """
    Ana görev tablosu - Görev Takip Sistemi
    """
    __tablename__ = "task"
    id = db.Column(db.Integer, primary_key=True)
    
    # Görev No: NG0001 formatında otomatik üretilir
    task_no = db.Column(db.String(20), nullable=False, unique=True, index=True)
    
    # Görev Tipi: Normal, Uygunsuzluk, Düzeltici Faaliyet, Önleyici Faaliyet, Diğer
    task_type = db.Column(db.String(50), nullable=False, default="Normal", index=True)
    
    # İlgili Kişi (Kullanıcı)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    
    # Önem Kodu: 1-5
    priority = db.Column(db.Integer, nullable=False, default=3, index=True)
    
    # Hedef Tarih
    target_date = db.Column(db.Date, nullable=True, index=True)
    
    # Şimdiki Durum
    status = db.Column(db.String(50), nullable=False, default="İlk Giriş", index=True)
    
    # Proje Kodları (virgülle ayrılmış)
    project_codes = db.Column(db.Text, nullable=True)
    
    # Konu
    subject = db.Column(db.String(300), nullable=False)
    
    # Açıklama
    description = db.Column(db.Text, nullable=True)
    
    # Oluşturan
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, index=True)
    
    # Mail Hatırlatma Ayarları
    reminder_days_before = db.Column(db.Integer, nullable=False, default=0) # Kaç gün önce
    reminder_count = db.Column(db.Integer, nullable=False, default=0) # Toplam hatırlatma sayısı
    last_reminder_at = db.Column(db.DateTime, nullable=True) # Son hatırlatma ne zaman yapıldı
    reminder_sent_count = db.Column(db.Integer, nullable=False, default=0) # Şimdiye kadar kaç kez atıldı
    # Süre bitim maili kontrolü
    last_deadline_mail_at = db.Column(db.DateTime, nullable=True, index=True)
    
    # Bildirim Ayarları
    notification_enabled = db.Column(db.Boolean, nullable=False, default=True)
    
    # Kapatma bilgisi
    closed_at = db.Column(db.DateTime, nullable=True, index=True)
    closed_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    
    # İlişkiler
    assigned_user = db.relationship("User", foreign_keys=[assigned_user_id], backref=db.backref("assigned_tasks", lazy="dynamic"))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    closed_by = db.relationship("User", foreign_keys=[closed_by_user_id])
    
    __table_args__ = (
        db.Index("ix_task_status_priority", "status", "priority"),
        db.Index("ix_task_assigned_status", "assigned_user_id", "status"),
    )
    
    @property
    def is_open(self):
        """Görev açık mı?"""
        closed_statuses = ["İş Halledildi", "Reddedildi", "Hatalı Giriş", "İptal"]
        return self.status not in closed_statuses
    
    @classmethod
    def generate_task_no(cls):
        """Yeni görev numarası üret: NG0001, NG0002, ..."""
        last_task = cls.query.order_by(cls.id.desc()).first()
        if last_task and last_task.task_no:
            try:
                num = int(last_task.task_no.replace("NG", ""))
                return f"NG{num + 1:04d}"
            except:
                pass
        return "NG0001"


class TaskLog(db.Model):
    """
    Görev log tablosu - Kim, ne zaman, ne yaptı
    """
    __tablename__ = "task_log"
    id = db.Column(db.Integer, primary_key=True)
    
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    
    # Log tipi: status_change, field_change, comment, attachment_add, attachment_delete, create
    action_type = db.Column(db.String(30), nullable=False, index=True)
    
    # Değişiklik detayları
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    field_name = db.Column(db.String(50), nullable=True)  # Hangi alan değişti
    
    # Yorum
    comment = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    
    # İlişkiler
    task = db.relationship("Task", backref=db.backref("logs", cascade="all, delete-orphan", order_by="TaskLog.created_at.desc()"))
    user = db.relationship("User")
    
    __table_args__ = (
        db.Index("ix_task_log_task_created", "task_id", "created_at"),
    )


class TaskAttachment(db.Model):
    """
    Görev ekleri - Resim, dosya
    """
    __tablename__ = "task_attachment"
    id = db.Column(db.Integer, primary_key=True)
    
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False, index=True)
    
    file_path = db.Column(db.String(400), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(30), nullable=False, default="file")  # image, document, other
    file_size = db.Column(db.Integer, nullable=True)  # bytes
    
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    
    # İlişkiler
    task = db.relationship("Task", backref=db.backref("attachments", cascade="all, delete-orphan", order_by="TaskAttachment.uploaded_at.desc()"))
    uploaded_by = db.relationship("User")


# ========== ROLE-BASED ACCESS CONTROL ==========

class MailQueue(db.Model):
    """
    Asenkron mail gönderimi için kuyruk tablosu
    Durumlar: pending -> processing -> sent | failed
    """
    __tablename__ = "mail_queue"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Mail bilgileri
    mail_type = db.Column(db.String(50), nullable=False)  # task_created, project_added vb.
    recipients = db.Column(db.Text, nullable=False)  # JSON listesi veya virgülle ayrılmış string
    subject = db.Column(db.String(255), nullable=False)
    html_content = db.Column(db.Text, nullable=False)
    
    # Opsiyonel alanlar
    cc = db.Column(db.Text, nullable=True)
    bcc = db.Column(db.Text, nullable=True)
    meta_json = db.Column(db.Text, nullable=True)  # JSON string olarak saklanan ekstra veriler
    
    # İlişkili ID'ler (Loglama ve takip için - Foreign Key tanımlamıyoruz, generic kalabilir)
    user_id = db.Column(db.Integer, nullable=True)
    project_id = db.Column(db.Integer, nullable=True)
    job_id = db.Column(db.Integer, nullable=True)
    task_id = db.Column(db.Integer, nullable=True)
    
    # Durum bilgileri
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)  # pending, processing, sent, failed
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    
    # Hata yönetimi
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    
    # Öncelik
    priority = db.Column(db.Integer, nullable=False, default=0)


class RolePermission(db.Model):
    """
    Rol bazlı erişim kontrolü - Hangi rolün hangi sayfaya erişebileceğini belirler
    """
    __tablename__ = "role_permission"
    
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50), nullable=False, index=True)  # admin/planner/field/user/gözlemci
    permission_key = db.Column(db.String(100), nullable=False, index=True)  # reports_analytics, admin_users, vb.
    can_access = db.Column(db.Boolean, nullable=False, default=True)  # True=erişim var, False=erişim yok
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    
    updated_by = db.relationship("User")
    
    __table_args__ = (
        db.UniqueConstraint("role", "permission_key", name="uq_role_permission"),
    )


# Mevcut rol izinlerini başlangıçta oluşturan fonksiyon
def init_role_permissions():
    """Varsayılan rol izinlerini oluşturur (eğer yoksa)"""
    default_permissions = [
        # admin rolü - tüm izinler açık
        ("admin", "reports_analytics", True),
        ("admin", "admin_users", True),
        ("admin", "tasks_management", True),
        ("admin", "planner", True),
        ("admin", "chat", True),
        
        # planner rolü
        ("planner", "reports_analytics", True),
        ("planner", "admin_users", False),
        ("planner", "tasks_management", True),
        ("planner", "planner", True),
        ("planner", "chat", True),
        
        # field rolü
        ("field", "reports_analytics", False),
        ("field", "admin_users", False),
        ("field", "tasks_management", False),
        ("field", "planner", True),
        ("field", "chat", True),
        
        # user rolü
        ("user", "reports_analytics", False),
        ("user", "admin_users", False),
        ("user", "tasks_management", False),
        ("user", "planner", True),
        ("user", "chat", True),
        
        # gözlemci rolü - varsayılan olarak kapalı
        ("gözlemci", "reports_analytics", False),
        ("gözlemci", "admin_users", False),
        ("gözlemci", "tasks_management", False),
        ("gözlemci", "planner", False),
        ("gözlemci", "chat", False),
    ]
    
    from extensions import db
    for role, perm_key, can_access in default_permissions:
        existing = RolePermission.query.filter_by(role=role, permission_key=perm_key).first()
        if not existing:
            rp = RolePermission(role=role, permission_key=perm_key, can_access=can_access)
            db.session.add(rp)
    db.session.commit()
