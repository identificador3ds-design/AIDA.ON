/* ==========================================================================
   AIDA — painel administrativo
   ==========================================================================

   Defesa em camadas. Do mais forte para o mais fraco:

   1. Banco (a barreira real). Toda leitura e escrita passa pelo RLS e pelas
      funcoes de docs/migracao-admin-seguro.sql, que exigem papel admin no JWT,
      segundo fator (aal2) e a conta em `admin_contas`. Manipular este script
      no navegador nao abre nada no servidor.
   2. Sessao. Fica em sessionStorage (morre ao fechar a aba), expira por
      inatividade e por tempo maximo, e o logout revoga os refresh tokens.
   3. Interface. Mensagens genericas no login (nao revelam se o e-mail existe),
      espera progressiva apos erros, todo texto vindo do banco e escapado.
   ========================================================================== */
"use strict";

const SUPABASE_URL = "https://nwzijdudhemuibsyzpub.supabase.co";
const SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";

function armazenamentoDaAba() {
  try {
    window.sessionStorage.setItem("aida-admin-teste", "1");
    window.sessionStorage.removeItem("aida-admin-teste");
    return window.sessionStorage;
  } catch (erro) {
    // Sem sessionStorage: sessao so em memoria (some ao recarregar). Nunca localStorage.
    const memoria = {};
    return {
      getItem: (k) => (k in memoria ? memoria[k] : null),
      setItem: (k, v) => { memoria[k] = String(v); },
      removeItem: (k) => { delete memoria[k]; },
    };
  }
}

const ARMAZENAMENTO = armazenamentoDaAba();

/* Cliente proprio do painel: sessao separada da do site, na aba atual. */
const _supabase = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    storage: ARMAZENAMENTO,
    storageKey: "aida-admin-auth",
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: false,
  },
});

const INATIVIDADE_MS = 15 * 60 * 1000;
const SESSAO_MAXIMA_MS = 8 * 60 * 60 * 1000;
const CHAVE_INICIO_SESSAO = "aida-admin-inicio";
const CHAVE_TENTATIVAS = "aida-admin-tentativas";
const FALHAS_SEM_ESPERA = 3;
const ESPERA_MAXIMA_MS = 15 * 60 * 1000;
const EMAIL_SUPORTE_PADRAO = window.AidaAdminAuth?.ADMIN_EMAIL_PADRAO || "admin@gmail.com";
const PADRAO_EMAIL = /^[^\s@<>"']{1,64}@[^\s@<>"']{1,190}\.[a-z]{2,}$/i;

const COLUNAS_CHAVE =
  "id,prefixo,descricao,empresa,contato,plano,tokens_total,tokens_usados,limite_por_janela,revogada,criada_em,ultimo_uso_em,revogada_em,expira_em";

const PLANOS = {
  free: "Free",
  basico: "Básico",
  pro: "Pro",
  enterprise: "Enterprise",
  custom: "Personalizado",
};

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
  supportEmail: EMAIL_SUPORTE_PADRAO,
  announcementMessage: "",
  analysisButtonLabel: "Analisar imagem",
  unloggedAnalysisLimit: 1,
  methods: METODOS_PADRAO,
};

const CHECKBOXES_CONFIG = {
  configAllowRegistrations: "allowRegistrations",
  configEnableInstallPrompt: "enableInstallPrompt",
  configMaintenanceMode: "maintenanceMode",
  configAllowUploadPage: "allowUploadPage",
  configAllowHistoryPage: "allowHistoryPage",
  configAllowProfilePage: "allowProfilePage",
  configLockAnalysisPage: "lockAnalysisPage",
  configDefaultWatermarkCheck: "defaultWatermarkCheck",
  configDefaultMetadataCheck: "defaultMetadataCheck",
};

const estado = {
  emailSessao: "",
  fatorId: null,
  configAtual: null,
  chaves: [],
  usuarios: [],
  filtroUsuarios: "",
  ultimaAtividade: Date.now(),
  relogio: null,
  painelAberto: false,
};

/* -------------------------------------------------------------------------- */
/* Utilitarios                                                                */
/* -------------------------------------------------------------------------- */

function $(id) {
  return document.getElementById(id);
}

function escaparHtml(valor) {
  return String(valor ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatarData(dataIso) {
  if (!dataIso) {
    return "—";
  }

  try {
    return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(
      new Date(dataIso)
    );
  } catch (erro) {
    return "—";
  }
}

function formatarNumero(valor) {
  const numero = Number(valor);
  return Number.isFinite(numero) ? numero.toLocaleString("pt-BR") : "--";
}

function inteiroEntre(valor, minimo, maximo) {
  const texto = String(valor ?? "").trim();

  if (!/^\d+$/.test(texto)) {
    return null;
  }

  const numero = Number(texto);
  return numero >= minimo && numero <= maximo ? numero : null;
}

function texto(id) {
  return String($(id)?.value || "").trim();
}

function definirStatusConfiguracao(mensagem, tipo = "neutro") {
  const status = $("configStatus");

  if (!status) {
    return;
  }

  status.textContent = mensagem;
  status.dataset.tipo = tipo;
}

/* Erros do banco viram mensagem curta. Detalhe tecnico vai so para o console. */
function mensagemDeErro(error) {
  const codigo = String(error?.code || "");

  if (codigo === "42501" || codigo === "PGRST301" || /jwt/i.test(error?.message || "")) {
    return "Sem permissão. A sessão precisa de senha e autenticador.";
  }

  if (codigo === "22023" || codigo === "P0002") {
    return String(error.message || "Dados inválidos.").slice(0, 160);
  }

  console.warn("Operação administrativa falhou:", error);
  return "Não foi possível concluir a operação.";
}

function erroDePermissao(error) {
  const codigo = String(error?.code || "");
  return codigo === "42501" || codigo === "PGRST301";
}

async function chamarRpc(nome, parametros) {
  const { data, error } = await _supabase.rpc(nome, parametros || {});

  if (error) {
    if (erroDePermissao(error)) {
      await encerrarSessao("Sessão sem permissão no servidor. Entre novamente.");
    }
    throw error;
  }

  return data;
}

/* -------------------------------------------------------------------------- */
/* Espera progressiva apos erros de login (complementa o limite do Supabase)  */
/* -------------------------------------------------------------------------- */

function lerTentativas() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_TENTATIVAS) || "{}");
    return { falhas: Number(salvo.falhas) || 0, ate: Number(salvo.ate) || 0 };
  } catch (erro) {
    return { falhas: 0, ate: 0 };
  }
}

