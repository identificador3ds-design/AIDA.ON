(function () {
  if (!("serviceWorker" in navigator)) {
    return;
  }

  const hostLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  if (hostLocal) {
    window.addEventListener("load", () => {
      navigator.serviceWorker
        .getRegistrations()
        .then((registrations) => registrations.forEach((registration) => registration.unregister()))
        .catch((error) => {
          console.warn("Nao foi possivel desregistrar o service worker local:", error);
        });
    });
    return;
  }

  const currentScript = document.currentScript;
  const serviceWorkerUrl = currentScript
    ? new URL("../service-worker.js", currentScript.src)
    : new URL("../service-worker.js", window.location.href);
const favicon = document.getElementById('favicon');

function updateFavicon() {
  if (!favicon) {
    return;
  }

  if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    favicon.href = '../assets/images/AIDABranco.ico';
  } else {
    favicon.href = '../assets/images/AIDAPreto.ico';
  }
}


updateFavicon();
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register(serviceWorkerUrl.href, { updateViaCache: "none" })
      .then((registration) => registration.update())
      .catch((error) => {
        console.warn("Nao foi possivel registrar o service worker do AIDA.ON:", error);
      });
  });
})();


