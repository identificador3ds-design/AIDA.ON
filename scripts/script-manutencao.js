const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const CHAVE_MANUTENCAO_ACESSO = "AIDA_MAINTENANCE_ACCESS";
const CODIGO_ACESSO_MANUTENCAO = "admin3ds";
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

function possuiAcessoManutencao() {
  return sessionStorage.getItem(CHAVE_MANUTENCAO_ACESSO) === "granted";
}

function concederAcessoManutencao() {
  sessionStorage.setItem(CHAVE_MANUTENCAO_ACESSO, "granted");
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
  const form = document.getElementById("maintenanceAccessForm");
  const input = document.getElementById("maintenanceAccessCode");
  const status = document.getElementById("maintenanceStatus");

  if (supportEmail) {
    supportEmail.textContent = configuracao.supportEmail || ADMIN_EMAIL;
  }

  if (targetLabel) {
    targetLabel.textContent = descreverDestino(destino);
  }

  if (message && configuracao.announcementMessage) {
    message.textContent = configuracao.announcementMessage;
  }

  if (usuarioEhAdmin() || !configuracao.maintenanceMode || possuiAcessoManutencao()) {
    redirecionarParaDestino(destino);
    return;
  }

  if (!form || !input || !status) {
    return;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const codigo = String(input.value || "").trim();

    status.classList.remove("is-error", "is-success");

    if (codigo !== CODIGO_ACESSO_MANUTENCAO) {
      status.textContent = "Codigo invalido. Verifique o acesso informado e tente novamente.";
      status.classList.add("is-error");
      input.focus();
      input.select();
      return;
    }

    concederAcessoManutencao();
    status.textContent = "Codigo validado. Redirecionando para a ferramenta.";
    status.classList.add("is-success");
    window.setTimeout(() => redirecionarParaDestino(destino), 350);
  });
});
