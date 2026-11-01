import os
import io
import csv
from datetime import datetime, date, timedelta
from functools import wraps
import pytz
import jinja2
from flask import Flask, request, jsonify, render_template, send_from_directory, send_file, session, Response, make_response
from flask_cors import CORS

from config import Config
from models import db, User, Medicine, MedicineSchedule, ReminderLog, NotificationSubscription, AdherenceRecord
from scheduler import init_scheduler, update_adherence_summary, send_push_to_user, process_reminders_for_user
from vapid_manager import get_or_create_vapid_keys

def create_app():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    templates_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')

    app = Flask(__name__, static_folder=static_dir, template_folder=templates_dir)
    # Support index.html located either in templates/ or directly in the repository root
    app.jinja_loader = jinja2.ChoiceLoader([
        jinja2.FileSystemLoader(templates_dir),
        jinja2.FileSystemLoader(base_dir)
    ])
    app.config.from_object(Config)

    # Initialize CORS
    CORS(app, supports_credentials=True)

    # Initialize Database
    db.init_app(app)

    # Ensure tables exist
    with app.app_context():
        db.create_all()
        # Initialize VAPID keys if not present
        get_or_create_vapid_keys()

    # Initialize APScheduler (avoid double initialization in debug reload)
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        init_scheduler(app)

    # -------------------------------------------------------------
    # Helpers & Authentication Decorators
    # -------------------------------------------------------------
    def get_current_user():
        user_id = session.get('user_id')
        if not user_id:
            # Fallback for API clients with Authorization header "Bearer <id>"
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                try:
                    user_id = int(auth_header.split(' ')[1])
                except Exception:
                    user_id = None
        if user_id:
            return db.session.get(User, user_id)
        return None

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Unauthorized', 'message': 'Please login to access this resource.'}), 401
            return f(user, *args, **kwargs)
        return decorated_function

    def get_user_today(user):
        tz_str = user.timezone or app.config.get('DEFAULT_TIMEZONE', 'Asia/Kolkata')
        try:
            tz = pytz.timezone(tz_str)
        except Exception:
            tz = pytz.timezone('Asia/Kolkata')
        return datetime.now(tz).date()

    # -------------------------------------------------------------
    # Frontend & PWA Serving (Smart multi-path fallback)
    # -------------------------------------------------------------
    @app.route('/')
    def index():
        candidates = [
            os.path.join(base_dir, 'templates', 'index.html'),
            os.path.join(base_dir, 'index.html'),
        ]
        # Search recursively for index.html if not in standard locations
        for root, dirs, files in os.walk(base_dir):
            if 'index.html' in files:
                candidates.insert(0, os.path.join(root, 'index.html'))
                break

        for path in candidates:
            if os.path.isfile(path):
                return send_file(path)

        tree = []
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                tree.append(os.path.relpath(os.path.join(root, f), base_dir))
        return f"<h3>MediReminder: index.html not found on server</h3><p>Uploaded repository files:</p><pre>{chr(10).join(tree)}</pre>", 404

    @app.route('/manifest.json')
    def manifest():
        candidates = [
            os.path.join(base_dir, 'static', 'manifest.json'),
            os.path.join(base_dir, 'manifest.json'),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return send_file(c, mimetype='application/manifest+json')
        return jsonify({'error': 'manifest not found'}), 404

    @app.route('/sw.js')
    def service_worker():
        candidates = [
            os.path.join(base_dir, 'static', 'js', 'sw.js'),
            os.path.join(base_dir, 'static', 'sw.js'),
            os.path.join(base_dir, 'sw.js'),
        ]
        for c in candidates:
            if os.path.isfile(c):
                response = make_response(send_file(c, mimetype='application/javascript'))
                response.headers['Service-Worker-Allowed'] = '/'
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                return response
        return make_response("// Service worker placeholder", 200, {'Content-Type': 'application/javascript'})

    @app.route('/static/<path:filename>')
    def custom_static(filename):
        candidates = [
            os.path.join(base_dir, 'static', filename),
            os.path.join(base_dir, filename),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return send_file(c)
        return jsonify({'error': f'Static file {filename} not found'}), 404

    @app.errorhandler(500)
    def handle_500(e):
        import traceback
        return f"<h3>500 Internal Server Error</h3><pre>{traceback.format_exc()}</pre>", 500

    # -------------------------------------------------------------
    # Authentication Endpoints
    # -------------------------------------------------------------
    @app.route('/api/auth/register', methods=['POST'])
    def register():
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        full_name = data.get('full_name', '').strip()
        timezone = data.get('timezone', app.config.get('DEFAULT_TIMEZONE', 'Asia/Kolkata'))

        if not username or not email or not password or not full_name:
            return jsonify({'error': 'Validation Error', 'message': 'Username, email, password, and full name are required.'}), 400

        if len(password) < 6:
            return jsonify({'error': 'Validation Error', 'message': 'Password must be at least 6 characters long.'}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Conflict', 'message': 'Username is already taken.'}), 409

        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Conflict', 'message': 'Email is already registered.'}), 409

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            timezone=timezone
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Log user in
        session['user_id'] = user.id
        return jsonify({
            'message': 'Registration successful',
            'user': user.to_dict()
        }), 201

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        data = request.get_json() or {}
        login_id = data.get('username', '').strip()
        password = data.get('password', '')

        if not login_id or not password:
            return jsonify({'error': 'Validation Error', 'message': 'Username/email and password are required.'}), 400

        user = User.query.filter((User.username == login_id) | (User.email == login_id.lower())).first()
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid Credentials', 'message': 'Invalid username/email or password.'}), 401

        session['user_id'] = user.id
        # Run reminder sync for today
        process_reminders_for_user(user, app.config)

        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict()
        }), 200

    @app.route('/api/auth/logout', methods=['POST'])
    def logout():
        session.pop('user_id', None)
        return jsonify({'message': 'Logged out successfully'}), 200

    @app.route('/api/auth/me', methods=['GET'])
    def me():
        user = get_current_user()
        if not user:
            return jsonify({'authenticated': False}), 200
        return jsonify({
            'authenticated': True,
            'user': user.to_dict()
        }), 200

    @app.route('/api/auth/profile', methods=['PUT'])
    @login_required
    def update_profile(user):
        data = request.get_json() or {}
        full_name = data.get('full_name', '').strip()
        timezone = data.get('timezone', '').strip()

        if full_name:
            user.full_name = full_name
        if timezone:
            user.timezone = timezone

        db.session.commit()
        return jsonify({'message': 'Profile updated successfully', 'user': user.to_dict()}), 200

    @app.route('/api/auth/password', methods=['PUT'])
    @login_required
    def change_password(user):
        data = request.get_json() or {}
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')

        if not current_password or not new_password:
            return jsonify({'error': 'Validation Error', 'message': 'Current and new password are required.'}), 400

        if not user.check_password(current_password):
            return jsonify({'error': 'Forbidden', 'message': 'Current password is incorrect.'}), 400

        if len(new_password) < 6:
            return jsonify({'error': 'Validation Error', 'message': 'New password must be at least 6 characters.'}), 400

        user.set_password(new_password)
        db.session.commit()
        return jsonify({'message': 'Password changed successfully'}), 200

    # -------------------------------------------------------------
    # Dashboard API
    # -------------------------------------------------------------
    @app.route('/api/dashboard/summary', methods=['GET'])
    @login_required
    def dashboard_summary(user):
        # Refresh today's reminders
        process_reminders_for_user(user, app.config)

        tz_str = user.timezone or app.config.get('DEFAULT_TIMEZONE', 'Asia/Kolkata')
        try:
            user_tz = pytz.timezone(tz_str)
        except Exception:
            user_tz = pytz.timezone('Asia/Kolkata')
        now_user = datetime.now(user_tz)
        today = now_user.date()
        current_time_str = now_user.strftime('%H:%M')

        total_medicines = Medicine.query.filter_by(user_id=user.id, is_active=True).count()
        today_reminders = ReminderLog.query.filter_by(user_id=user.id, scheduled_date=today).order_by(ReminderLog.scheduled_time.asc()).all()

        total_scheduled = len(today_reminders)
        taken_count = sum(1 for r in today_reminders if r.status == 'taken')
        missed_count = sum(1 for r in today_reminders if r.status == 'missed')
        pending_count = sum(1 for r in today_reminders if r.status in ('pending', 'snoozed'))

        adherence_rate = round((taken_count / total_scheduled * 100.0), 1) if total_scheduled > 0 else 100.0

        # Enrich reminders with time-lock flags
        enriched_reminders = []
        upcoming_doses = []
        for r in today_reminders:
            rd = r.to_dict()
            is_future = (r.scheduled_time > current_time_str)
            rd['is_future'] = is_future
            rd['is_due'] = not is_future
            enriched_reminders.append(rd)
            if is_future and r.status == 'pending':
                upcoming_doses.append(r)

        next_dose = None
        if upcoming_doses:
            earliest = upcoming_doses[0]
            next_dose = f"{earliest.medicine.name} at {earliest.scheduled_time}"
        elif any(r.status == 'pending' for r in today_reminders):
            next_dose = "Doses due now for intake"
        else:
            next_dose = "All today's doses completed!"

        # Last 7 days history for weekly quick bar
        seven_days_ago = today - timedelta(days=6)
        recent_records = AdherenceRecord.query.filter(
            AdherenceRecord.user_id == user.id,
            AdherenceRecord.record_date >= seven_days_ago,
            AdherenceRecord.record_date <= today
        ).order_by(AdherenceRecord.record_date.asc()).all()

        records_map = {r.record_date: r for r in recent_records}
        weekly_stats = []
        for i in range(7):
            d = seven_days_ago + timedelta(days=i)
            rec = records_map.get(d)
            weekly_stats.append({
                'date': d.isoformat(),
                'day': d.strftime('%a'),
                'scheduled': rec.total_scheduled if rec else 0,
                'taken': rec.total_taken if rec else 0,
                'missed': rec.total_missed if rec else 0,
                'adherence_rate': rec.adherence_rate if rec else 0.0
            })

        return jsonify({
            'today': today.isoformat(),
            'current_time': current_time_str,
            'next_dose': next_dose,
            'total_medicines': total_medicines,
            'total_scheduled': total_scheduled,
            'taken_count': taken_count,
            'missed_count': missed_count,
            'pending_count': pending_count,
            'adherence_rate': adherence_rate,
            'reminders': enriched_reminders,
            'weekly_stats': weekly_stats
        }), 200

    # -------------------------------------------------------------
    # Medicine Management API (CRUD)
    # -------------------------------------------------------------
    @app.route('/api/medicines', methods=['GET'])
    @login_required
    def list_medicines(user):
        medicines = Medicine.query.filter_by(user_id=user.id).order_by(Medicine.created_at.desc()).all()
        return jsonify({'medicines': [m.to_dict() for m in medicines]}), 200

    @app.route('/api/medicines', methods=['POST'])
    @login_required
    def create_medicine(user):
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        dosage = data.get('dosage', '').strip()
        medicine_type = data.get('medicine_type', 'Tablet').strip()
        instructions = data.get('instructions', 'After food').strip()
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        notes = data.get('notes', '').strip()
        color = data.get('color', '#2563eb').strip()
        schedules_data = data.get('schedules', [])

        if not name or not dosage:
            return jsonify({'error': 'Validation Error', 'message': 'Medicine name and dosage are required.'}), 400

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else get_user_today(user)
        except Exception:
            start_date = get_user_today(user)

        end_date = None
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except Exception:
                end_date = None

        if end_date and end_date < start_date:
            return jsonify({'error': 'Validation Error', 'message': 'End date cannot be earlier than start date.'}), 400

        med = Medicine(
            user_id=user.id,
            name=name,
            dosage=dosage,
            medicine_type=medicine_type,
            instructions=instructions,
            start_date=start_date,
            end_date=end_date,
            notes=notes,
            color=color,
            is_active=True
        )
        db.session.add(med)
        db.session.flush()

        # Add Schedules
        if not schedules_data:
            schedules_data = [{'time': '08:00', 'days_of_week': 'ALL'}]

        for item in schedules_data:
            time_val = item.get('time') if isinstance(item, dict) else str(item)
            days_val = item.get('days_of_week', 'ALL') if isinstance(item, dict) else 'ALL'
            if time_val:
                sched = MedicineSchedule(
                    medicine_id=med.id,
                    time=time_val.strip(),
                    days_of_week=days_val.strip()
                )
                db.session.add(sched)

        db.session.commit()

        # Generate today's reminders immediately if eligible
        process_reminders_for_user(user, app.config)

        return jsonify({'message': 'Medicine created successfully', 'medicine': med.to_dict()}), 201

    @app.route('/api/medicines/<int:med_id>', methods=['GET'])
    @login_required
    def get_medicine(user, med_id):
        med = Medicine.query.filter_by(id=med_id, user_id=user.id).first()
        if not med:
            return jsonify({'error': 'Not Found', 'message': 'Medicine not found.'}), 404
        return jsonify({'medicine': med.to_dict()}), 200

    @app.route('/api/medicines/<int:med_id>', methods=['PUT'])
    @login_required
    def update_medicine(user, med_id):
        med = Medicine.query.filter_by(id=med_id, user_id=user.id).first()
        if not med:
            return jsonify({'error': 'Not Found', 'message': 'Medicine not found.'}), 404

        data = request.get_json() or {}
        med.name = data.get('name', med.name).strip()
        med.dosage = data.get('dosage', med.dosage).strip()
        med.medicine_type = data.get('medicine_type', med.medicine_type).strip()
        med.instructions = data.get('instructions', med.instructions).strip()
        med.notes = data.get('notes', med.notes).strip()
        med.color = data.get('color', med.color).strip()

        if 'start_date' in data and data['start_date']:
            try:
                med.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            except Exception:
                pass

        if 'end_date' in data:
            if data['end_date']:
                try:
                    med.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
                except Exception:
                    med.end_date = None
            else:
                med.end_date = None

        if 'is_active' in data:
            med.is_active = bool(data['is_active'])

        if 'schedules' in data:
            # Replace schedules
            MedicineSchedule.query.filter_by(medicine_id=med.id).delete()
            for item in data['schedules']:
                time_val = item.get('time') if isinstance(item, dict) else str(item)
                days_val = item.get('days_of_week', 'ALL') if isinstance(item, dict) else 'ALL'
                if time_val:
                    sched = MedicineSchedule(
                        medicine_id=med.id,
                        time=time_val.strip(),
                        days_of_week=days_val.strip()
                    )
                    db.session.add(sched)

        db.session.commit()
        process_reminders_for_user(user, app.config)

        return jsonify({'message': 'Medicine updated successfully', 'medicine': med.to_dict()}), 200

    @app.route('/api/medicines/<int:med_id>', methods=['DELETE'])
    @login_required
    def delete_medicine(user, med_id):
        med = Medicine.query.filter_by(id=med_id, user_id=user.id).first()
        if not med:
            return jsonify({'error': 'Not Found', 'message': 'Medicine not found.'}), 404

        db.session.delete(med)
        db.session.commit()
        today = get_user_today(user)
        update_adherence_summary(user.id, today)
        db.session.commit()

        return jsonify({'message': 'Medicine deleted successfully'}), 200

    @app.route('/api/medicines/<int:med_id>/toggle', methods=['PATCH'])
    @login_required
    def toggle_medicine_active(user, med_id):
        med = Medicine.query.filter_by(id=med_id, user_id=user.id).first()
        if not med:
            return jsonify({'error': 'Not Found', 'message': 'Medicine not found.'}), 404

        med.is_active = not med.is_active
        db.session.commit()
        return jsonify({'message': f"Medicine marked as {'active' if med.is_active else 'inactive'}", 'medicine': med.to_dict()}), 200

    # -------------------------------------------------------------
    # Reminder Logs & Actions API
    # -------------------------------------------------------------
    @app.route('/api/reminders/today', methods=['GET'])
    @login_required
    def get_today_reminders(user):
        tz_str = user.timezone or app.config.get('DEFAULT_TIMEZONE', 'Asia/Kolkata')
        try:
            user_tz = pytz.timezone(tz_str)
        except Exception:
            user_tz = pytz.timezone('Asia/Kolkata')
        now_user = datetime.now(user_tz)
        today = now_user.date()
        current_time_str = now_user.strftime('%H:%M')

        process_reminders_for_user(user, app.config)
        reminders = ReminderLog.query.filter_by(user_id=user.id, scheduled_date=today).order_by(ReminderLog.scheduled_time.asc()).all()
        enriched = []
        for r in reminders:
            rd = r.to_dict()
            rd['is_future'] = (r.scheduled_time > current_time_str)
            rd['is_due'] = not rd['is_future']
            enriched.append(rd)
        return jsonify({'reminders': enriched, 'current_time': current_time_str}), 200

    @app.route('/api/reminders/<int:reminder_id>/action', methods=['POST'])
    @login_required
    def handle_reminder_action(user, reminder_id):
        reminder = ReminderLog.query.filter_by(id=reminder_id, user_id=user.id).first()
        if not reminder:
            return jsonify({'error': 'Not Found', 'message': 'Reminder not found.'}), 404

        data = request.get_json() or {}
        action = data.get('action', '').lower()

        # Check current user local time
        tz_str = user.timezone or app.config.get('DEFAULT_TIMEZONE', 'Asia/Kolkata')
        try:
            user_tz = pytz.timezone(tz_str)
        except Exception:
            user_tz = pytz.timezone('Asia/Kolkata')
        now_user = datetime.now(user_tz)
        today_user = now_user.date()
        current_time_str = now_user.strftime('%H:%M')

        # Doses scheduled in future cannot be marked as taken/missed/snoozed before the registered time
        is_future = (reminder.scheduled_date > today_user) or (reminder.scheduled_date == today_user and reminder.scheduled_time > current_time_str)

        med_name = reminder.medicine.name if reminder.medicine else "Medicine"

        if action == 'take':
            if is_future:
                return jsonify({
                    'error': 'Too Early',
                    'message': f"Cannot mark {med_name} as taken before its registered time ({reminder.scheduled_time}). Doses can only be recorded once the scheduled time has arrived."
                }), 400
            reminder.status = 'taken'
            reminder.taken_at = datetime.now(pytz.utc)
        elif action == 'miss':
            if is_future:
                return jsonify({
                    'error': 'Too Early',
                    'message': f"Cannot mark {med_name} as missed before its registered time ({reminder.scheduled_time})."
                }), 400
            reminder.status = 'missed'
            reminder.taken_at = None
        elif action == 'snooze':
            if is_future:
                return jsonify({
                    'error': 'Too Early',
                    'message': f"Cannot snooze a dose before its registered time ({reminder.scheduled_time})."
                }), 400
            reminder.status = 'snoozed'
            # Push time forward by 15 mins
            try:
                h, m = map(int, reminder.scheduled_time.split(':'))
                now_dt = datetime(2026, 1, 1, h, m) + timedelta(minutes=15)
                reminder.scheduled_time = now_dt.strftime('%H:%M')
                reminder.notification_sent = False  # Allows another push reminder after snooze
            except Exception:
                pass
        elif action == 'reset':
            reminder.status = 'pending'
            reminder.taken_at = None
        else:
            return jsonify({'error': 'Invalid Action', 'message': 'Supported actions: take, miss, snooze, reset'}), 400

        db.session.commit()
        update_adherence_summary(user.id, reminder.scheduled_date)
        db.session.commit()

        return jsonify({'message': f'Reminder updated to {reminder.status}', 'reminder': reminder.to_dict()}), 200

    @app.route('/api/reminders/history', methods=['GET'])
    @login_required
    def get_reminder_history(user):
        status_filter = request.args.get('status')
        limit = min(int(request.args.get('limit', 50)), 200)

        query = ReminderLog.query.filter_by(user_id=user.id)
        if status_filter and status_filter != 'all':
            query = query.filter_by(status=status_filter)

        history = query.order_by(ReminderLog.scheduled_date.desc(), ReminderLog.scheduled_time.desc()).limit(limit).all()
        return jsonify({'history': [r.to_dict() for r in history]}), 200

    # -------------------------------------------------------------
    # Adherence Statistics & Reports API
    # -------------------------------------------------------------
    @app.route('/api/adherence/stats', methods=['GET'])
    @login_required
    def adherence_stats(user):
        today = get_user_today(user)
        update_adherence_summary(user.id, today)
        db.session.commit()

        # Monthly (last 30 days)
        thirty_days_ago = today - timedelta(days=29)
        month_records = AdherenceRecord.query.filter(
            AdherenceRecord.user_id == user.id,
            AdherenceRecord.record_date >= thirty_days_ago,
            AdherenceRecord.record_date <= today
        ).order_by(AdherenceRecord.record_date.asc()).all()

        record_map = {r.record_date: r for r in month_records}

        daily_series = []
        total_taken_sum = 0
        total_scheduled_sum = 0
        total_missed_sum = 0

        for i in range(30):
            d = thirty_days_ago + timedelta(days=i)
            rec = record_map.get(d)
            if rec:
                total_taken_sum += rec.total_taken
                total_scheduled_sum += rec.total_scheduled
                total_missed_sum += rec.total_missed
                rate = rec.adherence_rate
            else:
                rate = None  # No medicines scheduled

            daily_series.append({
                'date': d.isoformat(),
                'display': d.strftime('%b %d'),
                'rate': rate,
                'taken': rec.total_taken if rec else 0,
                'missed': rec.total_missed if rec else 0,
                'scheduled': rec.total_scheduled if rec else 0
            })

        overall_rate = round((total_taken_sum / total_scheduled_sum * 100.0), 1) if total_scheduled_sum > 0 else 100.0

        # Calculate current consecutive streak (days with 100% adherence or >=80%)
        current_streak = 0
        check_date = today
        while True:
            rec = record_map.get(check_date)
            if rec and rec.total_scheduled > 0 and rec.adherence_rate >= 80.0:
                current_streak += 1
                check_date -= timedelta(days=1)
            else:
                break

        return jsonify({
            'overall_rate': overall_rate,
            'total_scheduled': total_scheduled_sum,
            'total_taken': total_taken_sum,
            'total_missed': total_missed_sum,
            'current_streak': current_streak,
            'daily_series': daily_series
        }), 200

    @app.route('/api/adherence/export', methods=['GET'])
    @login_required
    def export_adherence_csv(user):
        logs = ReminderLog.query.filter_by(user_id=user.id).order_by(ReminderLog.scheduled_date.desc(), ReminderLog.scheduled_time.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Record ID', 'Medicine Name', 'Dosage', 'Medicine Type', 'Scheduled Date', 'Scheduled Time', 'Status', 'Taken At UTC', 'Notes'])

        for log in logs:
            med = log.medicine
            writer.writerow([
                log.id,
                med.name if med else 'Unknown',
                med.dosage if med else '',
                med.medicine_type if med else '',
                log.scheduled_date.isoformat(),
                log.scheduled_time,
                log.status.capitalize(),
                log.taken_at.strftime('%Y-%m-%d %H:%M:%S') if log.taken_at else 'N/A',
                log.notes or ''
            ])

        response = Response(output.getvalue(), mimetype='text/csv')
        response.headers['Content-Disposition'] = f'attachment; filename=medireminder_report_{user.username}_{date.today().isoformat()}.csv'
        return response

    # -------------------------------------------------------------
    # Notifications & Push API
    # -------------------------------------------------------------
    @app.route('/api/notifications/vapid-public-key', methods=['GET'])
    def get_vapid_public_key():
        keys = get_or_create_vapid_keys()
        return jsonify({'publicKey': keys.get('public_key')}), 200

    @app.route('/api/notifications/subscribe', methods=['POST'])
    @login_required
    def subscribe_push(user):
        data = request.get_json() or {}
        endpoint = data.get('endpoint')
        keys = data.get('keys', {})
        p256dh = keys.get('p256dh')
        auth = keys.get('auth')

        if not endpoint or not p256dh or not auth:
            return jsonify({'error': 'Validation Error', 'message': 'Missing push subscription parameters.'}), 400

        sub = NotificationSubscription.query.filter_by(endpoint=endpoint).first()
        if not sub:
            sub = NotificationSubscription(
                user_id=user.id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                user_agent=request.headers.get('User-Agent', '')[:250]
            )
            db.session.add(sub)
        else:
            sub.user_id = user.id
            sub.p256dh = p256dh
            sub.auth = auth
            sub.last_used_at = datetime.utcnow()

        db.session.commit()
        return jsonify({'message': 'Push notification subscription registered successfully.'}), 201

    @app.route('/api/notifications/unsubscribe', methods=['POST'])
    @login_required
    def unsubscribe_push(user):
        data = request.get_json() or {}
        endpoint = data.get('endpoint')
        if endpoint:
            NotificationSubscription.query.filter_by(endpoint=endpoint, user_id=user.id).delete()
            db.session.commit()
        return jsonify({'message': 'Unsubscribed successfully.'}), 200

    @app.route('/api/notifications/test', methods=['POST'])
    @login_required
    def test_notification(user):
        payload = {
            "title": "MediReminder Test Alert 🔔",
            "body": f"Hello {user.full_name}! Web Push and Service Worker notifications are active and operational.",
            "icon": "/static/icons/icon-192.png",
            "badge": "/static/icons/icon-192.png",
            "tag": "medireminder-test",
            "data": {
                "url": "/#settings",
                "test": True
            }
        }
        sent = send_push_to_user(user.id, payload, app.config)
        if sent > 0:
            return jsonify({'message': f'Test push notification sent successfully to {sent} device(s).'}), 200
        else:
            return jsonify({
                'warning': 'No active push subscription found.',
                'message': 'Please allow push notification permissions in browser Settings to receive live alerts.'
            }), 200

    # -------------------------------------------------------------
    # Demo Data Seeding API (One-click realistic sample data)
    # -------------------------------------------------------------
    @app.route('/api/demo/seed', methods=['POST'])
    @login_required
    def seed_user_demo_data(user):
        from seed_demo import seed_data_for_user
        count = seed_data_for_user(user.id, app.config)
        return jsonify({'message': f'Demo data successfully seeded ({count} medicines and past 14 days adherence records created).'}), 200

    return app

app = create_app()

if __name__ == '__main__':
    # Default port 5000, host 0.0.0.0
    app.run(host='0.0.0.0', port=5000, debug=True)
