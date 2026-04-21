from datetime import date, datetime
from itertools import product

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from extensions import db
from models import Job, JobAssignment, Project, SubProject, Team, User, Vehicle, CellCancellation, TeamOvertime, PlanCell, Person, Firma, Seviye, JobFeedback
from services.analytics_helpers import calculate_hours, get_job_km, get_vehicle_info


ALLOWED_DIMENSIONS = {
    "project", "sub_project", "person", "vehicle", "city", "bucket",
    "team", "firma", "status", "shift", "seviye", "feedback_outcome"
}
ALLOWED_METRICS = {"job_count", "work_hours", "km_total", "usage_count"}
ALLOWED_BUCKETS = {"day", "week", "month", "year"}


WHITELIST = {
    # Project (8)
    ("project",): {"work_hours", "job_count"},
    ("project", "sub_project"): {"work_hours", "job_count"},
    ("bucket", "project"): {"work_hours", "job_count"},
    ("bucket", "project", "sub_project"): {"work_hours", "job_count"},
    ("city", "project"): {"job_count", "work_hours"},
    ("bucket", "city", "project"): {"job_count", "work_hours"},

    # Person (6)
    ("person",): {"work_hours", "job_count"},
    ("bucket", "person"): {"work_hours", "job_count"},
    ("person", "project"): {"work_hours", "job_count"},
    ("person", "project", "sub_project"): {"work_hours", "job_count"},
    ("person", "city"): {"job_count", "work_hours"},

    # Vehicle (4)
    ("vehicle",): {"km_total", "job_count"},
    ("bucket", "vehicle"): {"km_total", "job_count"},
    ("vehicle", "city"): {"km_total", "job_count"},

    # Person x Vehicle (2)
    ("person", "vehicle"): {"usage_count", "job_count", "km_total"},
    ("bucket", "person", "vehicle"): {"usage_count"},

    # Team (6)
    ("team",): {"work_hours", "job_count", "km_total"},
    ("bucket", "team"): {"work_hours", "job_count"},
    ("team", "project"): {"work_hours", "job_count"},
    ("team", "city"): {"work_hours", "job_count", "km_total"},
    ("team", "vehicle"): {"job_count", "km_total"},
    ("bucket", "team", "project"): {"work_hours", "job_count"},

    # Firma (5)
    ("firma",): {"work_hours", "job_count"},
    ("bucket", "firma"): {"work_hours", "job_count"},
    ("firma", "project"): {"work_hours", "job_count"},
    ("firma", "city"): {"work_hours", "job_count"},
    ("firma", "person"): {"work_hours", "job_count"},

    # Status (4)
    ("status",): {"job_count"},
    ("bucket", "status"): {"job_count"},
    ("status", "project"): {"job_count"},
    ("status", "city"): {"job_count"},

    # Shift (4)
    ("shift",): {"work_hours", "job_count"},
    ("bucket", "shift"): {"work_hours", "job_count"},
    ("shift", "project"): {"work_hours", "job_count"},
    ("shift", "person"): {"work_hours", "job_count"},

    # Seviye (4)
    ("seviye",): {"work_hours", "job_count"},
    ("bucket", "seviye"): {"work_hours", "job_count"},
    ("seviye", "project"): {"work_hours", "job_count"},
    ("seviye", "firma"): {"work_hours", "job_count"},

    # Feedback Outcome (3)
    ("feedback_outcome",): {"job_count"},
    ("bucket", "feedback_outcome"): {"job_count"},
    ("feedback_outcome", "project"): {"job_count"},
}


def _parse_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value.strip():
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    return None


def _bucket_value(work_date: date, bucket: str) -> str:
    b = (bucket or "month").strip().lower()
    if b == "day":
        return work_date.strftime("%Y-%m-%d")
    if b == "week":
        return f"{work_date.year}-W{work_date.strftime('%V')}"
    if b == "year":
        return str(work_date.year)
    return work_date.strftime("%Y-%m")


