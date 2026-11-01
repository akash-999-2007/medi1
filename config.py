import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'medireminder-idp2502-supersecret-production-key-2026')
    
    # Database: SQLite for development, seamlessly compatible with PostgreSQL via DATABASE_URL
    database_url = os.environ.get('DATABASE_URL', f"sqlite:///{BASE_DIR / 'medireminder.db'}")
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Application Defaults
    DEFAULT_TIMEZONE = os.environ.get('DEFAULT_TIMEZONE', 'Asia/Kolkata')
    
    # Web Push / VAPID Configuration
    VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
    VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
    VAPID_CLAIMS = {
        "sub": os.environ.get('VAPID_CLAIM_EMAIL', 'mailto:adherence@medireminder.idp2502.edu')
    }
    
    # Scheduler interval in seconds (checks every minute)
    SCHEDULER_INTERVAL_SECONDS = int(os.environ.get('SCHEDULER_INTERVAL_SECONDS', 60))
    
    # Missed threshold: auto-mark pending dose as missed after N minutes past scheduled time
    MISSED_THRESHOLD_MINUTES = int(os.environ.get('MISSED_THRESHOLD_MINUTES', 120))
