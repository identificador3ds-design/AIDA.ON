const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

const EXEMPLOS_LSB = [
  {
    rotulo: "IA",
    classe: "ia",
    titulo: "Referencia de imagem gerada por IA",
    imagem: "../assets/images/exemplo-lsb-ia.png",
    descricao:
      "Neste mapa LSB, o ruído aparece mais concentrado e com padrões repetitivos. Esse comportamento costuma indicar uma distribuição artificial dos bits menos significativos.",
  },
  {
    rotulo: "Real",
    classe: "real",
    titulo: "Referencia de imagem real",
    imagem: "../assets/images/exemplo-lsb-real.png",
    descricao:
      "Aqui a distribuição dos pixels ativos fica mais irregular e orgânica, sem blocos tão consistentes. Esse comportamento tende a combinar melhor com fotos reais.",
  },
];

const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const CHAVE_LOGIN_FEEDBACK = "AIDA_LOGIN_FEEDBACK";
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
  methods: {
    FFT: { label: "FFT", enabled: true, backendReady: true },
    PSEM: { label: "PSEM", enabled: false, backendReady: false },
    M4: { label: "LSB", enabled: true, backendReady: true },
    GRAD: { label: "Gradiente Laplaciano (Neon)", enabled: true, backendReady: true },
  },
  accountStates: {},
};
const PWA_INSTALL_VERSION = "2026-03-site-after-analysis";
const CHAVE_PWA_DECISAO = "AIDA_PWA_INSTALL_DECISION";
const CHAVE_TUTORIAL_ANALISE = "AIDA_ANALYSIS_TUTORIAL_V1";
const CHAVE_TUTORIAL_ANALISE_LEGADA = "AIDA_ANALYSIS_TUTORIAL";
const TIPOS_IMAGEM_CONFIG = {
  pessoa: {
    label: "Pessoa",
    preferredMethods: ["M4", "GRAD", "FFT"],
    recommendation:
      "Para imagens com pessoas, o LSB costuma ser o metodo mais indicado porque ajuda a revelar padroes sutis em pele, cabelo e transicoes finas.",
  },
  objeto: {
    label: "Objeto",
    preferredMethods: ["GRAD", "FFT", "M4"],
    recommendation:
      "Para objetos, o Gradiente costuma funcionar bem porque destaca bordas, recortes e texturas artificiais.",
  },
  paisagem: {
    label: "Paisagem",
    preferredMethods: ["FFT", "GRAD", "M4"],
    recommendation:
      "Para paisagens, a FFT costuma ser uma boa escolha para observar padroes amplos de frequencia e repeticao.",
  },
  documento: {
    label: "Documento",
    preferredMethods: ["FFT", "GRAD", "M4"],
    recommendation:
      "Para documentos, a FFT costuma ajudar mais a notar regularidades artificiais e blocos de compressao.",
  },
  ilustracao: {
    label: "Ilustracao ou arte digital",
    preferredMethods: ["FFT", "GRAD", "M4"],
    recommendation:
      "Para ilustracoes e artes digitais, a FFT costuma ser a recomendacao mais segura para capturar repeticoes e assinaturas artificiais.",
  },
  logo: {
    label: "Logo ou identidade visual",
    preferredMethods: ["GRAD", "FFT", "M4"],
    recommendation:
      "Para logos e marcas, o Gradiente costuma ajudar mais porque evidencia contornos fortes e composicoes muito limpas.",
  },
  tela: {
    label: "Tela ou interface",
    preferredMethods: ["FFT", "GRAD", "M4"],
    recommendation:
      "Para telas e interfaces, a FFT costuma ser a opcao mais indicada para observar padroes repetitivos e estruturas muito regulares.",
  },
  outro: {
    label: "Outro",
    preferredMethods: ["FFT", "GRAD", "M4"],
    recommendation:
      "Quando a imagem nao se encaixa bem em uma categoria, a FFT costuma ser uma boa recomendacao inicial.",
  },
};

let deferredInstallPrompt = null;

function obterAdminConfig() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_ADMIN_CONFIG) || "{}");
    const metodos = {};
    const accountStates = {};

    Object.keys(CONFIG_ADMIN_PADRAO.methods).forEach((chave) => {
      metodos[chave] = {
        ...CONFIG_ADMIN_PADRAO.methods[chave],
        ...(salvo.methods?.[chave] || {}),
      };
      metodos[chave].label =
        String(metodos[chave].label || CONFIG_ADMIN_PADRAO.methods[chave].label).trim() ||
        CONFIG_ADMIN_PADRAO.methods[chave].label;
      metodos[chave].enabled = Boolean(metodos[chave].enabled);
      metodos[chave].backendReady = Boolean(metodos[chave].backendReady);
    });

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

    return {
      ...CONFIG_ADMIN_PADRAO,
      ...salvo,
      analysisButtonLabel:
        String(salvo.analysisButtonLabel || CONFIG_ADMIN_PADRAO.analysisButtonLabel).trim() ||
        CONFIG_ADMIN_PADRAO.analysisButtonLabel,
      methods: metodos,
      accountStates,
    };
  } catch (erro) {
    return { ...CONFIG_ADMIN_PADRAO };
  }
}

function usuarioEhAdmin() {
  const tipo = localStorage.getItem("usuarioTipo");
  const email = (localStorage.getItem("usuarioEmail") || "").trim().toLowerCase();
  return tipo === "admin" || email === ADMIN_EMAIL;
}

function obterIdentificadorTutorialConta() {
  const email = (localStorage.getItem("usuarioEmail") || "").trim().toLowerCase();
  const tipo = (localStorage.getItem("usuarioTipo") || "").trim().toLowerCase();
  const nome = (localStorage.getItem("usuarioNome") || "").trim().toLowerCase();

  return email || `${tipo || "usuario"}:${nome || "anonimo"}`;
}

function obterChaveTutorialConta() {
  return `${CHAVE_TUTORIAL_ANALISE}:${obterIdentificadorTutorialConta()}`;
}

function redirecionarParaManutencao(destino = "./index-analise.html") {
  window.location.href = `./index-manutencao.html?redirect=${encodeURIComponent(destino)}`;
}

function obterStatusConta(email) {
  const emailNormalizado = String(email || "").trim().toLowerCase();

  if (!emailNormalizado || emailNormalizado === ADMIN_EMAIL) {
    return "active";
  }

  return obterAdminConfig().accountStates[emailNormalizado]?.status || "active";
}

