
import os

file_path = "routes/planner.py"
new_code = """

# ----------------------------------------------------------------
# NEW ANALYTICS MODULE (v4.0 - Real Data Only)
# ----------------------------------------------------------------

@planner_bp.get("/reports-analytics")
@login_required
def reports_analytics_page():
    from sqlalchemy import func, extract
    
    year = int(request.args.get("year") or datetime.now().year)
    
    # 1. Base Query: Jobs in that year
    jobs_query = db.session.query(Job).filter(extract('year', Job.work_date) == year)
    all_jobs = jobs_query.all()
    
    total_jobs = len(all_jobs)
    
    # 2. Monthly Distribution
    monthly_data = db.session.query(
        extract('month', Job.work_date).label('adj_month'), 
        func.count(Job.id)
    ).filter(extract('year', Job.work_date) == year)\\
     .group_by('adj_month')\\
     .order_by('adj_month').all()
    
    months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    monthly_counts = [0] * 12
    for m, c in monthly_data:
        if m: monthly_counts[int(m)-1] = c
        
    # 3. Project Distribution
    project_data = db.session.query(
        Project.project_code,
        Project.region,
        func.count(Job.id)
    ).join(Project, Job.project_id == Project.id)\\
     .filter(extract('year', Job.work_date) == year)\\
     .group_by(Project.project_code, Project.region)\\
     .order_by(func.count(Job.id).desc()).limit(10).all()
    
    proj_names = [f"{p[0]} ({p[1]})" for p in project_data]
    proj_counts = [p[2] for p in project_data]
    
    top_project_name = proj_names[0] if proj_names else "-"
    top_project_count = proj_counts[0] if proj_counts else 0

    # 4. Personnel Distribution
    person_data = db.session.query(
        User.full_name,
        func.count(Job.id)
    ).join(User, Job.assigned_user_id == User.id)\\
     .filter(extract('year', Job.work_date) == year)\\
     .group_by(User.full_name)\\
     .order_by(func.count(Job.id).desc()).limit(10).all()
     
    person_names = [p[0] or "Bilinmiyor" for p in person_data]
    person_counts = [p[1] for p in person_data]

    # 5. Status Distribution (Kanban)
    status_data = db.session.query(
        Job.kanban_status, 
        func.count(Job.id)
    ).filter(extract('year', Job.work_date) == year)\\
     .group_by(Job.kanban_status).all()
    
    status_chart = []
    for s, c in status_data:
        status_chart.append({"name": s or "Unknown", "value": c})

    # 6. Recent Jobs Table
    recent_jobs_q = jobs_query.order_by(Job.work_date.desc()).limit(50).all()
    recent_jobs = []
    for j in recent_jobs_q:
        p_code = j.project.project_code if j.project else "-"
        p_region = j.project.region if j.project else "-"
        t_name = j.team_name or "-"
        
        u_name = "-"
        if j.assigned_user:
            u_name = j.assigned_user.full_name or j.assigned_user.username
            
        recent_jobs.append({
            "work_date": j.work_date.strftime("%Y-%m-%d") if j.work_date else "-",
            "project_code": p_code,
            "project_region": p_region,
            "team_name": t_name,
            "assigned_person": u_name,
            "kanban_status": j.kanban_status or "Unknown"
        })

    chart_data = {
        "months": months,
        "monthly_counts": monthly_counts,
        "projects": {"names": proj_names, "counts": proj_counts},
        "people": {"names": person_names, "counts": person_counts},
        "statuses": status_chart
    }

    return render_template(
        "reports_analytics.html",
        year=year,
        total_jobs=total_jobs,
        top_project_name=top_project_name,
        top_project_count=top_project_count,
        chart_data=chart_data,
        recent_jobs=recent_jobs
    )

@planner_bp.get("/reports-analytics/export/csv")
@login_required
def reports_analytics_export_csv():
    import csv
    from sqlalchemy import extract
    
    year = int(request.args.get("year") or datetime.now().year)
    
    jobs = db.session.query(Job).filter(extract('year', Job.work_date) == year).order_by(Job.work_date).all()
    
    # Simple CSV Export
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["ID", "Tarih", "Proje Kodu", "Proje Bolge", "Ekip", "Personel", "Durum", "Yayinlandi", "Not"])
    
    for j in jobs:
        p_code = j.project.project_code if j.project else ""
        p_region = j.project.region if j.project else ""
        u_name = j.assigned_user.full_name if j.assigned_user else ""
        
        cw.writerow([
            j.id,
            j.work_date,
            p_code,
            p_region,
            j.team_name,
            u_name,
            j.kanban_status,
            "Evet" if j.is_published else "Hayir",
            j.note
        ])
        
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    
    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"saha_analiz_{year}.csv"
    )
"""

with open(file_path, "a", encoding="utf-8") as f:
    f.write(new_code)

print("Appended new analytics routes.")