function gravarTentativas(tentativas) {
  try {
    localStorage.setItem(CHAVE_TENTATIVAS, JSON.stringify(tentativas));
  } catch (erro) {
    /* modo privado: a espera vale so nesta pagina */
  }
}

function registrarFalha() {
  const tentativas = lerTentativas();
  tentativas.falhas += 1;

  if (tentativas.falhas >= FALHAS_SEM_ESPERA) {
    const espera = Math.min(ESPERA_MAXIMA_MS, 30000 * 2 ** (tentativas.falhas - FALHAS_SEM_ESPERA));
    tentativas.ate = Date.now() + espera;
  }

  gravarTentativas(tentativas);
}

function limparFalhas() {
  try {
    localStorage.removeItem(CHAVE_TENTATIVAS);
  } catch (erro) {
    /* sem armazenamento */
  }
}

function segundosDeEspera() {
  const { ate } = lerTentativas();
  return ate > Date.now() ? Math.ceil((ate - Date.now()) / 1000) : 0;
}

/* -------------------------------------------------------------------------- */
/* Portao de acesso                                                           */
/* -------------------------------------------------------------------------- */

function mensagemPortao(mensagem, tipo = "erro") {
  const alvo = $("gateMsg");

  if (alvo) {
    alvo.textContent = mensagem || "";
    alvo.dataset.tipo = tipo;
  }
}

function mostrarEtapa(etapa) {
  $("adminGate").hidden = etapa === "painel";
  $("adminApp").hidden = etapa !== "painel";
  $("gateLogin").hidden = etapa !== "login";
  $("gateMfa").hidden = etapa !== "mfa";
  $("gateMfaCadastro").hidden = etapa !== "cadastro";
  $("btnLogoutAdmin").hidden = etapa === "login";
  $("adminSessionInfo").hidden = etapa !== "painel";

  const foco = { login: "gateEmail", mfa: "mfaCodigo", cadastro: "mfaCodigoCadastro" }[etapa];

  if (foco) {
    window.setTimeout(() => $(foco)?.focus(), 0);
  }
}

async function processarSessao(session) {
  if (!session?.user) {
    mostrarEtapa("login");
    return;
  }

  if (!window.AidaAdminAuth.sessaoEhAdmin(session)) {
    // Mesma mensagem de senha errada: nao confirma que a conta existe.
    await _supabase.auth.signOut();
    registrarFalha();
    mensagemPortao("E-mail ou senha inválidos.");
    mostrarEtapa("login");
    return;
  }

  estado.emailSessao = String(session.user.email || "").toLowerCase();
  const { atual, proximo } = await window.AidaAdminAuth.nivelGarantia(_supabase);

  if (atual === "aal2") {
    await abrirPainel();
    return;
  }

  if (proximo === "aal2") {
    const { data } = await _supabase.auth.mfa.listFactors();
    const fator = (data?.totp || []).find((item) => item.status === "verified");

    if (fator) {
      estado.fatorId = fator.id;
      mensagemPortao("", "neutro");
      mostrarEtapa("mfa");
      return;
    }
  }

  await iniciarCadastroMfa();
}

async function iniciarCadastroMfa() {
  // Cadastro interrompido deixa fator "unverified"; ele impediria um novo.
  const { data: fatores } = await _supabase.auth.mfa.listFactors();

  for (const fator of fatores?.all || []) {
    if (fator.status !== "verified") {
      await _supabase.auth.mfa.unenroll({ factorId: fator.id });
    }
  }

  const { data, error } = await _supabase.auth.mfa.enroll({
    factorType: "totp",
    friendlyName: `AIDA Admin ${new Date().toISOString().slice(0, 10)}`,
  });

  if (error || !data?.totp) {
    console.warn("Cadastro do autenticador falhou:", error);
    await _supabase.auth.signOut();
    mensagemPortao("Não foi possível iniciar a verificação em duas etapas. Confira se o TOTP está habilitado no Supabase.");
    mostrarEtapa("login");
    return;
  }

  estado.fatorId = data.id;
  $("mfaQr").src = data.totp.qr_code;
  $("mfaSegredo").textContent = data.totp.secret;
  mensagemPortao("Primeiro acesso: ative a verificação em duas etapas.", "neutro");
  mostrarEtapa("cadastro");
}

async function verificarCodigo(campoId) {
  const espera = segundosDeEspera();

  if (espera) {
    mensagemPortao(`Muitas tentativas. Aguarde ${espera}s.`);
    return;
  }

  const codigo = texto(campoId).replace(/\s+/g, "");

  if (!/^\d{6}$/.test(codigo)) {
    mensagemPortao("Digite os 6 dígitos do aplicativo.");
    return;
  }

  const { error } = await _supabase.auth.mfa.challengeAndVerify({
    factorId: estado.fatorId,
    code: codigo,
  });
  $(campoId).value = "";

  if (error) {
    registrarFalha();
    mensagemPortao("Código inválido ou expirado.");
    return;
  }

  limparFalhas();
  $("mfaQr").removeAttribute("src");
  $("mfaSegredo").textContent = "";
  ARMAZENAMENTO.setItem(CHAVE_INICIO_SESSAO, String(Date.now()));
  await abrirPainel();
}

async function entrar(event) {
  event.preventDefault();
  const espera = segundosDeEspera();

  if (espera) {
    mensagemPortao(`Muitas tentativas. Aguarde ${espera}s antes de tentar de novo.`);
    return;
  }

  const email = texto("gateEmail").toLowerCase();
  const senha = String($("gateSenha").value || "");

  if (!PADRAO_EMAIL.test(email) || !senha) {
    mensagemPortao("Preencha e-mail e senha.");
    return;
  }

  const botao = $("gateEntrar");
  botao.disabled = true;
  mensagemPortao("Verificando...", "neutro");

  try {
    const { data, error } = await _supabase.auth.signInWithPassword({ email, password: senha });

    if (error || !data?.session) {
      registrarFalha();
      mensagemPortao("E-mail ou senha inválidos.");
      return;
    }

    mensagemPortao("", "neutro");
    await processarSessao(data.session);
  } catch (erro) {
    console.warn("Login administrativo falhou:", erro);
    mensagemPortao("Não foi possível conectar. Tente novamente.");
  } finally {
    $("gateSenha").value = "";
    botao.disabled = false;
  }
}

