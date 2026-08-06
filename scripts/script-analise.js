const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";

const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

const CHAVE_IMAGEM_SELECIONADA = "AIDA_ImagemSelecionada";
const DB_IMAGEM_SELECIONADA = "AIDA_ImagemSelecionada_DB";
const STORE_IMAGEM_SELECIONADA = "imagem";
const URLS_API_ANALISAR = [
  "https://aida-modelo-api.onrender.com/analisar", // Exemplo: "https://sua-api.onrender.com/analisar"
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
  const probReal = Number(dados.probabilidade_real || 0);
  const pctIA = Math.round(probIA * 1000) / 10;
  const pctReal = Math.round(probReal * 1000) / 10;
  const ehIA = dados.resultado === "IA/MANIPULADA";

  if (porcentagemIA) {
    porcentagemIA.textContent = `${pctIA.toFixed(1)}%`;
  }

  if (tituloMetodo) {
    tituloMetodo.textContent = ehIA
      ? "Imagem provavelmente gerada por IA ou manipulada"
      : "Imagem provavelmente real";
  }

  const statsContainer = document.getElementById("statsContainer");
  if (statsContainer) {
    statsContainer.style.display = "grid";
    
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

  if (textoMetodo) {
    textoMetodo.style.display = "none";
  }

  if (areaResultado) {
    areaResultado.style.display = "block";
    areaResultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const isLogged = localStorage.getItem("usuarioNome") || localStorage.getItem("usuarioEmail");
  if (!isLogged) {
    localStorage.setItem("AIDA_AnaliseUnlogged", "true");
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
    const resposta = await enviarParaApi(formData, abortController.signal);
    registrarStatus("Obtendo resultados");

    const dados = await resposta.json().catch(() => ({}));

    if (!resposta.ok || dados.erro) {
      throw new Error(dados.erro || `Falha no servidor (${resposta.status})`);
    }

    exibirResultado(dados);
    registrarStatus("Analise concluida com sucesso.", "sucesso");
    if (previewStatus) {
      previewStatus.textContent = "Analise concluida";
    }

    if (salvarNoHistorico) {
      salvarHistoricoSupabase(imagemAtual, dados)
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

async function enviarParaApi(formData, signal) {
  let ultimoErro = null;

  for (const url of URLS_API_ANALISAR) {
    try {
      registrarStatus("Aplicação do método de Análise");
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
    "Não foi possível conectar com a API Python. Verifique se o servidor no Render está online ou se o backend local está rodando."
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

  const probIA = Number(dadosAnalisados.probabilidade_ia || 0);
  const probReal = Number(dadosAnalisados.probabilidade_real || 0);
  const probabilidadeFormatada = `IA: ${(probIA * 100).toFixed(1)}% | Real: ${(probReal * 100).toFixed(1)}%`;

  const payload = {
    user_id: user.id,
    data_analise: new Date().toISOString(),
    imagem_original: imagem_original,
    metodo: dadosAnalisados.modelo_utilizado || "ML Unificado",
    probabilidade: probabilidadeFormatada,
    resultado_img: null // ou a imagem tratada se a API fornecesse
  };

  const { error: insertError } = await _supabase
    .from("historico_analises")
    .insert([payload]);

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
