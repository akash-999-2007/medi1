# MediReminder – Smart Medicine Reminder and Adherence Tracking System
### IDP2502 College Project

MediReminder is an end-to-end, modern, responsive healthcare application built to help patients maintain consistent medication adherence. It features an automated reminder scheduler, real browser Web Push notifications with interactive action buttons, intake logging, adherence analytics charts, offline-ready Progressive Web App (PWA) capabilities, and clinical CSV reports.

---

## 🌟 Key Features

- **Responsive Healthcare Dashboard:** Clean modern blue/emerald design with live KPI counters (Active Medicines, Scheduled Today, Taken, Missed, Pending, and Daily Adherence %).
- **Smart Reminder Scheduling:** Background APScheduler engine runs automatically every minute, calculates doses based on user timezone (`Asia/Kolkata` default), and prevents duplicate notifications.
- **Web Push Notifications:** Native browser push notifications powered by VAPID (ECDSA P-256) and Service Workers (`sw.js`). Includes interactive action buttons (**"Mark as Taken"** and **"Snooze 15m"**) that record doses without needing the tab open.
- **Complete Medication CRUD:** Add, edit, delete, and toggle medications. Supports dosages, form factor types (Tablet, Capsule, Syrup, Injection, Drops, Inhaler, Topical), meal instructions, color tags, and multi-schedule times (e.g. 08:30 and 20:30).
- **Adherence Analytics & Streak Tracking:**
  - 7-day weekly adherence bar chart.
  - 30-day compliance trend area chart.
  - Taken vs. Missed proportional doughnut chart.
  - Adherence streak counter (consecutive days with $\ge 80\%$ adherence).
- **Audit Logs & Clinical Export:** Download medication intake logs as formatted CSV reports for doctors and healthcare providers.
- **Progressive Web App (PWA):** Installable on Android mobile devices and desktop browsers with app icon, splash experience, and offline asset caching.
- **Demonstration Ready:** Built-in one-click demo data seeder (`seed_demo.py`) that loads a realistic patient account with 5 medications and 14 days of realistic historical adherence logs.

---

## 📁 Project Structure & File Guide

```
MediReminder/
├── app.py                     # Flask application factory, routes, REST API endpoints, session auth
├── config.py                  # App configuration, database URI, VAPID settings, timezone defaults
├── models.py                  # SQLAlchemy ORM database models (Users, Medicines, Schedules, ReminderLogs, etc.)
├── scheduler.py               # APScheduler background engine, timezone handling, push dispatcher
├── vapid_manager.py           # VAPID ECDSA P-256 key pair generator and manager
├── seed_demo.py               # Demonstration script generating sample user and 14-day adherence data
├── test_app.py                # Automated 10-point test suite for APIs and endpoints
├── requirements.txt           # Python package dependencies
├── .env                       # Local active environment configuration
├── .env.example               # Example environment template
├── static/
│   ├── css/
│   │   └── style.css          # Healthcare UI design system (colors, cards, responsive layout)
│   ├── js/
│   │   ├── app.js             # Client SPA controller (Dashboard, CRUD, Charts, UI interactions)
│   │   ├── notifications.js   # Push subscription manager and Web Audio chime synthesizer
│   │   └── sw.js              # Service Worker (offline caching, push handlers, action clicks)
│   ├── icons/
│   │   ├── icon-192.png       # PWA app icon 192x192
│   │   ├── icon-512.png       # PWA app icon 512x512
│   │   ├── icon.svg           # Scalable vector medical icon
│   │   └── favicon.ico        # Browser favicon
│   └── manifest.json          # PWA web app manifest
├── templates/
│   └── index.html             # Main dashboard template with responsive sidebar and modals
└── docs/
    └── PROJECT_REPORT_IDP2502.md # Complete college project report with UML diagrams & test cases
```

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
- Python 3.10 or higher (tested on Python 3.14).
- Modern web browser (Chrome, Edge, Firefox, or Brave).

### 2. Setup Virtual Environment & Install Dependencies
Open PowerShell or your command terminal in the project directory:

```powershell
# Create Python virtual environment
python -m venv venv

# Activate virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# (On Command Prompt: .\venv\Scripts\activate.bat)
# (On macOS/Linux: source venv/bin/activate)

# Install required packages
pip install -r requirements.txt
```

### 3. Initialize Database & Seed Demonstration Data
Run the demo seeder to create the database tables, generate VAPID keys, and create the default test patient:

