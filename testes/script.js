const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const CHAVE_LOGIN_FEEDBACK = "AIDA_LOGIN_FEEDBACK";
const CONFIG_ADMIN_PADRAO = {
  allowRegistrations: true,
  enableInstallPrompt: true,
  maintenanceMode: false,
  allowProfilePage: true,
  supportEmail: ADMIN_EMAIL,
  announcementMessage: "",
  accountStates: {},
};

function obterAdminConfig() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_ADMIN_CONFIG) || "{}");
    const accountStates = {};

    if (salvo.accountStates && typeof salvo.accountStates === "object") {
      Object.entries(salvo.accountStates).forEach(([email, dados]) => {
        const emailNormalizado = String(email || "").trim().toLowerCase();

        if (!emailNormalizado || emailNormalizado === ADMIN_EMAIL) {
          return;
        }

        accountStates[emailNormalizado] = {
          status: ["active", "blocked", "deleted"].includes(dados?.status)
            ? dados.status
            : "active",
        };
      });
    }

    return { ...CONFIG_ADMIN_PADRAO, ...salvo, accountStates };
  } catch (erro) {
    return { ...CONFIG_ADMIN_PADRAO };
  }
}

function contaAtualSemAcesso() {
  const email = (localStorage.getItem("usuarioEmail") || "").trim().toLowerCase();

  if (!email || email === ADMIN_EMAIL) {
    return false;
  }

  const status = obterAdminConfig().accountStates[email]?.status || "active";
  return ["blocked", "deleted"].includes(status);
}

function renderizarAvisoSistema() {
  const configuracao = obterAdminConfig();
  const mensagem = String(configuracao.announcementMessage || "").trim();
  const mensagens = [];
  let possuiAvisoPrincipal = false;

  if (configuracao.maintenanceMode) {
    mensagens.push("Modo manutencao ativo.");
    possuiAvisoPrincipal = true;
  }

  if (mensagem) {
    mensagens.push(mensagem);
    possuiAvisoPrincipal = true;
  }

  if (possuiAvisoPrincipal && configuracao.supportEmail) {
    mensagens.push(`Contato: ${configuracao.supportEmail}.`);
  }

  if (!mensagens.length) {
    return;
  }

  const main = document.querySelector("main");

  if (!main || document.getElementById("systemNotice")) {
    return;
  }

  const aviso = document.createElement("section");
  aviso.id = "systemNotice";
  aviso.className = "system-notice";
  const conteudo = document.createElement("div");
  conteudo.className = "system-notice-inner";

  const etiqueta = document.createElement("span");
  etiqueta.className = "system-notice-kicker";
  etiqueta.textContent = "Aviso do sistema";

  const texto = document.createElement("p");
  texto.textContent = mensagens.join(" ");

  conteudo.appendChild(etiqueta);
  conteudo.appendChild(texto);
  aviso.appendChild(conteudo);

  main.insertBefore(aviso, main.firstChild);
}

document.addEventListener("DOMContentLoaded", () => {
  const configuracaoAdmin = obterAdminConfig();

  if (!configuracaoAdmin.allowProfilePage && !localStorage.getItem("usuarioTipo")?.includes("admin")) {
    window.location.href = "../Tela-apresenta%C3%A7%C3%A3o/index-apresenta%C3%A7%C3%A3o.html";
    return;
  }

  if (contaAtualSemAcesso()) {
    localStorage.removeItem("usuarioNome");
    localStorage.removeItem("usuarioEmail");
    localStorage.removeItem("usuarioTipo");
    localStorage.setItem(
      CHAVE_LOGIN_FEEDBACK,
      "Seu acesso foi bloqueado pelo administrador."
    );
    window.location.href = "../login/index-login.html";
    return;
  }

  renderizarAvisoSistema();
  const nomeSalvo = localStorage.getItem("usuarioNome");
  const emailSalvo = localStorage.getItem("usuarioEmail");
  const tipoSalvo = localStorage.getItem("usuarioTipo");
  const nome = document.getElementById("nome-usuario");
  const email = document.getElementById("email-usuario");
  const logoutLink = document.getElementById("logout-link");
  const adminLink = document.createElement("a");

  if (nome) {
    nome.textContent = tipoSalvo === "admin" ? "Admin" : nomeSalvo || "Usuario";
  }

  if (email) {
    email.textContent = emailSalvo || "usuarioaida@gmail.com";
  }

  if (tipoSalvo === "admin") {
    adminLink.href = "../Administrador/index-admin.html";
    adminLink.className = "profile-action glass-card";
    adminLink.innerHTML = `
      <span class="action-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M12 3L4 7V12C4 17 7.4 21.2 12 22C16.6 21.2 20 17 20 12V7L12 3Z" />
          <path d="M9.5 12L11.2 13.7L14.8 10.1" />
        </svg>
      </span>
      <strong>Painel admin</strong>
    `;

    const actions = document.querySelector(".profile-actions");

    if (actions) {
      actions.insertBefore(adminLink, actions.firstChild);
    }
  }

  if (logoutLink) {
    logoutLink.addEventListener("click", () => {
      localStorage.removeItem("usuarioNome");
      localStorage.removeItem("usuarioEmail");
      localStorage.removeItem("usuarioTipo");
    });
  }
});