def _normalize_sort(sort_key: str, sort_dir: str, metrics):
    key = (sort_key or "").strip().lower()
    if key not in {"job_count", "work_hours", "km_total", "usage_count", "name"}:
        key = metrics[0] if metrics else "job_count"
    direction = (sort_dir or "desc").strip().lower()
    if direction not in {"asc", "desc"}:
        direction = "desc"
    return key, direction


def _validate_payload(payload):
    dims = [d for d in (payload.get("dimensions") or []) if d]
    metrics = [m for m in (payload.get("metrics") or []) if m]
    bucket = (payload.get("bucket") or "month").strip().lower()
    if bucket not in ALLOWED_BUCKETS:
        raise ValueError("Gecersiz bucket. day/week/month/year olmali.")
    if not dims:
        raise ValueError("dimensions bos olamaz.")
    if not metrics:
        metrics = ["job_count"]
    if any(d not in ALLOWED_DIMENSIONS for d in dims):
        raise ValueError("Gecersiz dimension kullanildi.")
    if any(m not in ALLOWED_METRICS for m in metrics):
        raise ValueError("Gecersiz metric kullanildi.")

    dims_key = tuple(dims)
    allowed_metrics = WHITELIST.get(dims_key)
    if not allowed_metrics:
        dims_set = frozenset(dims)
        for k, v in WHITELIST.items():
            if frozenset(k) == dims_set:
                allowed_metrics = v
                break
    if not allowed_metrics:
        raise ValueError("Bu kombinasyon whitelist disinda.")
    if not set(metrics).issubset(allowed_metrics):
        raise ValueError("Bu kombinasyon icin izinli metric listesi disinda istek var.")

    if frozenset(dims) == frozenset(("bucket", "person", "vehicle")):
        top_n = int(payload.get("top_n") or 10)
        if top_n > 10:
            raise ValueError("bucket+person+vehicle icin Top N limiti 10 olmalidir.")

    return dims, metrics, bucket


def _top_n_other(rows, dims, metrics, *, top_n: int, rank_metric: str, bucket_dim: str = "bucket"):
    if not rows or top_n <= 0:
        return rows
    if len(rows) <= top_n:
        return rows
    primary_idx = None
    for i, d in enumerate(dims):
        if d != bucket_dim:
            primary_idx = i
            break
    if primary_idx is None:
        return rows

    totals = {}
    for r in rows:
        k = r.get(dims[primary_idx], "Bilinmiyor")
        totals[k] = totals.get(k, 0) + float(r.get(rank_metric, 0) or 0)
    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    keep = {k for k, _ in ranked[:top_n]}

    folded = {}
    for r in rows:
        is_other = r.get(dims[primary_idx], "Bilinmiyor") not in keep
        out = dict(r)
        if is_other:
            for d in dims:
                if d != bucket_dim:
                    out[d] = "Diger"
        key = tuple(out.get(d) for d in dims)
        if key not in folded:
            folded[key] = {m: 0 for m in metrics}
            for d in dims:
                folded[key][d] = out.get(d)
        for m in metrics:
            folded[key][m] += float(out.get(m, 0) or 0)

    return list(folded.values())


def _job_persons(job):
    people = []
    try:
        people = [ja.person for ja in (job.assignments or []) if getattr(ja, "person", None)]
    except Exception:
        people = []
    if not people:
        try:
            if job.assigned_user:
                people = [job.assigned_user]
        except Exception:
            people = []
    return people


