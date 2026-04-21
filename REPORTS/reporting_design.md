# Reporting Design (taslak)

## Hedef
Gelis,mis raporlama: haftalik plan + is atama + geri bildirim + mail log + ekip performansi tek ekranda raporlansin.

## Yeni Modul
- UI: `/reports/advanced` (admin)
- Export: `/reports/advanced.xlsx` (admin)
- JSON API: `/api/reports/advanced?start=&end=&city=&project_id=&team_name=&status=&include_leave=&only_overdue=&only_problem=&page=&page_size=`
- Drill-down API: `/api/job_detail?job_id=...`
- Durum API: `POST /api/job_feedback`

## Kapsam
- Yonetici Dashboard
  - Toplam is (filtreli aralik)
  - Durum dagilimi: pending / completed / problem
  - Geciken isler sayisi (work_date < today ve completed degil)
  - Ortalama kapanis suresi (job maili gonderim -> feedback.closed_at)
  - Tamamlanma orani (%), is/ekip
- Is listesi (drill-down)
- Ekip performans (top ekipler + ort kapanis)
- Mail raporu (basarili/basarisiz + hata nedenleri + gecmis)

## Veri Kaynaklari
- Plan: `PlanCell`, `CellAssignment`, `Project`, `Team`
- Mail: `MailLog` (meta_json icinde `type=job/weekly/team`)
- Gelis,mis rapor snapshot tablolari:
  - `Job` (PlanCell -> job snapshot)
  - `JobAssignment` (job -> person snapshot)
  - `JobFeedback` (completed/problem kapanis)

## Senkronizasyon / Backfill
- `upsert_jobs_for_range(start, end)` rapor acilisinda secilen tarih araligi icin:
  - PlanCell icerigi varsa Job olusturur/gunceller.
  - PlanCell bos ise Job kaydini siler.
  - Personelleri JobAssignment'e snapshot olarak yazar.
  - Job.status degerini latest JobFeedback'e gore ayarlar (yoksa pending).

## Filtreler
- Tarih araligi: `start`, `end`
- Il: `city`
- Proje: `project_id`
- Ekip: `team_name`
- Durum: `status`
- Ek opsiyonlar:
  - `include_leave=1`: personel sayisina izinlileri dahil et
  - `only_overdue=1`: sadece geciken isler
  - `only_problem=1`: sadece problemli isler
- Sekme: `tab=dashboard|jobs|team|mail|export`
- Sayfalama: `page`, `page_size` (server-side)

## Export
- Excel sayfalari: `Dashboard`, `Jobs`, `Teams`, `MailLogs`
- Minimum hedef: Excel (PDF opsiyonel).

## Performans Notlari
- Default aralik son 7 gun; genis araliklarda Job backfill maliyeti artar.
- Is listesinde server-side pagination kullanilir.
- MailLog meta_json parse SQL icinde degil Python icinde yapilir (limitli).

## Manuel Kontrol
1) `/reports/advanced` ac (admin) ve tarih araligini degistir: KPI + listeler dolmali.
2) Jobs sekmesi: sayfalama (Onceki/Sonraki) dogru calismali.
3) `only_overdue` / `only_problem` checkbox'lari: metrikler ve liste filtrelenmeli.
4) `include_leave`: Jobs tablosundaki personel sayisi degismeli.
5) Excel export: `/reports/advanced.xlsx` 4 sayfa uretmeli ve filtre degerlerini Dashboard sayfasinda gostermeli.
