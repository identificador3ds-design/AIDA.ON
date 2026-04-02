const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const CHAVE_LOGIN_FEEDBACK = "AIDA_LOGIN_FEEDBACK";
const CONFIG_ADMIN_PADRAO = {
  allowUploadPage: true,
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

function usuarioEhAdmin() {
  const tipo = localStorage.getItem("usuarioTipo");
  const email = (localStorage.getItem("usuarioEmail") || "").trim().toLowerCase();
  return tipo === "admin" || email === ADMIN_EMAIL;
}

document.addEventListener("DOMContentLoaded", () => {
  const btnAcaoSelecionar = document.getElementById("btnAcaoSelecionar");
  const inputFileBotao = document.getElementById("inputFileBotao");
  const configuracaoAdmin = obterAdminConfig();

  if (contaAtualSemAcesso()) {
    localStorage.removeItem("usuarioNome");
    localStorage.removeItem("usuarioEmail");
    localStorage.removeItem("usuarioTipo");
    localStorage.setItem(
      CHAVE_LOGIN_FEEDBACK,
      "Seu acesso foi bloqueado pelo administrador."
    );
    window.location.href = "./index-login.html";
    return;
  }

  if (!configuracaoAdmin.allowUploadPage && !usuarioEhAdmin()) {
    window.location.href = "./index-apresentacao.html";
    return;
  }

  if (btnAcaoSelecionar && inputFileBotao) {
    btnAcaoSelecionar.addEventListener("click", () => {
      inputFileBotao.click();
    });

    inputFileBotao.addEventListener("change", () => {
      const arquivo = inputFileBotao.files[0];

      if (arquivo) {
        const reader = new FileReader();
        reader.onload = (evento) => {
          localStorage.setItem("AIDA_ImagemSelecionada", evento.target.result);
          window.location.href = "./index-analise.html";
        };
        reader.readAsDataURL(arquivo);
      }
    });
  }
});