def _dim_values(job, dim: str, bucket: str):
    if dim == "project":
        # Önce relationship'ten kontrol et
        if job.project:
            project_code = job.project.project_code or ""
            project_name = job.project.project_name or ""
            # Soft delete kontrolü
            if hasattr(job.project, 'is_deleted') and job.project.is_deleted:
                return ["Bilinmiyor (Silinmiş)"]
            if project_code:
                return [project_code]
            if project_name:
                return [project_name]
            return ["Bilinmiyor"]
        # Eğer project relationship yüklenmemişse veya None ise, project_id ile tekrar sorgula
        if job.project_id:
            try:
                project = Project.query.get(job.project_id)
                if project:
                    # Soft delete kontrolü
                    if hasattr(project, 'is_deleted') and project.is_deleted:
                        return ["Bilinmiyor (Silinmiş)"]
                    project_code = project.project_code or ""
                    project_name = project.project_name or ""
                    if project_code:
                        return [project_code]
                    if project_name:
                        return [project_name]
                    return ["Bilinmiyor"]
            except Exception:
                pass
        return ["Bilinmiyor"]
    if dim == "sub_project":
        return [job.subproject.name if job.subproject else "Genel"]
    if dim == "person":
        people = _job_persons(job)
        out = []
        for p in people:
            name = getattr(p, "full_name", None) or getattr(p, "username", None) or "Atanmamis"
            out.append(name)
        return out or ["Atanmamis"]
    if dim == "vehicle":
        return [get_vehicle_info(job) or "Belirsiz"]
    if dim == "city":
        return [job.project.region if job.project and job.project.region else "Bilinmiyor"]
    if dim == "bucket":
        return [_bucket_value(job.work_date, bucket)]

    if dim == "team":
        if job.team:
            return [job.team.name or f"Ekip #{job.team.id}"]
        if hasattr(job, 'team_name') and job.team_name:
            return [job.team_name]
        return ["Ekip Atanmamış"]

    if dim == "firma":
        firms = set()
        for ja in (job.assignments or []):
            if ja.person and hasattr(ja.person, 'firma') and ja.person.firma:
                firms.add(ja.person.firma.name or "Firma Belirtilmemiş")
            elif ja.person and hasattr(ja.person, 'firma_id') and ja.person.firma_id:
                try:
                    firma = Firma.query.get(ja.person.firma_id)
                    if firma:
                        firms.add(firma.name or "Firma Belirtilmemiş")
                except:
                    pass
        return list(firms) if firms else ["Firma Belirtilmemiş"]

    if dim == "status":
        status = job.status or job.kanban_status or "bilinmiyor"
        status_map = {
            "pending": "Beklemede",
            "in_progress": "Devam Ediyor",
            "completed": "Tamamlandı",
            "cancelled": "İptal Edildi",
            "reported": "Raporlandı",
            "problem": "Problem",
        }
        return [status_map.get(status.lower(), status.capitalize())]

    if dim == "shift":
        shift = (job.shift or "").strip()
        if not shift:
            return ["Vardiya Belirtilmemiş"]
        if 'gece' in shift.lower():
            return ["Gece Vardiyası"]
        if 'gündüz' in shift.lower() or 'gunduz' in shift.lower():
            return ["Gündüz Vardiyası"]
        return [shift]

    if dim == "seviye":
        levels = set()
        for ja in (job.assignments or []):
            if ja.person and hasattr(ja.person, 'seviye') and ja.person.seviye:
                levels.add(ja.person.seviye.name or "Seviye Belirtilmemiş")
            elif ja.person and hasattr(ja.person, 'seviye_id') and ja.person.seviye_id:
                try:
                    seviye = Seviye.query.get(ja.person.seviye_id)
                    if seviye:
                        levels.add(seviye.name or "Seviye Belirtilmemiş")
                except:
                    pass
        return list(levels) if levels else ["Seviye Belirtilmemiş"]

    if dim == "feedback_outcome":
        outcomes = set()
        try:
            for fb in (job.feedback_rows or []):
                if hasattr(fb, 'outcome') and fb.outcome:
                    outcome = fb.outcome.strip()
                    outcome_map = {
                        "positive": "Olumlu",
                        "negative": "Olumsuz",
                        "neutral": "Nötr",
                        "pending": "Beklemede"
                    }
                    outcomes.add(outcome_map.get(outcome.lower(), outcome.capitalize()))
        except:
            pass
        return list(outcomes) if outcomes else ["Geri Bildirim Yok"]

    return ["N/A"]