function contaAtualSemAcesso() {
  const email = localStorage.getItem("usuarioEmail");
  return ["blocked", "deleted"].includes(obterStatusConta(email));
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

function obterMetodoDisponivel(configuracao, chavesPreferidas = []) {
  const listaPreferida = Array.isArray(chavesPreferidas) ? chavesPreferidas : [];

  for (const chave of listaPreferida) {
    const metodo = configuracao.methods?.[chave];

    if (metodo?.enabled && metodo?.backendReady) {
      return chave;
    }
  }

  for (const [chave, metodo] of Object.entries(configuracao.methods || {})) {
    if (metodo?.enabled && metodo?.backendReady) {
      return chave;
    }
  }

  for (const [chave, metodo] of Object.entries(configuracao.methods || {})) {
    if (metodo?.enabled) {
      return chave;
    }
  }

  return "";
}

function obterTipoImagemConfig(tipoImagem) {
  const chave = String(tipoImagem || "").trim().toLowerCase();
  return TIPOS_IMAGEM_CONFIG[chave] || null;
}

function obterMetodoRecomendadoParaTipo(tipoImagem, configuracao) {
  const tipoConfig = obterTipoImagemConfig(tipoImagem);

  if (!tipoConfig) {
    return "";
  }

  return obterMetodoDisponivel(configuracao, tipoConfig.preferredMethods);
}

function montarRotuloMetodo(chave, metodo, recomendacaoChave) {
  const pronto = Boolean(metodo?.backendReady);
  let label = pronto ? metodo.label : `${metodo.label} (em breve)`;

  if (pronto && chave === recomendacaoChave) {
    label = `${label} (recomendado)`;
  }

  return label;
}

function renderizarMetodosDisponiveis(
  select,
  configuracao,
  recomendacaoChave = "",
  valorSelecionado = ""
) {
  if (!select) {
    return;
  }

  const placeholder = '<option value="" disabled selected>Escolha uma opção</option>';
  const opcoes = [placeholder];

  Object.entries(configuracao.methods).forEach(([chave, metodo]) => {
    if (!metodo.enabled) {
      return;
    }

    const label = montarRotuloMetodo(chave, metodo, recomendacaoChave);
    const disabled = metodo.backendReady ? "" : "disabled";
    const selected = valorSelecionado && valorSelecionado === chave ? "selected" : "";
    opcoes.push(`<option value="${chave}" ${disabled} ${selected}>${label}</option>`);
  });

  select.innerHTML = opcoes.join("");

  if (!valorSelecionado) {
    select.value = "";
  }
}

function dispositivoIOS() {
  return (
    /iPhone|iPad|iPod/i.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  );
}

function dispositivoMovel() {
  return (
    /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ||
    dispositivoIOS() ||
    window.matchMedia("(pointer: coarse) and (max-width: 1024px)").matches
  );
}

function appInstalado() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.matchMedia("(display-mode: fullscreen)").matches ||
    window.matchMedia("(display-mode: minimal-ui)").matches ||
    window.matchMedia("(display-mode: window-controls-overlay)").matches ||
    window.navigator.standalone === true ||
    document.referrer.startsWith("android-app://")
  );
}

function usuarioDispensouConviteInstalacao() {
  return localStorage.getItem(CHAVE_PWA_DECISAO) === PWA_INSTALL_VERSION;
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
});

window.addEventListener("appinstalled", () => {
  localStorage.setItem(CHAVE_PWA_DECISAO, PWA_INSTALL_VERSION);
});

function base64ToBlob(base64, mime) {
  const byteString = atob(base64.split(",")[1]);
  const bytes = new Uint8Array(byteString.length);

  for (let index = 0; index < byteString.length; index += 1) {
    bytes[index] = byteString.charCodeAt(index);
  }

  return new Blob([bytes], { type: mime });
}

function obterMimeType(base64) {
  const correspondencia = base64.match(/^data:(.*?);base64,/);
  return correspondencia ? correspondencia[1] : "image/png";
}

function mostrarAlerta(mensagem) {
  let container = document.getElementById("toast-container");

  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = "toast-card";
  toast.innerText = mensagem;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("fadeOut");
    setTimeout(() => toast.remove(), 350);
  }, 3200);
}

function montarDescricaoMetodo(dados) {
  const metodoRetornado = String(dados.metodo || "").toLowerCase();

  if (metodoRetornado.includes("marca visual")) {
    const iaNome = dados.metodo.replace("Marca Visual (", "").replace(")", "");
    return `Marca visual encontrada\n\nEncontramos uma marca visível no canto inferior direito da imagem, ligada à ferramenta ${iaNome}. Isso é um sinal forte de que a imagem foi gerada por IA.`;
  }

  if (metodoRetornado.includes("metadados")) {
    const iaNome = dados.metodo.replace("Metadados (", "").replace(")", "");
    return `Metadados encontrados\n\nO arquivo traz informações internas ligadas à ferramenta ${iaNome}. Isso sugere que a imagem foi exportada por um gerador de imagem.`;
  }

  if (metodoRetornado.includes("lsb")) {
    return `Resultado do método LSB\n\nO método encontrou ${dados.energia} pixels ativos nas partes menos visíveis da imagem. Quando esse número fica muito concentrado, pode haver sinais artificiais ou marcas digitais escondidas.`;
  }

  if (
    metodoRetornado.includes("gradiente") ||
    metodoRetornado.includes("laplaciano") ||
    metodoRetornado.includes("neon")
  ) {
    return `Resultado do gradiente\n\nO método destacou bordas e áreas com mudanças fortes na imagem. A intensidade média encontrada foi ${dados.energia}, o que ajuda a revelar texturas artificiais e padrões de geração por IA.`;
  }

  if (
    metodoRetornado.includes("frequencia") ||
    metodoRetornado.includes("fft") ||
    metodoRetornado.includes("consistencia")
  ) {
    return `Resultado da frequência\n\nA leitura de frequência encontrou energia ${dados.energia}. Quando esse valor foge do esperado, a imagem pode ter sido criada ou alterada de forma artificial.`;
  }

  return `Resumo da análise\n\nMétodo utilizado: ${dados.metodo}\nChance de IA: ${dados.probabilidade}\nEnergia encontrada: ${dados.energia}`;
}

function limparExemplosMetodo(bloco, titulo, descricao, lista) {
  if (bloco) {
    bloco.hidden = true;
  }

  if (titulo) {
    titulo.innerText = "Referências para comparação";
  }

  if (descricao) {
    descricao.innerText = "";
  }

  if (lista) {
    lista.innerHTML = "";
  }
}

