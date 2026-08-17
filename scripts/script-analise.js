const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";

const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

const CHAVE_IMAGEM_SELECIONADA = "AIDA_ImagemSelecionada";
const DB_IMAGEM_SELECIONADA = "AIDA_ImagemSelecionada_DB";
const STORE_IMAGEM_SELECIONADA = "imagem";
// Bases da API, nao URLs de /analisar: os mapas de evidencia vem como caminhos
// relativos ("/evidencia/<id>/<mapa>") e precisam ser prefixados pela mesma base
// que atendeu a analise.
//
// A API do Render (aida-modelo-api) ficou para tras: ela responde em dois estados
// e nao conhece INCONCLUSIVO nem fora_de_dominio. Apontar para ela faria o codigo
// abaixo nunca exercitar a abstencao. A porta local e 7860 (app_port do Space),
// nao 5000 — 5000 era o Flask antigo, de contrato incompativel.
const BASES_API = [
  "https://aidaon-aida-api.hf.space",
  "http://127.0.0.1:7860",
  "http://localhost:7860",
];

const favicon = document.getElementById("favicon");
const imagemPreview = document.getElementById("imagemPreview");
const imagemProcessada = document.getElementById("imagemProcessada");
const previewStatus = document.getElementById("previewStatus");
const btnVerificar = document.getElementById("btnVerificar");
const btnTrocar = document.getElementById("btnTrocar");
const inputTrocarImagem = document.getElementById("inputTrocarImagem");
const checkSalvarHistorico = document.getElementById("checkSalvarHistorico");
const loading = document.getElementById("loading");
const areaResultado = document.getElementById("areaResultado");
const porcentagemIA = document.getElementById("porcentagemIA");
const tituloMetodo = document.getElementById("tituloMetodo");
const textoMetodo = document.getElementById("textoMetodo");
const statusAnalise = document.getElementById("statusAnalise");

let imagemAtual = null;
let abortController = null;
let analiseEmAndamento = false;

function registrarStatus(mensagem, tipo = "info") {
  console.log(`[AIDA.ON] ${mensagem}`);
  if (statusAnalise) {
    statusAnalise.textContent = mensagem;
    statusAnalise.dataset.tipo = tipo;
  }
}

function updateFavicon() {
  if (!favicon) return;
  favicon.href = window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "../assets/images/AIDABranco.ico"
    : "../assets/images/AIDAPreto.ico";
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

async function obterImagemSelecionadaDoBanco() {
  const db = await abrirBancoImagemSelecionada();

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_IMAGEM_SELECIONADA, "readonly");
    const request = transaction.objectStore(STORE_IMAGEM_SELECIONADA).get(CHAVE_IMAGEM_SELECIONADA);

    request.onsuccess = () => {
      db.close();
      resolve(request.result || null);
    };
    request.onerror = () => {
      db.close();
      reject(request.error || new Error("Nao foi possivel recuperar a imagem."));
    };
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
    console.warn("Nao foi possivel salvar no IndexedDB:", erro);
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

async function obterImagemSelecionada() {
  const imagemSessao = sessionStorage.getItem(CHAVE_IMAGEM_SELECIONADA);
  if (imagemSessao) return imagemSessao;

  const imagemLocal = localStorage.getItem(CHAVE_IMAGEM_SELECIONADA);
  if (imagemLocal) return imagemLocal;

  try {
    return await obterImagemSelecionadaDoBanco();
  } catch (erro) {
    console.warn("Nao foi possivel recuperar do IndexedDB:", erro);
    return null;
  }
}

// O padrao vai sem extensao de proposito: quando nao ha nome original, a unica
// pista de formato e o MIME, e o bloco abaixo so recorre a ele nesse caso.
function dataUrlParaArquivo(dataUrl, nomePadrao = "imagem-aida") {
  const partes = dataUrl.split(",");
  const cabecalho = partes[0] || "";
  const conteudo = partes[1] || "";
  const mime = cabecalho.match(/data:(.*?);base64/)?.[1] || "image/png";

  // A extensao do nome original vale mais que a derivada do MIME. Windows nao
  // registra .heic/.avif como image/*, entao File.type chega vazio (ou
  // application/octet-stream) e o data URL perde o formato: derivar do MIME
  // rebatizava um .heic como ".png" e um .avif como ".octet-stream". So caimos
  // no MIME quando o nome nao traz extensao alguma.
  const extensaoOriginal = nomePadrao.match(/\.([^.]+)$/)?.[1]?.toLowerCase();
  const extensao =
    extensaoOriginal ||
    mime.split("/")[1]?.replace("jpeg", "jpg") ||
    "png";
  const binario = atob(conteudo);
  const bytes = new Uint8Array(binario.length);

  for (let i = 0; i < binario.length; i += 1) {
    bytes[i] = binario.charCodeAt(i);
  }

  return new File([bytes], nomePadrao.replace(/\.[^.]+$/, "") + "." + extensao, { type: mime });
}

function arquivoParaDataUrl(arquivo) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (evento) => resolve(evento.target.result);
    reader.onerror = () => reject(new Error("Nao foi possivel carregar a imagem selecionada."));
    reader.readAsDataURL(arquivo);
  });
}

