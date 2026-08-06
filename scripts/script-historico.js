const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);
const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const CHAVE_LOGIN_FEEDBACK = "AIDA_LOGIN_FEEDBACK";
const CONFIG_ADMIN_PADRAO = {
  allowRegistrations: true,
  enableInstallPrompt: true,
  maintenanceMode: false,
  allowHistoryPage: true,
  supportEmail: ADMIN_EMAIL,
  announcementMessage: "",
  accountStates: {},
};
const favicon = document.getElementById('favicon');

function updateFavicon() {

  if (!favicon) return;
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

function renderizarAvisoSistema() {
  const configuracao = obterAdminConfig();
  const mensagem = String(configuracao.announcementMessage || "").trim();
  const mensagens = [];
  let possuiAvisoPrincipal = false;

  if (configuracao.maintenanceMode) {
    mensagens.push("Modo manutenção ativo.");
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

  if (document.getElementById("systemNotice")) {
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

  document.body.appendChild(aviso);
}

function escaparHtml(valor) {
  return String(valor ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function removerEvidenciasUsuario(userId) {
  if (!userId) {
    return;
  }

  const { data, error } = await _supabase.storage.from("evidencias").list(userId, {
    limit: 1000,
  });

  if (error) {
    console.warn("Nao foi possivel listar evidencias do usuario:", error.message);
    return;
  }

  const caminhos = (data || [])
    .filter((item) => item?.name)
    .map((item) => `${userId}/${item.name}`);

  if (!caminhos.length) {
    return;
  }

  const { error: removeError } = await _supabase.storage.from("evidencias").remove(caminhos);

  if (removeError) {
    console.warn("Nao foi possivel remover todas as evidencias:", removeError.message);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const configuracaoAdmin = obterAdminConfig();
  const tipoUsuario = localStorage.getItem("usuarioTipo");

  if (!configuracaoAdmin.allowHistoryPage && tipoUsuario !== "admin") {
      window.location.href = "./index-analise.html";
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
    window.location.href = "./index-login.html";
    return;
  }

  renderizarAvisoSistema();
  const lista = document.getElementById("listaHistorico");
  const modal = document.getElementById("modalDetalhes");
  const btnLimpar = document.getElementById("btnLimparHistorico");
  const btnFechar = document.querySelector(".btn-fechar-modal");

  let historicoNuvem = [];

  // Botão Voltar agora gerido diretamente no HTML via onclick

  const carregarHistorico = async () => {
    lista.innerHTML = '<div style="padding: 30px; text-align: center; color: var(--neutral);">Buscando evidências na nuvem...</div>';

    const {
      data: { user },
    } = await _supabase.auth.getUser();

    if (!user) {
      lista.innerHTML = '<div style="padding: 30px; text-align: center; color: var(--neutral);">Você precisa estar logado para ver o histórico.</div>';
      return;
    }

    const { data: registros, error } = await _supabase
      .from("historico_analises")
      .select("*")
      .eq("user_id", user.id)
      .order("data_analise", { ascending: false });

    if (error) {
      lista.innerHTML = '<div style="padding: 30px; text-align: center; color: var(--neutral);">Erro ao conectar com o banco de dados.</div>';
      alert("Erro ao buscar histórico: " + error.message);
      return;
    }

    historicoNuvem = registros || [];

    if (!historicoNuvem.length) {
      lista.innerHTML = '<div style="padding: 30px; text-align: center; color: var(--neutral);">Nenhuma análise encontrada no banco de dados.</div>';
      // alert("Nenhum histórico encontrado para o usuário: " + user.id);
      return;
    }

    lista.innerHTML = "";

    historicoNuvem.forEach((item, index) => {
      const dataFormatada = new Date(item.data_analise).toLocaleString("pt-BR");
      const card = document.createElement("div");
      card.className = "action-item";
      card.innerHTML = `
        <a href="javascript:void(0)" class="btn-detalhes" data-index="${index}" style="display: flex; align-items: center; gap: 16px; flex: 1; text-decoration: none;">
          <div class="action-item-icon history-thumb">
            <img src="${escaparHtml(item.imagem_original)}" alt="Evidência">
          </div>
          <div class="action-item-text">
            <span class="action-title">${escaparHtml(item.metodo)} <span style="font-size: 0.8rem; opacity: 0.8; margin-left: 6px;">${escaparHtml(item.probabilidade)}</span></span>
            <span class="action-desc">${escaparHtml(dataFormatada)}</span>
          </div>
        </a>
        <button class="btn-apagar-item" data-id="${item.id}" data-url="${item.imagem_original}" title="Apagar análise" style="background: none; border: none; color: #ff6b6b; cursor: pointer; padding: 8px; transition: opacity 0.2s;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
             <polyline points="3 6 5 6 21 6"></polyline>
             <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      `;
      lista.appendChild(card);
    });

    lista.querySelectorAll(".btn-detalhes").forEach((button) => {
      button.addEventListener("click", () => {
        const item = historicoNuvem[Number(button.dataset.index)];
        document.getElementById("modalImgProcessada").src = item.resultado_img || item.imagem_original;
        document.getElementById("modalTitulo").textContent = `Método: ${item.metodo}`;
        modal.style.display = "flex";
      });
    });

    lista.querySelectorAll(".btn-apagar-item").forEach((button) => {
      button.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = button.dataset.id;
        const url = button.dataset.url;
        
        const confirmed = window.confirm("Deseja realmente apagar esta análise?");
        if (!confirmed) return;
        
        button.style.opacity = "0.5";
        button.disabled = true;
        
        if (url && url.includes("/evidencias/")) {
          const path = url.split("/evidencias/")[1];
          await _supabase.storage.from("evidencias").remove([path]);
        }
        
        const { error } = await _supabase.from("historico_analises").delete().eq("id", id);
        
        if (error) {
          alert("Erro ao apagar análise: " + error.message);
          button.style.opacity = "1";
          button.disabled = false;
        } else {
          carregarHistorico();
        }
      });
    });
  };

  btnFechar.addEventListener("click", () => {
    modal.style.display = "none";
  });

  window.addEventListener("click", (event) => {
    if (event.target === modal) {
      modal.style.display = "none";
    }
  });

  btnLimpar.addEventListener("click", async () => {
    const confirmed = window.confirm(
      "Deseja apagar todos os seus registros periciais da nuvem? Esta ação é irreversível."
    );

    if (!confirmed) {
      return;
    }

    const {
      data: { user },
    } = await _supabase.auth.getUser();

    if (!user) {
      lista.innerHTML = '<div class="mensagem-vazia">Voce precisa estar logado para limpar o historico.</div>';
      return;
    }

    btnLimpar.disabled = true;
    lista.innerHTML = '<div class="mensagem-vazia">Removendo historico e evidencias salvas...</div>';

    await removerEvidenciasUsuario(user.id);
    const { error } = await _supabase.from("historico_analises").delete().eq("user_id", user.id);

    if (error) {
      lista.innerHTML = '<div class="mensagem-vazia">Nao foi possivel limpar o historico agora.</div>';
      btnLimpar.disabled = false;
      return;
    }

    btnLimpar.disabled = false;
    carregarHistorico();
  });

  carregarHistorico();
});


