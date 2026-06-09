(function () {
  if (!("serviceWorker" in navigator)) {
    return;
  }

  let recarregandoPorNovoServiceWorker = false;
  const currentScript = document.currentScript;
  const serviceWorkerUrl = currentScript
    ? new URL("../service-worker.js", currentScript.src)
    : new URL("../service-worker.js", window.location.href);

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (recarregandoPorNovoServiceWorker) {
      return;
    }

    recarregandoPorNovoServiceWorker = true;
    window.location.reload();
  });
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