async function abrirPainel() {
  // Confirmacao NO SERVIDOR antes de mostrar qualquer coisa: o JWT lido no
  // navegador e so dica. Se o banco recusar, a sessao e encerrada.
  try {
    const { data, error } = await _supabase.rpc("admin_registrar_acesso");

    if (error) {
      throw error;
    }

    estado.emailSessao = String(data?.email || estado.emailSessao).toLowerCase();
  } catch (erro) {
    console.warn("Servidor recusou o acesso administrativo:", erro);
    await _supabase.auth.signOut();
    mensagemPortao(
      erroDePermissao(erro)
        ? "Acesso negado pelo servidor."
        : "Servidor indisponível ou migração docs/migracao-admin-seguro.sql pendente."
    );
    mostrarEtapa("login");
    return;
  }

  if (!ARMAZENAMENTO.getItem(CHAVE_INICIO_SESSAO)) {
    ARMAZENAMENTO.setItem(CHAVE_INICIO_SESSAO, String(Date.now()));
  }

  limparFalhas();
  estado.painelAberto = true;
  estado.ultimaAtividade = Date.now();
  $("adminSessaoEmail").textContent = estado.emailSessao;
  mostrarEtapa("painel");
  iniciarRelogioSessao();
  definirStatusConfiguracao("Painel carregado.", "sucesso");
  await atualizarTudo();
}

function limparDadosDaTela() {
  ["chavesTabela", "empresasTabela", "usersTableBody", "auditoriaTabela", "methodsConfigGrid"].forEach(
    (id) => {
      if ($(id)) {
        $(id).innerHTML = "";
      }
    }
  );
  estado.chaves = [];
  estado.usuarios = [];
  estado.configAtual = null;
  $("dialogChaveValor").textContent = "";
}

async function encerrarSessao(mensagem) {
  const estavaAberto = estado.painelAberto;
  estado.painelAberto = false;
  window.clearInterval(estado.relogio);
  limparDadosDaTela();
  ARMAZENAMENTO.removeItem(CHAVE_INICIO_SESSAO);

  try {
    // Escopo global: revoga os refresh tokens de todas as sessoes da conta.
    await _supabase.auth.signOut({ scope: "global" });
  } catch (erro) {
    await _supabase.auth.signOut({ scope: "local" }).catch(() => {});
  }

  mensagemPortao(mensagem || (estavaAberto ? "Sessão encerrada." : ""), "neutro");
  mostrarEtapa("login");
}

function iniciarRelogioSessao() {
  window.clearInterval(estado.relogio);

  const atualizar = () => {
    const agora = Date.now();
    const inicio = Number(ARMAZENAMENTO.getItem(CHAVE_INICIO_SESSAO)) || agora;
    const restanteInatividade = INATIVIDADE_MS - (agora - estado.ultimaAtividade);
    const restanteMaximo = SESSAO_MAXIMA_MS - (agora - inicio);

    if (restanteInatividade <= 0) {
      encerrarSessao("Sessão encerrada por inatividade.");
      return;
    }

    if (restanteMaximo <= 0) {
      encerrarSessao("Tempo máximo de sessão atingido. Entre novamente.");
      return;
    }

    const minutos = Math.ceil(Math.min(restanteInatividade, restanteMaximo) / 60000);
    $("adminSessionInfo").textContent = `Sessão expira em ${minutos} min`;
  };

  atualizar();
  estado.relogio = window.setInterval(atualizar, 15000);
}

/* -------------------------------------------------------------------------- */
/* Abas                                                                       */
/* -------------------------------------------------------------------------- */

function selecionarAba(aba) {
  document.querySelectorAll(".admin-tab").forEach((botao) => {
    const ativa = botao === aba;
    botao.setAttribute("aria-selected", ativa ? "true" : "false");
    botao.tabIndex = ativa ? 0 : -1;
    $(botao.getAttribute("aria-controls")).hidden = !ativa;
  });

  if (aba.id === "tab-auditoria") {
    carregarAuditoria();
  }
}

/* -------------------------------------------------------------------------- */
/* Visao geral                                                                */
/* -------------------------------------------------------------------------- */

async function carregarResumo() {
  try {
    const r = (await chamarRpc("admin_resumo")) || {};
    $("statUsuarios").textContent = formatarNumero(r.usuarios);
    $("statUsuariosBloqueados").textContent = `${formatarNumero(r.usuarios_bloqueados)} com restrição`;
    $("statAnalises").textContent = formatarNumero(r.analises);
    $("statChaves").textContent = formatarNumero(r.chaves_ativas);
    $("statEmpresas").textContent = `${formatarNumero(r.empresas)} empresa(s), ${formatarNumero(r.chaves_revogadas)} revogada(s)`;
    $("statChamadas24h").textContent = formatarNumero(r.chamadas_24h);
    $("statChamadas30d").textContent = `${formatarNumero(r.chamadas_30d)} em 30 dias`;
    $("statTokensUsados").textContent = formatarNumero(r.tokens_usados);
    $("statTokensContratados").textContent = formatarNumero(r.tokens_contratados);
    $("statTokensDisponiveis").textContent = formatarNumero(r.tokens_disponiveis);
    $("statErros24h").textContent = formatarNumero(r.erros_24h);
    $("resumoStatus").textContent = `Atualizado em ${formatarData(new Date().toISOString())}.`;
  } catch (erro) {
    $("resumoStatus").textContent = mensagemDeErro(erro);
  }
}

/* -------------------------------------------------------------------------- */
/* API e empresas                                                             */
/* -------------------------------------------------------------------------- */

function estadoDaChave(chave) {
  if (chave.revogada) {
    return { rotulo: "Revogada", classe: "deleted" };
  }

  if (chave.expira_em && new Date(chave.expira_em) <= new Date()) {
    return { rotulo: "Expirada", classe: "deleted" };
  }

  if (Number(chave.limite_por_janela) === 0) {
    return { rotulo: "Suspensa", classe: "blocked" };
  }

  if (Number(chave.tokens_total) > 0 && Number(chave.tokens_usados) >= Number(chave.tokens_total)) {
    return { rotulo: "Esgotada", classe: "blocked" };
  }

  return { rotulo: "Ativa", classe: "" };
}

