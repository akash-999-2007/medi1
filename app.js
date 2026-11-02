// MediReminder Application Core Logic (IDP2502)
class MediReminderApp {
  constructor() {
    this.currentUser = null;
    this.currentView = 'dashboard';
    this.weeklyChart = null;
    this.monthlyChart = null;
    this.doughnutChart = null;
    this.deferredInstallPrompt = null;
    this.medicinesList = [];
    this.todayReminders = [];

    this.init();
  }

  async init() {
    this.setupEventListeners();
    this.setupPWAInstall();
    await this.checkAuthStatus();
    if (window.notificationManager) {
      await window.notificationManager.init();
      this.updateNotificationUI();
    }
  }

  // -------------------------------------------------------------
  // Event Listeners & Router Setup
  // -------------------------------------------------------------
  setupEventListeners() {
    // Nav links router
    document.querySelectorAll('[data-view-target]').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const view = link.getAttribute('data-view-target');
        this.navigateTo(view);
      });
    });

    // Mobile FAB
    const fabAdd = document.getElementById('fabAddMed');
    if (fabAdd) {
      fabAdd.addEventListener('click', () => this.openMedicineModal());
    }

    // Auth forms
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
      loginForm.addEventListener('submit', (e) => this.handleLogin(e));
    }

    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
      registerForm.addEventListener('submit', (e) => this.handleRegister(e));
    }

    // Medicine form
    const medForm = document.getElementById('medicineForm');
    if (medForm) {
      medForm.addEventListener('submit', (e) => this.handleSaveMedicine(e));
    }

    // Add schedule time pill button in modal
    const btnAddTime = document.getElementById('btnAddScheduleTime');
    if (btnAddTime) {
      btnAddTime.addEventListener('click', () => this.addScheduleTimeInput());
    }

    // Profile & Password forms
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
      profileForm.addEventListener('submit', (e) => this.handleUpdateProfile(e));
    }

    const passwordForm = document.getElementById('passwordForm');
    if (passwordForm) {
      passwordForm.addEventListener('submit', (e) => this.handleChangePassword(e));
    }

    // Notification toggle in Settings
    const btnTogglePush = document.getElementById('btnTogglePush');
    if (btnTogglePush) {
      btnTogglePush.addEventListener('click', () => this.handleTogglePush());
    }

    // Test notification button
    const btnTestPush = document.getElementById('btnTestPush');
    if (btnTestPush) {
      btnTestPush.addEventListener('click', () => this.handleTestPush());
    }

    // Seed Demo Data button
    const btnSeedDemo = document.getElementById('btnSeedDemo');
    if (btnSeedDemo) {
      btnSeedDemo.addEventListener('click', () => this.handleSeedDemo());
    }

    // Quick demo fill buttons on login page
    const btnDemoLogin = document.getElementById('btnFillDemoLogin');
    if (btnDemoLogin) {
      btnDemoLogin.addEventListener('click', () => {
        document.getElementById('loginUsername').value = 'demo_patient';
        document.getElementById('loginPassword').value = 'demo1234';
      });
    }

    // Logout buttons (sidebar, topbar, settings)
    document.querySelectorAll('.btn-logout-action, #btnLogout, #btnTopbarLogout, #btnSettingsLogout').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        this.handleLogout();
      });
    });
  }

  // -------------------------------------------------------------
  // PWA Install Handling
  // -------------------------------------------------------------
  setupPWAInstall() {
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      this.deferredInstallPrompt = e;
      const banner = document.getElementById('pwaInstallBanner');
      if (banner) banner.classList.remove('d-none');
    });

    const btnInstallPwa = document.getElementById('btnInstallPwa');
    if (btnInstallPwa) {
      btnInstallPwa.addEventListener('click', async () => {
        if (!this.deferredInstallPrompt) return;
        this.deferredInstallPrompt.prompt();
        const { outcome } = await this.deferredInstallPrompt.userChoice;
        if (outcome === 'accepted') {
          this.showToast('MediReminder installed to your device!', 'success');
        }
        this.deferredInstallPrompt = null;
        const banner = document.getElementById('pwaInstallBanner');
        if (banner) banner.classList.add('d-none');
      });
    }
  }

  // -------------------------------------------------------------
  // Authentication & Session
  // -------------------------------------------------------------
  async checkAuthStatus() {
    try {
      const resp = await fetch('/api/auth/me');
      const data = await resp.json();
      if (data.authenticated) {
        this.currentUser = data.user;
        this.renderUserSessionUI();
        this.navigateTo('dashboard');
      } else {
        this.currentUser = null;
        this.renderAuthView();
      }
    } catch (err) {
      console.error('Auth check error:', err);
      this.renderAuthView();
    }
  }

  renderAuthView() {
    document.getElementById('authContainer').classList.remove('d-none');
    document.getElementById('appContainer').classList.add('d-none');
  }

  renderUserSessionUI() {
    document.getElementById('authContainer').classList.add('d-none');
    document.getElementById('appContainer').classList.remove('d-none');

    // Update names & avatars
    const name = this.currentUser.full_name || this.currentUser.username;
    const initial = name.charAt(0).toUpperCase();

    document.querySelectorAll('.user-name-display').forEach(el => el.textContent = name);
    document.querySelectorAll('.user-avatar-initial').forEach(el => el.textContent = initial);

    // Update settings inputs
    const profileNameInput = document.getElementById('profileFullName');
    const profileTzInput = document.getElementById('profileTimezone');
    if (profileNameInput) profileNameInput.value = this.currentUser.full_name;
    if (profileTzInput) profileTzInput.value = this.currentUser.timezone || 'Asia/Kolkata';
  }

  async handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;

    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await resp.json();

      if (!resp.ok) {
        this.showToast(data.message || 'Login failed', 'error');
        return;
      }

      this.currentUser = data.user;
      this.showToast(`Welcome back, ${data.user.full_name}!`, 'success');
      this.renderUserSessionUI();
      this.navigateTo('dashboard');
    } catch (err) {
      this.showToast('Network error during login.', 'error');
    }
  }

  async handleRegister(e) {
    e.preventDefault();
    const full_name = document.getElementById('regFullName').value.trim();
    const username = document.getElementById('regUsername').value.trim();
    const email = document.getElementById('regEmail').value.trim();
    const password = document.getElementById('regPassword').value;
    const timezone = document.getElementById('regTimezone').value;

    try {
      const resp = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name, username, email, password, timezone })
      });
      const data = await resp.json();

      if (!resp.ok) {
        this.showToast(data.message || 'Registration failed', 'error');
        return;
      }

      this.currentUser = data.user;
      this.showToast('Registration successful! Welcome to MediReminder.', 'success');
      this.renderUserSessionUI();
      this.navigateTo('dashboard');
    } catch (err) {
      this.showToast('Network error during registration.', 'error');
    }
  }

  async handleLogout() {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
      this.currentUser = null;
      this.showToast('You have been logged out.', 'info');
      this.renderAuthView();
    } catch (err) {
      window.location.reload();
    }
  }

  // -------------------------------------------------------------
  // Router / View Navigation
  // -------------------------------------------------------------
  navigateTo(viewName) {
    this.currentView = viewName;

    // Update active nav links (desktop and mobile)
    document.querySelectorAll('[data-view-target]').forEach(link => {
      const target = link.getAttribute('data-view-target');
      if (target === viewName) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });

    // Hide all views, show targeted view
    document.querySelectorAll('.view-panel').forEach(panel => {
      panel.classList.add('d-none');
    });

    const activePanel = document.getElementById(`view-${viewName}`);
    if (activePanel) {
      activePanel.classList.remove('d-none');
    }

    // View specific data fetch
    if (viewName === 'dashboard') {
      this.loadDashboardSummary();
    } else if (viewName === 'medicines') {
      this.loadMedicines();
    } else if (viewName === 'history') {
      this.loadAdherenceStats();
      this.loadReminderHistory();
    } else if (viewName === 'settings') {
      this.updateNotificationUI();
    }
  }

  // -------------------------------------------------------------
  // Dashboard Logic
  // -------------------------------------------------------------
  async loadDashboardSummary() {
    try {
      const resp = await fetch('/api/dashboard/summary');
      if (!resp.ok) return;
      const data = await resp.json();

      // Update KPI counts
      document.getElementById('kpiTotalMeds').textContent = data.total_medicines;
      document.getElementById('kpiScheduled').textContent = data.total_scheduled;
      document.getElementById('kpiTaken').textContent = data.taken_count;
      document.getElementById('kpiMissed').textContent = data.missed_count;
      document.getElementById('kpiPending').textContent = data.pending_count;
      document.getElementById('kpiAdherence').textContent = `${data.adherence_rate}%`;

      // Update Progress bar
      const progressBar = document.getElementById('adherenceProgressBar');
      if (progressBar) {
        progressBar.style.width = `${data.adherence_rate}%`;
        progressBar.setAttribute('aria-valuenow', data.adherence_rate);
        if (data.adherence_rate >= 80) {
          progressBar.className = 'progress-bar bg-success';
        } else if (data.adherence_rate >= 50) {
          progressBar.className = 'progress-bar bg-warning';
        } else {
          progressBar.className = 'progress-bar bg-danger';
        }
      }

      // Update next dose banner
      const nextDoseEl = document.getElementById('nextDoseText');
      if (nextDoseEl && data.next_dose) {
        nextDoseEl.textContent = data.next_dose;
      }

      this.todayReminders = data.reminders || [];
      this.renderTodayTimeline(this.todayReminders);
      this.renderWeeklyChart(data.weekly_stats || []);
    } catch (err) {
      console.error('Error loading dashboard summary:', err);
    }
  }

  renderTodayTimeline(reminders) {
    const container = document.getElementById('todayTimelineContainer');
    if (!container) return;

    if (reminders.length === 0) {
      container.innerHTML = `
        <div class="text-center py-5">
          <div class="mb-3">
            <i class="bi bi-capsule-pill text-muted" style="font-size: 3rem;"></i>
          </div>
          <h5 class="fw-bold">No Reminders Scheduled for Today</h5>
          <p class="text-muted">You have no pending doses right now. Add a medicine or enjoy your day!</p>
          <button class="btn btn-primary-custom btn-sm mt-2" onclick="window.MediReminderApp.openMedicineModal()">
            <i class="bi bi-plus-lg"></i> Add First Medicine
          </button>
        </div>
      `;
      return;
    }

    container.innerHTML = reminders.map(r => {
      let statusBadge = '';
      let actionButtons = '';

      if (r.status === 'taken') {
        statusBadge = `<span class="reminder-status-badge status-taken"><i class="bi bi-check2-circle me-1"></i>Taken</span>`;
        actionButtons = `
          <button class="btn btn-sm btn-outline-secondary" title="Reset to pending" onclick="window.MediReminderApp.handleReminderAction(${r.id}, 'reset')">
            <i class="bi bi-arrow-counterclockwise"></i>
          </button>
        `;
      } else if (r.status === 'missed') {
        statusBadge = `<span class="reminder-status-badge status-missed"><i class="bi bi-x-circle me-1"></i>Missed</span>`;
        actionButtons = `
          <button class="btn btn-sm btn-success-custom" onclick="window.MediReminderApp.handleReminderAction(${r.id}, 'take')">
            <i class="bi bi-check-lg"></i> Take Now
          </button>
        `;
      } else if (r.status === 'snoozed') {
        statusBadge = `<span class="reminder-status-badge status-snoozed"><i class="bi bi-alarm me-1"></i>Snoozed (+15m)</span>`;
        actionButtons = `
          <button class="btn btn-sm btn-success-custom" onclick="window.MediReminderApp.handleReminderAction(${r.id}, 'take')">
            <i class="bi bi-check-lg"></i> Taken
          </button>
        `;
      } else {
        // Pending dose: Check if scheduled time has arrived
        if (r.is_future) {
          // Time has not arrived yet - Lock the action
          statusBadge = `<span class="reminder-status-badge status-upcoming"><i class="bi bi-clock-history me-1"></i>Upcoming</span>`;
          actionButtons = `
            <button class="btn btn-sm btn-light border text-muted disabled" disabled title="Locked until registered time (${r.scheduled_time})">
              <i class="bi bi-lock-fill me-1 text-secondary"></i> Available at ${r.scheduled_time}
            </button>
          `;
        } else {
          // Registered time has arrived or passed - Active for taking!
          statusBadge = `<span class="reminder-status-badge status-pending"><span class="pulse-indicator me-1"></span>Due Now</span>`;
          actionButtons = `
            <button class="btn btn-sm btn-success-custom" onclick="window.MediReminderApp.handleReminderAction(${r.id}, 'take')">
              <i class="bi bi-check-lg"></i> Take
            </button>
            <button class="btn btn-sm btn-outline-warning ms-1" title="Snooze 15 minutes" onclick="window.MediReminderApp.handleReminderAction(${r.id}, 'snooze')">
              <i class="bi bi-alarm"></i>
            </button>
            <button class="btn btn-sm btn-outline-danger ms-1" title="Mark Missed" onclick="window.MediReminderApp.handleReminderAction(${r.id}, 'miss')">
              <i class="bi bi-x-lg"></i>
            </button>
          `;
        }
      }

      return `
        <div class="reminder-item" style="--item-color: ${r.color || '#2563eb'};">
          <div class="d-flex align-items-center gap-3">
            <div class="reminder-time-badge">
              <i class="bi bi-clock"></i>
              <span>${r.scheduled_time}</span>
            </div>
            <div>
              <h6 class="mb-0 fw-bold text-dark">${this.escapeHTML(r.medicine_name)} <span class="badge bg-light text-secondary ms-1">${this.escapeHTML(r.dosage)}</span></h6>
              <div class="text-muted small mt-1">
                <i class="bi bi-info-circle me-1"></i>${this.escapeHTML(r.instructions)}
                ${r.taken_at ? ` • <span class="text-success"><i class="bi bi-check2"></i> Dose taken</span>` : ''}
              </div>
            </div>
          </div>
          <div class="d-flex align-items-center gap-2">
            ${statusBadge}
            <div class="d-flex align-items-center">
              ${actionButtons}
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  async handleReminderAction(reminderId, action) {
    try {
      const resp = await fetch(`/api/reminders/${reminderId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      });
      const data = await resp.json();

      if (!resp.ok) {
        this.showToast(data.message || 'Action failed', 'error');
        return;
      }

      if (action === 'take') {
        if (window.notificationManager) {
          window.notificationManager.playChime();
        }
        this.showToast('Dose recorded! Adherence updated.', 'success');
      } else if (action === 'snooze') {
        this.showToast('Reminder snoozed for 15 minutes.', 'info');
      } else if (action === 'miss') {
        this.showToast('Reminder marked as missed.', 'warning');
      }

      this.loadDashboardSummary();
    } catch (err) {
      this.showToast('Network error while updating reminder.', 'error');
    }
  }

  renderWeeklyChart(weeklyStats) {
    const ctx = document.getElementById('weeklyAdherenceChart');
    if (!ctx) return;

    const labels = weeklyStats.map(s => s.day);
    const adherenceRates = weeklyStats.map(s => s.adherence_rate);

    if (this.weeklyChart) {
      this.weeklyChart.destroy();
    }

    this.weeklyChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Adherence %',
          data: adherenceRates,
          backgroundColor: adherenceRates.map(r => r >= 80 ? 'rgba(16, 185, 129, 0.85)' : (r >= 50 ? 'rgba(245, 158, 11, 0.85)' : 'rgba(239, 68, 68, 0.85)')),
          borderRadius: 8,
          borderSkipped: false
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => `Adherence: ${context.raw}%`
            }
          }
        },
        scales: {
          y: {
            min: 0,
            max: 100,
            ticks: {
              stepSize: 25,
              callback: (val) => `${val}%`
            },
            grid: { color: 'rgba(226, 232, 240, 0.6)' }
          },
          x: {
            grid: { display: false }
          }
        }
      }
    });
  }

  // -------------------------------------------------------------
  // Medicines Management (CRUD)
  // -------------------------------------------------------------
  async loadMedicines() {
    try {
      const resp = await fetch('/api/medicines');
      if (!resp.ok) return;
      const data = await resp.json();
      this.medicinesList = data.medicines || [];
      this.renderMedicinesGrid(this.medicinesList);
    } catch (err) {
      console.error('Error fetching medicines:', err);
    }
  }

  renderMedicinesGrid(medicines) {
    const container = document.getElementById('medicinesGridContainer');
    if (!container) return;

    if (medicines.length === 0) {
      container.innerHTML = `
        <div class="col-12 text-center py-5">
          <i class="bi bi-capsule text-muted" style="font-size: 3.5rem;"></i>
          <h5 class="fw-bold mt-3">No Medicines Added Yet</h5>
          <p class="text-muted">Start by adding your prescriptions and supplement schedules.</p>
          <button class="btn btn-primary-custom" onclick="window.MediReminderApp.openMedicineModal()">
            <i class="bi bi-plus-lg"></i> Add Medicine
          </button>
        </div>
      `;
      return;
    }

    container.innerHTML = medicines.map(med => {
      const schedulesList = (med.schedules || []).map(s => `
        <span class="badge bg-light text-primary border border-primary-subtle me-1 mb-1">
          <i class="bi bi-clock me-1"></i>${s.time}
        </span>
      `).join('');

      return `
        <div class="col-12 col-md-6 col-xl-4 mb-4">
          <div class="med-card" style="border-top: 4px solid ${med.color || '#2563eb'};">
            <div>
              <div class="d-flex align-items-start justify-content-between mb-2">
                <div>
                  <span class="med-tag mb-1">${this.escapeHTML(med.medicine_type)}</span>
                  <h5 class="fw-bold mb-1 text-dark">${this.escapeHTML(med.name)}</h5>
                  <div class="text-primary fw-semibold small">${this.escapeHTML(med.dosage)}</div>
                </div>
                <div class="dropdown">
                  <button class="btn btn-sm btn-light border-0" type="button" data-bs-toggle="dropdown">
                    <i class="bi bi-three-dots-vertical"></i>
                  </button>
                  <ul class="dropdown-menu dropdown-menu-end shadow-sm">
                    <li><button class="dropdown-item" onclick="window.MediReminderApp.openMedicineModal(${med.id})"><i class="bi bi-pencil me-2 text-primary"></i>Edit</button></li>
                    <li><button class="dropdown-item" onclick="window.MediReminderApp.handleToggleMedicine(${med.id})"><i class="bi bi-toggle-${med.is_active ? 'on text-success' : 'off text-secondary'} me-2"></i>${med.is_active ? 'Deactivate' : 'Activate'}</button></li>
                    <li><hr class="dropdown-divider"></li>
                    <li><button class="dropdown-item text-danger" onclick="window.MediReminderApp.handleDeleteMedicine(${med.id})"><i class="bi bi-trash me-2"></i>Delete</button></li>
                  </ul>
                </div>
              </div>

              <p class="text-muted small mb-3">
                <i class="bi bi-card-text me-1"></i>${this.escapeHTML(med.instructions || 'As advised')}
                ${med.notes ? `<br><span class="fst-italic"><i class="bi bi-sticky me-1"></i>${this.escapeHTML(med.notes)}</span>` : ''}
              </p>

              <div class="mb-3">
                <div class="text-muted small fw-semibold mb-1">Reminder Times:</div>
                <div class="d-flex flex-wrap">${schedulesList || '<span class="text-muted small">None</span>'}</div>
              </div>
            </div>

            <div class="pt-3 border-top d-flex align-items-center justify-content-between text-muted small">
              <div>
                <span>Started: ${med.start_date || 'N/A'}</span>
                ${med.end_date ? ` • Ends: ${med.end_date}` : ' • Ongoing'}
              </div>
              <span class="badge ${med.is_active ? 'bg-success-subtle text-success' : 'bg-secondary-subtle text-secondary'}">
                ${med.is_active ? 'Active' : 'Paused'}
              </span>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  openMedicineModal(medId = null) {
    const modalEl = document.getElementById('medicineModal');
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

    const titleEl = document.getElementById('medicineModalTitle');
    const idInput = document.getElementById('medId');
    const nameInput = document.getElementById('medName');
    const dosageInput = document.getElementById('medDosage');
    const typeInput = document.getElementById('medType');
    const instructionsInput = document.getElementById('medInstructions');
    const startInput = document.getElementById('medStartDate');
    const endInput = document.getElementById('medEndDate');
    const notesInput = document.getElementById('medNotes');
    const colorInput = document.getElementById('medColor');
    const timesContainer = document.getElementById('scheduleTimesContainer');

    timesContainer.innerHTML = '';

    if (medId) {
      const med = this.medicinesList.find(m => m.id === medId);
      if (med) {
        titleEl.textContent = 'Edit Medicine Schedule';
        idInput.value = med.id;
        nameInput.value = med.name;
        dosageInput.value = med.dosage;
        typeInput.value = med.medicine_type;
        instructionsInput.value = med.instructions;
        startInput.value = med.start_date || '';
        endInput.value = med.end_date || '';
        notesInput.value = med.notes || '';
        colorInput.value = med.color || '#2563eb';

        if (med.schedules && med.schedules.length > 0) {
          med.schedules.forEach(s => this.addScheduleTimeInput(s.time));
        } else {
          this.addScheduleTimeInput('08:00');
        }
      }
    } else {
      titleEl.textContent = 'Add New Medicine';
      idInput.value = '';
      nameInput.value = '';
      dosageInput.value = '';
      typeInput.value = 'Tablet';
      instructionsInput.value = 'After food';
      startInput.value = new Date().toISOString().split('T')[0];
      endInput.value = '';
      notesInput.value = '';
      colorInput.value = '#2563eb';
      this.addScheduleTimeInput('08:00');
      this.addScheduleTimeInput('20:00');
    }

    modal.show();
  }

  addScheduleTimeInput(timeVal = '08:00') {
    const container = document.getElementById('scheduleTimesContainer');
    const div = document.createElement('div');
    div.className = 'input-group mb-2 schedule-time-row';
    div.innerHTML = `
      <span class="input-group-text bg-light"><i class="bi bi-clock"></i></span>
      <input type="time" class="form-control schedule-time-input" value="${timeVal}" required>
      <button class="btn btn-outline-danger" type="button" onclick="this.closest('.schedule-time-row').remove()">
        <i class="bi bi-trash"></i>
      </button>
    `;
    container.appendChild(div);
  }

  async handleSaveMedicine(e) {
    e.preventDefault();
    const id = document.getElementById('medId').value;
    const name = document.getElementById('medName').value.trim();
    const dosage = document.getElementById('medDosage').value.trim();
    const medicine_type = document.getElementById('medType').value;
    const instructions = document.getElementById('medInstructions').value;
    const start_date = document.getElementById('medStartDate').value;
    const end_date = document.getElementById('medEndDate').value || null;
    const notes = document.getElementById('medNotes').value.trim();
    const color = document.getElementById('medColor').value;

    const scheduleInputs = document.querySelectorAll('.schedule-time-input');
    const schedules = Array.from(scheduleInputs).map(inp => inp.value).filter(Boolean);

    if (schedules.length === 0) {
      this.showToast('Please add at least one reminder time.', 'error');
      return;
    }

    const payload = {
      name,
      dosage,
      medicine_type,
      instructions,
      start_date,
      end_date,
      notes,
      color,
      schedules
    };

    try {
      const url = id ? `/api/medicines/${id}` : '/api/medicines';
      const method = id ? 'PUT' : 'POST';

      const resp = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();

      if (!resp.ok) {
        this.showToast(data.message || 'Failed to save medicine.', 'error');
        return;
      }

      this.showToast(id ? 'Medicine updated successfully!' : 'New medicine scheduled!', 'success');
      const modalEl = document.getElementById('medicineModal');
      bootstrap.Modal.getInstance(modalEl).hide();
      this.loadMedicines();
      this.loadDashboardSummary();
    } catch (err) {
      this.showToast('Network error while saving medicine.', 'error');
    }
  }

  async handleToggleMedicine(id) {
    try {
      const resp = await fetch(`/api/medicines/${id}/toggle`, { method: 'PATCH' });
      const data = await resp.json();
      if (resp.ok) {
        this.showToast(data.message, 'info');
        this.loadMedicines();
      }
    } catch (err) {
      this.showToast('Error toggling medicine status.', 'error');
    }
  }

  async handleDeleteMedicine(id) {
    if (!confirm('Are you sure you want to delete this medicine and all its scheduled reminders?')) {
      return;
    }
    try {
      const resp = await fetch(`/api/medicines/${id}`, { method: 'DELETE' });
      const data = await resp.json();
      if (resp.ok) {
        this.showToast('Medicine deleted.', 'info');
        this.loadMedicines();
        this.loadDashboardSummary();
      }
    } catch (err) {
      this.showToast('Error deleting medicine.', 'error');
    }
  }

  // -------------------------------------------------------------
  // Adherence Analytics & History
  // -------------------------------------------------------------
  async loadAdherenceStats() {
    try {
      const resp = await fetch('/api/adherence/stats');
      if (!resp.ok) return;
      const data = await resp.json();

      document.getElementById('statOverallRate').textContent = `${data.overall_rate}%`;
      document.getElementById('statStreak').textContent = `${data.current_streak} Days 🔥`;
      document.getElementById('statTotalTaken').textContent = data.total_taken;
      document.getElementById('statTotalMissed').textContent = data.total_missed;

      this.renderMonthlyChart(data.daily_series || []);
      this.renderStatusDoughnut(data.total_taken, data.total_missed);
    } catch (err) {
      console.error('Error loading adherence stats:', err);
    }
  }

  renderMonthlyChart(series) {
    const ctx = document.getElementById('monthlyAdherenceChart');
    if (!ctx) return;

    const labels = series.map(s => s.display);
    const rates = series.map(s => s.rate !== null ? s.rate : null);

    if (this.monthlyChart) {
      this.monthlyChart.destroy();
    }

    this.monthlyChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Daily Adherence %',
          data: rates,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37, 99, 235, 0.12)',
          fill: true,
          tension: 0.35,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: '#2563eb',
          spanGaps: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => `Adherence: ${context.raw !== null ? context.raw + '%' : 'No doses'}`
            }
          }
        },
        scales: {
          y: {
            min: 0,
            max: 100,
            ticks: {
              stepSize: 20,
              callback: (v) => `${v}%`
            },
            grid: { color: 'rgba(226, 232, 240, 0.6)' }
          },
          x: {
            grid: { display: false },
            ticks: { maxTicksLimit: 10 }
          }
        }
      }
    });
  }

  renderStatusDoughnut(taken, missed) {
    const ctx = document.getElementById('statusDoughnutChart');
    if (!ctx) return;

    if (this.doughnutChart) {
      this.doughnutChart.destroy();
    }

    const total = taken + missed;
    if (total === 0) {
      taken = 1; // placeholder display
    }

    this.doughnutChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Taken Doses', 'Missed Doses'],
        datasets: [{
          data: [taken, missed],
          backgroundColor: ['#10b981', '#ef4444'],
          borderWidth: 2,
          borderColor: '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' }
        },
        cutout: '72%'
      }
    });
  }

  async loadReminderHistory(filterStatus = 'all') {
    try {
      const resp = await fetch(`/api/reminders/history?status=${filterStatus}&limit=60`);
      if (!resp.ok) return;
      const data = await resp.json();
      const container = document.getElementById('historyTableBody');
      if (!container) return;

      const history = data.history || [];
      if (history.length === 0) {
        container.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted">No historical records found for this filter.</td></tr>`;
        return;
      }

      container.innerHTML = history.map(item => {
        let badge = `<span class="badge bg-secondary">Pending</span>`;
        if (item.status === 'taken') {
          badge = `<span class="badge bg-success-subtle text-success"><i class="bi bi-check-circle me-1"></i>Taken</span>`;
        } else if (item.status === 'missed') {
          badge = `<span class="badge bg-danger-subtle text-danger"><i class="bi bi-x-circle me-1"></i>Missed</span>`;
        } else if (item.status === 'snoozed') {
          badge = `<span class="badge bg-warning-subtle text-warning"><i class="bi bi-alarm me-1"></i>Snoozed</span>`;
        }

        return `
          <tr>
            <td class="fw-bold">${item.scheduled_date}</td>
            <td><span class="badge bg-light text-dark border">${item.scheduled_time}</span></td>
            <td>
              <div class="fw-semibold">${this.escapeHTML(item.medicine_name)}</div>
              <div class="text-muted small">${this.escapeHTML(item.dosage)} • ${this.escapeHTML(item.medicine_type)}</div>
            </td>
            <td>${this.escapeHTML(item.instructions || 'N/A')}</td>
            <td>${badge}</td>
            <td class="small text-muted">${item.taken_at ? item.taken_at.replace('T', ' ').substring(0, 19) : (item.status === 'missed' ? 'Overdue' : 'Pending')}</td>
          </tr>
        `;
      }).join('');
    } catch (err) {
      console.error('Error fetching history:', err);
    }
  }

  // -------------------------------------------------------------
  // Settings & Push Notifications
  // -------------------------------------------------------------
  updateNotificationUI() {
    const statusText = document.getElementById('pushStatusText');
    const btnToggle = document.getElementById('btnTogglePush');
    if (!statusText || !btnToggle) return;

    if (!('Notification' in window)) {
      statusText.innerHTML = `<span class="badge bg-danger">Not Supported in this Browser</span>`;
      btnToggle.disabled = true;
      return;
    }

    if (Notification.permission === 'granted' && window.notificationManager && window.notificationManager.isSubscribed) {
      statusText.innerHTML = `<span class="badge bg-success"><i class="bi bi-bell-fill me-1"></i>Active & Subscribed</span>`;
      btnToggle.className = 'btn btn-outline-danger btn-sm';
      btnToggle.innerHTML = '<i class="bi bi-bell-slash me-1"></i> Disable Push Notifications';
    } else if (Notification.permission === 'denied') {
      statusText.innerHTML = `<span class="badge bg-danger"><i class="bi bi-slash-circle me-1"></i>Permission Blocked</span>`;
      btnToggle.className = 'btn btn-outline-secondary btn-sm';
      btnToggle.innerHTML = '<i class="bi bi-lock me-1"></i> Blocked by Browser';
      btnToggle.disabled = true;
    } else {
      statusText.innerHTML = `<span class="badge bg-warning text-dark"><i class="bi bi-bell me-1"></i>Not Enabled</span>`;
      btnToggle.className = 'btn btn-primary-custom btn-sm';
      btnToggle.innerHTML = '<i class="bi bi-bell me-1"></i> Enable Web Push Notifications';
      btnToggle.disabled = false;
    }
  }

  async handleTogglePush() {
    if (!window.notificationManager) return;
    try {
      if (window.notificationManager.isSubscribed) {
        await window.notificationManager.unsubscribe();
        this.showToast('Web Push notifications disabled.', 'info');
      } else {
        await window.notificationManager.subscribe();
        this.showToast('Push notifications successfully enabled! Real-time alerts are active.', 'success');
      }
      this.updateNotificationUI();
    } catch (err) {
      this.showToast(`Notification error: ${err.message}`, 'error');
      this.updateNotificationUI();
    }
  }

  async handleTestPush() {
    if (!window.notificationManager) return;
    try {
      const result = await window.notificationManager.testNotification();
      if (result.warning) {
        this.showToast(result.warning, 'warning');
      } else {
        this.showToast(result.message || 'Test notification sent!', 'success');
      }
    } catch (err) {
      this.showToast('Failed to trigger test notification.', 'error');
    }
  }

  async handleUpdateProfile(e) {
    e.preventDefault();
    const full_name = document.getElementById('profileFullName').value.trim();
    const timezone = document.getElementById('profileTimezone').value.trim();

    try {
      const resp = await fetch('/api/auth/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name, timezone })
      });
      const data = await resp.json();

      if (resp.ok) {
        this.currentUser = data.user;
        this.renderUserSessionUI();
        this.showToast('Profile updated successfully!', 'success');
      } else {
        this.showToast(data.message || 'Profile update failed.', 'error');
      }
    } catch (err) {
      this.showToast('Error updating profile.', 'error');
    }
  }

  async handleChangePassword(e) {
    e.preventDefault();
    const current_password = document.getElementById('pwdCurrent').value;
    const new_password = document.getElementById('pwdNew').value;

    try {
      const resp = await fetch('/api/auth/password', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password, new_password })
      });
      const data = await resp.json();

      if (resp.ok) {
        this.showToast('Password changed successfully!', 'success');
        document.getElementById('passwordForm').reset();
      } else {
        this.showToast(data.message || 'Password change failed.', 'error');
      }
    } catch (err) {
      this.showToast('Error changing password.', 'error');
    }
  }

  async handleSeedDemo() {
    try {
      const resp = await fetch('/api/demo/seed', { method: 'POST' });
      const data = await resp.json();
      if (resp.ok) {
        this.showToast(data.message, 'success');
        this.loadDashboardSummary();
        this.loadMedicines();
      } else {
        this.showToast('Demo data seeding failed.', 'error');
      }
    } catch (err) {
      this.showToast('Error seeding demo data.', 'error');
    }
  }

  // -------------------------------------------------------------
  // UI Helpers (Toast & Sanitization)
  // -------------------------------------------------------------
  showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'custom-toast';

    let icon = 'bi-info-circle-fill text-primary';
    let borderColor = 'var(--primary-blue)';

    if (type === 'success') {
      icon = 'bi-check-circle-fill text-success';
      borderColor = 'var(--health-green)';
    } else if (type === 'error') {
      icon = 'bi-exclamation-triangle-fill text-danger';
      borderColor = 'var(--danger-crimson)';
    } else if (type === 'warning') {
      icon = 'bi-exclamation-circle-fill text-warning';
      borderColor = 'var(--warning-amber)';
    }

    toast.style.borderLeftColor = borderColor;
    toast.innerHTML = `
      <i class="bi ${icon}" style="font-size: 1.3rem;"></i>
      <div class="flex-grow-1">
        <div class="fw-semibold text-dark small">${this.escapeHTML(message)}</div>
      </div>
      <button type="button" class="btn-close btn-sm" onclick="this.closest('.custom-toast').remove()"></button>
    `;

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }

  escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag] || tag));
  }
}

// Instantiate on DOM load
document.addEventListener('DOMContentLoaded', () => {
  window.MediReminderApp = new MediReminderApp();
});
