const STATIC_CACHE = "aida-static-v2";
const RUNTIME_CACHE = "aida-runtime-v2";

const APP_SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./pwa-register.js",
  "./shared-theme.css",
  "./Ferramenta/index-seleciona.html",
  "./Ferramenta/style.css",
  "./Ferramenta/script.js",
  "./Ferramenta-Analise/index-analise.html",
  "./Ferramenta-Analise/style.css",
  "./Ferramenta-Analise/script.js",
  "./img/LogoBranca.png",
  "./img/AIDABranco.ico",
  "./img/pwa-icon-180.png",
  "./img/pwa-icon-192.png",
  "./img/pwa-icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) =>
        Promise.all(
          cacheNames
            .filter((cacheName) => ![STATIC_CACHE, RUNTIME_CACHE].includes(cacheName))
            .map((cacheName) => caches.delete(cacheName))
        )
      )
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: "window" }))
      .then((clientList) =>
        Promise.all(
          clientList.map((client) => {
            if ("navigate" in client) {
              return client.navigate(client.url);
            }

            return Promise.resolve();
          })
        )
      )
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const requestUrl = new URL(event.request.url);
  const usarRedePrimeiro =
    event.request.mode === "navigate" ||
    ["script", "style", "font"].includes(event.request.destination) ||
    requestUrl.pathname.endsWith(".webmanifest");

  if (requestUrl.origin !== self.location.origin) {
    return;
  }

  if (usarRedePrimeiro) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const responseClone = response.clone();
          caches.open(RUNTIME_CACHE).then((cache) => {
            cache.put(event.request, responseClone);
          });
          return response;
        })
        .catch(async () => {
          const cachedResponse = await caches.match(event.request);

          if (cachedResponse) {
            return cachedResponse;
          }

          if (event.request.mode === "navigate") {
            return caches.match("./Ferramenta/index-seleciona.html");
          }

          return Response.error();
        })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(event.request)
        .then((networkResponse) => {
          const responseClone = networkResponse.clone();
          caches.open(RUNTIME_CACHE).then((cache) => {
            cache.put(event.request, responseClone);
          });
          return networkResponse;
        })
        .catch(() => {
          if (event.request.destination === "image") {
            return caches.match("./img/pwa-icon-192.png");
          }

          return Response.error();
        });
    })
  );
});