function disponivelDaChave(chave) {
  const total = Number(chave.tokens_total) || 0;
  return total === 0 ? Infinity : Math.max(0, total - (Number(chave.tokens_usados) || 0));
}

function barraDeUso(usados, total) {
  if (!total) {
    return '<span class="table-note">ilimitado</span>';
  }

  const pct = Math.min(100, Math.round((usados / total) * 100));
  const classe = pct >= 90 ? "is-critico" : pct >= 70 ? "is-alerta" : "";
  return `<span class="uso-barra ${classe}" role="img" aria-label="${pct}% usado"><span data-pct="${pct}"></span></span><span class="table-note">${pct}%</span>`;
}

function aplicarLargurasDasBarras(raiz) {
  // Largura via CSSOM: funciona com CSP sem 'unsafe-inline' em style-src.
  raiz.querySelectorAll("[data-pct]").forEach((barra) => {
    barra.style.width = `${Number(barra.dataset.pct) || 0}%`;
  });
}

function renderizarEmpresas() {
  const tbody = $("empresasTabela");
  const grupos = new Map();

  estado.chaves
    .filter((chave) => !chave.revogada)
    .forEach((chave) => {
      const nome = String(chave.empresa || "Sem empresa").trim();
      const id = nome.toLowerCase();
      const grupo = grupos.get(id) || { nome, chaves: 0, usados: 0, total: 0, ilimitada: false, ultimoUso: null };
      grupo.chaves += 1;
      grupo.usados += Number(chave.tokens_usados) || 0;

      if (Number(chave.tokens_total) > 0) {
        grupo.total += Number(chave.tokens_total);
      } else {
        grupo.ilimitada = true;
      }

      if (chave.ultimo_uso_em && (!grupo.ultimoUso || chave.ultimo_uso_em > grupo.ultimoUso)) {
        grupo.ultimoUso = chave.ultimo_uso_em;
      }

      grupos.set(id, grupo);
    });

  const lista = [...grupos.values()].sort((a, b) => b.usados - a.usados);
  $("listaEmpresas").innerHTML = lista
    .map((grupo) => `<option value="${escaparHtml(grupo.nome)}"></option>`)
    .join("");

  if (!lista.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="table-note">Nenhuma empresa com chave ativa.</td></tr>';
    return;
  }

  tbody.innerHTML = lista
    .map((grupo) => {
      const cota = grupo.ilimitada ? "Ilimitada" : formatarNumero(grupo.total);
      const disponivel = grupo.ilimitada ? "∞" : formatarNumero(Math.max(0, grupo.total - grupo.usados));
      return `
        <tr>
          <td>${escaparHtml(grupo.nome)}</td>
          <td>${grupo.chaves}</td>
          <td>${formatarNumero(grupo.usados)}</td>
          <td>${cota}</td>
          <td>${disponivel}</td>
          <td>${grupo.ilimitada ? barraDeUso(0, 0) : barraDeUso(grupo.usados, grupo.total)}</td>
          <td>${escaparHtml(formatarData(grupo.ultimoUso))}</td>
        </tr>`;
    })
    .join("");
  aplicarLargurasDasBarras(tbody);
}

function renderizarChaves() {
  const tbody = $("chavesTabela");
  const mostrarRevogadas = $("chavesMostrarRevogadas").checked;
  const lista = estado.chaves.filter((chave) => mostrarRevogadas || !chave.revogada);
  $("chavesStatus").textContent = `${lista.length} chave(s) exibida(s).`;

  if (!lista.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="table-note">Nenhuma chave emitida.</td></tr>';
    return;
  }

  tbody.innerHTML = lista
    .map((chave) => {
      const situacao = estadoDaChave(chave);
      const total = Number(chave.tokens_total) || 0;
      const usados = Number(chave.tokens_usados) || 0;
      const disponivel = disponivelDaChave(chave);
      const id = escaparHtml(chave.id);
      const suspensa = Number(chave.limite_por_janela) === 0;
      const acoes = chave.revogada
        ? `<span class="table-note">Revogada em ${escaparHtml(formatarData(chave.revogada_em))}</span>`
        : `<div class="table-actions">
            <button type="button" class="table-action" data-chave-acao="editar" data-chave-id="${id}">Editar</button>
            <button type="button" class="table-action success" data-chave-acao="tokens" data-chave-id="${id}">+ Tokens</button>
            <button type="button" class="table-action" data-chave-acao="zerar" data-chave-id="${id}">Zerar uso</button>
            <button type="button" class="table-action" data-chave-acao="${suspensa ? "reativar" : "suspender"}" data-chave-id="${id}">${suspensa ? "Reativar" : "Suspender"}</button>
            <button type="button" class="table-action danger" data-chave-acao="revogar" data-chave-id="${id}">Revogar</button>
          </div>`;

      return `
        <tr>
          <td><code>${escaparHtml(chave.prefixo)}…</code></td>
          <td>${escaparHtml(chave.empresa || "—")}<br><span class="table-note">${escaparHtml(chave.contato || "")}</span></td>
          <td>${escaparHtml(PLANOS[chave.plano] || chave.plano || "—")}</td>
          <td>${formatarNumero(usados)} / ${total ? formatarNumero(total) : "∞"}<br>${barraDeUso(usados, total)}</td>
          <td>${disponivel === Infinity ? "∞" : formatarNumero(disponivel)}</td>
          <td>${formatarNumero(chave.limite_por_janela)}</td>
          <td><span class="status-pill ${situacao.classe}">${situacao.rotulo}</span>${chave.expira_em ? `<br><span class="table-note">vence ${escaparHtml(formatarData(chave.expira_em))}</span>` : ""}</td>
          <td>${escaparHtml(formatarData(chave.ultimo_uso_em))}</td>
          <td>${acoes}</td>
        </tr>`;
    })
    .join("");
  aplicarLargurasDasBarras(tbody);
}

async function carregarChaves() {
  $("chavesStatus").textContent = "Carregando chaves...";
  const { data, error } = await _supabase
    .from("api_keys")
    .select(COLUNAS_CHAVE)
    .order("criada_em", { ascending: false });

  if (error) {
    $("chavesStatus").textContent = mensagemDeErro(error);
    estado.chaves = [];
  } else {
    estado.chaves = data || [];
  }

  renderizarEmpresas();
  renderizarChaves();
}