function criarCardExemplo(exemplo) {
  const card = document.createElement("article");
  card.className = "card-exemplo";

  const visual = document.createElement("div");
  visual.className = "visual-exemplo";

  const etiqueta = document.createElement("span");
  etiqueta.className = `etiqueta-exemplo ${exemplo.classe || ""}`.trim();
  etiqueta.innerText = exemplo.rotulo || "";
  visual.appendChild(etiqueta);

  const imagem = document.createElement("img");
  imagem.className = "imagem-exemplo";
  imagem.src = exemplo.imagem;
  imagem.alt = exemplo.titulo || exemplo.rotulo || "Exemplo";
  visual.appendChild(imagem);

  const corpo = document.createElement("div");
  corpo.className = "corpo-exemplo";

  const titulo = document.createElement("h5");
  titulo.className = "titulo-card-exemplo";
  titulo.innerText = exemplo.titulo || "";
  corpo.appendChild(titulo);

  const descricao = document.createElement("p");
  descricao.className = "descricao-card-exemplo";
  descricao.innerText = exemplo.descricao || "";
  corpo.appendChild(descricao);

  card.appendChild(visual);
  card.appendChild(corpo);

  return card;
}

function renderizarCardsExemplo(bloco, titulo, descricao, lista, conteudo) {
  if (!bloco || !titulo || !descricao || !lista) {
    return;
  }

  titulo.innerText = conteudo.titulo;
  descricao.innerText = conteudo.descricao;
  lista.innerHTML = "";

  conteudo.itens.forEach((item) => {
    lista.appendChild(criarCardExemplo(item));
  });

  bloco.hidden = conteudo.itens.length === 0;
}

function carregarImagem(src) {
  return new Promise((resolve, reject) => {
    const imagem = new Image();
    imagem.onload = () => resolve(imagem);
    imagem.onerror = () =>
      reject(new Error("Nao foi possivel carregar a imagem para gerar o recorte."));
    imagem.src = src;
  });
}

function numeroSeguro(valor, padrao = 0) {
  const numero = Number(valor);
  return Number.isFinite(numero) ? numero : padrao;
}

function normalizarCaixa(caixa, larguraMaxima, alturaMaxima) {
  if (!caixa) {
    return null;
  }

  const x = numeroSeguro(caixa.x);
  const y = numeroSeguro(caixa.y);
  const width = numeroSeguro(caixa.width);
  const height = numeroSeguro(caixa.height);

  if (width <= 0 || height <= 0 || larguraMaxima <= 0 || alturaMaxima <= 0) {
    return null;
  }

  const xLimitado = Math.max(0, Math.min(x, larguraMaxima - 1));
  const yLimitado = Math.max(0, Math.min(y, alturaMaxima - 1));
  const widthLimitado = Math.max(1, Math.min(width, larguraMaxima - xLimitado));
  const heightLimitado = Math.max(1, Math.min(height, alturaMaxima - yLimitado));

  return {
    x: xLimitado,
    y: yLimitado,
    width: widthLimitado,
    height: heightLimitado,
  };
}

function expandirCaixa(caixa, escala, larguraMaxima, alturaMaxima, tamanhoMinimo = 0) {
  if (!caixa) {
    return null;
  }

  const centroX = caixa.x + caixa.width / 2;
  const centroY = caixa.y + caixa.height / 2;
  let width = Math.max(caixa.width * escala, tamanhoMinimo);
  let height = Math.max(caixa.height * escala, tamanhoMinimo);

  width = Math.min(width, larguraMaxima);
  height = Math.min(height, alturaMaxima);

  const x = Math.max(0, Math.min(centroX - width / 2, larguraMaxima - width));
  const y = Math.max(0, Math.min(centroY - height / 2, alturaMaxima - height));

  return normalizarCaixa({ x, y, width, height }, larguraMaxima, alturaMaxima);
}

function cortarImagemParaDataUrl(imagem, caixa) {
  if (!imagem || !caixa) {
    return "";
  }

  const canvas = document.createElement("canvas");
  const largura = Math.max(1, Math.round(caixa.width));
  const altura = Math.max(1, Math.round(caixa.height));
  const ctx = canvas.getContext("2d");

  if (!ctx) {
    return "";
  }

  canvas.width = largura;
  canvas.height = altura;

  ctx.drawImage(
    imagem,
    Math.round(caixa.x),
    Math.round(caixa.y),
    largura,
    altura,
    0,
    0,
    largura,
    altura
  );

  return canvas.toDataURL("image/png");
}

function obterCaixaGemini(dados, larguraImagem, alturaImagem) {
  const caixaBackend = normalizarCaixa(
    dados?.marca_visual?.bounding_box,
    larguraImagem,
    alturaImagem
  );

  if (caixaBackend) {
    return caixaBackend;
  }

  return normalizarCaixa(
    {
      x: larguraImagem * 0.8,
      y: alturaImagem * 0.8,
      width: larguraImagem * 0.2,
      height: alturaImagem * 0.2,
    },
    larguraImagem,
    alturaImagem
  );
}

async function montarExemplosGemini(dados, imagemBase64) {
  if (!imagemBase64) {
    return [];
  }

  try {
    const imagem = await carregarImagem(imagemBase64);
    const larguraImagem = imagem.naturalWidth || imagem.width;
    const alturaImagem = imagem.naturalHeight || imagem.height;
    const caixaBase = obterCaixaGemini(dados, larguraImagem, alturaImagem);

    if (!caixaBase) {
      return [];
    }

    const recorteContexto = cortarImagemParaDataUrl(
      imagem,
      expandirCaixa(caixaBase, 3.4, larguraImagem, alturaImagem, 180)
    );
    const recorteDetalhe = cortarImagemParaDataUrl(
      imagem,
      expandirCaixa(caixaBase, 1.8, larguraImagem, alturaImagem, 90)
    );

    return [
      {
        rotulo: "Recorte",
        classe: "recorte",
        titulo: "Regiao usada para confirmar a marca visual",
        imagem: recorteContexto || imagemBase64,
        descricao:
          "O detector procura a assinatura do Gemini no canto inferior direito. Este recorte mostra a area principal usada na confirmacao.",
      },
      {
        rotulo: "Logo",
        classe: "recorte",
        titulo: "Ampliacao da evidencia encontrada",
        imagem: recorteDetalhe || recorteContexto || imagemBase64,
        descricao:
          "Este zoom ajuda a verificar se o simbolo esta consistente com a marca do Gemini. Quando a assinatura aparece nitida, a evidencia fica mais forte.",
      },
    ];
  } catch (erro) {
    console.error("Erro ao montar os recortes do Gemini:", erro);
    return [];
  }
}

