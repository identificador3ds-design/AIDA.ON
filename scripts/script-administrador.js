const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);
const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const CHAVE_ADMIN_LAST_ACCESS = "AIDA_ADMIN_LAST_ACCESS";
const CHAVE_ADMIN_REDIRECT_MESSAGE = "AIDA_ADMIN_REDIRECT_MESSAGE";

const METODOS_PADRAO = {
  FFT: {
    label: "FFT",
    enabled: true,
    backendReady: true,
    descricao: "Analise espectral para observar frequencias e padroes menos naturais.",
  },
  PSEM: {
    label: "PSEM",
    enabled: false,
    backendReady: false,
    descricao: "Espaco reservado para metodo experimental ainda nao conectado no backend.",
  },
  M4: {
    label: "LSB",
    enabled: true,
    backendReady: true,
    descricao: "Leitura do plano de bits menos significativos para sinais artificiais.",
  },
  GRAD: {
    label: "Gradiente Laplaciano (Neon)",
    enabled: true,
    backendReady: true,
    descricao: "Realce de bordas e texturas para encontrar artefatos de geracao.",
  },
};

const MODULOS_SISTEMA = [
  {
    nome: "Login e cadastro",
    descricao: "Acesso principal do usuario e controle de novas entradas na plataforma.",
    href: "./index-login.html",
  },
  {
    nome: "Tela de apresentacao",
    descricao: "Pagina institucional com visao geral da proposta e entrada para a jornada.",
    href: "./index-apresentacao.html",
  },
  {
    nome: "Selecao de imagem",
    descricao: "Entrada do upload e troca de imagem antes da etapa tecnica.",
    href: "./index-seleciona.html",
  },
  {
    nome: "Analise forense",
    descricao: "Tela operacional onde o usuario escolhe metodo, ve o processamento e o resultado.",
    href: "./index-analise.html",
  },
  {
    nome: "Historico de analises",
    descricao: "Consulta dos registros salvos na conta e revisao de evidencias anteriores.",
    href: "./index-historico.html",
  },
  {
    nome: "Perfil do usuario",
    descricao: "Pagina de conta com atalhos pessoais e acesso rapido para retorno ao site.",
    href: "./index-perfil.html",
  },
];

const CONFIG_ADMIN_PADRAO = {
  allowRegistrations: true,
  enableInstallPrompt: true,
  maintenanceMode: false,
  allowUploadPage: true,
  allowHistoryPage: true,
  allowProfilePage: true,
  lockAnalysisPage: false,
  defaultWatermarkCheck: true,
  defaultMetadataCheck: true,
  supportEmail: ADMIN_EMAIL,
  announcementMessage: "",
  analysisButtonLabel: "Analisar imagem",
  methods: METODOS_PADRAO,
  accountStates: {},
};

let cacheUsuarios = [];
let filtroUsuariosAtual = "";

function escaparHtml(valor) {
  return String(valor ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function normalizarEstadosConta(salvo = {}) {
  const estados = {};

  if (salvo && typeof salvo === "object" && !Array.isArray(salvo)) {
    Object.entries(salvo).forEach(([email, dados]) => {
      const emailNormalizado = String(email || "").trim().toLowerCase();

      if (!emailNormalizado || emailNormalizado === ADMIN_EMAIL) {
        return;
      }

      estados[emailNormalizado] = {
        name: String(dados?.name || "").trim(),
        origin: String(dados?.origin || "").trim(),
        status: ["active", "blocked", "deleted"].includes(dados?.status)
          ? dados.status
          : "active",
        updatedAt: String(dados?.updatedAt || "").trim(),
      };
    });
  }

  return estados;
}

function normalizarMetodos(salvos = {}) {
  const metodos = {};

  Object.keys(METODOS_PADRAO).forEach((chave) => {
    metodos[chave] = {
      ...METODOS_PADRAO[chave],
      ...(salvos?.[chave] || {}),
    };

    metodos[chave].label =
      String(metodos[chave].label || METODOS_PADRAO[chave].label).trim() ||
      METODOS_PADRAO[chave].label;
    metodos[chave].descricao =
      String(metodos[chave].descricao || METODOS_PADRAO[chave].descricao).trim() ||
      METODOS_PADRAO[chave].descricao;
    metodos[chave].enabled = Boolean(metodos[chave].enabled);
    metodos[chave].backendReady = Boolean(metodos[chave].backendReady);
  });

  return metodos;
}

function normalizarAdminConfig(salvo = {}) {
  const config = {
    ...CONFIG_ADMIN_PADRAO,
    ...salvo,
  };

  const estadosConta = normalizarEstadosConta(config.accountStates);

  if (Array.isArray(salvo.blockedEmails)) {
    salvo.blockedEmails.forEach((email) => {
      const emailNormalizado = String(email || "").trim().toLowerCase();

      if (!emailNormalizado || emailNormalizado === ADMIN_EMAIL) {
        return;
      }

      estadosConta[emailNormalizado] = {
        ...(estadosConta[emailNormalizado] || {}),
        status: "blocked",
      };
    });
  }

  if (Array.isArray(salvo.deletedEmails)) {
    salvo.deletedEmails.forEach((email) => {
      const emailNormalizado = String(email || "").trim().toLowerCase();

      if (!emailNormalizado || emailNormalizado === ADMIN_EMAIL) {
        return;
      }

      estadosConta[emailNormalizado] = {
        ...(estadosConta[emailNormalizado] || {}),
        status: "deleted",
      };
    });
  }

  return {
    ...CONFIG_ADMIN_PADRAO,
    ...config,
    supportEmail: String(config.supportEmail || ADMIN_EMAIL).trim() || ADMIN_EMAIL,
    announcementMessage: String(config.announcementMessage || "").trim(),
    analysisButtonLabel:
      String(config.analysisButtonLabel || CONFIG_ADMIN_PADRAO.analysisButtonLabel).trim() ||
      CONFIG_ADMIN_PADRAO.analysisButtonLabel,
    methods: normalizarMetodos(config.methods),
    accountStates: estadosConta,
  };
}

function obterAdminConfig() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_ADMIN_CONFIG) || "{}");
    return normalizarAdminConfig(salvo);
  } catch (erro) {
    return normalizarAdminConfig();
  }
}