async function emitirChave(event) {
  event.preventDefault();
  const formulario = event.currentTarget;
  const empresa = texto("chaveEmpresa");
  const contato = texto("chaveContato");
  const tokens = inteiroEntre($("chaveTokens").value, 0, 100000000);
  const limite = inteiroEntre($("chaveLimite").value, 1, 100000);
  const diasTexto = texto("chaveDias");
  const dias = diasTexto ? inteiroEntre(diasTexto, 1, 3650) : null;

  if (!empresa || empresa.length > 120) {
    definirStatusConfiguracao("Informe a empresa (até 120 caracteres).", "erro");
    return;
  }

  if (contato && !PADRAO_EMAIL.test(contato)) {
    definirStatusConfiguracao("Contato precisa ser um e-mail válido.", "erro");
    return;
  }

  if (tokens === null || limite === null || (diasTexto && dias === null)) {
    definirStatusConfiguracao("Confira cota, limite e validade.", "erro");
    return;
  }

  const botoes = formulario.querySelectorAll("button");
  botoes.forEach((botao) => { botao.disabled = true; });

  try {
    const resultado = await chamarRpc("admin_emitir_chave", {
      p_empresa: empresa,
      p_contato: contato || null,
      p_descricao: texto("chaveDescricao") || null,
      p_plano: $("chavePlano").value,
      p_tokens_total: tokens,
      p_limite_por_janela: limite,
      p_dias_validade: dias,
    });

    formulario.reset();
    $("dialogChaveValor").textContent = resultado.chave;
    $("dialogChave").showModal();
    definirStatusConfiguracao(`Chave ${resultado.prefixo}… emitida para ${empresa}.`, "sucesso");
    await Promise.all([carregarChaves(), carregarResumo()]);
  } catch (erro) {
    definirStatusConfiguracao(mensagemDeErro(erro), "erro");
  } finally {
    botoes.forEach((botao) => { botao.disabled = false; });
  }
}

function fecharDialogChave() {
  $("dialogChaveValor").textContent = "";
  $("dialogChave").close();
}

async function copiarChave() {
  const valor = $("dialogChaveValor").textContent;

  try {
    await navigator.clipboard.writeText(valor);
    $("dialogChaveCopiar").textContent = "Copiada";
  } catch (erro) {
    const selecao = window.getSelection();
    const intervalo = document.createRange();
    intervalo.selectNodeContents($("dialogChaveValor"));
    selecao.removeAllRanges();
    selecao.addRange(intervalo);
    $("dialogChaveCopiar").textContent = "Selecionada: use Ctrl+C";
  }

  window.setTimeout(() => { $("dialogChaveCopiar").textContent = "Copiar"; }, 2500);
}

function abrirEdicao(chave) {
  $("editarPrefixo").textContent = `${chave.prefixo}…`;
  $("editarEmpresa").value = chave.empresa || "";
  $("editarContato").value = chave.contato || "";
  $("editarPlano").value = PLANOS[chave.plano] ? chave.plano : "custom";
  $("editarTokens").value = String(Number(chave.tokens_total) || 0);
  $("editarLimite").value = String(Number(chave.limite_por_janela) || 0);
  $("editarExpira").value = chave.expira_em ? String(chave.expira_em).slice(0, 10) : "";
  $("editarDescricao").value = chave.descricao || "";
  $("formEditarChave").dataset.chaveId = chave.id;
  $("dialogEditar").showModal();
}

async function salvarEdicao(event) {
  if (event.submitter?.value !== "salvar") {
    return;
  }

  event.preventDefault();
  const id = $("formEditarChave").dataset.chaveId;
  const empresa = texto("editarEmpresa");
  const contato = texto("editarContato");
  const tokens = inteiroEntre($("editarTokens").value, 0, 100000000);
  const limite = inteiroEntre($("editarLimite").value, 0, 100000);
  const expira = texto("editarExpira");

  if (!empresa || tokens === null || limite === null || (contato && !PADRAO_EMAIL.test(contato))) {
    definirStatusConfiguracao("Confira empresa, contato, cota e limite.", "erro");
    return;
  }

  if (expira && !/^\d{4}-\d{2}-\d{2}$/.test(expira)) {
    definirStatusConfiguracao("Data de expiração inválida.", "erro");
    return;
  }

  try {
    await chamarRpc("admin_atualizar_chave", {
      p_id: id,
      p_empresa: empresa,
      p_contato: contato,
      p_descricao: texto("editarDescricao"),
      p_plano: $("editarPlano").value,
      p_tokens_total: tokens,
      p_limite_por_janela: limite,
      p_expira_em: expira ? new Date(`${expira}T23:59:59`).toISOString() : null,
      p_sem_expiracao: !expira,
    });
    $("dialogEditar").close();
    definirStatusConfiguracao("Chave atualizada.", "sucesso");
    await Promise.all([carregarChaves(), carregarResumo()]);
  } catch (erro) {
    definirStatusConfiguracao(mensagemDeErro(erro), "erro");
  }
}

