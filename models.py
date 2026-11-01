from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    timezone = db.Column(db.String(50), default='Asia/Kolkata', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    medicines = db.relationship('Medicine', backref='user', cascade='all, delete-orphan', lazy=True)
    notification_subscriptions = db.relationship('NotificationSubscription', backref='user', cascade='all, delete-orphan', lazy=True)
    reminder_logs = db.relationship('ReminderLog', backref='user', cascade='all, delete-orphan', lazy=True)
    adherence_records = db.relationship('AdherenceRecord', backref='user', cascade='all, delete-orphan', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'timezone': self.timezone,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Medicine(db.Model):
    __tablename__ = 'medicines'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    dosage = db.Column(db.String(60), nullable=False)  # e.g., "500 mg", "10 ml", "1 capsule"
    medicine_type = db.Column(db.String(40), default='Tablet', nullable=False)  # Tablet, Capsule, Syrup, Injection, Drops, Inhaler, Topical, Other
    instructions = db.Column(db.String(100), default='After food', nullable=False)  # Before food, After food, With food, Empty stomach, Bedtime, As needed
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=True)  # Null indicates ongoing / chronic
    notes = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(20), default='#2563eb')
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    schedules = db.relationship('MedicineSchedule', backref='medicine', cascade='all, delete-orphan', lazy=True)
    reminder_logs = db.relationship('ReminderLog', backref='medicine', cascade='all, delete-orphan', lazy=True)

    def to_dict(self, include_schedules=True):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'dosage': self.dosage,
            'medicine_type': self.medicine_type,
            'instructions': self.instructions,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'notes': self.notes or '',
            'color': self.color or '#2563eb',
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_schedules:
            data['schedules'] = [s.to_dict() for s in self.schedules]
        return data


class MedicineSchedule(db.Model):
    __tablename__ = 'medicine_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='CASCADE'), nullable=False, index=True)
    time = db.Column(db.String(5), nullable=False)  # Format HH:MM (24-hr)
    days_of_week = db.Column(db.String(60), default='ALL', nullable=False)  # 'ALL' or comma-separated 'MON,TUE,WED...'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'medicine_id': self.medicine_id,
            'time': self.time,
            'days_of_week': self.days_of_week,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ReminderLog(db.Model):
    __tablename__ = 'reminder_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='CASCADE'), nullable=False, index=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('medicine_schedules.id', ondelete='SET NULL'), nullable=True)
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    scheduled_time = db.Column(db.String(5), nullable=False)  # HH:MM
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, taken, missed, snoozed
    taken_at = db.Column(db.DateTime, nullable=True)
    notification_sent = db.Column(db.Boolean, default=False, nullable=False)
    notification_sent_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'medicine_id', 'scheduled_date', 'scheduled_time', name='uq_user_medicine_schedule_time'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'medicine_id': self.medicine_id,
            'medicine_name': self.medicine.name if self.medicine else 'Unknown',
            'dosage': self.medicine.dosage if self.medicine else '',
            'medicine_type': self.medicine.medicine_type if self.medicine else 'Tablet',
            'instructions': self.medicine.instructions if self.medicine else '',
            'color': self.medicine.color if self.medicine else '#2563eb',
            'schedule_id': self.schedule_id,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'scheduled_time': self.scheduled_time,
            'status': self.status,
            'taken_at': self.taken_at.isoformat() if self.taken_at else None,
            'notification_sent': self.notification_sent,
            'notification_sent_at': self.notification_sent_at.isoformat() if self.notification_sent_at else None,
            'notes': self.notes or '',
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class NotificationSubscription(db.Model):
    __tablename__ = 'notification_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    endpoint = db.Column(db.Text, unique=True, nullable=False)
    p256dh = db.Column(db.Text, nullable=False)
    auth = db.Column(db.Text, nullable=False)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'endpoint': self.endpoint,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class AdherenceRecord(db.Model):
    __tablename__ = 'adherence_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    record_date = db.Column(db.Date, nullable=False, index=True)
    total_scheduled = db.Column(db.Integer, default=0, nullable=False)
    total_taken = db.Column(db.Integer, default=0, nullable=False)
    total_missed = db.Column(db.Integer, default=0, nullable=False)
    adherence_rate = db.Column(db.Float, default=0.0, nullable=False)  # 0.0 to 100.0%
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'record_date', name='uq_user_record_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'record_date': self.record_date.isoformat() if self.record_date else None,
            'total_scheduled': self.total_scheduled,
            'total_taken': self.total_taken,
            'total_missed': self.total_missed,
            'adherence_rate': round(self.adherence_rate, 1),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
