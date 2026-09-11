/* Em desenvolvimento local, o service worker guarda versoes antigas das telas e
   confunde o teste. Este script limpa registro e cache — e so roda em
   localhost, entao nao afeta producao. */
(function () {
  "use strict";

  if (!["localhost", "127.0.0.1"].includes(location.hostname)) {
    return;
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker
      .getRegistrations()
      .then((regs) => regs.forEach((reg) => reg.unregister()));
  }

  if ("caches" in window) {
    caches.keys().then((keys) => keys.forEach((key) => caches.delete(key)));
  }
})();
