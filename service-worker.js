const STATIC_CACHE = "aida-static-v6";
const RUNTIME_CACHE = "aida-runtime-v6";

const APP_SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./styles/style-home.css",
  "./styles/style-shared-theme.css",
  "./scripts/script-pwa-register.js",
  "./scripts/script-home.js",
  "pages/index-login.html",
  "./styles/style-login.css",
  "./scripts/script-login.js",
  "pages/index-seleciona.html",
  "./styles/style-ferramenta.css",
  "./scripts/script-ferramenta.js",
  "pages/index-manutencao.html",
  "./styles/style-manutencao.css",
  "./scripts/script-manutencao.js",
  "pages/index-analise.html",
  "./styles/style-analise.css",
  "./scripts/script-analise.js",
  "pages/index-admin.html",
  "./styles/style-administrador.css",
  "./scripts/script-administrador.js",
  "pages/index-apresentacao.html",
  "./styles/style-apresentacao.css",
  "./scripts/script-apresentacao.js",
  "pages/index-historico.html",
  "./styles/style-historico.css",
  "./scripts/script-historico.js",
  "pages/index-perfil.html",
  "./styles/style-perfil.css",
  "./scripts/script-perfil.js",
  "./assets/images/LogoBranca.png",
  "./assets/images/AIDABranco.ico",
  "./assets/images/pwa-icon-180.png",
  "./assets/images/pwa-icon-192.png",
  "./assets/images/pwa-icon-512.png"
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
            return caches.match("pages/index-seleciona.html");
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
            return caches.match("./assets/images/pwa-icon-192.png");
          }

          return Response.error();
        });
    })
  );
});