def _collect_jobs(payload):
    start_date = _parse_date(payload.get("date_range", {}).get("start"))
    end_date = _parse_date(payload.get("date_range", {}).get("end"))
    filters = payload.get("filters", {}) or {}

    query = db.session.query(Job)
    if start_date:
        query = query.filter(Job.work_date >= start_date)
    if end_date:
        query = query.filter(Job.work_date <= end_date)

    project_ids = [int(x) for x in (filters.get("project_ids") or []) if int(x or 0) > 0]
    if project_ids:
        query = query.filter(Job.project_id.in_(project_ids))

    subproject_ids = [int(x) for x in (filters.get("sub_project_ids") or []) if int(x or 0) > 0]
    if subproject_ids:
        query = query.filter(Job.subproject_id.in_(subproject_ids))

    status_filters = [str(x or "").strip() for x in (filters.get("status") or []) if str(x or "").strip()]
    if status_filters:
        query = query.filter(or_(Job.status.in_([s.upper() for s in status_filters]), Job.kanban_status.in_([s.upper() for s in status_filters])))

    team_ids = [int(x) for x in (filters.get("team_ids") or []) if int(x or 0) > 0]
    if team_ids:
        query = query.filter(Job.team_id.in_(team_ids))

    query = query.options(
        joinedload(Job.project),
        joinedload(Job.subproject),
        joinedload(Job.assigned_user),
        joinedload(Job.team).joinedload(Team.vehicle),
        joinedload(Job.assignments).joinedload(JobAssignment.person),
    )

    jobs = query.all()
    
    # Project relationship'leri yüklenmemişse veya None ise, project_id ile tekrar yükle
    # Bu, soft delete veya relationship sorunlarını çözer
    project_ids_to_load = set()
    for job in jobs:
        if not job.project and job.project_id:
            project_ids_to_load.add(job.project_id)
    
    if project_ids_to_load:
        projects_map = {p.id: p for p in Project.query.filter(Project.id.in_(project_ids_to_load)).all()}
        for job in jobs:
            if not job.project and job.project_id:
                job.project = projects_map.get(job.project_id)

    city_filters = [str(x or "").strip().lower() for x in (filters.get("city") or []) if str(x or "").strip()]
    if city_filters:
        jobs = [j for j in jobs if (j.project and (j.project.region or "").strip().lower() in city_filters)]

    person_ids = [int(x) for x in (filters.get("person_ids") or []) if int(x or 0) > 0]
    if person_ids:
        pid_set = set(person_ids)
        out = []
        for j in jobs:
            persons = [ja.person_id for ja in (j.assignments or []) if getattr(ja, "person_id", None)]
            if pid_set.intersection(persons):
                out.append(j)
        jobs = out

    vehicle_ids = [int(x) for x in (filters.get("vehicle_ids") or []) if int(x or 0) > 0]
    if vehicle_ids:
        vehicles = Vehicle.query.filter(Vehicle.id.in_(vehicle_ids)).all()
        plate_set = {v.plate for v in vehicles if v and v.plate}
        vid_set = {v.id for v in vehicles if v and v.id}
        out = []
        for j in jobs:
            vid = None
            if j.team and j.team.vehicle_id:
                vid = int(j.team.vehicle_id)
            plate = get_vehicle_info(j) or ""
            if (vid and vid in vid_set) or (plate and plate in plate_set):
                out.append(j)
        jobs = out

    firma_ids = [int(x) for x in (filters.get("firma_ids") or []) if int(x or 0) > 0]
    if firma_ids:
        fid_set = set(firma_ids)
        out = []
        for j in jobs:
            has_firm = False
            for ja in (j.assignments or []):
                if ja.person and hasattr(ja.person, 'firma_id') and ja.person.firma_id in fid_set:
                    has_firm = True
                    break
            if has_firm:
                out.append(j)
        jobs = out

    seviye_ids = [int(x) for x in (filters.get("seviye_ids") or []) if int(x or 0) > 0]
    if seviye_ids:
        sid_set = set(seviye_ids)
        out = []
        for j in jobs:
            has_level = False
            for ja in (j.assignments or []):
                if ja.person and hasattr(ja.person, 'seviye_id') and ja.person.seviye_id in sid_set:
                    has_level = True
                    break
            if has_level:
                out.append(j)
        jobs = out

    return jobs


