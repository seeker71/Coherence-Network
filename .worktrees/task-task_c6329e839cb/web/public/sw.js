/* Coherence Network service worker.
 *
 * Minimal: registers push event + notification click handlers so real
 * browser pushes can land on the device lock screen even when the app
 * tab is closed.
 *
 * Payload shape (JSON):
 *   { "title": "...", "body": "...", "url": "/feed/you", "icon": "/icon.svg" }
 */

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let payload = {};
  if (event.data) {
    try {
      payload = event.data.json();
    } catch {
      payload = { title: "Coherence Network", body: event.data.text() };
    }
  }
  const title = payload.title || "Coherence Network";
  const body = payload.body || "";
  const url = payload.url || "/feed/you";
  const icon = payload.icon || "/icon.svg";
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon,
      badge: icon,
      data: { url },
      // Keep the notification quiet — no vibration, no sound override.
      // The OS ringer profile wins.
      silent: false,
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/feed/you";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      // If a Coherence tab is already open, focus it and navigate.
      for (const client of list) {
        if ("focus" in client) {
          client.focus();
          if ("navigate" in client) client.navigate(target);
          return;
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