async function renderizarExemplosMetodo(dados, imagemBase64, elementos) {
  const metodoRetornado = String(dados?.metodo || "").toLowerCase();

  limparExemplosMetodo(
    elementos.bloco,
    elementos.titulo,
    elementos.descricao,
    elementos.lista
  );

  if (metodoRetornado.includes("lsb")) {
    renderizarCardsExemplo(
      elementos.bloco,
      elementos.titulo,
      elementos.descricao,
      elementos.lista,
      {
        titulo: "Referencias visuais do LSB",
        descricao:
          "Compare o seu resultado com estes exemplos. Padroes mais concentrados e repetitivos tendem a favorecer IA; distribuicoes mais organicas e irregulares tendem a favorecer imagem real.",
        itens: EXEMPLOS_LSB,
      }
    );
    return;
  }

  if (metodoRetornado.includes("marca visual") && metodoRetornado.includes("gemini")) {
    const exemplosGemini = await montarExemplosGemini(dados, imagemBase64);

    if (exemplosGemini.length > 0) {
      renderizarCardsExemplo(
        elementos.bloco,
        elementos.titulo,
        elementos.descricao,
        elementos.lista,
        {
          titulo: "Recortes da evidencia detectada",
          descricao:
            "A leitura por marca visual encontrou a assinatura do Gemini. Os recortes abaixo mostram a regiao usada para confirmar essa evidencia.",
          itens: exemplosGemini,
        }
      );
    }
  }
}

