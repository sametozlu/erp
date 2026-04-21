
@planner_bp.get("/api/project/<int:project_id>/has-active-subprojects")
@login_required
@observer_required
def api_project_has_active_subprojects(project_id: int):
    """Projeye ait aktif alt proje var mı?"""
    count = SubProject.query.filter(
        SubProject.project_id == project_id,
        SubProject.is_active == True
    ).count()
    
    return jsonify({
        "ok": True,
        "has_active_subprojects": count > 0,
        "active_subproject_count": count
    })