// Nenhum navegador de desktop decodifica HEIC/HEIF, e TIFF só em parte. O
// backend lê esses formatos via pillow-heif, então a análise roda normalmente —
// quem falha é apenas o <img>, que ficava com o ícone de imagem quebrada e dava
// a impressão de que a análise tinha dado errado. Converter no cliente exigiria
// um decodificador WASM de ~2 MB; enquanto não houver prévia vinda da API, o
// caminho honesto é dizer que a visualização não existe, sem sugerir falha.
const EXTENSOES_SEM_PREVIA_NO_NAVEGADOR = ["heic", "heif", "tif", "tiff"];

function extensaoDe(nome) {
  return (nome || "").split(".").pop()?.toLowerCase() || "";
}

function marcarPreviaIndisponivel(img, extensao) {
  if (!img || img.dataset.previaIndisponivel === "true") return;
  img.dataset.previaIndisponivel = "true";
  img.removeAttribute("src");
  img.hidden = true;

  const aviso = document.createElement("p");
  aviso.className = "previa-indisponivel";
  // Só afirma que o formato não tem suporte quando ele realmente não tem. Um
  // PNG que falhou por estar truncado renderiza em qualquer navegador, e culpar
  // o formato mandaria o usuário procurar o problema no lugar errado.
  aviso.textContent = EXTENSOES_SEM_PREVIA_NO_NAVEGADOR.includes(extensao)
    ? `O navegador não exibe arquivos ${extensao.toUpperCase()}. A imagem foi enviada e analisada normalmente.`
    : "O navegador não conseguiu exibir esta imagem. A análise segue normalmente.";
  img.insertAdjacentElement("afterend", aviso);
}

function aplicarPrevia(img, dataUrl, extensao) {
  if (!img) return;

  // Troca de imagem: limpa o aviso da anterior antes de decidir de novo.
  const avisoAnterior = img.parentElement?.querySelector(".previa-indisponivel");
  if (avisoAnterior) avisoAnterior.remove();
  img.dataset.previaIndisponivel = "false";

  // Formato conhecidamente sem suporte: nem chega a atribuir o src. Um HEIC de
  // 5 MB vira ~6,7 MB de base64 que o navegador descartaria de qualquer forma.
  if (EXTENSOES_SEM_PREVIA_NO_NAVEGADOR.includes(extensao)) {
    marcarPreviaIndisponivel(img, extensao);
    return;
  }

  // Rede de seguranca para o que a lista acima nao previu: `onerror` antes do
  // `src`, porque com data URL a falha dispara de imediato.
  img.onerror = () => marcarPreviaIndisponivel(img, extensao);
  img.src = dataUrl;
  img.hidden = false;
}

function mostrarImagem(dataUrl) {
  registrarStatus("Imagem recuperada. Pronto para analisar.");

  // Recupera o nome original guardado na tela de selecao: o data URL perde a
  // extensao, e um .heic chegava ao backend renomeado como ".png".
  const nomeOriginal = sessionStorage.getItem("AIDA_NomeArquivoSelecionado");

  try {
    imagemAtual = nomeOriginal
      ? dataUrlParaArquivo(dataUrl, nomeOriginal)
      : dataUrlParaArquivo(dataUrl);
  } catch (erro) {
    console.error("Nao foi possivel preparar a imagem para analise:", erro);
    imagemAtual = null;
    if (previewStatus) {
      previewStatus.textContent = "Imagem invalida. Troque a imagem.";
    }
    registrarStatus("Imagem invalida. Troque a imagem.", "erro");
    return;
  }

  const extensao = extensaoDe(nomeOriginal);
  aplicarPrevia(imagemPreview, dataUrl, extensao);
  aplicarPrevia(imagemProcessada, dataUrl, extensao);

  if (previewStatus) {
    previewStatus.textContent = EXTENSOES_SEM_PREVIA_NO_NAVEGADOR.includes(extensao)
      ? "Imagem pronta (sem prévia neste formato)"
      : "Imagem pronta";
  }

  if (btnVerificar) {
    btnVerificar.disabled = false;
  }
}

function setCarregando(ativo) {
  if (loading) loading.style.display = ativo ? "flex" : "none";
  if (btnVerificar) {
    btnVerificar.disabled = ativo;
    btnVerificar.textContent = ativo ? "Analisando..." : "Analisar imagem";
  }
  if (btnTrocar) btnTrocar.disabled = ativo;
}

// A API tem TRES estados, mais o caso "fora do escopo". A versao anterior desta
// funcao testava apenas `resultado === "IA/MANIPULADA"` e caia no ramo
// "provavelmente real" para todo o resto — ou seja, quando o sistema respondia
// INCONCLUSIVO, a tela afirmava que a imagem era real.
const ESTADOS = {
  "IA/MANIPULADA": {
    titulo: "Indícios de imagem gerada ou manipulada por IA",
    cor: "#c62828",
    mostrarProbabilidades: true,
  },
  REAL: {
    titulo: "Indícios de fotografia real",
    cor: "#2e7d32",
    mostrarProbabilidades: true,
  },
  INCONCLUSIVO: {
    titulo: "",
    cor: "#e08a1e",
    mostrarProbabilidades: true,
  },
  FORA_DE_DOMINIO: {
    titulo: "Fora do escopo da ferramenta",
    cor: "#6b7280",
    // Quando a imagem nao e fotografica, a probabilidade nao tem significado:
    // exibi-la convida o usuario a interpretar um numero sem sentido.
    mostrarProbabilidades: false,
  },
};