async function salvarHistorico(imagemBase64, dados) {
  const {
    data: { user },
  } = await _supabase.auth.getUser();

  if (!user) {
    console.warn("Nenhum usuario logado. O historico nao sera salvo.");
    return;
  }

  const mimeType = obterMimeType(imagemBase64);
  const subtipo = mimeType.split("/")[1] || "png";
  const extensao = subtipo === "jpeg" ? "jpg" : subtipo;
  const blob = base64ToBlob(imagemBase64, mimeType);
  const nomeArquivo = `${user.id}/${Date.now()}_original.${extensao}`;

  const { error: uploadError } = await _supabase.storage
    .from("evidencias")
    .upload(nomeArquivo, blob);

  if (uploadError) {
    console.error("Erro no upload do storage:", uploadError.message);
    return;
  }

  const {
    data: { publicUrl },
  } = _supabase.storage.from("evidencias").getPublicUrl(nomeArquivo);

  const { error: dbError } = await _supabase.from("historico_analises").insert([
    {
      user_id: user.id,
      metodo: dados.metodo,
      probabilidade: dados.probabilidade,
      imagem_original: publicUrl,
      resultado_img: dados.imagem_fft,
    },
  ]);

  if (dbError) {
    console.error("Erro ao salvar na tabela:", dbError.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const nomeSalvo = localStorage.getItem("usuarioNome");
  const botaoUsuario = document.getElementById("nome-usuario2");
  const btnSair = document.getElementById("btn-sair");
  const linkHistorico = document.querySelector(".analysis-header-actions .top-link");
  const linkPerfilUsuario = document.querySelector(".dropdown-content .dropa");
  const linkVoltarSelecao = document.querySelector(".inline-link");
  const imagemPreview = document.getElementById("imagemPreview");
  const previewStatus = document.getElementById("previewStatus");
  const btnVerificar = document.getElementById("btnVerificar");
  const btnTrocar = document.getElementById("btnTrocar");
  const inputTrocarImagem = document.getElementById("inputTrocarImagem");
  const tipoImagemInput = document.getElementById("tipoImagem");
  const metodoAnalise = document.getElementById("metodoAnalise");
  const checkMarcaDagua = document.getElementById("checkMarcaDagua");
  const checkMetadados = document.getElementById("checkMetadados");
  const loading = document.getElementById("loading");
  const areaResultado = document.getElementById("areaResultado");
  const imagemProcessada = document.getElementById("imagemProcessada");
  const porcentagemIA = document.getElementById("porcentagemIA");
  const tituloMetodo = document.getElementById("tituloMetodo");
  const textoMetodo = document.getElementById("textoMetodo");
  const blocoExemplosMetodo = document.getElementById("blocoExemplosMetodo");
  const tituloExemplosMetodo = document.getElementById("tituloExemplosMetodo");
  const descricaoExemplosMetodo = document.getElementById("descricaoExemplosMetodo");
  const exemplosMetodo = document.getElementById("exemplosMetodo");
  const installAppPrompt = document.getElementById("installAppPrompt");
  const installIosSteps = document.getElementById("installIosSteps");
  const installPromptTitle = document.getElementById("installPromptTitle");
  const installPromptText = document.getElementById("installPromptText");
  const btnInstalarApp = document.getElementById("btnInstalarApp");
  const btnAgoraNao = document.getElementById("btnAgoraNao");
  const btnFecharInstalacao = document.getElementById("btnFecharInstalacao");
  const checkNaoMostrarInstalacao = document.getElementById("checkNaoMostrarInstalacao");
  const tipoImagemGroup = document.getElementById("tipoImagemGroup");
  const metodoAnaliseGroup = document.getElementById("metodoAnaliseGroup");
  const ajudasAutomaticasGroup = document.getElementById("ajudasAutomaticasGroup");
  const acoesAnaliseGroup = document.getElementById("acoesAnaliseGroup");
  const tipoImagemHint = document.getElementById("tipoImagemHint");
  const metodoRecomendadoHint = document.getElementById("metodoRecomendadoHint");
  const analysisTutorial = document.getElementById("analysisTutorial");
  const tutorialStepBadge = document.getElementById("tutorialStepBadge");
  const tutorialTitle = document.getElementById("tutorialTitle");
  const tutorialText = document.getElementById("tutorialText");
  const tutorialTargetLabel = document.getElementById("tutorialTargetLabel");
  const tutorialPrev = document.getElementById("tutorialPrev");
  const tutorialNext = document.getElementById("tutorialNext");
  const tutorialSkip = document.getElementById("tutorialSkip");
  const tutorialCard = document.querySelector(".analysis-tutorial-card");
  const btnReabrirTutorial = document.getElementById("btnReabrirTutorial");
  const tutorialDots = Array.from(
    document.querySelectorAll(".analysis-tutorial-progress .analysis-tutorial-dot")
  );
  const configuracaoAdmin = obterAdminConfig();

  let imagemAtual = localStorage.getItem("AIDA_ImagemSelecionada") || "";
  let tutorialIndiceAtual = 0;
  let tutorialAtivo = false;

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
    redirecionarParaManutencao("./index-analise.html");
    return;
  }

  renderizarAvisoSistema();

  atualizarRecomendacaoMetodo(tipoImagemInput ? tipoImagemInput.value : "", false);

  if (btnVerificar) {
    btnVerificar.innerText = configuracaoAdmin.lockAnalysisPage
      ? "Analise temporariamente indisponivel"
      : configuracaoAdmin.analysisButtonLabel;
    btnVerificar.disabled = Boolean(configuracaoAdmin.lockAnalysisPage);
  }

  if (checkMarcaDagua) {
    checkMarcaDagua.checked = Boolean(configuracaoAdmin.defaultWatermarkCheck);
  }

  if (checkMetadados) {
    checkMetadados.checked = Boolean(configuracaoAdmin.defaultMetadataCheck);
  }

  if (linkHistorico && !configuracaoAdmin.allowHistoryPage) {
    linkHistorico.hidden = true;
  }

  if (linkPerfilUsuario && !usuarioEhAdmin() && !configuracaoAdmin.allowProfilePage) {
    linkPerfilUsuario.hidden = true;
  }

  if (
    !configuracaoAdmin.allowUploadPage &&
    !configuracaoAdmin.maintenanceMode &&
    !usuarioEhAdmin()
  ) {
    if (btnTrocar) {
      btnTrocar.hidden = true;
    }

    if (linkVoltarSelecao) {
      linkVoltarSelecao.hidden = true;
    }
  }

  if (appInstalado()) {
    localStorage.setItem(CHAVE_PWA_DECISAO, PWA_INSTALL_VERSION);
  }

  if (localStorage.getItem(CHAVE_TUTORIAL_ANALISE_LEGADA)) {
    localStorage.removeItem(CHAVE_TUTORIAL_ANALISE_LEGADA);
  }

  function atualizarTextoRecomendacao(tipoSelecionado, recomendacaoChave, configuracaoAtual) {
    const tipoConfig = obterTipoImagemConfig(tipoSelecionado);
    const metodoConfig = recomendacaoChave ? configuracaoAtual.methods?.[recomendacaoChave] : null;

    if (tipoImagemHint) {
      tipoImagemHint.innerText = tipoConfig
        ? tipoConfig.recommendation
        : "Escolha o que mais aparece na imagem para receber uma recomendacao de metodo.";
    }

    if (metodoRecomendadoHint) {
      metodoRecomendadoHint.classList.toggle("is-recommended", Boolean(metodoConfig));
      metodoRecomendadoHint.innerText = metodoConfig
        ? `Recomendado para ${tipoConfig.label.toLowerCase()}: ${metodoConfig.label}. Se voce nao conhecer os metodos, deixe essa opcao selecionada.`
        : "Se voce nao conhecer os metodos, deixe a opcao marcada como recomendada.";
    }

    if (metodoAnaliseGroup) {
      metodoAnaliseGroup.classList.toggle("is-recommended", Boolean(metodoConfig));
    }
  }

  function atualizarRecomendacaoMetodo(tipoSelecionado, forcarSelecao = false) {
    const configuracaoAtual = obterAdminConfig();
    const valorAtual = metodoAnalise ? metodoAnalise.value : "";
    const recomendacaoChave = obterMetodoRecomendadoParaTipo(tipoSelecionado, configuracaoAtual);
    const valorSelecionado = forcarSelecao && recomendacaoChave ? recomendacaoChave : valorAtual;

    renderizarMetodosDisponiveis(
      metodoAnalise,
      configuracaoAtual,
      recomendacaoChave,
      valorSelecionado
    );

    if (metodoAnalise && forcarSelecao && recomendacaoChave) {
      metodoAnalise.value = recomendacaoChave;
    }

    atualizarTextoRecomendacao(tipoSelecionado, recomendacaoChave, configuracaoAtual);
  }

  function obterPassosTutorial() {
    return [
      {
        target: tipoImagemGroup,
        title: "Escolha o que compoe a imagem",
        text:
          "Neste primeiro campo, selecione o tipo principal da imagem, como pessoa, objeto ou paisagem. Essa escolha ajuda a tela a sugerir o metodo mais indicado para a analise.",
        targetLabel: "Campo destacado: Tipo de imagem.",
      },
      {
        target: metodoAnaliseGroup,
        title: "Deixe o metodo recomendado quando tiver duvida",
        text:
          "Aqui voce escolhe o metodo tecnico da leitura. Se voce nao tiver conhecimento sobre os metodos, mantenha a opcao marcada como recomendada, porque ela tende a trazer mais precisao para esse tipo de imagem.",
        targetLabel: "Campo destacado: Metodo de analise.",
      },
      {
        target: ajudasAutomaticasGroup,
        title: "Metadados e logo ajudam bastante",
        text:
          "Esses dois checkboxes verificam pistas comuns em varias imagens: marcas visiveis e metadados escondidos no arquivo. Se voce nao souber exatamente quando desligar, deixe como esta para nao perder evidencias importantes.",
        targetLabel: "Campo destacado: Procurar marca visivel e Ler metadados.",
      },
      {
        target: acoesAnaliseGroup || btnVerificar,
        title: "Agora e so analisar",
        text:
          "Depois disso, basta clicar em analisar imagem. O tempo da analise pode variar de acordo com o tamanho e a qualidade da imagem enviada.",
        targetLabel: "Campo destacado: area de acoes da analise.",
      },
    ].filter((passo) => passo.target);
  }

  function limparDestaquesTutorial() {
    document.querySelectorAll(".tutorial-target").forEach((elemento) => {
      elemento.classList.remove("tutorial-target");
    });

    document.querySelectorAll(".tutorial-blur").forEach((elemento) => {
      elemento.classList.remove("tutorial-blur");
    });
  }

  function obterUnidadesDesfoqueTutorial() {
    return Array.from(
      document.querySelectorAll(
        [
          ".page-header > *",
          ".analysis-main > *",
          ".analysis-content > *",
          ".container-controles > *",
          ".container-imagem > *",
          ".card-resultado > *",
          ".resultado-corpo-vertical > *",
          ".container-explicacao > *",
          ".container-imagem-processada > *",
        ].join(", ")
      )
    );
  }

  function limitarValor(valor, minimo, maximo) {
    return Math.min(Math.max(valor, minimo), maximo);
  }

  function tutorialEmLayoutCompacto() {
    return window.innerWidth <= 900;
  }

  function posicionarCardTutorial(target, opcoes = {}) {
    if (!tutorialCard || !target || analysisTutorial?.hidden) {
      return;
    }

    const layoutCompacto = tutorialEmLayoutCompacto();
    const padding = layoutCompacto ? 14 : 24;
    const gap = layoutCompacto ? 16 : 24;
    const larguraMaxima = layoutCompacto
      ? Math.min(480, window.innerWidth - padding * 2)
      : Math.min(500, Math.round(window.innerWidth * 0.28), window.innerWidth - padding * 2);

    tutorialCard.classList.toggle("is-docked-top", layoutCompacto);
    tutorialCard.style.visibility = "hidden";
    tutorialCard.style.width = `${Math.max(280, larguraMaxima)}px`;
    tutorialCard.style.left = `${padding}px`;
    tutorialCard.style.top = `${padding}px`;

    const cardRect = tutorialCard.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();

    if (layoutCompacto) {
      const left = Math.max(padding, (window.innerWidth - cardRect.width) / 2);
      const top = padding;

      tutorialCard.style.left = `${Math.round(left)}px`;
      tutorialCard.style.top = `${Math.round(top)}px`;
      tutorialCard.style.visibility = "visible";

      if (!opcoes.skipScroll) {
        const distanciaDesejada = top + cardRect.height + gap;
        const diferencaScroll = targetRect.top - distanciaDesejada;

        if (Math.abs(diferencaScroll) > 8) {
          window.scrollBy({ top: diferencaScroll, behavior: "smooth" });
          window.setTimeout(() => {
            if (tutorialAtivo) {
              posicionarCardTutorial(target, { skipScroll: true });
            }
          }, 260);
        }
      }

      return;
    }

    const areaEsquerdaInicio = padding;
    const larguraAreaEsquerda = Math.max(280, targetRect.left - gap - areaEsquerdaInicio);
    const larguraCard = Math.min(
      cardRect.width,
      Math.max(280, Math.min(500, larguraAreaEsquerda - 32))
    );

    tutorialCard.style.width = `${Math.round(larguraCard)}px`;

    const cardRectAtualizado = tutorialCard.getBoundingClientRect();
    const left = limitarValor(
      areaEsquerdaInicio + (larguraAreaEsquerda - cardRectAtualizado.width) / 2,
      padding,
      Math.max(padding, targetRect.left - cardRectAtualizado.width - gap)
    );

    const top = limitarValor(
      window.innerHeight / 2 - cardRectAtualizado.height / 2,
      padding,
      Math.max(padding, window.innerHeight - cardRectAtualizado.height - padding)
    );

    tutorialCard.style.left = `${Math.round(left)}px`;
    tutorialCard.style.top = `${Math.round(top)}px`;
    tutorialCard.style.visibility = "visible";
  }

  function aplicarDesfoqueTutorial(target) {
    const unidades = obterUnidadesDesfoqueTutorial();

    unidades.forEach((elemento) => {
      const contemTarget = elemento === target || elemento.contains(target) || target.contains(elemento);
      elemento.classList.toggle("tutorial-blur", !contemTarget);
    });
  }

  function encerrarTutorial(marcarComoVisto = true) {
    tutorialAtivo = false;
    limparDestaquesTutorial();

    if (analysisTutorial) {
      analysisTutorial.hidden = true;
      analysisTutorial.setAttribute("aria-hidden", "true");
    }

    document.body.classList.remove("tutorial-active");

    if (marcarComoVisto) {
      localStorage.setItem(obterChaveTutorialConta(), "seen");
    }
  }

  function mostrarPassoTutorial(indice) {
    const passos = obterPassosTutorial();

    if (!tutorialAtivo || !analysisTutorial || passos.length === 0) {
      return;
    }

    const indiceLimitado = Math.max(0, Math.min(indice, passos.length - 1));
    const passoAtual = passos[indiceLimitado];

    tutorialIndiceAtual = indiceLimitado;
    limparDestaquesTutorial();
    aplicarDesfoqueTutorial(passoAtual.target);
    passoAtual.target.classList.add("tutorial-target");

    if (tutorialStepBadge) {
      tutorialStepBadge.innerText = `Passo ${indiceLimitado + 1} de ${passos.length}`;
    }

    if (tutorialTitle) {
      tutorialTitle.innerText = passoAtual.title;
    }

    if (tutorialText) {
      tutorialText.innerText = passoAtual.text;
    }

    if (tutorialTargetLabel) {
      tutorialTargetLabel.innerText = passoAtual.targetLabel;
    }

    if (tutorialPrev) {
      tutorialPrev.hidden = indiceLimitado === 0;
    }

    if (tutorialNext) {
      tutorialNext.innerText = indiceLimitado === passos.length - 1 ? "Concluir" : "Proximo";
    }

    tutorialDots.forEach((dot, dotIndex) => {
      dot.classList.toggle("active", dotIndex === indiceLimitado);
    });

    if (!tutorialEmLayoutCompacto()) {
      passoAtual.target.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
      window.setTimeout(() => {
        if (tutorialAtivo && obterPassosTutorial()[tutorialIndiceAtual]?.target === passoAtual.target) {
          posicionarCardTutorial(passoAtual.target, { skipScroll: true });
        }
      }, 120);
      return;
    }

    posicionarCardTutorial(passoAtual.target);
  }

  function iniciarTutorialPrimeiroAcesso() {
    const passos = obterPassosTutorial();

    if (!analysisTutorial || passos.length === 0) {
      return;
    }

    if (localStorage.getItem(obterChaveTutorialConta()) === "seen") {
      return;
    }

    tutorialAtivo = true;
    tutorialIndiceAtual = 0;
    analysisTutorial.hidden = false;
    analysisTutorial.setAttribute("aria-hidden", "false");
    document.body.classList.add("tutorial-active");
    mostrarPassoTutorial(0);
  }

  function iniciarTutorialManual() {
    const passos = obterPassosTutorial();

    if (!analysisTutorial || passos.length === 0) {
      return;
    }

    tutorialAtivo = true;
    tutorialIndiceAtual = 0;
    analysisTutorial.hidden = false;
    analysisTutorial.setAttribute("aria-hidden", "false");
    document.body.classList.add("tutorial-active");
    mostrarPassoTutorial(0);
  }

  function deveOferecerInstalacao() {
    if (!installAppPrompt) {
      return false;
    }

    if (!obterAdminConfig().enableInstallPrompt) {
      return false;
    }

    if (appInstalado()) {
      return false;
    }

    if (usuarioDispensouConviteInstalacao()) {
      return false;
    }

    return true;
  }

  function salvarPreferenciaConviteInstalacao() {
    if (checkNaoMostrarInstalacao && checkNaoMostrarInstalacao.checked) {
      localStorage.setItem(CHAVE_PWA_DECISAO, PWA_INSTALL_VERSION);
      return;
    }

    localStorage.removeItem(CHAVE_PWA_DECISAO);
  }

  function fecharConviteInstalacao(registrarDecisao = false) {
    if (!installAppPrompt) {
      return;
    }

    installAppPrompt.hidden = true;
    installAppPrompt.setAttribute("aria-hidden", "true");
    document.body.classList.remove("install-sheet-open");

    if (registrarDecisao) {
      salvarPreferenciaConviteInstalacao();
    }
  }

  function mostrarConviteInstalacao() {
    if (!installAppPrompt || !deveOferecerInstalacao()) {
      return;
    }

    const emIOS = dispositivoIOS();
    const emCelular = dispositivoMovel();
    const promptDisponivel = !!deferredInstallPrompt;

    if (installPromptTitle) {
      if (emIOS) {
        installPromptTitle.innerText = "Adicione o AIDA.ON a tela inicial";
      } else if (emCelular) {
        installPromptTitle.innerText = "Instale o AIDA.ON no seu celular";
      } else {
        installPromptTitle.innerText = "Instale o AIDA.ON no seu computador";
      }
    }

    if (installPromptText) {
      if (emIOS) {
        installPromptText.innerText =
          "No iPhone e no iPad a instalacao e feita pelo menu do navegador. Assim o AIDA.ON fica com icone, nome e abertura em tela cheia.";
      } else if (promptDisponivel) {
        installPromptText.innerText = emCelular
          ? "Deixe a ferramenta na tela inicial com cara de app e acesso mais rapido sempre que precisar analisar uma imagem."
          : "Deixe a ferramenta instalada no seu computador para abrir como app e acessar mais rapido sempre que precisar analisar uma imagem.";
      } else {
        installPromptText.innerText =
          "Quando a instalacao estiver disponivel neste navegador, voce podera instalar o AIDA.ON para acessar a ferramenta com mais rapidez.";
      }
    }

    if (installIosSteps) {
      installIosSteps.hidden = !emIOS;
    }

    if (btnInstalarApp) {
      btnInstalarApp.innerText = emIOS ? "Entendi" : promptDisponivel ? "Instalar" : "Entendi";
    }

    if (checkNaoMostrarInstalacao) {
      checkNaoMostrarInstalacao.checked = false;
    }

    installAppPrompt.hidden = false;
    installAppPrompt.setAttribute("aria-hidden", "false");
    document.body.classList.add("install-sheet-open");
  }

  async function tratarInstalacaoApp() {
    if (dispositivoIOS()) {
      fecharConviteInstalacao(true);
      return;
    }

    if (!deferredInstallPrompt) {
      fecharConviteInstalacao(true);
      return;
    }

    btnInstalarApp.disabled = true;

    try {
      deferredInstallPrompt.prompt();
      const escolha = await deferredInstallPrompt.userChoice;

      if (escolha.outcome === "accepted") {
        localStorage.setItem(CHAVE_PWA_DECISAO, PWA_INSTALL_VERSION);
        mostrarAlerta("AIDA.ON instalado com sucesso.");
      } else if (checkNaoMostrarInstalacao && checkNaoMostrarInstalacao.checked) {
        localStorage.setItem(CHAVE_PWA_DECISAO, PWA_INSTALL_VERSION);
      } else {
        localStorage.removeItem(CHAVE_PWA_DECISAO);
      }

      fecharConviteInstalacao(false);
    } catch (erro) {
      console.error("Nao foi possivel abrir o prompt de instalacao:", erro);
      mostrarAlerta("Nao foi possivel iniciar a instalacao agora.");
    } finally {
      deferredInstallPrompt = null;
      btnInstalarApp.disabled = false;
    }
  }

  if (btnAgoraNao) {
    btnAgoraNao.addEventListener("click", () => fecharConviteInstalacao(true));
  }

  if (btnFecharInstalacao) {
    btnFecharInstalacao.addEventListener("click", () => fecharConviteInstalacao(true));
  }

  if (btnInstalarApp) {
    btnInstalarApp.addEventListener("click", tratarInstalacaoApp);
  }

  if (tutorialSkip) {
    tutorialSkip.addEventListener("click", () => encerrarTutorial(true));
  }

  if (btnReabrirTutorial) {
    btnReabrirTutorial.addEventListener("click", () => iniciarTutorialManual());
  }

  if (tutorialPrev) {
    tutorialPrev.addEventListener("click", () => mostrarPassoTutorial(tutorialIndiceAtual - 1));
  }

  if (tutorialNext) {
    tutorialNext.addEventListener("click", () => {
      const passos = obterPassosTutorial();

      if (tutorialIndiceAtual >= passos.length - 1) {
        encerrarTutorial(true);
        return;
      }

      mostrarPassoTutorial(tutorialIndiceAtual + 1);
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && tutorialAtivo) {
      encerrarTutorial(true);
    }
  });

  window.addEventListener("resize", () => {
    if (!tutorialAtivo) {
      return;
    }

    const passoAtual = obterPassosTutorial()[tutorialIndiceAtual];

    if (!passoAtual?.target) {
      return;
    }

    window.setTimeout(() => {
      if (tutorialAtivo) {
        posicionarCardTutorial(passoAtual.target);
      }
    }, 80);
  });

  if (botaoUsuario) {
    if (usuarioEhAdmin()) {
      botaoUsuario.innerText = "Admin";
      botaoUsuario.addEventListener("click", (event) => {
        event.preventDefault();
        window.location.href = "./index-admin.html";
      });

      const linkPerfil = document.querySelector(".dropdown-content .dropa");

      if (linkPerfil) {
        linkPerfil.href = "./index-admin.html";
        linkPerfil.innerText = "Painel admin";
      }
    } else if (nomeSalvo) {
      botaoUsuario.innerText = `Ola, ${nomeSalvo}`;
    }
  }

  if (window.gsap) {
    gsap.from(".page-header", { opacity: 0, duration: 0.6, y: -18, ease: "power2.out" });
    gsap.from(".card-analise", { opacity: 0, duration: 0.7, y: 24, ease: "power2.out" });
  }

  if (btnSair) {
    btnSair.addEventListener("click", async (event) => {
      event.preventDefault();
      localStorage.removeItem("usuarioNome");
      localStorage.removeItem("usuarioEmail");
      localStorage.removeItem("usuarioTipo");
      localStorage.removeItem("AIDA_ImagemSelecionada");

      try {
        await _supabase.auth.signOut();
      } catch (erro) {
        console.warn("Nao foi possivel encerrar a sessao do Supabase:", erro);
      }

      window.location.href = "./index-login.html";
    });
  }

  function limparResultado() {
    if (loading) {
      loading.style.display = "none";
    }

    if (areaResultado) {
      areaResultado.style.display = "none";
    }

    if (imagemProcessada) {
      imagemProcessada.src = "#";
    }

    if (porcentagemIA) {
      porcentagemIA.innerText = "0%";
    }

    if (tituloMetodo) {
      tituloMetodo.innerText = "Sobre o resultado";
    }

    if (textoMetodo) {
      textoMetodo.innerText = "Aguardando processamento...";
    }

    limparExemplosMetodo(
      blocoExemplosMetodo,
      tituloExemplosMetodo,
      descricaoExemplosMetodo,
      exemplosMetodo
    );
  }

  function atualizarPreviewImagem(imagemBase64) {
    if (!imagemPreview) {
      return;
    }

    if (imagemBase64) {
      imagemPreview.src = imagemBase64;
      imagemPreview.hidden = false;

      if (previewStatus) {
        previewStatus.innerText = "Imagem pronta";
      }

      return;
    }

    imagemPreview.src = "#";
    imagemPreview.hidden = true;

    if (previewStatus) {
      previewStatus.innerText = "Sem imagem";
    }
  }

  function definirImagemAtual(imagemBase64) {
    imagemAtual = imagemBase64 || "";

    if (imagemAtual) {
      localStorage.setItem("AIDA_ImagemSelecionada", imagemAtual);
    } else {
      localStorage.removeItem("AIDA_ImagemSelecionada");
    }

    atualizarPreviewImagem(imagemAtual);
    limparResultado();
  }

  atualizarPreviewImagem(imagemAtual);
  limparResultado();

  if (btnTrocar && inputTrocarImagem) {
    btnTrocar.addEventListener("click", () => {
      inputTrocarImagem.value = "";
      inputTrocarImagem.click();
    });

    inputTrocarImagem.addEventListener("change", () => {
      const arquivo = inputTrocarImagem.files[0];

      if (!arquivo) {
        return;
      }

      const reader = new FileReader();
      reader.onload = (evento) => {
        definirImagemAtual(evento.target.result);

        if (tipoImagemInput) {
          tipoImagemInput.value = "";
        }

        if (metodoAnalise) {
          metodoAnalise.value = "";
        }

        atualizarRecomendacaoMetodo("", false);

        mostrarAlerta("Imagem trocada. Escolha o metodo e analise novamente.");
      };
      reader.readAsDataURL(arquivo);
    });
  }

  if (tipoImagemInput) {
    tipoImagemInput.addEventListener("change", () => {
      atualizarRecomendacaoMetodo(tipoImagemInput.value, true);
      limparResultado();
    });
  }

  if (metodoAnalise) {
    metodoAnalise.addEventListener("change", limparResultado);
  }

  if (checkMarcaDagua) {
    checkMarcaDagua.addEventListener("change", limparResultado);
  }

  if (checkMetadados) {
    checkMetadados.addEventListener("change", limparResultado);
  }

  window.setTimeout(iniciarTutorialPrimeiroAcesso, 450);

  if (!btnVerificar) {
    return;
  }

  btnVerificar.addEventListener("click", async () => {
    const configuracaoAtual = obterAdminConfig();
    const metodoSelecionado = metodoAnalise ? metodoAnalise.value : "";
    const analisarMarcaDagua = checkMarcaDagua ? checkMarcaDagua.checked : true;
    const analisarMetadados = checkMetadados ? checkMetadados.checked : true;

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
      configuracaoAtual.maintenanceMode &&
      !usuarioEhAdmin()
    ) {
      redirecionarParaManutencao("./index-analise.html");
      return;
    }

    if (configuracaoAtual.lockAnalysisPage) {
      mostrarAlerta("A analise foi travada temporariamente pelo administrador.");
      return;
    }

    if (!imagemAtual) {
      mostrarAlerta("Selecione uma imagem antes de analisar.");
      return;
    }

    if (!metodoSelecionado) {
      mostrarAlerta("Selecione o metodo de analise.");
      return;
    }

    limparResultado();
    btnVerificar.disabled = true;

    if (loading) {
      loading.style.display = "flex";
    }

    try {
      const response = await fetch("https://aida-on.onrender.com/analisar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          imagem: imagemAtual,
          metodo: metodoSelecionado,
          analisarMarcaDagua,
          analisarMetadados,
        }),
      });

      const dados = await response.json();

      if (!response.ok || dados.status !== "sucesso") {
        throw new Error(dados.mensagem || "Falha ao analisar a imagem.");
      }

      if (loading) {
        loading.style.display = "none";
      }

      if (areaResultado) {
        areaResultado.style.display = "block";
      }

      if (imagemProcessada) {
        imagemProcessada.src = dados.imagem_fft || "#";
      }

      if (porcentagemIA) {
        porcentagemIA.innerText = dados.probabilidade || "0%";
      }

      if (tituloMetodo) {
        tituloMetodo.innerText = dados.metodo || "Sobre o resultado";
      }

      if (textoMetodo) {
        textoMetodo.innerText = montarDescricaoMetodo(dados);
      }

      await renderizarExemplosMetodo(dados, imagemAtual, {
        bloco: blocoExemplosMetodo,
        titulo: tituloExemplosMetodo,
        descricao: descricaoExemplosMetodo,
        lista: exemplosMetodo,
      });

      await salvarHistorico(imagemAtual, dados);
      mostrarConviteInstalacao();
      mostrarAlerta("Analise concluida!");
    } catch (erro) {
      console.error("Erro ao processar imagem:", erro);

      if (loading) {
        loading.style.display = "none";
      }

      mostrarAlerta("Erro ao processar imagem.");
    } finally {
      btnVerificar.disabled = false;
    }
  });
});


