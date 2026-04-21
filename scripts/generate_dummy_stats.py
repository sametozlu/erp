import sys
import os
import random
from datetime import date, timedelta

# Add parent dir to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from analytics_models import StatisticsEvent

def generate_data():
    with app.app_context():
        # Opsiyonel: Mevcut verileri temizlemek isterseniz alt satırı açın.
        # Şimdilik temizlemiyoruz, üstüne ekliyoruz ki varsa silinmesin.
        # Ancak kullanıcının DB'si boş olduğu için temizlemek sorun değil.
        # Temizleyelim ki mükerrer olmasın.
        print("Eski test verileri temizleniyor...")
        try:
            db.session.query(StatisticsEvent).delete()
            db.session.commit()
        except:
            db.session.rollback()

        vehicles = ["34 VP 5567", "06 AB 1234", "35 KS 889", "34 TB 112", "16 BUR 99"]
        people = ["Ahmet Yılmaz", "Ayşe Demir", "Mehmet Kaya", "Canan Çelik", "Ali Veli", "Burak Y.", "Selin K."]
        projects = [
            ("PRJ-001", "GSM Bakım", ["Kule Kontrol", "Klima Bakım", "Enerji Hat"]),
            ("PRJ-002", "Fiber Altyapı", ["Kazı", "Kablolama", "Terminasyon"]),
            ("PRJ-003", "Saha Keşif", ["Röperli Kroki", "Zemin Etüdü"]),
            ("PRJ-004", "Montaj", ["Anten Montaj", "Radio Link", "Kabinet"])
        ]
        
        # 2026 Yılı için veri (User 2026'da)
        start_date = date(2026, 1, 1)
        
        print("Yeni veriler üretiliyor (Yıl: 2026)...")
        new_events = []
        
        # 300 Adet rastgele iş kaydı
        for _ in range(300): 
            day_offset = random.randint(0, 364) # Tüm yıl
            event_date = start_date + timedelta(days=day_offset)
            
            # Gelecek tarihli veri olmasın (bugün 18 Ocak 2026 varsayılıyor user metadata'ya göre)
            # Metadata: 2026-01-18. Sadece ocak ayına veri basarsak grafikler boş kalır.
            # Ama user "Yıl Sonu İstatistiği" istiyor. Geleceği simüle edelim.
            
            p_code, p_name, sub_list = random.choice(projects)
            sub_name = random.choice(sub_list)
            person = random.choice(people)
            vehicle = random.choice(vehicles)
            
            is_revisit = random.choices([True, False], weights=[20, 80])[0] # %20 tekrar
            
            hours = random.randint(2, 10)
            # KM hesabı: araç çalıştıysa km yazar
            km = random.randint(20, 300)
            
            # Gelir hesabı (iş başına)
            revenue = random.randint(2000, 25000)

            evt = StatisticsEvent(
                event_type="job_completion",
                event_date=event_date,
                year=event_date.year,
                month=event_date.month,
                week=event_date.isocalendar()[1],
                
                person_name=person,
                vehicle_plate=vehicle,
                
                project_code=p_code,
                project_name=p_name,
                subproject_name=sub_name,
                
                hours_work=hours,
                km_driven=km,
                revenue=revenue,
                
                is_revisit=is_revisit,
                revisit_reason="Müşteri İsteği" if is_revisit else None,
                
                created_at=datetime.now() - timedelta(hours=random.randint(0, 24))
            )
            new_events.append(evt)
            
        db.session.add_all(new_events)
        db.session.commit()
        print(f"Toplam {len(new_events)} adet demo veri eklendi.")

if __name__ == "__main__":
    from datetime import datetime
    generate_data()
