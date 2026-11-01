import os
import random
from datetime import datetime, date, timedelta
from models import db, User, Medicine, MedicineSchedule, ReminderLog, AdherenceRecord
from config import Config
from scheduler import update_adherence_summary

SAMPLE_MEDICINES = [
    {
        "name": "Metformin HCl",
        "dosage": "500 mg",
        "medicine_type": "Tablet",
        "instructions": "After breakfast & dinner with a glass of water",
        "color": "#2563eb",  # Primary Blue
        "schedules": ["08:30", "20:30"],
        "notes": "Prescribed for blood sugar management."
    },
    {
        "name": "Atorvastatin",
        "dosage": "20 mg",
        "medicine_type": "Tablet",
        "instructions": "Take at bedtime",
        "color": "#7c3aed",  # Purple
        "schedules": ["21:30"],
        "notes": "Cholesterol control regimen."
    },
    {
        "name": "Amoxicillin & Clavulanate",
        "dosage": "625 mg",
        "medicine_type": "Capsule",
        "instructions": "After lunch (course of 5 days)",
        "color": "#059669",  # Emerald Green
        "schedules": ["14:00"],
        "notes": "Antibiotic regimen. Complete entire course."
    },
    {
        "name": "Cetirizine HCl",
        "dosage": "10 mg",
        "medicine_type": "Tablet",
        "instructions": "Before sleep if allergic symptoms arise",
        "color": "#d97706",  # Amber
        "schedules": ["22:00"],
        "notes": "Allergy and dust sensitivity relief."
    },
    {
        "name": "Vitamin D3 & B12",
        "dosage": "1 Softgel",
        "medicine_type": "Capsule",
        "instructions": "Morning after breakfast",
        "color": "#0284c7",  # Sky Blue
        "schedules": ["09:00"],
        "notes": "Bone health and energy supplement."
    }
]

def seed_data_for_user(user_id: int, app_config=None):
    """Seed sample medicines and 14 days of adherence logs for a specific user."""
    user = db.session.get(User, user_id)
    if not user:
        return 0

    today = date.today()
    created_meds = []

    # Check if medicines already exist to prevent duplicate creation
    existing_med_names = {m.name for m in Medicine.query.filter_by(user_id=user.id).all()}

    for sample in SAMPLE_MEDICINES:
        if sample["name"] in existing_med_names:
            med = Medicine.query.filter_by(user_id=user.id, name=sample["name"]).first()
        else:
            med = Medicine(
                user_id=user.id,
                name=sample["name"],
                dosage=sample["dosage"],
                medicine_type=sample["medicine_type"],
                instructions=sample["instructions"],
                start_date=today - timedelta(days=20),
                end_date=today + timedelta(days=40),
                notes=sample["notes"],
                color=sample["color"],
                is_active=True
            )
            db.session.add(med)
            db.session.flush()

            for sched_time in sample["schedules"]:
                ms = MedicineSchedule(
                    medicine_id=med.id,
                    time=sched_time,
                    days_of_week="ALL"
                )
                db.session.add(ms)

        created_meds.append(med)

    db.session.commit()

    # Generate past 14 days of realistic logs
    # Simulated high adherence (approx 90% taken, 10% missed)
    random.seed(42)

    for days_back in range(14, 0, -1):
        past_date = today - timedelta(days=days_back)
        for med in created_meds:
            for sched in med.schedules:
                existing = ReminderLog.query.filter_by(
                    user_id=user.id,
                    medicine_id=med.id,
                    scheduled_date=past_date,
                    scheduled_time=sched.time
                ).first()

                if not existing:
                    # 90% chance taken, 10% missed
                    is_taken = random.random() < 0.90
                    status = "taken" if is_taken else "missed"
                    taken_dt = datetime.combine(past_date, datetime.strptime(sched.time, "%H:%M").time()) + timedelta(minutes=random.randint(2, 25)) if is_taken else None
                    
                    log = ReminderLog(
                        user_id=user.id,
                        medicine_id=med.id,
                        schedule_id=sched.id,
                        scheduled_date=past_date,
                        scheduled_time=sched.time,
                        status=status,
                        taken_at=taken_dt,
                        notification_sent=True,
                        notification_sent_at=datetime.combine(past_date, datetime.strptime(sched.time, "%H:%M").time()),
                        notes="Sample demonstration record"
                    )
                    db.session.add(log)

        db.session.commit()
        update_adherence_summary(user.id, past_date)

    # Also generate today's reminders (some taken, some pending)
    for med in created_meds:
        for sched in med.schedules:
            existing = ReminderLog.query.filter_by(
                user_id=user.id,
                medicine_id=med.id,
                scheduled_date=today,
                scheduled_time=sched.time
            ).first()

            if not existing:
                # If scheduled earlier than now, mark taken or pending
                log = ReminderLog(
                    user_id=user.id,
                    medicine_id=med.id,
                    schedule_id=sched.id,
                    scheduled_date=today,
                    scheduled_time=sched.time,
                    status="pending",
                    notification_sent=False
                )
                db.session.add(log)

    db.session.commit()
    update_adherence_summary(user.id, today)
    db.session.commit()

    return len(created_meds)

def main():
    from app import create_app
    app = create_app()
    with app.app_context():
        print("[MediReminder] Seeding sample demo user and data...")
        demo_user = User.query.filter_by(username="demo_patient").first()
        if not demo_user:
            demo_user = User(
                username="demo_patient",
                email="patient.demo@medireminder.edu",
                full_name="Akash Sharma",
                timezone="Asia/Kolkata"
            )
            demo_user.set_password("demo1234")
            db.session.add(demo_user)
            db.session.commit()
            print("Created default demo user: username='demo_patient', password='demo1234'")
        else:
            print("Demo user 'demo_patient' already exists.")

        count = seed_data_for_user(demo_user.id)
        print(f"Successfully seeded {count} medicines with 14 days of realistic adherence logs!")

if __name__ == "__main__":
    main()