function salvarAdminConfig(configuracao) {
  const configNormalizado = normalizarAdminConfig(configuracao);
  localStorage.setItem(CHAVE_ADMIN_CONFIG, JSON.stringify(configNormalizado));
  return configNormalizado;
}

function usuarioEhAdmin() {
  const tipo = localStorage.getItem("usuarioTipo");
  const email = (localStorage.getItem("usuarioEmail") || "").trim().toLowerCase();
  return tipo === "admin" || email === ADMIN_EMAIL;
}

function redirecionarSeNaoAdmin() {
  if (usuarioEhAdmin()) {
    return false;
  }

  const possuiSessaoComum =
    Boolean(localStorage.getItem("usuarioNome")) ||
    Boolean(localStorage.getItem("usuarioEmail"));

  if (possuiSessaoComum) {
    window.location.href = "./index-apresentacao.html";
    return true;
  }

  localStorage.setItem(
    CHAVE_ADMIN_REDIRECT_MESSAGE,
    "Acesso restrito. Entre com a conta administrativa para abrir o painel."
  );
  window.location.href = "./index-login.html";
  return true;
}

function formatarData(dataIso) {
  if (!dataIso) {
    return "Agora";
  }

  try {
    return new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(dataIso));
  } catch (erro) {
    return "Agora";
  }
}

function atualizarUltimoAcesso() {
  const ultimoAcesso = document.getElementById("adminLastAccess");
  const acessoAnterior = localStorage.getItem(CHAVE_ADMIN_LAST_ACCESS);

  if (ultimoAcesso) {
    ultimoAcesso.textContent = acessoAnterior
      ? formatarData(acessoAnterior)
      : "Primeiro acesso";
  }

  localStorage.setItem(CHAVE_ADMIN_LAST_ACCESS, new Date().toISOString());
}

function definirStatusConfiguracao(texto, tipo = "neutro") {
  const status = document.getElementById("configStatus");

  if (!status) {
    return;
  }

  const cores = {
    neutro: "var(--text-soft)",
    sucesso: "rgba(145, 236, 208, 0.98)",
    erro: "#ffbcbc",
  };

  status.textContent = texto;
  status.style.color = cores[tipo] || cores.neutro;
}

function atualizarEstatistica(id, valor) {
  const elemento = document.getElementById(id);

  if (elemento) {
    elemento.textContent = String(valor);
  }
}

function atualizarPreviewSuporte(configuracao) {
  const suporte = document.getElementById("adminSupportPreview");

  if (suporte) {
    suporte.textContent = configuracao.supportEmail;
  }
}

function contarControlesAtivos(configuracao) {
  return [
    configuracao.allowRegistrations,
    configuracao.enableInstallPrompt,
    configuracao.maintenanceMode,
    configuracao.allowUploadPage,
    configuracao.allowHistoryPage,
    configuracao.allowProfilePage,
    configuracao.lockAnalysisPage,
    configuracao.defaultWatermarkCheck,
    configuracao.defaultMetadataCheck,
  ].filter(Boolean).length;
}

function preencherFormulario(configuracao) {
  const mapInputs = {
    configSupportEmail: configuracao.supportEmail,
    configAnnouncement: configuracao.announcementMessage,
    configAnalysisButtonLabel: configuracao.analysisButtonLabel,
  };

  Object.entries(mapInputs).forEach(([id, valor]) => {
    const elemento = document.getElementById(id);

    if (elemento) {
      elemento.value = valor;
    }
  });

  const mapCheckboxes = {
    configAllowRegistrations: configuracao.allowRegistrations,
    configEnableInstallPrompt: configuracao.enableInstallPrompt,
    configMaintenanceMode: configuracao.maintenanceMode,
    configAllowUploadPage: configuracao.allowUploadPage,
    configAllowHistoryPage: configuracao.allowHistoryPage,
    configAllowProfilePage: configuracao.allowProfilePage,
    configLockAnalysisPage: configuracao.lockAnalysisPage,
    configDefaultWatermarkCheck: configuracao.defaultWatermarkCheck,
    configDefaultMetadataCheck: configuracao.defaultMetadataCheck,
  };

  Object.entries(mapCheckboxes).forEach(([id, valor]) => {
    const elemento = document.getElementById(id);

    if (elemento) {
      elemento.checked = Boolean(valor);
    }
  });

  renderizarMetodosConfiguraveis(configuracao);
  renderizarResumoVivo(configuracao);
  atualizarMiniBoard(configuracao);
  atualizarPreviewSuporte(configuracao);
}

