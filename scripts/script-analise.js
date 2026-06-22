const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";

const CHAVE_IMAGEM_SELECIONADA = "AIDA_ImagemSelecionada";
const DB_IMAGEM_SELECIONADA = "AIDA_ImagemSelecionada_DB";
const STORE_IMAGEM_SELECIONADA = "imagem";
const URLS_API_ANALISAR = [
  "http://127.0.0.1:5000/analisar",
  "http://localhost:5000/analisar",
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

function dataUrlParaArquivo(dataUrl, nomePadrao = "imagem-aida.png") {
  const partes = dataUrl.split(",");
  const cabecalho = partes[0] || "";
  const conteudo = partes[1] || "";
  const mime = cabecalho.match(/data:(.*?);base64/)?.[1] || "image/png";
  const extensao = mime.split("/")[1]?.replace("jpeg", "jpg") || "png";
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

function mostrarImagem(dataUrl) {
  registrarStatus("Imagem recuperada. Pronto para analisar.");

  try {
    imagemAtual = dataUrlParaArquivo(dataUrl);
  } catch (erro) {
    console.error("Nao foi possivel preparar a imagem para analise:", erro);
    imagemAtual = null;
    if (previewStatus) {
      previewStatus.textContent = "Imagem invalida. Troque a imagem.";
    }
    registrarStatus("Imagem invalida. Troque a imagem.", "erro");
    return;
  }

  if (imagemPreview) {
    imagemPreview.src = dataUrl;
    imagemPreview.hidden = false;
  }

  if (imagemProcessada) {
    imagemProcessada.src = dataUrl;
  }

  if (previewStatus) {
    previewStatus.textContent = "Imagem pronta";
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

function exibirResultado(dados) {
  const probIA = Number(dados.probabilidade_ia || 0);
  const pctIA = Math.round(probIA * 1000) / 10;
  const ehIA = dados.resultado === "IA/MANIPULADA";

  if (porcentagemIA) {
    porcentagemIA.textContent = `${pctIA.toFixed(1)}%`;
  }

  if (tituloMetodo) {
    tituloMetodo.textContent = ehIA
      ? "Imagem provavelmente gerada por IA ou manipulada"
      : "Imagem provavelmente real";
  }

  if (textoMetodo) {
    textoMetodo.textContent = montarDescricaoMetodo(dados);
  }

  if (areaResultado) {
    areaResultado.style.display = "block";
    areaResultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }
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
  registrarStatus("Botao analisar clicado. Preparando envio para a API...");

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
  formData.append("historico", salvarNoHistorico ? "true" : "false");

  try {
    registrarStatus("Enviando imagem para a API Python na porta 5000...");
    const resposta = await enviarParaApi(formData, abortController.signal);
    registrarStatus(`API respondeu com status ${resposta.status}. Processando resultado...`);

    const dados = await resposta.json().catch(() => ({}));

    if (!resposta.ok || !dados.sucesso) {
      throw new Error(dados.erro || `Falha no servidor (${resposta.status})`);
    }

    exibirResultado(dados);
    registrarStatus("Analise concluida com sucesso.", "sucesso");
    if (previewStatus) {
      previewStatus.textContent = "Analise concluida";
    }

    if (salvarNoHistorico) {
      salvarHistoricoSupabase(imagemAtual, dados).catch((erro) => {
        console.warn("Nao foi possivel sincronizar com o Supabase:", erro);
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

async function enviarParaApi(formData, signal) {
  let ultimoErro = null;

  for (const url of URLS_API_ANALISAR) {
    try {
      registrarStatus(`Tentando conexao com ${url}...`);
      return await fetch(url, {
        method: "POST",
        body: formData,
        signal,
      });
    } catch (erro) {
      ultimoErro = erro;
      registrarStatus(`Falha ao conectar em ${url}: ${erro.message}`, "erro");
    }
  }

  throw new Error(
    "Nao consegui conectar na API Python em http://127.0.0.1:5000. Abra o backend com: python AIDA.ON/apps/metodo/app.py"
  );
}

function montarDescricaoMetodo(dados) {
  const probReal = Number(dados.probabilidade_real || 0);
  const probIA = Number(dados.probabilidade_ia || 0);
  const linhas = [
    dados.explicacao || "Analise estatistica concluida pelo modelo AIDA.ON.",
    "",
    `Modelo utilizado: ${dados.modelo_utilizado || "Modelo AIDA.ON"}.`,
    `Probabilidade de imagem real: ${(probReal * 100).toFixed(1)}%.`,
    `Probabilidade de IA/manipulacao: ${(probIA * 100).toFixed(1)}%.`,
    `Confianca: ${dados.confianca || "nao informada"}.`,
  ];

  if (dados.id_analise) {
    linhas.push(`ID da analise: ${dados.id_analise}.`);
  }

  return linhas.join("\n");
}

async function salvarHistoricoSupabase(arquivo, dadosAnalisados) {
  if (!window.supabase) return;

  const payload = {
    id_analise: dadosAnalisados.id_analise || `AIDA-${new Date().getFullYear()}-XXXX`,
    data_hora: new Date().toISOString(),
    nome_arquivo: arquivo.name,
    resultado: dadosAnalisados.resultado,
    probabilidade_real: dadosAnalisados.probabilidade_real,
    probabilidade_ia: dadosAnalisados.probabilidade_ia,
    confianca: dadosAnalisados.confianca,
    modelo_utilizado: dadosAnalisados.modelo_utilizado || "ML Unificado",
  };

  const resposta = await fetch(`${supabaseUrl}/rest/v1/historico_analises`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: supabaseKey,
      Authorization: `Bearer ${supabaseKey}`,
      Prefer: "return=minimal",
    },
    body: JSON.stringify(payload),
  });

  if (!resposta.ok) {
    throw new Error(`Erro na persistencia do Supabase: ${resposta.statusText}`);
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

  if (btnVerificar) {
    btnVerificar.disabled = false;
    btnVerificar.setAttribute("data-aida-handler", "ativo");
  }

  if (btnTrocar && inputTrocarImagem) {
    btnTrocar.addEventListener("click", () => inputTrocarImagem.click());
    inputTrocarImagem.addEventListener("change", () => trocarImagem(inputTrocarImagem.files[0]));
  }

  const imagemSalva = await obterImagemSelecionada();
  if (imagemSalva) {
    mostrarImagem(imagemSalva);
  } else if (previewStatus) {
    previewStatus.textContent = "Nenhuma imagem selecionada";
    registrarStatus("Nenhuma imagem foi encontrada. Use Trocar imagem ou volte para selecionar.", "erro");
  }
});
