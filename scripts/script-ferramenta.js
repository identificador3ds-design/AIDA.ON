const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const CHAVE_LOGIN_FEEDBACK = "AIDA_LOGIN_FEEDBACK";
const CHAVE_IMAGEM_SELECIONADA = "AIDA_ImagemSelecionada";
const DB_IMAGEM_SELECIONADA = "AIDA_ImagemSelecionada_DB";
const STORE_IMAGEM_SELECIONADA = "imagem";
const CONFIG_ADMIN_PADRAO = {
  maintenanceMode: false,
  allowUploadPage: true,
  accountStates: {},
};
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

function redirecionarParaManutencao(destino = "./index-seleciona.html") {
  window.location.href = `./index-manutencao.html?redirect=${encodeURIComponent(destino)}`;
}

function abrirBancoImagemSelecionada() {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      reject(new Error("IndexedDB indisponivel."));
      return;
    }

    const request = indexedDB.open(DB_IMAGEM_SELECIONADA, 1);

    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE_IMAGEM_SELECIONADA);
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Nao foi possivel abrir o banco."));
  });
}

async function salvarImagemSelecionadaNoBanco(imagemBase64) {
  const db = await abrirBancoImagemSelecionada();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_IMAGEM_SELECIONADA, "readwrite");
    transaction.objectStore(STORE_IMAGEM_SELECIONADA).put(imagemBase64, CHAVE_IMAGEM_SELECIONADA);
    transaction.oncomplete = () => {
      db.close();
      resolve();
    };
    transaction.onerror = () => {
      db.close();
      reject(transaction.error || new Error("Nao foi possivel salvar a imagem."));
    };
  });
}

async function salvarImagemSelecionada(imagemBase64) {
  try {
    await salvarImagemSelecionadaNoBanco(imagemBase64);
  } catch (erro) {
    console.warn("Nao foi possivel salvar a imagem no IndexedDB:", erro);
  }

  try {
    sessionStorage.setItem(CHAVE_IMAGEM_SELECIONADA, imagemBase64);
  } catch (erro) {
    sessionStorage.removeItem(CHAVE_IMAGEM_SELECIONADA);
  }

  try {
    localStorage.setItem(CHAVE_IMAGEM_SELECIONADA, imagemBase64);
  } catch (erro) {
    localStorage.removeItem(CHAVE_IMAGEM_SELECIONADA);
  }
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

  if (
    configuracaoAdmin.maintenanceMode &&
    !usuarioEhAdmin()
  ) {
    redirecionarParaManutencao("./index-seleciona.html");
    return;
  }

  if (
    !configuracaoAdmin.allowUploadPage &&
    !configuracaoAdmin.maintenanceMode &&
    !usuarioEhAdmin()
  ) {
    window.location.href = "./index-apresentacao.html";
    return;
  }

  if (btnAcaoSelecionar && inputFileBotao) {
    btnAcaoSelecionar.addEventListener("click", () => {
      inputFileBotao.value = "";
      inputFileBotao.click();
    });

    inputFileBotao.addEventListener("change", () => {
      const arquivo = inputFileBotao.files[0];

      if (arquivo) {
        const reader = new FileReader();
        reader.onload = async (evento) => {
          await salvarImagemSelecionada(evento.target.result);
          window.location.href = "./index-analise.html";
        };
        reader.onerror = () => {
          alert("Nao foi possivel carregar a imagem selecionada. Tente outro arquivo.");
        };
        reader.readAsDataURL(arquivo);
      }
    });
  }
});