function lerConfiguracaoMetodos(configAtual) {
  const metodos = {};

  Object.keys(METODOS_PADRAO).forEach((chave) => {
    const valorAtual = configAtual.methods[chave] || METODOS_PADRAO[chave];
    const inputLabel = document.querySelector(`[data-method-label="${chave}"]`);
    const inputDescricao = document.querySelector(`[data-method-description="${chave}"]`);
    const inputEnabled = document.querySelector(`[data-method-enabled="${chave}"]`);
    const inputBackendReady = document.querySelector(`[data-method-backend="${chave}"]`);

    metodos[chave] = {
      ...valorAtual,
      label:
        String(inputLabel?.value || valorAtual.label || METODOS_PADRAO[chave].label).trim() ||
        METODOS_PADRAO[chave].label,
      descricao:
        String(
          inputDescricao?.value || valorAtual.descricao || METODOS_PADRAO[chave].descricao
        ).trim() || METODOS_PADRAO[chave].descricao,
      enabled: Boolean(inputEnabled?.checked),
      backendReady: Boolean(inputBackendReady?.checked),
    };
  });

  return metodos;
}

function lerFormularioConfiguracao() {
  const configAtual = obterAdminConfig();

  return normalizarAdminConfig({
    ...configAtual,
    supportEmail:
      String(document.getElementById("configSupportEmail")?.value || "").trim() || ADMIN_EMAIL,
    announcementMessage: String(
      document.getElementById("configAnnouncement")?.value || ""
    ).trim(),
    analysisButtonLabel:
      String(document.getElementById("configAnalysisButtonLabel")?.value || "").trim() ||
      CONFIG_ADMIN_PADRAO.analysisButtonLabel,
    allowRegistrations: Boolean(document.getElementById("configAllowRegistrations")?.checked),
    enableInstallPrompt: Boolean(document.getElementById("configEnableInstallPrompt")?.checked),
    maintenanceMode: Boolean(document.getElementById("configMaintenanceMode")?.checked),
    allowUploadPage: Boolean(document.getElementById("configAllowUploadPage")?.checked),
    allowHistoryPage: Boolean(document.getElementById("configAllowHistoryPage")?.checked),
    allowProfilePage: Boolean(document.getElementById("configAllowProfilePage")?.checked),
    lockAnalysisPage: Boolean(document.getElementById("configLockAnalysisPage")?.checked),
    defaultWatermarkCheck: Boolean(
      document.getElementById("configDefaultWatermarkCheck")?.checked
    ),
    defaultMetadataCheck: Boolean(
      document.getElementById("configDefaultMetadataCheck")?.checked
    ),
    methods: lerConfiguracaoMetodos(configAtual),
  });
}

function renderizarResumoVivo(configuracao) {
  const preview = document.getElementById("configPreviewList");

  if (!preview) {
    return;
  }

  const itens = [
    {
      titulo: "Cadastros",
      descricao: configuracao.allowRegistrations
        ? "Novas contas permitidas"
        : "Cadastro fechado",
      selo: configuracao.allowRegistrations ? "Liberado" : "Pausado",
    },
    {
      titulo: "Modo manutencao",
      descricao: configuracao.maintenanceMode
        ? "Tela de manutencao ativa com acesso temporario por codigo."
        : "Ferramenta aberta sem barreira de manutencao.",
      selo: configuracao.maintenanceMode ? "Ativo" : "Livre",
    },
    {
      titulo: "Acessos",
      descricao: `${
        [configuracao.allowUploadPage, configuracao.allowHistoryPage, configuracao.allowProfilePage]
          .filter(Boolean)
          .length
      } areas liberadas para o usuario`,
      selo: "Fluxo",
    },
    {
      titulo: "Analise",
      descricao: configuracao.lockAnalysisPage
        ? "Processamento travado"
        : "Processamento ativo",
      selo: configuracao.lockAnalysisPage ? "Travada" : "Online",
    },
    {
      titulo: "Botao principal",
      descricao: configuracao.analysisButtonLabel,
      selo: "CTA",
    },
  ];

  preview.innerHTML = itens
    .map(
      (item) => `
        <article class="preview-item">
          <div>
            <strong>${escaparHtml(item.titulo)}</strong>
            <span>${escaparHtml(item.descricao)}</span>
          </div>
          <span class="preview-pill">${escaparHtml(item.selo)}</span>
        </article>
      `
    )
    .join("");
}