async function acaoDaChave(event) {
  const botao = event.target.closest("[data-chave-acao]");

  if (!botao) {
    return;
  }

  const chave = estado.chaves.find((item) => item.id === botao.dataset.chaveId);

  if (!chave) {
    return;
  }

  const acao = botao.dataset.chaveAcao;

  if (acao === "editar") {
    abrirEdicao(chave);
    return;
  }

  let rpc = null;
  let parametros = { p_id: chave.id };
  let sucesso = "";

  if (acao === "tokens") {
    const quantidade = inteiroEntre(window.prompt(`Quantos tokens adicionar para ${chave.empresa || chave.prefixo}?`, "1000"), 1, 100000000);

    if (quantidade === null) {
      return;
    }

    rpc = "admin_adicionar_tokens";
    parametros = { p_id: chave.id, p_quantidade: quantidade };
    sucesso = `${formatarNumero(quantidade)} tokens adicionados.`;
  } else if (acao === "zerar") {
    if (!window.confirm(`Zerar o uso de ${chave.prefixo}… (início de novo ciclo)?`)) {
      return;
    }

    rpc = "admin_zerar_uso_chave";
    sucesso = "Uso zerado.";
  } else if (acao === "suspender" || acao === "reativar") {
    let limite = 0;

    if (acao === "reativar") {
      limite = inteiroEntre(window.prompt("Novo limite de chamadas por hora:", "60"), 1, 100000);

      if (limite === null) {
        return;
      }
    } else if (!window.confirm(`Suspender ${chave.prefixo}…? As chamadas passam a ser recusadas.`)) {
      return;
    }

    rpc = "admin_atualizar_chave";
    parametros = {
      p_id: chave.id, p_empresa: null, p_contato: null, p_descricao: null, p_plano: null,
      p_tokens_total: null, p_limite_por_janela: limite, p_expira_em: null, p_sem_expiracao: false,
    };
    sucesso = acao === "reativar" ? "Chave reativada." : "Chave suspensa.";
  } else if (acao === "revogar") {
    const confirmacao = window.prompt(
      `Revogar é DEFINITIVO. Para confirmar, digite o prefixo ${chave.prefixo}`
    );

    if (String(confirmacao || "").trim() !== chave.prefixo) {
      return;
    }

    rpc = "admin_revogar_chave";
    sucesso = `Chave ${chave.prefixo}… revogada.`;
  }

  if (!rpc) {
    return;
  }

  botao.disabled = true;

  try {
    await chamarRpc(rpc, parametros);
    definirStatusConfiguracao(sucesso, "sucesso");
    await Promise.all([carregarChaves(), carregarResumo()]);
  } catch (erro) {
    definirStatusConfiguracao(mensagemDeErro(erro), "erro");
  } finally {
    botao.disabled = false;
  }
}

/* -------------------------------------------------------------------------- */
/* Usuarios                                                                   */
/* -------------------------------------------------------------------------- */

function humanizarStatusConta(status) {
  return { blocked: "Bloqueada", deleted: "Removida", admin: "Admin" }[status] || "Ativa";
}

function renderizarTabelaUsuarios() {
  const tbody = $("usersTableBody");
  const termo = estado.filtroUsuarios.toLowerCase();
  const filtrados = estado.usuarios.filter(
    (usuario) => !termo || usuario.name.toLowerCase().includes(termo) || usuario.email.includes(termo)
  );
  const restritas = estado.usuarios.filter((usuario) => usuario.status !== "active").length;

  $("blockedUsersInfo").textContent = restritas
    ? `${restritas} conta(s) com bloqueio ou remoção.`
    : "Nenhuma conta com restrição no momento.";
  $("usersStatus").textContent = `${filtrados.length} conta(s) na busca atual.`;

  if (!filtrados.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="table-note">Nenhuma conta encontrada.</td></tr>';
    return;
  }

  tbody.innerHTML = filtrados
    .map((usuario) => {
      const email = escaparHtml(usuario.email);
      let acoes = '<span class="table-note">Sua conta</span>';

      if (usuario.email !== estado.emailSessao) {
        const bloqueio = usuario.status === "blocked"
          ? `<button type="button" class="table-action success" data-user-action="active" data-user-email="${email}">Desbloquear</button>`
          : `<button type="button" class="table-action" data-user-action="blocked" data-user-email="${email}">Bloquear</button>`;
        const remocao = usuario.status === "deleted"
          ? `<button type="button" class="table-action success" data-user-action="active" data-user-email="${email}">Restaurar</button>`
          : `<button type="button" class="table-action danger" data-user-action="deleted" data-user-email="${email}">Remover</button>`;
        acoes = `<div class="table-actions">${bloqueio}${remocao}</div>`;
      }

      const classe = usuario.status === "active" ? "" : escaparHtml(usuario.status);
      return `
        <tr>
          <td>${escaparHtml(usuario.name)}</td>
          <td>${email}</td>
          <td><span class="status-pill ${classe}">${humanizarStatusConta(usuario.status)}</span></td>
          <td>${acoes}</td>
        </tr>`;
    })
    .join("");
}

async function carregarUsuarios() {
  $("usersStatus").textContent = "Carregando usuários...";
  let { data, error } = await _supabase
    .from("usuarios")
    .select("nome,email,status")
    .order("nome", { ascending: true });

  // Antes de docs/migracao-status-conta.sql a coluna não existe.
  if (error && /status|column|PGRST/i.test(error.message || "")) {
    ({ data, error } = await _supabase
      .from("usuarios")
      .select("nome,email",)
      .order("nome", { ascending: true }));
  }

  if (error) {
    $("usersStatus").textContent = mensagemDeErro(error);
    estado.usuarios = [];
    return;
  }

  estado.usuarios = (data || [])
    .map((registro) => ({
      name: String(registro.nome || registro.email || "Usuário").trim(),
      email: String(registro.email || "").trim().toLowerCase(),
      status: ["active", "blocked", "deleted"].includes(registro.status) ? registro.status : "active",
    }))
    .filter((usuario) => usuario.email);
  renderizarTabelaUsuarios();
}

/* O status vale no servidor: trigger usuarios_status_so_admin + RLS do histórico.
   A linha nunca é apagada daqui — apagá-la apagaria o próprio bloqueio. */
async function publicarStatusConta(email, status) {
  const { error } = await _supabase.from("usuarios").update({ status }).eq("email", email);

  if (error) {
    throw error;
  }
}

async function acaoDoUsuario(event) {
  const botao = event.target.closest("[data-user-action]");

  if (!botao) {
    return;
  }

  const email = String(botao.dataset.userEmail || "").trim().toLowerCase();
  const status = botao.dataset.userAction;

  if (!email || email === estado.emailSessao || !["active", "blocked", "deleted"].includes(status)) {
    return;
  }

  if (status === "deleted" && !window.confirm(`Remover a conta ${email}? O acesso ao site fica bloqueado.`)) {
    return;
  }

  botao.disabled = true;

  try {
    await publicarStatusConta(email, status);
    const usuario = estado.usuarios.find((item) => item.email === email);

    if (usuario) {
      usuario.status = status;
    }

    renderizarTabelaUsuarios();
    definirStatusConfiguracao(`Conta ${email}: ${humanizarStatusConta(status).toLowerCase()}.`, "sucesso");
  } catch (erro) {
    definirStatusConfiguracao(mensagemDeErro(erro), "erro");
  } finally {
    botao.disabled = false;
  }
}

