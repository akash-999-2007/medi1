import json
import logging
from datetime import datetime, date, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from pywebpush import webpush, WebPushException
from models import db, User, Medicine, MedicineSchedule, ReminderLog, NotificationSubscription, AdherenceRecord
from vapid_manager import get_or_create_vapid_keys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MediReminder.Scheduler")

scheduler = None

def get_day_abbr(dt: date) -> str:
    """Return 3-letter uppercase day of week, e.g., MON, TUE."""
    days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    return days[dt.weekday()]

def update_adherence_summary(user_id: int, target_date: date):
    """Recalculate and persist the daily adherence rate for a given user and date."""
    logs = ReminderLog.query.filter_by(user_id=user_id, scheduled_date=target_date).all()
    total_scheduled = len(logs)
    if total_scheduled == 0:
        return None
        
    total_taken = sum(1 for log in logs if log.status == 'taken')
    total_missed = sum(1 for log in logs if log.status == 'missed')
    
    # Adherence rate calculation
    adherence_rate = (total_taken / total_scheduled) * 100.0 if total_scheduled > 0 else 100.0
    
    record = AdherenceRecord.query.filter_by(user_id=user_id, record_date=target_date).first()
    if not record:
        record = AdherenceRecord(
            user_id=user_id,
            record_date=target_date,
            total_scheduled=total_scheduled,
            total_taken=total_taken,
            total_missed=total_missed,
            adherence_rate=round(adherence_rate, 1)
        )
        db.session.add(record)
    else:
        record.total_scheduled = total_scheduled
        record.total_taken = total_taken
        record.total_missed = total_missed
        record.adherence_rate = round(adherence_rate, 1)
        record.updated_at = datetime.utcnow()
        
    return record

def send_push_to_user(user_id: int, payload_dict: dict, app_config):
    """Deliver a Web Push notification to all registered subscriptions for a user."""
    subscriptions = NotificationSubscription.query.filter_by(user_id=user_id).all()
    if not subscriptions:
        logger.info(f"User {user_id} has no active push notification subscriptions.")
        return 0

    keys = get_or_create_vapid_keys()
    private_key = keys.get('private_key') or app_config.get('VAPID_PRIVATE_KEY')
    claims = app_config.get('VAPID_CLAIMS', {"sub": "mailto:adherence@medireminder.idp2502.edu"})
    
    payload_str = json.dumps(payload_dict)
    sent_count = 0
    expired_ids = []

    for sub in subscriptions:
        sub_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
        }
        try:
            webpush(
                subscription_info=sub_info,
                data=payload_str,
                vapid_private_key=private_key,
                vapid_claims=claims,
                ttl=3600
            )
            sent_count += 1
            sub.last_used_at = datetime.utcnow()
        except WebPushException as ex:
            logger.warning(f"WebPush failed for endpoint {sub.id}: {ex}")
            # If 404 or 410, subscription is no longer valid or unsubscribed
            if ex.response is not None and ex.response.status_code in (404, 410):
                logger.info(f"Pruning expired push subscription ID {sub.id}")
                expired_ids.append(sub.id)
        except Exception as e:
            logger.error(f"Unexpected push delivery error: {e}")

    if expired_ids:
        NotificationSubscription.query.filter(NotificationSubscription.id.in_(expired_ids)).delete(synchronize_session=False)
        db.session.commit()

    return sent_count

