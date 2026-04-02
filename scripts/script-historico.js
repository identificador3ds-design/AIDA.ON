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

  const carregarHistorico = async () => {
    lista.innerHTML = '<div class="mensagem-vazia">Buscando evidencias na nuvem...</div>';

    const {
      data: { user },
    } = await _supabase.auth.getUser();

    if (!user) {
      lista.innerHTML = '<div class="mensagem-vazia">Voce precisa estar logado para ver o historico.</div>';
      return;
    }

    const { data: registros, error } = await _supabase
      .from("historico_analises")
      .select("*")
      .eq("user_id", user.id)
      .order("data_analise", { ascending: false });

    if (error) {
      lista.innerHTML = '<div class="mensagem-vazia">Erro ao conectar com o banco de dados.</div>';
      return;
    }

    historicoNuvem = registros || [];

    if (!historicoNuvem.length) {
      lista.innerHTML = '<div class="mensagem-vazia">Nenhuma analise encontrada no banco de dados.</div>';
      return;
    }

    lista.innerHTML = "";

    historicoNuvem.forEach((item, index) => {
      const dataFormatada = new Date(item.data_analise).toLocaleString("pt-BR");
      const card = document.createElement("article");
      card.className = "card-historico-item glass-card";
      card.innerHTML = `
        <div class="thumb-container">
          <img src="${item.imagem_original}" alt="Imagem analisada">
        </div>
        <div class="info-historico">
          <span class="data-badge">${dataFormatada}</span>
          <h4>${item.metodo}</h4>
          <div class="status-badge">${item.probabilidade}</div>
        </div>
        <button class="aida-button secondary btn-detalhes" data-index="${index}">Examinar resultado</button>
      `;
      lista.appendChild(card);
    });

    lista.querySelectorAll(".btn-detalhes").forEach((button) => {
      button.addEventListener("click", () => {
        const item = historicoNuvem[Number(button.dataset.index)];
        document.getElementById("modalImgProcessada").src = item.resultado_img || item.imagem_original;
        document.getElementById("modalTitulo").textContent = `Metodo: ${item.metodo}`;
        modal.style.display = "flex";
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
      "Deseja apagar todos os seus registros periciais da nuvem? Esta acao e irreversivel."
    );

    if (!confirmed) {
      return;
    }

    const {
      data: { user },
    } = await _supabase.auth.getUser();

    await _supabase.from("historico_analises").delete().eq("user_id", user.id);
    carregarHistorico();
  });

  carregarHistorico();
});