/* -------------------------------------------------------------------------- */
/* Configuracao do site                                                       */
/* -------------------------------------------------------------------------- */

function normalizarMetodos(salvos = {}) {
  const metodos = {};

  Object.keys(METODOS_PADRAO).forEach((chave) => {
    const base = { ...METODOS_PADRAO[chave], ...(salvos?.[chave] || {}) };
    metodos[chave] = {
      label: String(base.label || METODOS_PADRAO[chave].label).trim().slice(0, 60) || METODOS_PADRAO[chave].label,
      descricao: String(base.descricao || METODOS_PADRAO[chave].descricao).trim().slice(0, 300) || METODOS_PADRAO[chave].descricao,
      enabled: Boolean(base.enabled),
      backendReady: Boolean(base.backendReady),
    };
  });

  return metodos;
}

function normalizarAdminConfig(salvo = {}) {
  const config = { ...CONFIG_ADMIN_PADRAO, ...(salvo && typeof salvo === "object" ? salvo : {}) };
  const limite = inteiroEntre(config.unloggedAnalysisLimit, 0, 50);
  const suporte = String(config.supportEmail || "").trim();

  Object.values(CHECKBOXES_CONFIG).forEach((campo) => {
    config[campo] = Boolean(config[campo]);
  });

  return {
    ...config,
    supportEmail: PADRAO_EMAIL.test(suporte) ? suporte : EMAIL_SUPORTE_PADRAO,
    announcementMessage: String(config.announcementMessage || "").trim().slice(0, 500),
    analysisButtonLabel:
      String(config.analysisButtonLabel || "").trim().slice(0, 60) || CONFIG_ADMIN_PADRAO.analysisButtonLabel,
    unloggedAnalysisLimit: limite === null ? CONFIG_ADMIN_PADRAO.unloggedAnalysisLimit : limite,
    methods: normalizarMetodos(config.methods),
  };
}

function renderizarMetodosConfiguraveis(configuracao) {
  $("methodsConfigGrid").innerHTML = Object.entries(configuracao.methods)
    .map(([chave, metodo]) => `
      <article class="${metodo.enabled ? "method-config-panel" : "method-config-panel is-disabled"}">
        <div class="method-config-head">
          <div>
            <h3>${escaparHtml(chave)}</h3>
            <p>${escaparHtml(metodo.descricao)}</p>
          </div>
          <div class="method-config-meta">
            ${metodo.backendReady ? '<span class="micro-pill">Backend pronto</span>' : '<span class="micro-pill warning">Backend pendente</span>'}
            <span class="micro-pill">${metodo.enabled ? "Ativo" : "Oculto"}</span>
          </div>
        </div>
        <div class="method-config-body">
          <div class="admin-field">
            <label for="methodLabel-${chave}">Nome exibido ao usuário</label>
            <input id="methodLabel-${chave}" data-method-label="${chave}" type="text" class="field-input" maxlength="60" value="${escaparHtml(metodo.label)}">
          </div>
          <div class="admin-field">
            <label for="methodDescription-${chave}">Descrição interna</label>
            <textarea id="methodDescription-${chave}" data-method-description="${chave}" class="field-textarea" rows="3" maxlength="300">${escaparHtml(metodo.descricao)}</textarea>
          </div>
        </div>
        <div class="method-config-switches">
          <label class="method-config-switch" for="methodEnabled-${chave}">
            <div><strong>Visível na análise</strong><span>Aparece no seletor público.</span></div>
            <input id="methodEnabled-${chave}" data-method-enabled="${chave}" type="checkbox" ${metodo.enabled ? "checked" : ""}>
          </label>
          <label class="method-config-switch" for="methodBackend-${chave}">
            <div><strong>Backend liberado</strong><span>Permite uso operacional real.</span></div>
            <input id="methodBackend-${chave}" data-method-backend="${chave}" type="checkbox" ${metodo.backendReady ? "checked" : ""}>
          </label>
        </div>
      </article>`)
    .join("");
}

function preencherFormulario(configuracao) {
  $("configSupportEmail").value = configuracao.supportEmail;
  $("configAnnouncement").value = configuracao.announcementMessage;
  $("configAnalysisButtonLabel").value = configuracao.analysisButtonLabel;
  $("configUnloggedLimit").value = String(configuracao.unloggedAnalysisLimit);

  Object.entries(CHECKBOXES_CONFIG).forEach(([id, campo]) => {
    $(id).checked = Boolean(configuracao[campo]);
  });

  renderizarMetodosConfiguraveis(configuracao);
}

function lerFormularioConfiguracao() {
  const configuracao = { ...estado.configAtual };
  const limite = inteiroEntre($("configUnloggedLimit").value, 0, 50);
  const suporte = texto("configSupportEmail");

  if (limite === null) {
    throw new Error("Análises sem login: use um número de 0 a 50.");
  }

  if (suporte && !PADRAO_EMAIL.test(suporte)) {
    throw new Error("E-mail de suporte inválido.");
  }

  Object.entries(CHECKBOXES_CONFIG).forEach(([id, campo]) => {
    configuracao[campo] = $(id).checked;
  });

  configuracao.unloggedAnalysisLimit = limite;
  configuracao.supportEmail = suporte || EMAIL_SUPORTE_PADRAO;
  configuracao.announcementMessage = texto("configAnnouncement");
  configuracao.analysisButtonLabel = texto("configAnalysisButtonLabel");
  configuracao.methods = {};

  Object.keys(METODOS_PADRAO).forEach((chave) => {
    configuracao.methods[chave] = {
      label: String(document.querySelector(`[data-method-label="${chave}"]`)?.value || "").trim(),
      descricao: String(document.querySelector(`[data-method-description="${chave}"]`)?.value || "").trim(),
      enabled: Boolean(document.querySelector(`[data-method-enabled="${chave}"]`)?.checked),
      backendReady: Boolean(document.querySelector(`[data-method-backend="${chave}"]`)?.checked),
    };
  });

  return normalizarAdminConfig(configuracao);
}

async function carregarConfiguracao() {
  const { data, error } = await _supabase.from("admin_config").select("config").eq("id", 1).maybeSingle();

  if (error) {
    definirStatusConfiguracao(mensagemDeErro(error), "erro");
  }

  estado.configAtual = normalizarAdminConfig(data?.config || {});
  preencherFormulario(estado.configAtual);
}