class AnalyticsRobot:
    @staticmethod
    def query(payload):
        dims, metrics, bucket = _validate_payload(payload)
        jobs = _collect_jobs(payload)
        sort_key, sort_dir = _normalize_sort(payload.get("sort_key"), payload.get("sort_dir"), metrics)
        top_n = int(payload.get("top_n") or 10)

        grouped = {}
        for job in jobs:
            dim_sets = [_dim_values(job, dim, bucket) for dim in dims]
            for combo in product(*dim_sets):
                if combo not in grouped:
                    grouped[combo] = {m: 0 for m in ALLOWED_METRICS}
                grouped[combo]["job_count"] += 1
                grouped[combo]["work_hours"] += calculate_hours(job)
                grouped[combo]["km_total"] += get_job_km(job)
                if "usage_count" in metrics or sort_key == "usage_count":
                    grouped[combo]["usage_count"] += 1

        results = []
        for key, vals in grouped.items():
            row = {}
            for i, dim in enumerate(dims):
                row[dim] = key[i]
            for met in ALLOWED_METRICS:
                row[met] = vals[met]
            results.append(row)

        # Not: "Diger" gruplama mantığı kaldırıldı - tüm sonuçlar gösteriliyor
        # rank_metric = sort_key if sort_key != "name" else (metrics[0] if metrics else "job_count")
        # results = _top_n_other(results, dims, list(ALLOWED_METRICS), top_n=top_n, rank_metric=rank_metric)

        if sort_key == "name":
            results.sort(key=lambda x: str(x.get(dims[0], "")).lower(), reverse=(sort_dir == "desc"))
        else:
            results.sort(key=lambda x: float(x.get(sort_key, 0) or 0), reverse=(sort_dir == "desc"))

        for row in results:
            row["work_hours"] = round(row.get("work_hours", 0) or 0, 1)
            row["km_total"] = round(row.get("km_total", 0) or 0, 1)
            row["job_count"] = int(row.get("job_count", 0) or 0)
            row["usage_count"] = int(row.get("usage_count", 0) or 0)

        return {
            "ok": True,
            "rows": results,
            "meta": {
                "dimensions": dims,
                "metrics": metrics,
                "bucket": bucket,
                "sort_key": sort_key,
                "sort_dir": sort_dir,
                "top_n": top_n,
                "total_rows": int(len(results)),
            },
        }

    @staticmethod
    def get_tops(payload):
        limit = int(payload.get("limit") or 10)
        jobs = _collect_jobs({
            "date_range": payload.get("date_range"),
            "filters": payload.get("filters", {}) or {},
        })

        person_hours = {}
        person_jobs = {}
        person_projects = {}
        person_cities = {}
        person_vehicles = {}

        project_hours = {}
        project_jobs = {}

        subproject_hours = {}
        subproject_jobs = {}

        vehicle_km = {}
        vehicle_jobs = {}
        vehicle_cities = {}
        vehicle_people = {}

        city_jobs = {}
        city_hours = {}
        city_km = {}

        person_vehicle_usage = {}

        for job in jobs:
            h = calculate_hours(job)
            km = get_job_km(job)
            city = job.project.region if job.project and job.project.region else "Bilinmiyor"
            vehicle_label = get_vehicle_info(job) or "Belirsiz"

            people = []
            for ja in (job.assignments or []):
                if ja.person:
                    people.append((ja.person.id, ja.person.full_name))
            if not people and job.assigned_user:
                uname = job.assigned_user.full_name or job.assigned_user.username or "Atanmamis"
                people = [(-job.assigned_user.id, uname)]

            for _, pname in people:
                person_hours[pname] = person_hours.get(pname, 0) + h
                person_jobs[pname] = person_jobs.get(pname, 0) + 1
                person_projects.setdefault(pname, set()).add(job.project_id or 0)
                person_cities.setdefault(pname, set()).add(city)
                if vehicle_label and vehicle_label != "Belirsiz":
                    person_vehicles.setdefault(pname, set()).add(vehicle_label)
                    key = (pname, vehicle_label)
                    person_vehicle_usage[key] = person_vehicle_usage.get(key, 0) + 1

            if job.project:
                proj_label = job.project.project_name or job.project.project_code
                project_hours[proj_label] = project_hours.get(proj_label, 0) + h
                project_jobs[proj_label] = project_jobs.get(proj_label, 0) + 1

            if job.subproject:
                sub_label = job.subproject.name
                subproject_hours[sub_label] = subproject_hours.get(sub_label, 0) + h
                subproject_jobs[sub_label] = subproject_jobs.get(sub_label, 0) + 1

            if vehicle_label and vehicle_label != "Belirsiz":
                vehicle_km[vehicle_label] = vehicle_km.get(vehicle_label, 0) + km
                vehicle_jobs[vehicle_label] = vehicle_jobs.get(vehicle_label, 0) + 1
                vehicle_cities.setdefault(vehicle_label, set()).add(city)
                for _, pname in people:
                    vehicle_people.setdefault(vehicle_label, set()).add(pname)

            city_jobs[city] = city_jobs.get(city, 0) + 1
            city_hours[city] = city_hours.get(city, 0) + h
            city_km[city] = city_km.get(city, 0) + km

        def to_list(d, decimals=0, reverse=True):
            items = [{"name": k, "value": round(v, decimals)} for k, v in d.items()]
            items.sort(key=lambda x: x["value"], reverse=reverse)
            return items[:limit]

        def to_distinct_list(d, reverse=True):
            items = [{"name": k, "value": len(v)} for k, v in d.items()]
            items.sort(key=lambda x: x["value"], reverse=reverse)
            return items[:limit]

        efficiency = {}
        for name, count in person_jobs.items():
            hours = person_hours.get(name, 0) or 0
            if hours > 0:
                efficiency[name] = round(count / hours, 3)

        person_vehicle_list = [{"name": f"{p} x {v}", "value": c, "person": p, "vehicle": v} for (p, v), c in person_vehicle_usage.items()]
        person_vehicle_list.sort(key=lambda x: x["value"], reverse=True)

        return {
            "ok": True,
            "cards": {
                "person_max_hours": to_list(person_hours, 1, True),
                "person_min_hours": to_list(person_hours, 1, False),
                "person_max_jobs": to_list(person_jobs, 0, True),
                "person_min_jobs": to_list(person_jobs, 0, False),
                "person_efficiency": to_list(efficiency, 3, True),
                "person_diversity_proj": to_distinct_list(person_projects, True),
                "person_diversity_city": to_distinct_list(person_cities, True),

                "proj_max_hours": to_list(project_hours, 1, True),
                "proj_min_hours": to_list(project_hours, 1, False),
                "proj_max_jobs": to_list(project_jobs, 0, True),
                "proj_min_jobs": to_list(project_jobs, 0, False),
                "proj_city_peak": to_list(project_jobs, 0, True),

                "sub_max_hours": to_list(subproject_hours, 1, True),
                "sub_max_jobs": to_list(subproject_jobs, 0, True),
                "sub_min_jobs": to_list(subproject_jobs, 0, False),

                "veh_max_km": to_list(vehicle_km, 1, True),
                "veh_min_km": to_list(vehicle_km, 1, False),
                "veh_max_jobs": to_list(vehicle_jobs, 0, True),
                "veh_diversity_city": to_distinct_list(vehicle_cities, True),

                "person_vehicle_max_usage": person_vehicle_list[:limit],
                "person_most_vehicles": to_distinct_list(person_vehicles, True),
                "veh_most_people": to_distinct_list(vehicle_people, True),

                "city_max_jobs": to_list(city_jobs, 0, True),
                "city_max_hours": to_list(city_hours, 1, True),
                "city_max_km": to_list(city_km, 1, True),
            },
        }

    @staticmethod
    def get_cancellation_overtime_stats(payload):
        """İptal ve mesai istatistikleri"""
        start_date = _parse_date(payload.get("date_range", {}).get("start"))
        end_date = _parse_date(payload.get("date_range", {}).get("end"))
        limit = int(payload.get("limit") or 10)
        
        # İptal sorgulama
        cancel_query = db.session.query(CellCancellation).join(
            PlanCell, CellCancellation.cell_id == PlanCell.id
        ).join(
            Project, PlanCell.project_id == Project.id
        )
        
        if start_date:
            cancel_query = cancel_query.filter(CellCancellation.cancelled_at >= start_date)
        if end_date:
            cancel_query = cancel_query.filter(CellCancellation.cancelled_at <= end_date)
        
        cancellations = cancel_query.all()
        
        # Mesai sorgulama
        overtime_query = db.session.query(TeamOvertime)
        
        if start_date:
            overtime_query = overtime_query.filter(TeamOvertime.work_date >= start_date)
        if end_date:
            overtime_query = overtime_query.filter(TeamOvertime.work_date <= end_date)
        
        overtimes = overtime_query.all()
        
        # İptal istatistikleri
        cancel_by_project = {}
        cancel_by_user = {}
        cancel_by_reason = {}
        cancel_by_city = {}
        
        for c in cancellations:
            try:
                cell = PlanCell.query.get(c.cell_id)
                if cell and cell.project:
                    proj_name = cell.project.project_name or cell.project.project_code
                    city = cell.project.region or "Bilinmiyor"
                    
                    cancel_by_project[proj_name] = cancel_by_project.get(proj_name, 0) + 1
                    cancel_by_city[city] = cancel_by_city.get(city, 0) + 1
                
                user = User.query.get(c.cancelled_by_user_id)
                if user:
                    user_name = user.full_name or user.username
                    cancel_by_user[user_name] = cancel_by_user.get(user_name, 0) + 1
                
                reason = (c.reason or "Neden belirtilmedi")[:50]
                cancel_by_reason[reason] = cancel_by_reason.get(reason, 0) + 1
            except:
                pass
        
        # Mesai istatistikleri
        overtime_by_person = {}
        overtime_by_project = {}
        overtime_by_city = {}
        overtime_total_hours = 0
        
        for ot in overtimes:
            try:
                hours = ot.duration_hours or 0
                overtime_total_hours += hours
                
                if ot.person:
                    person_name = ot.person.full_name or "Bilinmiyor"
                    overtime_by_person[person_name] = overtime_by_person.get(person_name, 0) + hours
                
                if ot.cell:
                    cell = ot.cell
                    if cell.project:
                        proj_name = cell.project.project_name or cell.project.project_code
                        city = cell.project.region or "Bilinmiyor"
                        
                        overtime_by_project[proj_name] = overtime_by_project.get(proj_name, 0) + hours
                        overtime_by_city[city] = overtime_by_city.get(city, 0) + hours
            except:
                pass
        
        def to_list(d, decimals=0):
            items = [{"name": k, "value": round(v, decimals)} for k, v in d.items()]
            items.sort(key=lambda x: x["value"], reverse=True)
            return items[:limit]
        
        return {
            "ok": True,
            "summary": {
                "total_cancellations": len(cancellations),
                "total_overtime_records": len(overtimes),
                "total_overtime_hours": round(overtime_total_hours, 1),
            },
            "cancellations": {
                "by_project": to_list(cancel_by_project),
                "by_user": to_list(cancel_by_user),
                "by_city": to_list(cancel_by_city),
                "by_reason": to_list(cancel_by_reason),
            },
            "overtime": {
                "by_person": to_list(overtime_by_person, 1),
                "by_project": to_list(overtime_by_project, 1),
                "by_city": to_list(overtime_by_city, 1),
            },
        }
