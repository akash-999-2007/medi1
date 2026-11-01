// MediReminder Service Worker - IDP2502
const CACHE_NAME = 'medireminder-cache-v1.0';
const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/js/notifications.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon.svg',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js'
];

// Install event - Cache essential app shell assets
self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Pre-caching offline application shell');
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[SW] Non-critical asset cache failed:', err);
      });
    })
  );
});

// Activate event - Purge old caches and claim clients
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - Network-first for dynamic API routes, cache-first for static assets
self.addEventListener('fetch', (event) => {
  const requestUrl = new URL(event.request.url);

  // Dynamic API calls or non-GET requests: bypass cache
  if (requestUrl.pathname.startsWith('/api/') || event.request.method !== 'GET') {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        // Fetch fresh copy in background for next time
        fetch(event.request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, networkResponse.clone()));
          }
        }).catch(() => {});
        return cachedResponse;
      }
      return fetch(event.request).then((networkResponse) => {
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
          return networkResponse;
        }
        const responseClone = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
        return networkResponse;
      }).catch(() => {
        // Offline fallback for navigation requests
        if (event.request.mode === 'navigate') {
          return caches.match('/');
        }
      });
    })
  );
});

// Push notification event listener
self.addEventListener('push', (event) => {
  console.log('[SW] Push notification payload received');
  let data = {
    title: 'MediReminder Alert',
    body: 'Time to check your medicine schedule.',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-192.png',
    tag: 'medireminder-general',
    data: { url: '/#dashboard' },
    actions: [
      { action: 'take', title: 'Mark as Taken' },
      { action: 'snooze', title: 'Snooze 15m' }
    ]
  };

  if (event.data) {
    try {
      const parsed = event.data.json();
      data = Object.assign(data, parsed);
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon || '/static/icons/icon-192.png',
    badge: data.badge || '/static/icons/icon-192.png',
    tag: data.tag || 'medireminder-push',
    data: data.data || {},
    actions: data.actions || [],
    vibrate: [200, 100, 200, 100, 300],
    renotify: true,
    requireInteraction: true
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification click event listener
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const action = event.action;
  const notifData = event.notification.data || {};
  const reminderId = notifData.reminder_id;
  const targetUrl = notifData.url || '/#dashboard';

  if (action === 'take' && reminderId) {
    event.waitUntil(
      fetch(`/api/reminders/${reminderId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'take' })
      }).then(() => {
        return self.registration.showNotification('MediReminder - Taken!', {
          body: 'Medicine intake recorded successfully. Well done!',
          icon: '/static/icons/icon-192.png',
          badge: '/static/icons/icon-192.png',
          tag: 'dose-taken-confirm',
          timeout: 4000
        });
      }).then(() => notifyClientsToRefresh())
    );
    return;
  }

  if (action === 'snooze' && reminderId) {
    event.waitUntil(
      fetch(`/api/reminders/${reminderId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'snooze' })
      }).then(() => {
        return self.registration.showNotification('MediReminder - Snoozed', {
          body: 'Reminder rescheduled by 15 minutes.',
          icon: '/static/icons/icon-192.png',
          badge: '/static/icons/icon-192.png',
          tag: 'dose-snooze-confirm',
          timeout: 4000
        });
      }).then(() => notifyClientsToRefresh())
    );
    return;
  }

  // Standard click on notification body: Open or focus application window
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

// Broadcast event to active UI tabs to refresh schedule view
function notifyClientsToRefresh() {
  return clients.matchAll({ type: 'window' }).then((clientList) => {
    clientList.forEach((client) => {
      client.postMessage({ type: 'REFRESH_REMINDERS' });
    });
  });
}