/* admin_config é de leitura pública: nada pessoal entra aqui. `accountStates`
   (e-mails de contas) de versões antigas nunca é republicado. */
async function salvarAdminConfig(configuracao) {
  const configNormalizado = normalizarAdminConfig(configuracao);
  const { accountStates: _privado, ...configPublica } = configNormalizado;
  const { error } = await _supabase
    .from("admin_config")
    .upsert({ id: 1, config: configPublica, atualizado_em: new Date().toISOString() });

  if (error) {
    throw error;
  }

  estado.configAtual = configPublica;
  return configNormalizado;
}

async function enviarConfiguracao(configuracao, mensagem) {
  try {
    const salvo = await salvarAdminConfig(configuracao);
    preencherFormulario(salvo);
    definirStatusConfiguracao(mensagem, "sucesso");
  } catch (erro) {
    definirStatusConfiguracao(erro instanceof Error && !erro.code ? erro.message : mensagemDeErro(erro), "erro");
  }
}

/* -------------------------------------------------------------------------- */
/* Auditoria                                                                  */
/* -------------------------------------------------------------------------- */

async function carregarAuditoria() {
  $("auditoriaStatus").textContent = "Carregando...";
  const { data, error } = await _supabase
    .from("admin_audit")
    .select("criado_em,admin_email,acao,alvo,ip,detalhes")
    .order("id", { ascending: false })
    .limit(200);

  if (error) {
    $("auditoriaStatus").textContent = mensagemDeErro(error);
    $("auditoriaTabela").innerHTML = "";
    return;
  }

  $("auditoriaStatus").textContent = `${(data || []).length} registro(s) mais recentes.`;
  $("auditoriaTabela").innerHTML = (data || [])
    .map((linha) => {
      const detalhes = JSON.stringify(linha.detalhes || {});
      return `
        <tr>
          <td>${escaparHtml(formatarData(linha.criado_em))}</td>
          <td>${escaparHtml(linha.admin_email || "—")}</td>
          <td><code>${escaparHtml(linha.acao)}</code></td>
          <td>${escaparHtml(linha.alvo || "—")}</td>
          <td>${escaparHtml(linha.ip || "—")}</td>
          <td class="audit-detalhes" title="${escaparHtml(detalhes.slice(0, 2000))}">${escaparHtml(detalhes.slice(0, 160))}</td>
        </tr>`;
    })
    .join("") || '<tr><td colspan="6" class="table-note">Nenhum registro.</td></tr>';
}

/* -------------------------------------------------------------------------- */
/* Montagem                                                                   */
/* -------------------------------------------------------------------------- */

async function atualizarTudo() {
  await Promise.all([carregarResumo(), carregarChaves(), carregarUsuarios(), carregarConfiguracao()]);
}

function configurarEventos() {
  $("gateLogin").addEventListener("submit", entrar);
  $("gateMfa").addEventListener("submit", (event) => {
    event.preventDefault();
    verificarCodigo("mfaCodigo");
  });
  $("gateMfaCadastroForm").addEventListener("submit", (event) => {
    event.preventDefault();
    verificarCodigo("mfaCodigoCadastro");
  });
  $("gateCancelar").addEventListener("click", () => encerrarSessao(""));
  $("btnLogoutAdmin").addEventListener("click", () => encerrarSessao("Sessão encerrada."));

  const abas = [...document.querySelectorAll(".admin-tab")];
  abas.forEach((aba, indice) => {
    aba.addEventListener("click", () => selecionarAba(aba));
    aba.addEventListener("keydown", (event) => {
      const passo = { ArrowRight: 1, ArrowLeft: -1 }[event.key];

      if (passo) {
        const proxima = abas[(indice + passo + abas.length) % abas.length];
        proxima.focus();
        selecionarAba(proxima);
      }
    });
  });

  $("formNovaChave").addEventListener("submit", emitirChave);
  $("chavesTabela").addEventListener("click", acaoDaChave);
  $("chavesMostrarRevogadas").addEventListener("change", renderizarChaves);
  $("btnAtualizarApi").addEventListener("click", () => Promise.all([carregarChaves(), carregarResumo()]));
  $("dialogChaveCopiar").addEventListener("click", copiarChave);
  $("dialogChaveFechar").addEventListener("click", fecharDialogChave);
  $("dialogChave").addEventListener("cancel", (event) => event.preventDefault());
  $("formEditarChave").addEventListener("submit", salvarEdicao);

  $("usersTableBody").addEventListener("click", acaoDoUsuario);
  $("userSearchInput").addEventListener("input", (event) => {
    estado.filtroUsuarios = String(event.target.value || "").trim();
    renderizarTabelaUsuarios();
  });
  $("btnRefreshData").addEventListener("click", carregarUsuarios);

  $("adminConfigForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    try {
      await enviarConfiguracao(lerFormularioConfiguracao(), "Configurações publicadas.");
    } catch (erro) {
      definirStatusConfiguracao(erro.message, "erro");
    }
  });
  $("btnResetConfig").addEventListener("click", () => {
    if (window.confirm("Restaurar todas as configurações do site para o padrão?")) {
      enviarConfiguracao(CONFIG_ADMIN_PADRAO, "Configurações restauradas para o padrão.");
    }
  });
  $("btnAtualizarAuditoria").addEventListener("click", carregarAuditoria);

  ["pointerdown", "keydown", "wheel", "touchstart"].forEach((tipo) => {
    document.addEventListener(tipo, () => { estado.ultimaAtividade = Date.now(); }, { passive: true });
  });

  _supabase.auth.onAuthStateChange((evento) => {
    if (evento === "SIGNED_OUT" && estado.painelAberto) {
      estado.painelAberto = false;
      window.clearInterval(estado.relogio);
      limparDadosDaTela();
      mostrarEtapa("login");
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  configurarEventos();

  // Sessao que estourou o tempo maximo enquanto a aba estava fechada/suspensa.
  const inicio = Number(ARMAZENAMENTO.getItem(CHAVE_INICIO_SESSAO)) || 0;

  if (inicio && Date.now() - inicio > SESSAO_MAXIMA_MS) {
    await encerrarSessao("Tempo máximo de sessão atingido. Entre novamente.");
    return;
  }

  const { data } = await _supabase.auth.getSession();
  await processarSessao(data?.session || null);
});