function renderizarMetodosConfiguraveis(configuracao) {
  const grade = document.getElementById("methodsConfigGrid");

  if (!grade) {
    return;
  }

  grade.innerHTML = Object.entries(configuracao.methods)
    .map(([chave, metodo]) => {
      const cardClass = metodo.enabled
        ? "method-config-panel"
        : "method-config-panel is-disabled";
      const badgeBackend = metodo.backendReady
        ? '<span class="micro-pill">Backend pronto</span>'
        : '<span class="micro-pill warning">Backend pendente</span>';

      return `
        <article class="${cardClass}">
          <div class="method-config-head">
            <div>
              <h3>${escaparHtml(chave)}</h3>
              <p>${escaparHtml(metodo.descricao)}</p>
            </div>
            <div class="method-config-meta">
              ${badgeBackend}
              <span class="micro-pill">${metodo.enabled ? "Ativo" : "Oculto"}</span>
            </div>
          </div>

          <div class="method-config-body">
            <div class="admin-field">
              <label for="methodLabel-${chave}">Nome exibido ao usuario</label>
              <input
                id="methodLabel-${chave}"
                data-method-label="${chave}"
                type="text"
                class="field-input"
                value="${escaparHtml(metodo.label)}"
              >
            </div>

            <div class="admin-field">
              <label for="methodDescription-${chave}">Descricao interna do metodo</label>
              <textarea
                id="methodDescription-${chave}"
                data-method-description="${chave}"
                class="field-textarea"
                rows="4"
              >${escaparHtml(metodo.descricao)}</textarea>
            </div>
          </div>

          <div class="method-config-switches">
            <label class="method-config-switch" for="methodEnabled-${chave}">
              <div>
                <strong>Metodo visivel na analise</strong>
                <span>Controla se o metodo aparece no seletor publico.</span>
              </div>
              <input
                id="methodEnabled-${chave}"
                data-method-enabled="${chave}"
                type="checkbox"
                ${metodo.enabled ? "checked" : ""}
              >
            </label>

            <label class="method-config-switch" for="methodBackend-${chave}">
              <div>
                <strong>Backend liberado</strong>
                <span>Permite uso operacional real do metodo escolhido.</span>
              </div>
              <input
                id="methodBackend-${chave}"
                data-method-backend="${chave}"
                type="checkbox"
                ${metodo.backendReady ? "checked" : ""}
              >
            </label>
          </div>
        </article>
      `;
    })
    .join("");
}

function atualizarMiniBoard(configuracao) {
  const estados = Object.values(configuracao.accountStates);
  const bloqueadas = estados.filter((item) => item.status === "blocked" || item.status === "deleted");
  const metodosAtivos = Object.values(configuracao.methods).filter((item) => item.enabled).length;

  atualizarEstatistica("blockedUsersCount", bloqueadas.length);
  atualizarEstatistica("activeMethodsCount", metodosAtivos);
}

function obterSeloModulo(modulo, configuracao) {
  if (
    configuracao.maintenanceMode &&
    ["Selecao de imagem", "Analise forense"].includes(modulo.nome)
  ) {
    return "Acesso por codigo";
  }

  if (modulo.nome === "Login e cadastro") {
    return configuracao.allowRegistrations ? "Cadastro aberto" : "Cadastro pausado";
  }

  if (modulo.nome === "Selecao de imagem") {
    return configuracao.allowUploadPage ? "Upload liberado" : "Upload fechado";
  }

  if (modulo.nome === "Historico de analises") {
    return configuracao.allowHistoryPage ? "Historico visivel" : "Historico oculto";
  }

  if (modulo.nome === "Perfil do usuario") {
    return configuracao.allowProfilePage ? "Perfil visivel" : "Perfil oculto";
  }

  if (modulo.nome === "Analise forense") {
    return configuracao.lockAnalysisPage ? "Processamento travado" : "Processamento ativo";
  }

  return "Disponivel";
}

function obterDescricaoModulo(modulo, configuracao) {
  if (modulo.nome === "Login e cadastro") {
    return configuracao.allowRegistrations
      ? "Usuarios ainda conseguem criar novas contas normalmente."
      : "O login continua ativo, mas novos registros foram fechados.";
  }

  if (modulo.nome === "Selecao de imagem") {
    if (configuracao.maintenanceMode) {
      return "A tentativa de entrada e enviada para a tela de manutencao.";
    }

    return configuracao.allowUploadPage
      ? "O usuario pode entrar na etapa de upload e trocar a imagem enviada."
      : "A entrada da jornada foi bloqueada temporariamente pelo painel.";
  }

  if (modulo.nome === "Historico de analises") {
    return configuracao.allowHistoryPage
      ? "Historico pessoal visivel para consulta dos registros salvos."
      : "Historico foi escondido do usuario final.";
  }

  if (modulo.nome === "Perfil do usuario") {
    return configuracao.allowProfilePage
      ? "Pagina de conta liberada com atalhos e informacoes pessoais."
      : "O atalho de perfil foi retirado temporariamente da experiencia.";
  }

  if (modulo.nome === "Analise forense") {
    if (configuracao.maintenanceMode) {
      return "A analise fica protegida por uma tela intermediaria com codigo temporario.";
    }

    return configuracao.lockAnalysisPage
      ? "A tela continua visivel, mas o processamento fica travado."
      : "A analise continua operacional com o CTA configurado pelo painel.";
  }

  if (modulo.nome === "Tela de apresentacao") {
    return configuracao.maintenanceMode || configuracao.announcementMessage
      ? "A home exibe aviso institucional e se adapta ao estado operacional."
      : modulo.descricao;
  }

  return modulo.descricao;
}

