
# Veri Analizi Raporu

**Tarih:** 2026-01-18
**Durum:** Kritik Veri Eksikliği Tespit Edildi

Bu rapor, mevcut veritabanı yapısı ve veri durumunu analiz ederek yeni dashboard tasarımına altlık oluşturmayı amaçlar.

## 1. Tablo Analizi

| Tablo | Önemli Kolonlar | Veri Var mı? | Analizde Kullanılabilir mi? | Notlar |
| :--- | :--- | :---: | :---: | :--- |
| **statistics_event** | Tüm kolonlar | **HAYIR** | **HAYIR** | Tablo tamamen boş. Bu tabloya dayalı kodlar silinmeli. |
| **monthly_stat** | Tüm kolonlar | **HAYIR** | **HAYIR** | Tablo tamamen boş. |
| **Job** | id, status, kanban_status, project_id, work_date, team_id | **EVET** | **EVET** | 104 satır. Çoğu 'pending', 3 'published'. Temel iş sayımı için uygun. |
| **PlanCell** | vehicle_info, work_date | **EVET** | **EVET** | Araç ve tarih bilgisi için kullanılabilir. |
| **Vehicle** | plate, brand | **EVET** | **EVET** | Referans tablosu. |
| **Person** | full_name, user_id | **EVET** | **EVET** | Referans tablosu. |
| **Team** | name, vehicle_id | **EVET** | **EVET** | Referans tablosu. |
| **Project** | project_code, region | **EVET** | **EVET** | Referans tablosu. |

## 2. Eksik Veriler (Kritik)

Aşağıdaki metrikler mevcut veritabanında **BULUNMAMAKTADIR** ve bu nedenle yeni dashboard'da gösterilmeyecektir veya sadece mevcut olan sınırlı veriden gösterilecektir:

1.  **Toplam KM**: `Job` ve `PlanCell` tablolarında KM verisi tutan yapılandırılmış bir kolon yoktur. `statistics_event.km_driven` boştur.
    *   *Karar:* Grafiklerde KM gösterilmeyecek. "Veri Yok" uyarısı verilecek veya bölüm çıkarılacak.
2.  **Çalışma Süresi**: `Job.closed_at` çoğu işte boştur (işler pending/planned durumda).
    *   *Karar:* Süre analizi yapılamaz.
3.  **Tekrar İş Analizi**: `Job.kanban_status` üzerinden statü değişimi izlenebilir ancak açıkça "Tekrar" olarak işaretlenmiş bir alan yoktur.
    *   *Karar:* Tekrar oranı hesaplanamaz.

## 3. Yeni Dashboard Tasarım Planı

Mevcut veri durumu göz önüne alındığında, dashboard sadece aşağıdaki metrikleri içerecektir:

*   **Toplam İş Sayısı** (Job tablosundan)
*   **Proje Bazlı İş Dağılımı** (Job x Project)
*   **Personel/Ekip Bazlı İş Dağılımı** (Job x Team/AssignedUser)
*   **Zaman Bazlı İş Dağılımı** (Job.work_date üzerinden gelecek/planlanan iş yükü)
*   **İş Durumu Dağılımı** (Job.kanban_status: Planned, Published, Closed vb.)

**3D Görselleştirmeler**, veri yoğunluğu düşük olduğu için (104 iş, çoğu tek günde veya dağılmış) anlamlı olmayabilir ancak kullanıcı isteği üzerine uygun veri (Zaman x Proje x İş Adedi) ile denenecektir.

---
**UYARI:** Eski 'analytics_models' ve 'planner_analytics_export' modülleri tamamen silinecektir.
