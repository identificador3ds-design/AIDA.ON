(function () {
  if (!("serviceWorker" in navigator)) {
    return;
  }

  const currentScript = document.currentScript;
  const serviceWorkerUrl = currentScript
    ? new URL("service-worker.js", currentScript.src)
    : new URL("service-worker.js", window.location.href);

  window.addEventListener("load", () => {
    navigator.serviceWorker.register(serviceWorkerUrl.href).catch((error) => {
      console.warn("Nao foi possivel registrar o service worker do AIDA.ON:", error);
    });
  });
})();
