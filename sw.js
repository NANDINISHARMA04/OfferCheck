/* Service worker: makes the app installable, opens offline, and receives shares.
   When someone taps "Share → Offer Check" on their phone, Android sends a POST to
   /share-target. We grab the shared text/file, park it in a cache, and open the app. */
const SHELL = "offercheck-shell-v1";
const SHARE = "offercheck-share";
const SHELL_FILES = ["/", "/static/manifest.webmanifest", "/static/icons/icon-192.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== SHELL && k !== SHARE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);

  if (e.request.method === "POST" && url.pathname === "/share-target") {
    e.respondWith((async () => {
      const form = await e.request.formData();
      const cache = await caches.open(SHARE);
      const text = [form.get("title"), form.get("text"), form.get("url")].filter(Boolean).join("\n");
      await cache.put("/shared/text", new Response(text));
      const file = form.get("file");
      if (file && file.size) {
        await cache.put("/shared/file", new Response(file, {
          headers: { "Content-Type": file.type, "X-Filename": encodeURIComponent(file.name || "shared") }
        }));
      }
      return Response.redirect("/?shared=1", 303);
    })());
    return;
  }

  // API calls always go to the network (results must be fresh).
  if (url.pathname.startsWith("/api/") || e.request.method !== "GET") return;

  // App shell: network first, fall back to cache when offline.
  e.respondWith(
    fetch(e.request)
      .then(res => {
        const copy = res.clone();
        caches.open(SHELL).then(c => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request).then(r => r || caches.match("/")))
  );
});
