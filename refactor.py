
import os

path = "app.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
models_removed = False

for line in lines:
    # Replace db init
    if "db = SQLAlchemy(app)" in line:
        new_lines.append("from extensions import db, socketio\n")
        new_lines.append("from models import User, Firma, Seviye, Person, Project, SubProject, ProjectComment, Team, TeamMailConfig, PlanCell, CellAssignment, PersonDayStatus, MailLog, Notification, Announcement, AnnouncementRead, ChatMessage, ChatUserMessage, MailTemplate, Job, JobAssignment, JobFeedback, JobFeedbackMedia, JobReport, JobStatusHistory, Vehicle\n")
        new_lines.append("db.init_app(app)\n")
        continue

    # Replace socketio init
    if "socketio = SocketIO(" in line:
        new_lines.append("socketio.init_app(\n")
        continue
    
    # Start of models removal
    if "class User(db.Model):" in line:
        skip = True
        continue
    
    # End of models removal (Found the HELPERS section)
    if "# ===================== HELPERS =====================" in line:
        skip = False
        models_removed = True
        new_lines.append(line)
        continue
    
    if skip:
        continue
        
    new_lines.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Refactoring complete.")
