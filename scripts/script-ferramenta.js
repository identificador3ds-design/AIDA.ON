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

// Os exemplos de cada metodo so descem na primeira vez que o bloco abre. Dentro
// de um <details> fechado o loading="lazy" nao dispara nem apos a abertura, e
// deixar os sete mapas no src custaria ~400 KB a quem so quer enviar a imagem.
function prepararExemplosMetodos() {
  const bloco = document.getElementById("detalhesMetodos");

  if (!bloco) {
    return;
  }

  const carregar = () => {
    bloco.querySelectorAll("img[data-src]").forEach((img) => {
      img.src = img.dataset.src;
      img.removeAttribute("data-src");
    });
  };

  if (bloco.open) {
    carregar();
    return;
  }

  bloco.addEventListener("toggle", carregar, { once: true });
}

document.addEventListener("DOMContentLoaded", () => {
  prepararExemplosMetodos();

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
    function exibirLoginOverlay(e) {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      let overlay = document.getElementById("unlogged-login-overlay");
      if (!overlay) {
        overlay = document.createElement("div");
        overlay.id = "unlogged-login-overlay";
        overlay.className = "login-overlay hidden";
        overlay.innerHTML = `
          <div class="login-overlay-backdrop"></div>
          <div class="login-overlay-card">
              <h2>Faça login para continuar</h2>
              <p>Você atingiu o limite de análises sem conta.</p>
              <a href="./index-login.html" class="btn-estilizado" style="text-decoration:none; display:inline-block; padding:10px 20px;">Fazer Login</a>
          </div>
        `;
        document.body.appendChild(overlay);
        
        const backdrop = overlay.querySelector(".login-overlay-backdrop");
        const card = overlay.querySelector(".login-overlay-card");
        
        backdrop.addEventListener("click", () => {
          card.style.transform = "translateY(150vh)";
          backdrop.style.backgroundColor = "transparent";
          backdrop.style.backdropFilter = "blur(0px)";
          setTimeout(() => overlay.classList.add("hidden"), 400);
        });
      }
      
      overlay.classList.remove("hidden");
      
      setTimeout(() => {
        const backdrop = overlay.querySelector(".login-overlay-backdrop");
        const card = overlay.querySelector(".login-overlay-card");
        card.style.transform = "translateY(0)";
        backdrop.style.backgroundColor = "rgba(0, 0, 0, 0.7)";
        backdrop.style.backdropFilter = "blur(8px)";
      }, 10);
    }

    btnAcaoSelecionar.addEventListener("click", (e) => {
      const isLogged = localStorage.getItem("usuarioNome") || localStorage.getItem("usuarioEmail");
      if (!isLogged && localStorage.getItem("AIDA_AnaliseUnlogged") === "true") {
        exibirLoginOverlay(e);
      } else {
        inputFileBotao.value = "";
        inputFileBotao.click();
      }
    });

    const areaSoltar = document.getElementById("areaSoltar");
    const erroUpload = document.getElementById("erroUpload");

    function mostrarErro(mensagem) {
      if (!erroUpload) {
        alert(mensagem);
        return;
      }
      erroUpload.textContent = mensagem;
      erroUpload.hidden = false;
    }

    function limparErro() {
      if (erroUpload) {
        erroUpload.hidden = true;
      }
    }

    // O Windows nao registra .heic/.avif como image/*, entao `type` vem vazio
    // para justamente os formatos que mais causam duvida. Nesses casos a
    // extensao e a unica pista, e recusar por `type` barraria arquivo valido.
    const EXTENSOES_ACEITAS = ["heic", "heif", "avif", "jpg", "jpeg", "png", "webp", "bmp"];

    function pareceImagem(arquivo) {
      if (arquivo.type) {
        return arquivo.type.startsWith("image/");
      }
      const extensao = (arquivo.name || "").split(".").pop()?.toLowerCase();
      return EXTENSOES_ACEITAS.includes(extensao);
    }

    function processarArquivo(arquivo) {
      if (!arquivo) {
        return;
      }

      if (!pareceImagem(arquivo)) {
        mostrarErro("Esse arquivo não é uma imagem. Escolha um JPG, PNG, WEBP, BMP, HEIC ou AVIF.");
        return;
      }

      limparErro();

      const reader = new FileReader();
      reader.onload = async (evento) => {
        await salvarImagemSelecionada(evento.target.result);
        // Guarda o nome original. O data URL sozinho perde a extensão, e um
        // .heic acabava chegando ao backend renomeado como ".png" — o que
        // funcionava por sorte (o decodificador identifica pelo conteúdo),
        // mas quebrava a validação por extensão.
        try {
          sessionStorage.setItem("AIDA_NomeArquivoSelecionado", arquivo.name || "");
        } catch (erro) {
          /* espaço esgotado: o nome é opcional, seguimos sem ele */
        }
        window.location.href = "./index-analise.html";
      };
      reader.onerror = () => {
        mostrarErro("Não foi possível carregar essa imagem. Tente outro arquivo.");
      };
      reader.readAsDataURL(arquivo);
    }

    inputFileBotao.addEventListener("change", () => {
      processarArquivo(inputFileBotao.files[0]);
    });

    if (areaSoltar) {
      // Fora do cartao, um arquivo solto faria o navegador abri-lo e descartar a
      // pagina. Barrar no documento evita perder a sessao por mira ruim.
      ["dragover", "drop"].forEach((evento) => {
        document.addEventListener(evento, (e) => {
          if (!areaSoltar.contains(e.target)) {
            e.preventDefault();
          }
        });
      });

      // Sem o preventDefault no dragover o navegador abre o arquivo solto em vez
      // de entregar o evento a pagina.
      ["dragenter", "dragover"].forEach((evento) => {
        areaSoltar.addEventListener(evento, (e) => {
          e.preventDefault();
          areaSoltar.classList.add("arrastando");
        });
      });

      ["dragleave", "dragend"].forEach((evento) => {
        areaSoltar.addEventListener(evento, () => {
          areaSoltar.classList.remove("arrastando");
        });
      });

      areaSoltar.addEventListener("drop", (e) => {
        e.preventDefault();
        areaSoltar.classList.remove("arrastando");

        const bloqueado =
          !localStorage.getItem("usuarioNome") &&
          !localStorage.getItem("usuarioEmail") &&
          localStorage.getItem("AIDA_AnaliseUnlogged") === "true";

        if (bloqueado) {
          exibirLoginOverlay();
          return;
        }

        processarArquivo(e.dataTransfer?.files?.[0]);
      });
    }
  }
});


