// MediReminder - Push Notification and Service Worker Management
class NotificationManager {
  constructor() {
    this.swRegistration = null;
    this.isSubscribed = false;
    this.audioContext = null;
  }

  // Convert base64url string to Uint8Array required for applicationServerKey
  urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  // Synthesize a pleasant medical chime alert using Web Audio API
  playChime() {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      if (!this.audioContext) {
        this.audioContext = new AudioContext();
      }
      if (this.audioContext.state === 'suspended') {
        this.audioContext.resume();
      }

      const now = this.audioContext.currentTime;

      // Note 1: C5 (523.25 Hz)
      const osc1 = this.audioContext.createOscillator();
      const gain1 = this.audioContext.createGain();
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(523.25, now);
      gain1.gain.setValueAtTime(0.2, now);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.6);
      osc1.connect(gain1);
      gain1.connect(this.audioContext.destination);
      osc1.start(now);
      osc1.stop(now + 0.6);

      // Note 2: G5 (783.99 Hz) delayed by 120ms
      const osc2 = this.audioContext.createOscillator();
      const gain2 = this.audioContext.createGain();
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(783.99, now + 0.12);
      gain2.gain.setValueAtTime(0.25, now + 0.12);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.9);
      osc2.connect(gain2);
      gain2.connect(this.audioContext.destination);
      osc2.start(now + 0.12);
      osc2.stop(now + 0.9);
    } catch (e) {
      console.warn('[Audio] Could not play synthetic chime:', e);
    }
  }

  // Initialize service worker
  async init() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      console.warn('[Push] Push notifications are not supported in this browser.');
      return { supported: false, subscribed: false };
    }

    try {
      this.swRegistration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      console.log('[SW] Service Worker registered with scope:', this.swRegistration.scope);

      // Check existing subscription
      const subscription = await this.swRegistration.pushManager.getSubscription();
      this.isSubscribed = subscription !== null;

      // Listen for message broadcasts from Service Worker
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'REFRESH_REMINDERS') {
          console.log('[SW] Refresh signal received from service worker');
          if (window.MediReminderApp) {
            window.MediReminderApp.loadDashboardSummary();
          }
        }
      });

      return { supported: true, subscribed: this.isSubscribed };
    } catch (err) {
      console.error('[SW] Service Worker registration failed:', err);
      return { supported: true, subscribed: false, error: err.message };
    }
  }

  // Request browser permission and subscribe to Web Push
  async subscribe() {
    if (!this.swRegistration) {
      await this.init();
    }
    if (!this.swRegistration) {
      throw new Error('Service Worker is not available.');
    }

    // 1. Request notification permission
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      throw new Error('Notification permission was denied by the user.');
    }

    // 2. Fetch VAPID public key from backend
    const keyResp = await fetch('/api/notifications/vapid-public-key');
    if (!keyResp.ok) throw new Error('Failed to retrieve VAPID public key from server.');
    const keyData = await keyResp.json();
    const convertedVapidKey = this.urlBase64ToUint8Array(keyData.publicKey);

    // 3. Subscribe with PushManager
    const subscription = await this.swRegistration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: convertedVapidKey
    });

    // 4. Send subscription details to backend
    const subJSON = subscription.toJSON();
    const saveResp = await fetch('/api/notifications/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        endpoint: subJSON.endpoint,
        keys: {
          p256dh: subJSON.keys.p256dh,
          auth: subJSON.keys.auth
        }
      })
    });

    if (!saveResp.ok) {
      throw new Error('Server failed to store push subscription.');
    }

    this.isSubscribed = true;
    this.playChime();
    return true;
  }

  // Unsubscribe from Web Push
  async unsubscribe() {
    if (!this.swRegistration) return;
    const subscription = await this.swRegistration.pushManager.getSubscription();
    if (subscription) {
      const endpoint = subscription.endpoint;
      await subscription.unsubscribe();
      await fetch('/api/notifications/unsubscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint })
      });
      this.isSubscribed = false;
    }
  }

  // Dispatch an instant test notification via backend
  async testNotification() {
    this.playChime();
    const resp = await fetch('/api/notifications/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    return await resp.json();
  }
}

// Global instance
window.notificationManager = new NotificationManager();