def process_reminders_for_user(user: User, app_config):
    """
    Core scheduler logic for a single user:
    1. Determine user local date/time in user timezone (Asia/Kolkata default).
    2. Ensure ReminderLog entries exist for today's active scheduled medicines.
    3. Dispatch Web Push notifications for reminders due at this minute.
    4. Auto-mark overdue pending reminders as missed.
    5. Update daily adherence summary.
    """
    user_tz_str = user.timezone or app_config.get('DEFAULT_TIMEZONE', 'Asia/Kolkata')
    try:
        user_tz = pytz.timezone(user_tz_str)
    except Exception:
        user_tz = pytz.timezone('Asia/Kolkata')

    now_user = datetime.now(user_tz)
    today_user = now_user.date()
    current_time_str = now_user.strftime('%H:%M')
    current_day_abbr = get_day_abbr(today_user)
    
    # 1. Fetch active medicines within date range
    medicines = Medicine.query.filter(
        Medicine.user_id == user.id,
        Medicine.is_active == True,
        Medicine.start_date <= today_user
    ).all()

    for med in medicines:
        if med.end_date and med.end_date < today_user:
            continue  # Medication course finished

        for schedule in med.schedules:
            # Check day of week match
            days_allowed = [d.strip().upper() for d in schedule.days_of_week.split(',')]
            if 'ALL' not in days_allowed and current_day_abbr not in days_allowed:
                continue

            # Check if reminder log already exists for today & this time
            existing_log = ReminderLog.query.filter_by(
                user_id=user.id,
                medicine_id=med.id,
                scheduled_date=today_user,
                scheduled_time=schedule.time
            ).first()

            if not existing_log:
                new_log = ReminderLog(
                    user_id=user.id,
                    medicine_id=med.id,
                    schedule_id=schedule.id,
                    scheduled_date=today_user,
                    scheduled_time=schedule.time,
                    status='pending',
                    notification_sent=False
                )
                db.session.add(new_log)
    
    db.session.commit()

    # 2. Find reminders due at this specific minute needing push notification
    due_reminders = ReminderLog.query.filter(
        ReminderLog.user_id == user.id,
        ReminderLog.scheduled_date == today_user,
        ReminderLog.scheduled_time == current_time_str,
        ReminderLog.notification_sent == False,
        ReminderLog.status.in_(['pending', 'snoozed'])
    ).all()

    for reminder in due_reminders:
        med = reminder.medicine
        med_name = med.name if med else "Medicine"
        dosage = med.dosage if med else ""
        instructions = med.instructions if med else ""
        
        payload = {
            "title": f"MediReminder: {med_name}",
            "body": f"Time to take {dosage} of {med_name} ({instructions}). Tap to mark as taken.",
            "icon": "/static/icons/icon-192.png",
            "badge": "/static/icons/icon-192.png",
            "tag": f"medireminder-{reminder.id}",
            "data": {
                "reminder_id": reminder.id,
                "medicine_id": reminder.medicine_id,
                "scheduled_time": reminder.scheduled_time,
                "url": "/#dashboard"
            },
            "actions": [
                {"action": "take", "title": "Mark as Taken"},
                {"action": "snooze", "title": "Snooze 15m"}
            ]
        }
        
        sent = send_push_to_user(user.id, payload, app_config)
        reminder.notification_sent = True
        reminder.notification_sent_at = datetime.utcnow()
        logger.info(f"Reminder {reminder.id} push notification dispatched to {sent} devices for user {user.username}")

    # 3. Auto-mark missed reminders: pending and more than MISSED_THRESHOLD_MINUTES past scheduled time
    threshold_minutes = app_config.get('MISSED_THRESHOLD_MINUTES', 120)
    pending_today = ReminderLog.query.filter(
        ReminderLog.user_id == user.id,
        ReminderLog.scheduled_date == today_user,
        ReminderLog.status == 'pending'
    ).all()

    for p in pending_today:
        try:
            sched_hour, sched_min = map(int, p.scheduled_time.split(':'))
            scheduled_dt = now_user.replace(hour=sched_hour, minute=sched_min, second=0, microsecond=0)
            diff = (now_user - scheduled_dt).total_seconds() / 60.0
            if diff >= threshold_minutes:
                p.status = 'missed'
                p.notes = f"Auto-marked as missed after {int(diff)} minutes"
                logger.info(f"Reminder {p.id} ({p.medicine.name}) automatically marked as missed.")
        except Exception as err:
            logger.error(f"Error checking missed status for reminder {p.id}: {err}")

    db.session.commit()

    # 4. Update daily adherence record
    update_adherence_summary(user.id, today_user)
    db.session.commit()

def run_scheduler_tick(app):
    """Periodic tick called by APScheduler within Flask application context."""
    with app.app_context():
        try:
            users = User.query.all()
            for user in users:
                process_reminders_for_user(user, app.config)
        except Exception as e:
            logger.error(f"Error during scheduler tick: {e}", exc_info=True)
            db.session.rollback()

def init_scheduler(app):
    """Initialize and start the BackgroundScheduler."""
    global scheduler
    if scheduler is not None and scheduler.running:
        return scheduler

    scheduler = BackgroundScheduler(daemon=True)
    interval = app.config.get('SCHEDULER_INTERVAL_SECONDS', 60)
    scheduler.add_job(
        func=run_scheduler_tick,
        args=[app],
        trigger='interval',
        seconds=interval,
        id='medireminder_tick',
        name='MediReminder Check & Push Dispatcher',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"MediReminder APScheduler started. Interval: {interval}s")
    return scheduler