function renderizarFerramentas(configuracao) {
  const toolsGrid = document.getElementById("toolsGrid");

  if (!toolsGrid) {
    return;
  }

  toolsGrid.innerHTML = MODULOS_SISTEMA.map(
    (modulo) => `
      <article class="tool-row">
        <div class="tool-row-main">
          <div class="tool-row-head">
            <h3>${escaparHtml(modulo.nome)}</h3>
            <span class="micro-pill">${escaparHtml(obterSeloModulo(modulo, configuracao))}</span>
          </div>
          <p>${escaparHtml(obterDescricaoModulo(modulo, configuracao))}</p>
        </div>
        <a href="${modulo.href}" class="tool-link">Abrir modulo</a>
      </article>
    `
  ).join("");

  atualizarEstatistica("statTools", MODULOS_SISTEMA.length);
  atualizarEstatistica("statConfigs", contarControlesAtivos(configuracao));
}

function obterStatusConta(email, configuracao) {
  if (email === ADMIN_EMAIL) {
    return "admin";
  }

  return configuracao.accountStates[email]?.status || "active";
}

function humanizarStatusConta(status) {
  if (status === "blocked") {
    return "Bloqueada";
  }

  if (status === "deleted") {
    return "Removida";
  }

  if (status === "admin") {
    return "Admin";
  }

  return "Ativa";
}

function ordenarUsuarios(lista) {
  const prioridade = {
    admin: 0,
    blocked: 1,
    deleted: 2,
    active: 3,
  };

  return [...lista].sort((a, b) => {
    const ordemA = prioridade[a.status] ?? 99;
    const ordemB = prioridade[b.status] ?? 99;

    if (ordemA !== ordemB) {
      return ordemA - ordemB;
    }

    return a.name.localeCompare(b.name, "pt-BR");
  });
}

function construirUsuariosRenderizaveis(registrosDb, configuracao) {
  const mapa = new Map();

  mapa.set(ADMIN_EMAIL, {
    name: "Admin",
    email: ADMIN_EMAIL,
    origin: "Conta especial",
    status: "admin",
  });

  (registrosDb || []).forEach((registro) => {
    const email = String(registro.email || "").trim().toLowerCase();

    if (!email) {
      return;
    }

    mapa.set(email, {
      name: String(registro.nome || registro.name || registro.email || "Usuario").trim(),
      email,
      origin: String(registro.origin || "Cadastro publico").trim(),
      status: obterStatusConta(email, configuracao),
    });
  });

  Object.entries(configuracao.accountStates).forEach(([email, estado]) => {
    if (!email || email === ADMIN_EMAIL) {
      return;
    }

    const existente = mapa.get(email);

    mapa.set(email, {
      name: estado.name || existente?.name || email,
      email,
      origin: estado.origin || existente?.origin || "Controle do painel",
      status: estado.status || existente?.status || "active",
    });
  });

  return ordenarUsuarios(Array.from(mapa.values()));
}