// Titulos que a tela nao exibe mais, venham de onde vierem.
const TITULOS_OCULTOS = new Set(["resultado inconclusivo"]);

function estadoDe(dados) {
  if (dados.fora_de_dominio) return ESTADOS.FORA_DE_DOMINIO;
  return ESTADOS[dados.resultado] || ESTADOS.INCONCLUSIVO;
}

function escapar(texto) {
  const div = document.createElement("div");
  div.textContent = String(texto ?? "");
  return div.innerHTML;
}

function exibirResultado(dados, baseApi) {
  const estado = estadoDe(dados);

  // O contrato e explicito: exiba probabilidade_ia_EXIBICAO. O limiar operacional
  // vem do indice de Youden e nao cai em 0,50; mostrar a probabilidade calibrada
  // produz telas como "28% de IA" ao lado do veredito "IA/MANIPULADA".
  const probIA = Number(
    dados.probabilidade_ia_exibicao ?? dados.probabilidade_ia ?? 0
  );
  const probReal = Number(
    dados.probabilidade_real_exibicao ?? dados.probabilidade_real ?? 1 - probIA
  );
  const pctIA = Math.round(probIA * 1000) / 10;
  const pctReal = Math.round(probReal * 1000) / 10;

  if (porcentagemIA) {
    porcentagemIA.textContent = estado.mostrarProbabilidades
      ? `${pctIA.toFixed(1)}%`
      : "não se aplica";
    const badge = porcentagemIA.closest(".status-badge");
    if (badge) {
      badge.style.borderLeft = `5px solid ${estado.cor}`;
      badge.style.paddingLeft = "10px";
    }
  }

  if (tituloMetodo) {
    // A API ja manda um titulo pronto; o mapa local e so a rede de seguranca.
    // O titulo do estado inconclusivo foi removido da tela, e APIs antigas ainda
    // mandam a frase — por isso o descarte explicito aqui, e nao so no mapa.
    const tituloApi = String(dados.titulo || "").trim();
    const texto = TITULOS_OCULTOS.has(tituloApi.toLowerCase())
      ? estado.titulo
      : tituloApi || estado.titulo;

    tituloMetodo.textContent = texto;
    tituloMetodo.style.color = estado.cor;
    tituloMetodo.hidden = !texto;
  }

  const statsContainer = document.getElementById("statsContainer");
  if (statsContainer) {
    statsContainer.style.display = estado.mostrarProbabilidades ? "grid" : "none";

    if (estado.mostrarProbabilidades) {
      document.getElementById("statReal").textContent = `${pctReal.toFixed(1)}%`;
      document.getElementById("statIA").textContent = `${pctIA.toFixed(1)}%`;

      setTimeout(() => {
        document.getElementById("barReal").style.width = `${pctReal}%`;
        document.getElementById("barIA").style.width = `${pctIA}%`;
      }, 150);

      const statConf = document.getElementById("statConfidence");
      if (statConf) {
        statConf.textContent = dados.confianca ? dados.confianca.toUpperCase() : "NÃO INFORMADA";
      }
    }
  }

  renderizarDetalhes(dados, estado);
  renderizarEvidencias(dados, baseApi);
  renderizarProveniencia(dados);
  prepararPassagemForense(dados, baseApi);

  if (areaResultado) {
    areaResultado.style.display = "block";
    areaResultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const isLogged = localStorage.getItem("usuarioNome") || localStorage.getItem("usuarioEmail");
  if (!isLogged) {
    localStorage.setItem("AIDA_AnaliseUnlogged", "true");
  }
}

// Chave lida pelo AIDA Forensics (scripts/script-forensics.js). Guarda apenas o
// necessario para reabrir a analise: o id, a base que a atendeu e o nome do
// arquivo. A imagem NAO vai junto — ela ja esta no armazenamento do navegador,
// e duplica-la aqui estouraria a cota do sessionStorage em imagens grandes.
const CHAVE_REPASSE_FORENSE = "AIDA_Forense";

function prepararPassagemForense(dados, baseApi) {
  const bloco = document.getElementById("blocoForense");
  const botao = document.getElementById("btnVerForense");
  if (!bloco || !botao) return;

  const idAnalise = String(dados.id_analise || "").trim();
  if (!idAnalise) {
    // Sem id nao ha o que reabrir: a API antiga nao devolvia o campo, e um
    // botao que sempre leva a "analise nao encontrada" e pior que nenhum botao.
    bloco.hidden = true;
    return;
  }

  const repasse = {
    id_analise: idAnalise,
    base_api: baseApi || "",
    nome_imagem: dados.nome_imagem_original || dados.nome_imagem || "",
    quando: Date.now(),
  };

  try {
    sessionStorage.setItem(CHAVE_REPASSE_FORENSE, JSON.stringify(repasse));
  } catch (erro) {
    console.warn("Nao foi possivel registrar a passagem para o Forensics:", erro);
  }

  // O id tambem vai na URL: assim o link continua valido se o usuario abrir em
  // outra aba, onde o sessionStorage nao existe.
  const parametros = new URLSearchParams({ id: idAnalise });
  if (baseApi) parametros.set("base", baseApi);
  botao.href = `./index-forensics.html?${parametros.toString()}`;
  bloco.hidden = false;
}

function renderizarDetalhes(dados, estado) {
  if (!textoMetodo) return;

  const partes = [];

  if (dados.explicacao) {
    partes.push(`<p>${escapar(dados.explicacao)}</p>`);
  }

  // Por que o sistema se absteve. Sem isto, "inconclusivo" parece falha da
  // ferramenta em vez de recusa deliberada de decidir sem base.
  const motivos = Array.isArray(dados.motivos) ? dados.motivos : [];
  if (motivos.length) {
    partes.push(
      `<p class="detalhe-titulo"><strong>Por que não foi possível decidir</strong></p>
       <ul class="detalhe-lista">${motivos.map((m) => `<li>${escapar(m)}</li>`).join("")}</ul>`
    );
  }

  // O que segue e leitura tecnica: fica recolhido, como os mapas de evidencia.
  // Motivos e ressalva ficam de fora deste bloco de proposito — sao o que
  // explica e qualifica o veredito, e nao podem depender de um clique.
  const tecnicos = [];

  // O desacordo entre modulos explica boa parte dos casos inconclusivos.
  const scores = dados.scores_modulos && Object.entries(dados.scores_modulos);
  if (scores && scores.length) {
    const linhas = scores
      .map(([nome, valor]) => `<li><span>${escapar(nome)}</span><span>${(Number(valor) * 100).toFixed(1)}%</span></li>`)
      .join("");
    const fusao = dados.fusao || {};
    const nota = fusao.calibrado === false
      ? " (fusão sem calibração — resultado menos confiável)"
      : "";
    tecnicos.push(
      `<p class="detalhe-titulo"><strong>Leitura por módulo${escapar(nota)}</strong></p>
       <ul class="detalhe-lista detalhe-modulos">${linhas}</ul>`
    );
  }

  const limitacoes = Array.isArray(dados.limitacoes) ? dados.limitacoes : [];
  if (limitacoes.length) {
    tecnicos.push(
      `<p class="detalhe-titulo"><strong>Limitações deste arquivo</strong></p>
       <ul class="detalhe-lista">${limitacoes.map((l) => `<li>${escapar(l)}</li>`).join("")}</ul>`
    );
  }

  if (tecnicos.length) {
    partes.push(
      `<details class="detalhe-tecnico">
         <summary class="detalhe-tecnico-summary">Detalhes técnicos</summary>
         <div class="detalhe-tecnico-corpo">${tecnicos.join("")}</div>
       </details>`
    );
  }

  // §8.2: a ressalva e obrigatoria e nao pode ser omitida da interface.
  const ressalva =
    dados.ressalva ||
    "Este resultado é um indício probabilístico, não uma prova. Não identifica autoria e não substitui a verificação da fonte da imagem.";
  partes.push(`<p class="detalhe-ressalva">${escapar(ressalva)}</p>`);

  textoMetodo.innerHTML = partes.join("");
  textoMetodo.style.display = "block";
}

// Os mapas de explicabilidade (§8.3) vao para o bloco de exemplos que ja existe
// na pagina.
const LEGENDAS_MAPAS = {
  gradiente: "Gradiente — onde a imagem varia mais bruscamente.",
  bordas: "Bordas detectadas — confere se o modelo reage à cena, não a artefato.",
  ruido_residual: "Ruído residual — câmeras deixam ruído homogêneo.",
  espectro_magnitude: "Espectro (magnitude) — picos regulares podem indicar geração.",
  espectro_fase: "Espectro (fase) — mais estável sob compressão.",
  clip_tokens: "Atenção do CLIP — regiões que mais pesam na representação visual.",
};

function renderizarEvidencias(dados, baseApi) {
  const bloco = document.getElementById("blocoExemplosMetodo");
  const grade = document.getElementById("exemplosMetodo");
  const titulo = document.getElementById("tituloExemplosMetodo");
  const descricao = document.getElementById("descricaoExemplosMetodo");
  const recolhivel = document.getElementById("detalhesExemplosMetodo");
  if (!bloco || !grade) return;

  // Cada analise recomeca recolhida: deixar aberto o que o usuario expandiu na
  // imagem anterior mostraria os mapas novos sem que ele tenha pedido.
  if (recolhivel) recolhivel.open = false;

  const urls = (dados.evidencias && dados.evidencias.urls) || {};
  const nomes = Object.keys(urls);
  if (!nomes.length || !baseApi) {
    bloco.hidden = true;
    grade.innerHTML = "";
    return;
  }

  if (titulo) titulo.textContent = "Evidências visuais da análise";
  if (descricao) {
    descricao.textContent =
      "Estes mapas mostram onde o sinal medido é mais forte — não onde houve " +
      "manipulação. Servem para inspeção, não como prova.";
  }

  bloco.hidden = false;

  // Sem loading="lazy": a imagem nao tem dimensao intrinseca antes de carregar e
  // colapsa para ~2px de altura, e o Chrome nunca considera o elemento visivel o
  // bastante para disparar o pedido — os seis mapas ficavam permanentemente em
  // branco, sem sequer uma requisicao. Sao seis PNGs pequenos, exibidos so depois
  // de uma analise que o usuario pediu; nao ha o que adiar.
  grade.innerHTML = nomes
    .map((nome) => {
      const src = `${baseApi}${urls[nome]}`;
      const legenda = LEGENDAS_MAPAS[nome] || nome;
      return `<figure class="exemplo-metodo">
        <img src="${escapar(src)}" alt="${escapar(legenda)}" decoding="async">
        <figcaption>${escapar(legenda)}</figcaption>
      </figure>`;
    })
    .join("");
}

// --- Proveniência digital -------------------------------------------------- //
// A camada de proveniência responde uma pergunta diferente da análise visual:
// "o arquivo diz de onde veio?". As duas leituras aparecem lado a lado e nunca
// somadas — somar porcentagens de fontes distintas não é probabilidade.
const ESTADOS_PROVENIENCIA = {
  AI_PROVENANCE_CONFIRMED: {
    rotulo: "Evidência muito forte de geração por IA",
    forca: "forte",
    resumo: "O próprio arquivo carrega uma credencial assinada declarando que foi gerado por IA.",
  },
  AI_EDIT_PROVENANCE: {
    rotulo: "Evidência forte de edição com IA",
    forca: "forte",
    resumo: "A credencial assinada declara que partes da imagem foram criadas ou alteradas por IA generativa.",
  },
  AI_PROVENANCE_LIKELY: {
    rotulo: "Evidência consistente de IA",
    forca: "media",
    resumo: "Os metadados declaram origem em IA, mas sem assinatura criptográfica que garanta a declaração.",
  },
  METADATA_AI_SIGNAL: {
    rotulo: "Sinal de ferramenta generativa",
    forca: "media",
    resumo: "Os metadados mencionam uma ferramenta de IA. É indício, não prova: esses campos são texto livre.",
  },
  C2PA_PRESENT: {
    rotulo: "Credencial encontrada, sem declaração sobre IA",
    forca: "neutra",
    resumo: "O arquivo tem Content Credentials, mas elas não dizem se houve IA na criação.",
  },
  C2PA_INVALID: {
    rotulo: "Credencial presente, porém inválida",
    forca: "media",
    resumo: "Há uma credencial no arquivo, mas ela não passou na verificação de integridade.",
  },
  CAPTURE_PROVENANCE_CONFIRMED: {
    rotulo: "Captura por câmera verificada",
    forca: "real",
    resumo: "Uma credencial assinada declara que a imagem foi capturada por câmera.",
  },
  NO_PROVENANCE_FOUND: {
    rotulo: "Nenhuma informação de proveniência",
    forca: "neutra",
    resumo:
      "Nenhuma informação de proveniência foi encontrada. Isso não significa que a imagem " +
      "seja real: print, recorte, recompressão, envio por aplicativo de mensagens e " +
      "exportação removem esses dados.",
  },
  UNKNOWN: {
    rotulo: "Não foi possível concluir",
    forca: "neutra",
    resumo: "O arquivo não pôde ser lido o suficiente para uma conclusão sobre a origem.",
  },
};

function porcentagem(valor) {
  return `${(Number(valor) * 100).toFixed(1)}%`;
}

function itemProveniencia(termo, valor) {
  return `<div class="proveniencia-item">
    <dt>${escapar(termo)}</dt>
    <dd>${escapar(valor)}</dd>
  </div>`;
}

function renderizarProveniencia(dados) {
  const bloco = document.getElementById("blocoProveniencia");
  if (!bloco) return;

  const prov = dados.proveniencia;
  if (!prov) {
    // API antiga, sem a camada. Esconder é melhor que mostrar campos vazios.
    bloco.hidden = true;
    return;
  }

  bloco.hidden = false;

  const info = ESTADOS_PROVENIENCIA[prov.status] || ESTADOS_PROVENIENCIA.UNKNOWN;
  const selo = document.getElementById("provenienciaSelo");
  if (selo) {
    selo.textContent = info.rotulo;
    selo.dataset.forca = info.forca;
  }

  const resumo = document.getElementById("provenienciaResumo");
  if (resumo) resumo.textContent = info.resumo;

  const divergencia = document.getElementById("provenienciaDivergencia");
  if (divergencia) {
    if (prov.divergencia) {
      divergencia.hidden = false;
      divergencia.textContent =
        "As duas fontes discordam: a proveniência do arquivo e a análise do conteúdo " +
        "apontam para lados opostos. Nenhuma das duas foi descartada — ambas estão " +
        "registradas abaixo.";
    } else {
      divergencia.hidden = true;
    }
  }

  const atribuicao = prov.atribuicao || {};
  const itens = [];

  const conteudo = dados.probabilidade_ia_conteudo;
  if (typeof conteudo === "number") {
    itens.push(itemProveniencia("Análise de conteúdo", porcentagem(conteudo)));
  }
  itens.push(itemProveniencia("Força da proveniência", info.rotulo));

  if (atribuicao.gerador && atribuicao.gerador !== "desconhecido") {
    itens.push(itemProveniencia("Origem provável", atribuicao.gerador));
    itens.push(itemProveniencia(
      "Confiança da atribuição",
      porcentagem(atribuicao.confianca || 0)
    ));
  } else {
    itens.push(itemProveniencia("Origem provável", "Não identificada"));
  }

  itens.push(itemProveniencia(
    "Content Credentials",
    prov.c2pa_presente
      ? (prov.c2pa_valido ? "Encontradas e verificadas" : "Encontradas, mas não verificadas")
      : "Não encontradas"
  ));

  if (prov.softwares && prov.softwares.length) {
    itens.push(itemProveniencia("Software identificado", prov.softwares.slice(0, 2).join(", ")));
  }

  const grade = document.getElementById("provenienciaGrade");
  if (grade) grade.innerHTML = itens.join("");

  const fusao = document.getElementById("provenienciaFusao");
  if (fusao) {
    // Explicação honesta do mecanismo: nada aqui é soma de porcentagens.
    const partes = [
      "As duas leituras não são somadas. A proveniência entra como um peso que " +
      "desloca a probabilidade da análise de conteúdo, na escala de chances " +
      "(log-odds), e o quanto ela desloca depende da força da evidência — uma " +
      "credencial assinada pesa muito mais que um campo de texto nos metadados.",
    ];
    if (typeof conteudo === "number") {
      partes.push(
        `Neste caso: conteúdo ${porcentagem(conteudo)} → resultado final ` +
        `${porcentagem(dados.probabilidade_ia)}.`
      );
    }
    partes.push(
      "A ausência de proveniência nunca reduz a probabilidade de IA: essas " +
      "informações se perdem com facilidade e sua falta não é sinal de autenticidade."
    );
    fusao.textContent = partes.join(" ");
  }

  const lista = document.getElementById("provenienciaEvidencias");
  if (lista) {
    const evidencias = prov.evidencias || [];
    lista.innerHTML = evidencias.length
      ? evidencias
          .map((e) => `<div class="proveniencia-evidencia">
              <span class="proveniencia-fonte">${escapar(e.confiabilidade || e.fonte)}</span>
              <strong>${escapar(e.chave)}</strong>
              <span>${escapar(String(e.valor).slice(0, 160))}</span>
            </div>`)
          .join("")
      : `<p class="proveniencia-nota">Nenhuma evidência de proveniência foi encontrada no arquivo.</p>`;
  }

  const detalhes = document.getElementById("provenienciaDetalhes");
  if (detalhes) detalhes.open = false;
}

async function executarAnalise(event) {
  event?.preventDefault();
  event?.stopPropagation();
  event?.stopImmediatePropagation?.();

  if (analiseEmAndamento) {
    registrarStatus("Analise ja esta em andamento. Aguarde o resultado...");
    return;
  }

  analiseEmAndamento = true;
  registrarStatus("Recebendo sua imagem");

  if (!imagemAtual) {
    if (previewStatus) {
      previewStatus.textContent = "Nenhuma imagem carregada";
    }
    registrarStatus("Nenhuma imagem carregada para analise.", "erro");
    alert("Nenhuma imagem carregada. Clique em Trocar imagem ou volte para selecionar uma imagem.");
    analiseEmAndamento = false;
    return;
  }

  if (previewStatus) {
    previewStatus.textContent = "Enviando para analise...";
  }

  abortController = new AbortController();
  setCarregando(true);
  if (areaResultado) areaResultado.style.display = "none";

  const salvarNoHistorico = checkSalvarHistorico?.checked ?? true;
  const formData = new FormData();
  formData.append("imagem", imagemAtual);
  formData.append("historico_habilitado", salvarNoHistorico ? "true" : "false");

  try {
    registrarStatus("Processando");
    const { resposta, base } = await enviarParaApi(formData, abortController.signal);
    registrarStatus("Obtendo resultados");

    const dados = await resposta.json().catch(() => ({}));

    if (!resposta.ok || dados.erro) {
      throw new Error(dados.erro || `Falha no servidor (${resposta.status})`);
    }

    exibirResultado(dados, base);
    registrarStatus("Analise concluida com sucesso.", "sucesso");
    if (previewStatus) {
      previewStatus.textContent = "Analise concluida";
    }

    if (salvarNoHistorico) {
      salvarHistoricoSupabase(imagemAtual, dados, base)
        .then(() => {
          registrarStatus("Histórico salvo com sucesso na nuvem.", "sucesso");
        })
        .catch((erro) => {
          console.warn("Nao foi possivel sincronizar com o Supabase:", erro);
          alert("Não foi possível salvar a imagem no histórico. Detalhes: " + erro.message);
        });
    }
  } catch (erro) {
    if (erro.name !== "AbortError") {
      if (previewStatus) {
        previewStatus.textContent = "Erro na analise";
      }
      registrarStatus(erro.message || "Erro na analise.", "erro");
      alert(
        erro.message ||
        "Nao foi possivel conectar com a API Python. Confirme se o servidor Flask esta rodando na porta 5000."
      );
    }
  } finally {
    abortController = null;
    analiseEmAndamento = false;
    setCarregando(false);
  }
}

// Devolve tambem a base que respondeu: os mapas de evidencia sao caminhos
// relativos e so fazem sentido prefixados pela mesma origem.
async function enviarParaApi(formData, signal) {
  for (const base of BASES_API) {
    try {
      registrarStatus("Aplicação do método de Análise");
      const resposta = await fetch(`${base}/analisar`, {
        method: "POST",
        body: formData,
        signal,
      });
      return { resposta, base };
    } catch (erro) {
      if (erro.name === "AbortError") throw erro;
      registrarStatus(`Falha ao conectar em ${base}: ${erro.message}`, "erro");
    }
  }

  throw new Error(
    "Não foi possível conectar com a API do AIDA. Verifique se o Space no Hugging Face está online ou se o backend local está rodando na porta 7860."
  );
}

async function salvarHistoricoSupabase(arquivo, dadosAnalisados, baseApi) {
  if (typeof _supabase === 'undefined') return;

  const { data: { user }, error: authError } = await _supabase.auth.getUser();
  if (authError) throw new Error("Erro de autenticacao: " + authError.message);
  if (!user) throw new Error("Usuário não está logado no Supabase.");

  // 1. Upload da imagem para o bucket "evidencias"
  const fileName = `${Date.now()}_${arquivo.name}`;
  const filePath = `${user.id}/${fileName}`;
  
  const { error: uploadError } = await _supabase.storage
    .from("evidencias")
    .upload(filePath, arquivo);

  if (uploadError) {
    throw new Error(`Erro ao subir imagem: ${uploadError.message}`);
  }

  // Obter URL pública
  const { data: publicUrlData } = _supabase.storage
    .from("evidencias")
    .getPublicUrl(filePath);

  const imagem_original = publicUrlData.publicUrl;

  // O historico guardava so o par de probabilidades, sem o veredito. Uma analise
  // INCONCLUSIVA ficava indistinguivel de uma decidida, e a tela do historico
  // apresentava os numeros como se fossem uma conclusao. O veredito vai junto.
  const estado = estadoDe(dadosAnalisados);
  const probIA = Number(
    dadosAnalisados.probabilidade_ia_exibicao ?? dadosAnalisados.probabilidade_ia ?? 0
  );
  const probReal = Number(
    dadosAnalisados.probabilidade_real_exibicao ?? dadosAnalisados.probabilidade_real ?? 1 - probIA
  );

  const veredito = dadosAnalisados.fora_de_dominio
    ? "FORA DE ESCOPO"
    : dadosAnalisados.resultado || "INCONCLUSIVO";
  const probabilidadeFormatada = estado.mostrarProbabilidades
    ? `${veredito} — IA: ${(probIA * 100).toFixed(1)}% | Real: ${(probReal * 100).toFixed(1)}%`
    : `${veredito} — probabilidades não se aplicam`;

  const payload = {
    user_id: user.id,
    data_analise: new Date().toISOString(),
    imagem_original: imagem_original,
    metodo: dadosAnalisados.versao_modelo || (dadosAnalisados.fusao && dadosAnalisados.fusao.metodo) || "AIDA",
    probabilidade: probabilidadeFormatada,
    resultado_img: null // ou a imagem tratada se a API fornecesse
  };

  // Proveniência no histórico. Guardamos só o que permite reconstruir a decisão
  // depois — estado, força, credencial e atribuição —, não o manifesto inteiro.
  const prov = dadosAnalisados.proveniencia;
  const camposProveniencia = prov
    ? {
        provenance_status: prov.status || null,
        provenance_score: typeof prov.score === "number" ? prov.score : null,
        provenance_confidence: prov.confianca || null,
        c2pa_present: !!prov.c2pa_presente,
        c2pa_valid: prov.c2pa_valido === true,
        ai_generated_claim: !!prov.declaracao_ia,
        generator: (prov.atribuicao && prov.atribuicao.gerador) || null,
        generator_confidence:
          prov.atribuicao && typeof prov.atribuicao.confianca === "number"
            ? prov.atribuicao.confianca
            : null,
        software: (prov.softwares && prov.softwares[0]) || null,
        probabilidade_conteudo:
          typeof dadosAnalisados.probabilidade_ia_conteudo === "number"
            ? dadosAnalisados.probabilidade_ia_conteudo
            : null,
        model_version: dadosAnalisados.versao_modelo || null,
      }
    : {};

  // Reabertura no AIDA Forensics.
  //
  // Dois campos curtos, e só. O que o Forensics precisa (mapas, scores,
  // metadados, proveniência) já está no cache do servidor, indexado por
  // `analysis_id`; duplicar esse conteúdo no Supabase multiplicaria o
  // armazenamento por análise sem ganho nenhum. `api_base` existe porque a
  // mesma conta pode ter análises feitas no backend local e no publicado, e o
  // id só vale na base que o gerou.
  //
  // O cache do servidor expira (sete dias, por padrão): análises antigas
  // deixarão de abrir, e a tela do Forensics já trata esse caso pedindo uma
  // nova análise. Persistir o dossiê inteiro para evitar isso é uma decisão de
  // armazenamento que ainda não se justifica.
  const camposForense = {
    analysis_id: dadosAnalisados.id_analise || null,
    api_base: baseApi || null,
  };

  // Enquanto a migração de colunas não roda (docs/migracao-proveniencia.sql), o
  // insert completo falha com PGRST204. Cair para o payload antigo mantém o
  // histórico funcionando em vez de derrubá-lo em produção.
  let { error: insertError } = await _supabase
    .from("historico_analises")
    .insert([{ ...payload, ...camposProveniencia, ...camposForense }]);

  if (insertError && /column|schema cache|PGRST204/i.test(insertError.message || "")) {
    console.warn(
      "[AIDA.ON] Colunas de proveniência ou de reabertura forense ausentes no " +
      "histórico; gravando sem elas. Rode docs/migracao-proveniencia.sql e " +
      "docs/migracao-forensics.sql no Supabase.",
      insertError.message
    );
    ({ error: insertError } = await _supabase
      .from("historico_analises")
      .insert([payload]));
  }

  if (insertError) {
    throw new Error(`Erro na persistencia do Supabase: ${insertError.message}`);
  }
}

async function trocarImagem(arquivo) {
  if (!arquivo) return;
  if (!arquivo.type.startsWith("image/")) {
    alert("Selecione um arquivo de imagem valido.");
    return;
  }

  const limiteMB = 15;
  if (arquivo.size > limiteMB * 1024 * 1024) {
    alert(`O arquivo excede o limite maximo de ${limiteMB} MB.`);
    return;
  }

  const dataUrl = await arquivoParaDataUrl(arquivo);
  await salvarImagemSelecionada(dataUrl);
  mostrarImagem(dataUrl);
  if (areaResultado) areaResultado.style.display = "none";
}

document.addEventListener(
  "click",
  (event) => {
    const botaoAnalise = event.target.closest?.("#btnVerificar");
    if (!botaoAnalise) return;
    executarAnalise(event);
  },
  true
);

document.addEventListener("submit", (event) => {
  if (event.target.closest?.(".analysis-page")) {
    event.preventDefault();
  }
});

document.addEventListener("DOMContentLoaded", async () => {
  window.executarAnaliseAida = executarAnalise;
  registrarStatus("Script da analise carregado. Recuperando imagem selecionada...");
  updateFavicon();
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", updateFavicon);

  if (checkSalvarHistorico) {
    checkSalvarHistorico.checked = !["localhost", "127.0.0.1"].includes(window.location.hostname);
  }

  const isLogged = localStorage.getItem("usuarioNome") || localStorage.getItem("usuarioEmail");
  if (!isLogged) {
    const retencaoGroup = document.getElementById("retencaoAnaliseGroup");
    if (retencaoGroup) retencaoGroup.style.display = "none";

    const btnHistorico = document.querySelector('.top-link[href="./index-historico.html"]');
    if (btnHistorico) btnHistorico.style.display = "none";

    const btnMinhaConta = document.getElementById("nome-usuario2");
    if (btnMinhaConta) {
      btnMinhaConta.textContent = "Fazer Login";
      const clone = btnMinhaConta.cloneNode(true);
      btnMinhaConta.parentNode.replaceChild(clone, btnMinhaConta);
      clone.addEventListener("click", (e) => {
        e.preventDefault();
        window.location.href = "./index-login.html";
      });
      
      const dropdownContent = clone.nextElementSibling;
      if (dropdownContent && dropdownContent.classList.contains("dropdown-content")) {
        dropdownContent.style.display = "none";
      }
    }
  }

  if (btnVerificar) {
    btnVerificar.disabled = false;
    btnVerificar.setAttribute("data-aida-handler", "ativo");
  }

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
            <a href="./index-login.html" class="aida-button">Fazer Login</a>
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

  if (btnTrocar && inputTrocarImagem) {
    btnTrocar.addEventListener("click", (e) => {
      if (!isLogged && localStorage.getItem("AIDA_AnaliseUnlogged") === "true") {
        exibirLoginOverlay(e);
      } else {
        inputTrocarImagem.click();
      }
    });
    inputTrocarImagem.addEventListener("change", () => trocarImagem(inputTrocarImagem.files[0]));
  }

  const linkNovaAnalise = document.querySelector('a[href="./index-seleciona.html"]');
  if (linkNovaAnalise) {
    linkNovaAnalise.addEventListener("click", (e) => {
      if (!isLogged && localStorage.getItem("AIDA_AnaliseUnlogged") === "true") {
        exibirLoginOverlay(e);
      }
    });
  }

  const imagemSalva = await obterImagemSelecionada();
  if (imagemSalva) {
    mostrarImagem(imagemSalva);
  } else if (previewStatus) {
    previewStatus.textContent = "Nenhuma imagem selecionada";
    registrarStatus("Nenhuma imagem foi encontrada. Use Trocar imagem ou volte para selecionar.", "erro");
  }
});