```powershell
python seed_demo.py
```

*Output:*
```
[VAPID] Generated new Web Push VAPID keypair in vapid_keys.json
[MediReminder] Seeding sample demo user and data...
Created default demo user: username='demo_patient', password='demo1234'
Successfully seeded 5 medicines with 14 days of realistic adherence logs!
```

### 4. Run the Automated Test Suite
Verify that all 10 core system modules and APIs are functioning:

```powershell
python test_app.py
```

### 5. Start the Application Server
Launch the Flask development server:

```powershell
python app.py
```

Open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🔑 Demonstration Credentials

| Role | Username | Password | Full Name | Timezone |
| :--- | :--- | :--- | :--- | :--- |
| **Demo Patient** | `demo_patient` | `demo1234` | Akash Sharma | Asia/Kolkata |

> **Pro-Tip:** On the Sign In page, you can simply click the **"⚡ Fill Demo Credentials"** button to populate the inputs instantly!

---

## 🔔 Testing Real Browser Push Notifications

The Web Push API requires a **Secure Context**:
- Browsers allow push notifications on **`http://localhost`** and **`http://127.0.0.1`** automatically for development.
- For remote devices (e.g., your Android phone), the site must be served over **HTTPS** (see deployment section below).

### Step-by-Step Test:
1. Log in to MediReminder at `http://127.0.0.1:5000`.
2. Navigate to **"Settings & Push"** in the sidebar.
3. Click **"Enable Web Push Notifications"**.
4. When your browser displays the permission dialog (`"127.0.0.1:5000 wants to Show notifications"`), click **"Allow"**.
5. The status badge will change to **"Active & Subscribed"**.
6. Click the **"Send Immediate Test Push Alert 🔔"** button.
   - You will hear a pleasant harmonic chime synthesized via Web Audio API.
   - A system push notification will appear on your desktop with the MediReminder icon and text!
7. Scheduled reminders that become due at the current minute will automatically trigger background push notifications without needing manual clicks.

---

## 📱 Installing the PWA on Android Devices

1. **Option A: Same Wi-Fi Network (Development)**
   - Find your computer's local IP address (e.g., `192.168.1.5`).
   - Run Flask with SSL, or use a secure tunnel such as **Cloudflare Tunnel** or **Ngrok**:
     ```bash
     ngrok http 5000
     ```
   - Open the resulting `https://...ngrok-free.app` URL on your Android Chrome browser.
2. **Option B: Chrome Install Prompt**
   - Tap the three dots menu (⋮) in Chrome on Android.
   - Tap **"Install app"** or **"Add to Home screen"**.
   - MediReminder will install as a standalone application on your Android launcher with the medical badge icon, custom splash screen, and bottom navigation bar!

---

## 🌐 Production Deployment with HTTPS & PostgreSQL

### 1. Database Migration to PostgreSQL
MediReminder is built with SQLAlchemy. To switch from SQLite to PostgreSQL:
1. In `.env`, update the `DATABASE_URL`:
   ```ini
   DATABASE_URL=postgresql://user:password@localhost:5432/medireminder_db
   ```
2. Restart the app. SQLAlchemy will automatically create all tables in PostgreSQL.

### 2. HTTPS Deployment with Nginx & Gunicorn
Web Push and Service Workers require HTTPS in production:

1. **WSGI Server (Gunicorn):**
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 127.0.0.1:5000 "app:create_app()"
   ```

2. **Nginx Reverse Proxy Configuration:**
   ```nginx
   server {
       server_name medireminder.yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. **Free SSL Certificate via Certbot:**
   ```bash
   sudo certbot --nginx -d medireminder.yourdomain.com
   ```

---

## 📊 College Project Documentation

Comprehensive academic documentation has been compiled in [`docs/PROJECT_REPORT_IDP2502.md`](file:///c:/Users/venka/OneDrive/Desktop/akash%20game/docs/PROJECT_REPORT_IDP2502.md) including:
- Project Abstract & Objectives
- Problem Statement & Comparison Table
- Hardware & Software Specifications
- System Architecture Diagram
- UML Use-Case Diagram
- DFD Level 0 & Level 1 Diagrams
- ER Diagram with Cardinalities
- Module Descriptions & Test Cases (TC-01 to TC-10)
- Future Enhancements & Conclusion

---

## 📜 License & Acknowledgements
- Developed for the **IDP2502** Interdisciplinary Project.
- Built with Python Flask, Bootstrap 5, Chart.js, and Web Push API.