function renderizarTabelaUsuarios(configuracao) {
  const tbody = document.getElementById("usersTableBody");
  const blockedInfo = document.getElementById("blockedUsersInfo");
  const usersStatus = document.getElementById("usersStatus");

  if (!tbody) {
    return;
  }

  const filtrados = cacheUsuarios.filter((usuario) => {
    if (!filtroUsuariosAtual) {
      return true;
    }

    const termo = filtroUsuariosAtual.toLowerCase();
    return (
      usuario.name.toLowerCase().includes(termo) ||
      usuario.email.toLowerCase().includes(termo)
    );
  });

  const restritas = cacheUsuarios.filter(
    (usuario) => usuario.status === "blocked" || usuario.status === "deleted"
  );

  if (!filtrados.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="table-note">Nenhuma conta encontrada para este filtro.</td>
      </tr>
    `;

    if (blockedInfo) {
      blockedInfo.textContent = restritas.length
        ? `${restritas.length} conta(s) com bloqueio ou remocao aplicada(s) no painel.`
        : "Nenhuma conta com restricao no momento.";
    }

    if (usersStatus) {
      usersStatus.textContent = "Nenhuma conta encontrada com a busca atual.";
    }

    return;
  }

  tbody.innerHTML = filtrados
    .map((usuario) => {
      const statusClass = usuario.status === "active" ? "" : usuario.status;
      const seloStatus = `
        <span class="status-pill ${statusClass}">
          ${escaparHtml(humanizarStatusConta(usuario.status))}
        </span>
      `;

      let acoes = '<span class="table-note">Conta principal</span>';

      if (usuario.email !== ADMIN_EMAIL) {
        const botaoBloqueio =
          usuario.status === "blocked"
            ? `<button type="button" class="table-action success" data-user-action="unblock" data-user-email="${escaparHtml(usuario.email)}">Desbloquear</button>`
            : `<button type="button" class="table-action" data-user-action="block" data-user-email="${escaparHtml(usuario.email)}">Bloquear</button>`;

        const botaoDelete =
          usuario.status === "deleted"
            ? `<button type="button" class="table-action success" data-user-action="restore" data-user-email="${escaparHtml(usuario.email)}">Restaurar</button>`
            : `<button type="button" class="table-action danger" data-user-action="delete" data-user-email="${escaparHtml(usuario.email)}">Apagar</button>`;

        acoes = `<div class="table-actions">${botaoBloqueio}${botaoDelete}</div>`;
      }

      return `
        <tr>
          <td>${escaparHtml(usuario.name)}</td>
          <td>${escaparHtml(usuario.email)}</td>
          <td>${escaparHtml(usuario.origin)}</td>
          <td>${seloStatus}</td>
          <td>${acoes}</td>
        </tr>
      `;
    })
    .join("");

  if (blockedInfo) {
    blockedInfo.textContent = restritas.length
      ? `${restritas.length} conta(s) com bloqueio ou remocao aplicada(s) no painel.`
      : "Nenhuma conta com restricao no momento.";
  }

  if (usersStatus) {
    usersStatus.textContent = `${filtrados.length} conta(s) visivel(is) na busca atual.`;
  }
}

function aplicarAlteracaoConta(email, dados) {
  const config = obterAdminConfig();
  const estadoAnterior = config.accountStates[email] || {};

  config.accountStates[email] = {
    ...estadoAnterior,
    ...dados,
    updatedAt: new Date().toISOString(),
  };

  if (config.accountStates[email].status === "active") {
    const semNome = !config.accountStates[email].name;
    const semOrigem = !config.accountStates[email].origin;

    if (semNome && semOrigem) {
      delete config.accountStates[email];
    }
  }

  const salvo = salvarAdminConfig(config);
  preencherFormulario(salvo);
  renderizarFerramentas(salvo);
  cacheUsuarios = construirUsuariosRenderizaveis(
    cacheUsuarios.filter((usuario) => usuario.email !== ADMIN_EMAIL),
    salvo
  );
  renderizarTabelaUsuarios(salvo);
  atualizarEstatistica("statUsers", cacheUsuarios.length);
  return salvo;
}

async function bloquearUsuario(email) {
  const usuario = cacheUsuarios.find((item) => item.email === email);

  if (!usuario || email === ADMIN_EMAIL) {
    return;
  }

  aplicarAlteracaoConta(email, {
    name: usuario.name,
    origin: usuario.origin,
    status: "blocked",
  });

  definirStatusConfiguracao(`A conta ${email} foi bloqueada no fluxo do site.`, "sucesso");
}

async function desbloquearUsuario(email) {
  const usuario = cacheUsuarios.find((item) => item.email === email);

  if (!usuario || email === ADMIN_EMAIL) {
    return;
  }

  aplicarAlteracaoConta(email, {
    name: usuario.name,
    origin: usuario.origin,
    status: "active",
  });

  definirStatusConfiguracao(`A conta ${email} foi liberada novamente.`, "sucesso");
}

async function apagarUsuario(email) {
  const usuario = cacheUsuarios.find((item) => item.email === email);

  if (!usuario || email === ADMIN_EMAIL) {
    return;
  }

  const confirmou = window.confirm(
    `Deseja remover a conta ${email} do painel e bloquear o acesso no site?`
  );

  if (!confirmou) {
    return;
  }

  let mensagem = `A conta ${email} foi marcada como removida e bloqueada no fluxo do site.`;

  try {
    const { error } = await _supabase.from("usuarios").delete().eq("email", email);

    if (error) {
      throw error;
    }
  } catch (erro) {
    console.warn("Nao foi possivel apagar o registro no Supabase:", erro);
    mensagem += " O registro remoto nao foi removido, mas o bloqueio local foi aplicado.";
  }

  aplicarAlteracaoConta(email, {
    name: usuario.name,
    origin: usuario.origin,
    status: "deleted",
  });

  definirStatusConfiguracao(mensagem, "sucesso");
}

async function restaurarUsuario(email) {
  const usuario = cacheUsuarios.find((item) => item.email === email);

  if (!usuario || email === ADMIN_EMAIL) {
    return;
  }

  try {
    await _supabase
      .from("usuarios")
      .upsert([{ nome: usuario.name, email }], { onConflict: "email" });
  } catch (erro) {
    console.warn("Nao foi possivel restaurar o registro remoto:", erro);
  }

  aplicarAlteracaoConta(email, {
    name: usuario.name,
    origin: "Cadastro restaurado",
    status: "active",
  });

  definirStatusConfiguracao(`A conta ${email} foi restaurada no painel.`, "sucesso");
}

function normalizarMetodo(metodo) {
  const valor = String(metodo || "").trim().toLowerCase();

  if (valor.includes("lsb") || valor.includes("m4")) {
    return "LSB";
  }

  if (valor.includes("fft") || valor.includes("frequencia")) {
    return "FFT";
  }

  if (valor.includes("grad") || valor.includes("laplac") || valor.includes("neon")) {
    return "Gradiente";
  }

  if (valor.includes("psem")) {
    return "PSEM";
  }

  if (valor.includes("marca visual")) {
    return "Marca visual";
  }

  if (valor.includes("metadados")) {
    return "Metadados";
  }

  return metodo || "Sem identificacao";
}

function renderizarMetodos(contagens, totalAnalises) {
  const methodsList = document.getElementById("methodsList");
  const analysisStatus = document.getElementById("analysisStatus");
  const entradas = Object.entries(contagens).sort((a, b) => b[1] - a[1]);

  if (!methodsList || !analysisStatus) {
    return;
  }

  if (!entradas.length) {
    methodsList.innerHTML = `
      <article class="method-card">
        <div>
          <strong>Nenhuma analise registrada</strong>
          <span>Assim que uma imagem for processada, os metodos usados aparecerao aqui.</span>
        </div>
        <span class="method-count">0</span>
      </article>
    `;
    analysisStatus.textContent = "Nenhuma analise encontrada.";
    return;
  }

  methodsList.innerHTML = entradas
    .map(
      ([metodo, quantidade]) => `
        <article class="method-card">
          <div>
            <strong>${escaparHtml(metodo)}</strong>
            <span>Metodo registrado nas analises salvas do sistema.</span>
          </div>
          <span class="method-count">${quantidade}</span>
        </article>
      `
    )
    .join("");

  analysisStatus.textContent = `${totalAnalises} analise(s) encontradas na base.`;
}

async function carregarUsuarios() {
  const usersStatus = document.getElementById("usersStatus");
  const configuracao = obterAdminConfig();

  if (usersStatus) {
    usersStatus.textContent = "Carregando usuarios...";
  }

  try {
    const { data, error, count } = await _supabase
      .from("usuarios")
      .select("nome,email", { count: "exact" })
      .order("nome", { ascending: true });

    if (error) {
      throw error;
    }

    cacheUsuarios = construirUsuariosRenderizaveis(data || [], configuracao);
    renderizarTabelaUsuarios(configuracao);
    atualizarEstatistica("statUsers", Math.max(cacheUsuarios.length, Number(count || 0) + 1));
  } catch (erro) {
    console.error("Erro ao carregar usuarios:", erro);
    cacheUsuarios = construirUsuariosRenderizaveis([], configuracao);
    renderizarTabelaUsuarios(configuracao);
    atualizarEstatistica("statUsers", cacheUsuarios.length);

    if (usersStatus) {
      usersStatus.textContent =
        "Nao foi possivel ler a tabela remota; exibindo apenas estados conhecidos pelo painel.";
    }
  }
}

async function carregarAnalises() {
  const analysisStatus = document.getElementById("analysisStatus");

  if (analysisStatus) {
    analysisStatus.textContent = "Carregando estatisticas...";
  }

  try {
    const { data, error, count } = await _supabase
      .from("historico_analises")
      .select("metodo,data_analise", { count: "exact" })
      .order("data_analise", { ascending: false })
      .limit(500);

    if (error) {
      throw error;
    }

    const contagens = {};

    (data || []).forEach((registro) => {
      const metodo = normalizarMetodo(registro.metodo);
      contagens[metodo] = (contagens[metodo] || 0) + 1;
    });

    atualizarEstatistica("statAnalyses", count || 0);
    renderizarMetodos(contagens, count || 0);
  } catch (erro) {
    console.error("Erro ao carregar analises:", erro);
    atualizarEstatistica("statAnalyses", "--");
    renderizarMetodos({}, 0);

    if (analysisStatus) {
      analysisStatus.textContent =
        "Nao foi possivel acessar o historico global com a permissao atual.";
    }
  }
}

async function atualizarPainel() {
  const configuracao = obterAdminConfig();
  renderizarFerramentas(configuracao);
  preencherFormulario(configuracao);
  await Promise.all([carregarUsuarios(), carregarAnalises()]);
}

async function fazerLogoutAdmin() {
  localStorage.removeItem("usuarioNome");
  localStorage.removeItem("usuarioEmail");
  localStorage.removeItem("usuarioTipo");

  try {
    await _supabase.auth.signOut();
  } catch (erro) {
    console.warn("Nao foi possivel encerrar a sessao do Supabase:", erro);
  }

  window.location.href = "./index-login.html";
}

function aplicarPreset(modo) {
  const base = obterAdminConfig();
  const novo = {
    ...base,
    allowRegistrations: modo === "aberto",
    enableInstallPrompt: modo === "aberto",
    maintenanceMode: modo === "restrito",
    allowUploadPage: modo === "aberto",
    allowHistoryPage: modo === "aberto",
    allowProfilePage: true,
    lockAnalysisPage: modo === "restrito",
    defaultWatermarkCheck: true,
    defaultMetadataCheck: true,
    announcementMessage:
      modo === "restrito"
        ? "A plataforma esta em operacao controlada. Algumas areas foram temporariamente restringidas."
        : "",
  };

  const salvo = salvarAdminConfig(novo);
  preencherFormulario(salvo);
  renderizarFerramentas(salvo);
  renderizarTabelaUsuarios(salvo);
  definirStatusConfiguracao(
    modo === "aberto"
      ? "Preset aberto aplicado com sucesso."
      : "Preset restrito aplicado com sucesso.",
    "sucesso"
  );
}

function limparAviso() {
  const config = obterAdminConfig();
  config.announcementMessage = "";
  config.maintenanceMode = false;

  const salvo = salvarAdminConfig(config);
  preencherFormulario(salvo);
  renderizarFerramentas(salvo);
  definirStatusConfiguracao("Aviso institucional removido.", "sucesso");
}

function desbloquearTodasAsContas() {
  const config = obterAdminConfig();

  Object.keys(config.accountStates).forEach((email) => {
    if (config.accountStates[email].status === "blocked") {
      config.accountStates[email].status = "active";
    }
  });

  const salvo = salvarAdminConfig(config);
  preencherFormulario(salvo);
  renderizarFerramentas(salvo);
  cacheUsuarios = cacheUsuarios.map((usuario) =>
    usuario.status === "blocked" ? { ...usuario, status: "active" } : usuario
  );
  renderizarTabelaUsuarios(salvo);
  definirStatusConfiguracao("Todas as contas bloqueadas foram liberadas.", "sucesso");
}

function configurarEventos() {
  const configForm = document.getElementById("adminConfigForm");
  const btnResetConfig = document.getElementById("btnResetConfig");
  const btnRefreshData = document.getElementById("btnRefreshData");
  const btnLogoutAdmin = document.getElementById("btnLogoutAdmin");
  const btnPresetOpen = document.getElementById("btnPresetOpen");
  const btnPresetRestrict = document.getElementById("btnPresetRestrict");
  const btnClearAnnouncement = document.getElementById("btnClearAnnouncement");
  const btnUnlockUsers = document.getElementById("btnUnlockUsers");
  const userSearchInput = document.getElementById("userSearchInput");
  const usersTableBody = document.getElementById("usersTableBody");

  if (configForm) {
    configForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const salvo = salvarAdminConfig(lerFormularioConfiguracao());
      preencherFormulario(salvo);
      renderizarFerramentas(salvo);
      renderizarTabelaUsuarios(salvo);
      definirStatusConfiguracao("Configuracoes salvas com sucesso.", "sucesso");
    });
  }

  if (btnResetConfig) {
    btnResetConfig.addEventListener("click", () => {
      const salvo = salvarAdminConfig(CONFIG_ADMIN_PADRAO);
      preencherFormulario(salvo);
      renderizarFerramentas(salvo);
      renderizarTabelaUsuarios(salvo);
      definirStatusConfiguracao("Painel restaurado para o estado padrao.", "sucesso");
    });
  }

  if (btnRefreshData) {
    btnRefreshData.addEventListener("click", async () => {
      btnRefreshData.disabled = true;
      definirStatusConfiguracao("Atualizando dados do painel...");

      try {
        await atualizarPainel();
        definirStatusConfiguracao("Dados atualizados com sucesso.", "sucesso");
      } catch (erro) {
        definirStatusConfiguracao("Nao foi possivel atualizar todos os dados.", "erro");
      } finally {
        btnRefreshData.disabled = false;
      }
    });
  }

  if (btnLogoutAdmin) {
    btnLogoutAdmin.addEventListener("click", fazerLogoutAdmin);
  }

  if (btnPresetOpen) {
    btnPresetOpen.addEventListener("click", () => aplicarPreset("aberto"));
  }

  if (btnPresetRestrict) {
    btnPresetRestrict.addEventListener("click", () => aplicarPreset("restrito"));
  }

  if (btnClearAnnouncement) {
    btnClearAnnouncement.addEventListener("click", limparAviso);
  }

  if (btnUnlockUsers) {
    btnUnlockUsers.addEventListener("click", desbloquearTodasAsContas);
  }

  if (userSearchInput) {
    userSearchInput.addEventListener("input", (event) => {
      filtroUsuariosAtual = String(event.target.value || "").trim();
      renderizarTabelaUsuarios(obterAdminConfig());
    });
  }

  if (usersTableBody) {
    usersTableBody.addEventListener("click", async (event) => {
      const botao = event.target.closest("[data-user-action]");

      if (!botao) {
        return;
      }

      const acao = botao.dataset.userAction;
      const email = String(botao.dataset.userEmail || "").trim().toLowerCase();

      if (!email) {
        return;
      }

      botao.disabled = true;

      try {
        if (acao === "block") {
          await bloquearUsuario(email);
        } else if (acao === "unblock") {
          await desbloquearUsuario(email);
        } else if (acao === "delete") {
          await apagarUsuario(email);
        } else if (acao === "restore") {
          await restaurarUsuario(email);
        }
      } finally {
        botao.disabled = false;
      }
    });
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  if (redirecionarSeNaoAdmin()) {
    return;
  }

  atualizarUltimoAcesso();
  preencherFormulario(obterAdminConfig());
  renderizarFerramentas(obterAdminConfig());
  configurarEventos();
  definirStatusConfiguracao("Central administrativa carregada.");
  await atualizarPainel();
});


