/* AIDA Audio — análise de áudio na página index-audio.html.
 *
 * Fala com o servidor do AIDA Video (Space aidaon/aida-video, ou o local na porta
 * 7870), nas rotas /audio/saude e /audio/analisar. Resposta síncrona.
 * Todo texto vindo do servidor entra por textContent.
 */
(function () {
  "use strict";

  const API_SPACE = "https://aidaon-aida-video.hf.space";
  const API_LOCAL = "http://127.0.0.1:7870";
  const EM_LOCALHOST = ["localhost", "127.0.0.1", "[::1]", ""].includes(location.hostname);
  const API_PADRAO = EM_LOCALHOST ? API_LOCAL : API_SPACE;
  const EXTENSOES = ["wav", "mp3", "m4a", "aac", "ogg", "opus", "flac", "webm", "amr", "3gp"];

  const $ = (id) => document.getElementById(id);
  const el = {
    servidor: $("audServidor"), servidorTitulo: $("audServidorTitulo"), servidorTexto: $("audServidorTexto"),
    form: $("audForm"), drop: $("audDrop"), arquivo: $("audArquivo"),
    dropTitulo: $("audDropTitulo"), dropTexto: $("audDropTexto"), player: $("audPlayer"),
    api: $("audApi"), enviar: $("audEnviar"), progresso: $("audProgresso"), painelEnvio: $("audPainelEnvio"),
    resultado: $("audResultado"), veredito: $("audVeredito"), vereditoTitulo: $("audVereditoTitulo"),
    significado: $("audSignificado"), motivos: $("audMotivos"), numeros: $("audNumeros"),
    medidor: $("audMedidor"), medidorFaixa: $("audMedidorFaixa"), medidorPonteiro: $("audMedidorPonteiro"),
    limites: $("audLimites"), limitesBloco: $("audLimitesBloco"), ressalva: $("audRessalva"),
    baixar: $("audBaixar"), novo: $("audNovo"),
  };
  if (!el.form) return;

  const ROTULOS = {
    "REAL": { texto: "Indícios de voz real", estado: "sucesso" },
    "IA/MANIPULADA": { texto: "Indícios de voz gerada por IA", estado: "erro" },
    "INCONCLUSIVO": { texto: "Inconclusivo", estado: "baixa-confianca" },
  };

  let servidorOk = false;
  let limiteMb = 30;
  let arquivoAtual = null;
  let relatorioAtual = null;
  let enviando = false;
  let novaTentativa = null;
  let urlPlayer = null;

  const baseApi = () => (el.api.value.trim() || API_PADRAO).replace(/\/+$/, "");
  const criar = (tag, classe, texto) => {
    const no = document.createElement(tag);
    if (classe) no.className = classe;
    if (texto !== undefined && texto !== null) no.textContent = texto;
    return no;
  };
  const definirEstado = (no, tipo) => { no.className = `aida-state aida-state--${tipo}`; };
  const formatarTamanho = (b) => (b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);
  const ehAudio = (f) => (f.type || "").startsWith("audio/") || EXTENSOES.includes((f.name.split(".").pop() || "").toLowerCase());
  const grandeDemais = (f) => Boolean(f && f.size > limiteMb * 1048576);

  async function verificarServidor() {
    clearTimeout(novaTentativa);
    definirEstado(el.servidor, "carregando");
    el.servidorTitulo.textContent = "Procurando o servidor…";
    el.servidorTexto.textContent = baseApi();
    try {
      const r = await fetch(`${baseApi()}/audio/saude`, { cache: "no-store" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const saude = await r.json();
      servidorOk = true;
      limiteMb = saude.tamanho_max_mb || limiteMb;
      definirEstado(el.servidor, "sucesso");
      el.servidorTitulo.textContent = "Servidor pronto para analisar";
      el.servidorTexto.textContent = `Áudio de até ${limiteMb} MB.`;
      if (arquivoAtual) escolherArquivo(arquivoAtual);
    } catch (_) {
      servidorOk = false;
      definirEstado(el.servidor, "indisponivel");
      if (baseApi() === API_SPACE) {
        el.servidorTitulo.textContent = "Servidor iniciando";
        el.servidorTexto.textContent = "O servidor pode estar acordando depois de um tempo sem uso. Tentando de novo em 20 segundos…";
        novaTentativa = setTimeout(verificarServidor, 20000);
      } else {
        el.servidorTitulo.textContent = "Servidor não encontrado";
        el.servidorTexto.textContent = `Na pasta AIDA.ON, rode "python -m aida_video.servidor". Endereço procurado: ${baseApi()}.`;
      }
    }
    atualizarBotao();
  }

  function atualizarBotao() {
    el.enviar.disabled = !(servidorOk && arquivoAtual && !enviando && ehAudio(arquivoAtual) && !grandeDemais(arquivoAtual));
  }

  function escolherArquivo(arquivo) {
    if (!arquivo) return;
    arquivoAtual = arquivo;
    el.dropTitulo.textContent = arquivo.name;
    let problema = "";
    if (!ehAudio(arquivo)) problema = "não parece um áudio. Para vídeos, use a análise de vídeo.";
    else if (grandeDemais(arquivo)) problema = `passa do limite de ${limiteMb} MB.`;
    el.dropTexto.textContent = `${formatarTamanho(arquivo.size)} · ${problema || "clique para trocar"}`;
    el.drop.classList.add("vid-drop--cheio");
    el.drop.classList.toggle("vid-drop--erro", Boolean(problema));
    if (urlPlayer) URL.revokeObjectURL(urlPlayer);
    urlPlayer = problema ? null : URL.createObjectURL(arquivo);
    el.player.hidden = !urlPlayer;
    if (urlPlayer) el.player.src = urlPlayer;
    atualizarBotao();
  }

  el.arquivo.addEventListener("change", () => escolherArquivo(el.arquivo.files[0]));
  if (window.AIDAEncaminhar) window.AIDAEncaminhar.entregarEm(el.arquivo, "audio");
  ["dragenter", "dragover"].forEach((ev) => el.drop.addEventListener(ev, (e) => { e.preventDefault(); el.drop.classList.add("vid-drop--sobre"); }));
  ["dragleave", "drop"].forEach((ev) => el.drop.addEventListener(ev, (e) => { e.preventDefault(); el.drop.classList.remove("vid-drop--sobre"); }));
  el.drop.addEventListener("drop", (e) => {
    const f = e.dataTransfer && e.dataTransfer.files[0];
    if (f) escolherArquivo(f);
  });

  el.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (el.enviar.disabled) return;
    enviando = true;
    atualizarBotao();
    el.progresso.hidden = false;
    const dados = new FormData();
    dados.append("audio", arquivoAtual, arquivoAtual.name);
    try {
      const r = await fetch(`${baseApi()}/audio/analisar`, { method: "POST", body: dados });
      let corpo = {};
      try { corpo = await r.json(); } catch (_) { /* sem JSON */ }
      if (!r.ok) throw new Error(corpo.erro || `O servidor respondeu com erro (HTTP ${r.status}).`);
      mostrarRelatorio(corpo);
    } catch (erro) {
      mostrarErro(erro instanceof TypeError ? "Sem conexão com o servidor. Tente de novo em instantes." : erro.message);
    } finally {
      enviando = false;
      el.progresso.hidden = true;
      atualizarBotao();
    }
  });

  function mostrarErro(mensagem) {
    relatorioAtual = null;
    el.resultado.hidden = false;
    definirEstado(el.veredito, "erro");
    el.vereditoTitulo.textContent = "Não foi possível analisar o áudio";
    el.significado.textContent = "";
    el.motivos.replaceChildren(criar("li", null, mensagem));
    el.numeros.replaceChildren();
    el.medidor.hidden = true;
    el.limitesBloco.hidden = true;
    el.ressalva.textContent = "";
    el.baixar.hidden = true;
  }

  function explicar(r) {
    if (r.resultado === "IA/MANIPULADA") {
      return "O sinal tem marcas típicas de voz sintética ou clonada. Antes de agir (transferência, cobrança, decisão), confirme por outro canal com a pessoa que supostamente falou.";
    }
    if (r.resultado === "REAL") {
      return "O sinal não mostra as marcas de síntese que o AIDA conhece. Clonagens novas podem escapar: em pedidos sensíveis, confirme por outro canal.";
    }
    if (r.probabilidade_ia === null || r.probabilidade_ia === undefined) {
      return "Não foi possível medir a voz neste arquivo. Envie um trecho mais longo, com fala clara, de preferência o arquivo original.";
    }
    return "O resultado ficou perto do ponto de decisão. Se puder, envie outro trecho da mesma voz ou o arquivo original (sem regravar pelo alto-falante).";
  }

  function numero(rotulo, valor) {
    const par = criar("div", "vid-numero");
    par.append(criar("dt", null, rotulo), criar("dd", null, valor));
    return par;
  }

  function mostrarRelatorio(r) {
    relatorioAtual = r;
    const rotulo = ROTULOS[r.resultado] || ROTULOS.INCONCLUSIVO;
    el.resultado.hidden = false;
    el.baixar.hidden = false;
    definirEstado(el.veredito, rotulo.estado);
    el.vereditoTitulo.textContent = `Resultado: ${rotulo.texto}`;
    el.significado.textContent = explicar(r);
    el.motivos.replaceChildren(...(r.motivos || []).map((m) => criar("li", null, m)));

    const p = typeof r.probabilidade_ia === "number" ? r.probabilidade_ia : null;
    el.medidor.hidden = p === null;
    if (p !== null) {
      el.medidorPonteiro.style.left = `${Math.min(100, Math.max(0, p * 100))}%`;
      const lim = typeof r.limiar === "number" ? r.limiar : 0.5;
      el.medidorFaixa.style.left = `${Math.max(0, (lim - 0.1) * 100)}%`;
      el.medidorFaixa.style.width = "20%";
    }
    const q = r.qualidade || {};
    el.numeros.replaceChildren(
      numero("Chance de ser IA", p === null ? "—" : `${Math.round(p * 100)}%`),
      numero("Confiança", r.confianca || "—"),
      numero("Duração analisada", typeof q.duracao_s === "number" ? `${q.duracao_s.toFixed(1)} s` : "—"),
      numero("Silêncio", typeof q.fracao_silencio === "number" ? `${Math.round(q.fracao_silencio * 100)}%` : "—"),
      numero("Modelo", r.modelo_utilizado || "indisponível"),
    );
    const limites = r.limitacoes || [];
    el.limites.replaceChildren(...limites.map((m) => criar("li", null, m)));
    el.limitesBloco.hidden = !limites.length;
    el.ressalva.textContent = r.ressalva || "";
    el.painelEnvio.hidden = true;
    el.resultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  el.baixar.addEventListener("click", () => {
    if (!relatorioAtual) return;
    const blob = new Blob([JSON.stringify(relatorioAtual, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `aida-audio-${(relatorioAtual.arquivo || "relatorio").replace(/\.[^.]+$/, "")}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });

  el.novo.addEventListener("click", () => {
    relatorioAtual = null;
    el.resultado.hidden = true;
    el.arquivo.value = "";
    arquivoAtual = null;
    el.player.hidden = true;
    el.drop.classList.remove("vid-drop--cheio", "vid-drop--erro");
    el.dropTitulo.textContent = "Selecione o áudio";
    el.dropTexto.textContent = "Prefira o arquivo original: o áudio do WhatsApp baixado direto, sem regravar pelo alto-falante.";
    el.painelEnvio.hidden = false;
    atualizarBotao();
    el.painelEnvio.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  const daUrl = new URLSearchParams(location.search).get("aud_api");
  el.api.value = daUrl || API_PADRAO;
  el.api.addEventListener("change", verificarServidor);
  verificarServidor();
})();
