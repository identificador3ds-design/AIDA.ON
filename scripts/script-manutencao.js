const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const DESTINOS_LIBERADOS = new Set(["./index-seleciona.html", "./index-analise.html"]);
const CONFIG_ADMIN_PADRAO = {
  maintenanceMode: false,
  allowUploadPage: true,
  supportEmail: ADMIN_EMAIL,
  announcementMessage: "",
};

function obterAdminConfig() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_ADMIN_CONFIG) || "{}");
    return { ...CONFIG_ADMIN_PADRAO, ...salvo };
  } catch (erro) {
    return { ...CONFIG_ADMIN_PADRAO };
  }
}

function usuarioEhAdmin() {
  const tipo = localStorage.getItem("usuarioTipo");
  const email = (localStorage.getItem("usuarioEmail") || "").trim().toLowerCase();
  return tipo === "admin" || email === ADMIN_EMAIL;
}

function obterDestinoSeguro() {
  const params = new URLSearchParams(window.location.search);
  const destino = String(params.get("redirect") || "./index-seleciona.html").trim();
  return DESTINOS_LIBERADOS.has(destino) ? destino : "./index-seleciona.html";
}

function descreverDestino(destino) {
  if (destino === "./index-analise.html") {
    return "Etapa de analise";
  }

  return "Selecao de imagem";
}

function redirecionarParaDestino(destino) {
  window.location.href = destino;
}

document.addEventListener("DOMContentLoaded", () => {
  const configuracao = obterAdminConfig();
  const destino = obterDestinoSeguro();
  const supportEmail = document.getElementById("maintenanceSupportEmail");
  const targetLabel = document.getElementById("maintenanceTargetLabel");
  const message = document.getElementById("maintenanceMessage");
  const status = document.getElementById("maintenanceStatus");

  if (supportEmail) {
    supportEmail.textContent = configuracao.supportEmail || ADMIN_EMAIL;
  }

  if (targetLabel) {
    targetLabel.textContent = descreverDestino(destino);
  }

  if (message) {
    message.textContent = configuracao.announcementMessage
      ? configuracao.announcementMessage
      : "Esta etapa da ferramenta permanece em fase de desenvolvimento e voltara a ficar disponivel em breve.";
  }

  if (status) {
    status.textContent =
      "A ferramenta esta temporariamente bloqueada para usuarios comuns enquanto esta funcionalidade evolui.";
  }

  if (usuarioEhAdmin() || !configuracao.maintenanceMode) {
    redirecionarParaDestino(destino);
    return;
  }
});
