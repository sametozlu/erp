# -*- coding: utf-8 -*-
"""
Yasin Yücel'e (veya verilen kullaniciya) atanmis islerin tarihlerini listeler.
Kullanim: python scripts/list_jobs_for_user.py
"""
import os
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

def main():
    from app import app
    from extensions import db
    from models import User, Job, PlanCell, Project

    with app.app_context():
        # Yasin Yücel kullanıcısını bul (isim benzeri)
        users = User.query.filter(
            db.or_(
                User.full_name.ilike("%yasin%yücel%"),
                User.full_name.ilike("%yasin%yucel%"),
                User.full_name.ilike("%Yasin%YÜCEL%"),
                User.email.ilike("%yasin%"),
            )
        ).all()

        if not users:
            print("Yasin Yücel adinda kullanici bulunamadi.")
            print("Tum kullanici isimleri:")
            for u in User.query.with_entities(User.id, User.full_name, User.email).all():
                print(f"  id={u.id}  full_name={u.full_name!r}  email={u.email!r}")
            return 0

        for user in users:
            print(f"\n--- Kullanici: {user.full_name} (id={user.id}, email={user.email}) ---")

            # 1) Job.assigned_user_id ile
            jobs_in_job = Job.query.filter_by(assigned_user_id=user.id, is_published=True).order_by(Job.work_date).all()
            # 2) Hücrede atanmış ama Job'da boş olanlar (PlanCell.assigned_user_id)
            from sqlalchemy import and_
            jobs_via_cell = (
                Job.query.join(PlanCell, Job.cell_id == PlanCell.id)
                .filter(
                    PlanCell.assigned_user_id == user.id,
                    Job.is_published == True,
                )
                .order_by(Job.work_date)
                .all()
            )

            # Tarihleri birlestir (tekrarsiz)
            all_dates = set()
            for j in jobs_in_job:
                all_dates.add(j.work_date)
            for j in jobs_via_cell:
                all_dates.add(j.work_date)

            # PlanCell'de assigned_user_id = bu kullanici olan (yayinlanmis job olsun olmasin)
            cells_with_user = PlanCell.query.filter_by(assigned_user_id=user.id).all()
            # Person.user_id = bu kullanici olan person var mi (ekip atamasi ile ise)
            from models import Person, CellAssignment
            person = Person.query.filter_by(user_id=user.id).first()
            cell_ids_via_person = set()
            if person:
                cell_ids_via_person = {a.cell_id for a in CellAssignment.query.filter_by(person_id=person.id).all()}

            if not all_dates:
                print("  Bu kullaniciya atanmis (yayinlanmis) is YOK.")
                print("  - Job.assigned_user_id ile:", len(jobs_in_job))
                print("  - PlanCell.assigned_user_id ile (Job bos):", len(jobs_via_cell))
                print("  - PlanCell.assigned_user_id = bu user olan hücre sayisi (yayin fark etmez):", len(cells_with_user))
                if cells_with_user:
                    dates_cell = sorted({c.work_date for c in cells_with_user})
                    print("    Bu hücrelerin tarihleri:", [d.strftime("%d.%m.%Y") for d in dates_cell[:15]], "..." if len(dates_cell) > 15 else "")
                    for c in cells_with_user[:10]:
                        job = Job.query.filter_by(cell_id=c.id).first()
                        proj = Project.query.get(c.project_id)
                        proj_label = (proj.region + " " + proj.project_code) if proj else "?"
                        print(f"      Tarih {c.work_date.strftime('%d.%m.%Y')} cell_id={c.id} proje={proj_label} -> Job var mi={job is not None} yayinli mi={getattr(job, 'is_published', False) if job else False}")
                if person:
                    print("  - Bu kullaniciya bagli Person (ekip atamasinda) var; ekip atamali hücre sayisi:", len(cell_ids_via_person))
                continue

            dates_sorted = sorted(all_dates)
            print(f"  Toplam {len(dates_sorted)} farkli tarihte is var:")
            for d in dates_sorted:
                print(f"    {d.strftime('%d.%m.%Y')} ({d})")

            # Haftalik aralik oneri
            if dates_sorted:
                first = dates_sorted[0]
                last = dates_sorted[-1]
                print(f"\n  Filtre onerisi Benim Islerim'de:")
                print(f"    Baslangic: {first.strftime('%d.%m.%Y')}")
                print(f"    Bitis:     {last.strftime('%d.%m.%Y')}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
