/* AIDA Video — teste da análise de vídeo na página index-video.html.
 *
 * Fala com o servidor do AIDA Video (aida_video/servidor.py), que roda na
 * máquina de quem testa. A análise de um vídeo leva minutos, então o fluxo é
 * por tarefa: POST /video/analisar devolve um id e a página consulta
 * GET /video/tarefa/<id> a cada segundo, desenhando os frames conforme chegam.
 *
 * Todo texto vindo do servidor entra por textContent: nome de arquivo e
 * motivos nunca são interpretados como HTML.
 */
(function () {
  "use strict";

  // Publicado: o Space aidaon/aida-video (liberado na CSP do vercel.json).
  // Aberto da própria máquina: o servidor local, para testar mudanças.
  const API_SPACE = "https://aidaon-aida-video.hf.space";
  const API_LOCAL = "http://127.0.0.1:7870";
  const EM_LOCALHOST = ["localhost", "127.0.0.1", "[::1]", ""].includes(location.hostname);
  const API_PADRAO = EM_LOCALHOST ? API_LOCAL : API_SPACE;
  const INTERVALO_CONSULTA_MS = 1000;
  const FALHAS_CONSULTA_TOLERADAS = 5;

  const $ = (id) => document.getElementById(id);
  const el = {
    servidor: $("vidServidor"),
    servidorTitulo: $("vidServidorTitulo"),
    servidorTexto: $("vidServidorTexto"),
    form: $("vidForm"),
    drop: $("vidDrop"),
    arquivo: $("vidArquivo"),
    dropTitulo: $("vidDropTitulo"),
    dropTexto: $("vidDropTexto"),
    previa: $("vidPrevia"),
    intervalo: $("vidIntervalo"),
    maxFrames: $("vidMaxFrames"),
    audio: $("vidAudio"),
    api: $("vidApi"),
    enviar: $("vidEnviar"),
    progresso: $("vidProgresso"),
    progressoTitulo: $("vidProgressoTitulo"),
    progressoTexto: $("vidProgressoTexto"),
    barra: $("vidBarra"),
    barraPreenchida: $("vidBarraPreenchida"),
    resultado: $("vidResultado"),
    veredito: $("vidVeredito"),
    vereditoTitulo: $("vidVereditoTitulo"),
    motivos: $("vidMotivos"),
    numeros: $("vidNumeros"),
    linha: $("vidLinha"),
    frames: $("vidFrames"),
    audioResultado: $("vidAudioResultado"),
    ressalva: $("vidRessalva"),
    baixar: $("vidBaixar"),
    novo: $("vidNovo"),
    // Tela no padrão do AIDA Image: o painel de envio sai de cena quando o
    // resultado final chega e volta em "Analisar outro vídeo".
    painelEnvio: $("vidPainelEnvio"),
    significado: $("vidSignificado"),
    verComo: $("vidVerComo"),
    comoFunciona: $("vidComoFunciona"),
  };
  if (!el.form) return;

  const ROTULOS = {
    "REAL": { texto: "Real", classe: "real" },
    "IA/MANIPULADA": { texto: "IA/manipulada", classe: "ia" },
    "INCONCLUSIVO": { texto: "Inconclusivo", classe: "inconclusivo" },
  };

  let servidorOk = false;
  let limiteMb = null; // informado por /video/saude
  let arquivoAtual = null;
  let urlPrevia = null;
  let tarefaAtual = null;
  let relatorioAtual = null;
  let consulta = null;
  let novaTentativa = null;

  // ------------------------------------------------------------------ util

  function baseApi() {
    return (el.api.value.trim() || API_PADRAO).replace(/\/+$/, "");
  }

  function lerPreferencia(chave) {
    try { return localStorage.getItem(chave); } catch (_) { return null; }
  }

  function gravarPreferencia(chave, valor) {
    try { localStorage.setItem(chave, valor); } catch (_) { /* modo privado */ }
  }

  function criar(tag, classe, texto) {
    const no = document.createElement(tag);
    if (classe) no.className = classe;
    if (texto !== undefined && texto !== null) no.textContent = texto;
    return no;
  }

  function porcentagem(valor) {
    return typeof valor === "number" ? `${Math.round(valor * 100)}%` : "—";
  }

  function tempo(segundos) {
    if (typeof segundos !== "number") return "—";
    const m = Math.floor(segundos / 60);
    const s = (segundos % 60).toFixed(1).padStart(4, "0");
    return m ? `${m}:${s}` : `${segundos.toFixed(1)} s`;
  }

  function classeFrame(frame) {
    if (frame.erro || frame.fora_de_dominio) return "neutro";
    return (ROTULOS[frame.resultado] || ROTULOS.INCONCLUSIVO).classe;
  }

  function rotuloFrame(frame) {
    if (frame.erro) return "Erro";
    if (frame.fora_de_dominio) return "Fora de domínio";
    return (ROTULOS[frame.resultado] || ROTULOS.INCONCLUSIVO).texto;
  }

  function definirEstado(no, tipo) {
    no.className = `aida-state aida-state--${tipo}`;
  }

  async function lerJson(resposta) {
    try { return await resposta.json(); } catch (_) { return {}; }
  }

  // ------------------------------------------------------------------ servidor

  async function verificarServidor() {
    clearTimeout(novaTentativa);
    definirEstado(el.servidor, "carregando");
    el.servidorTitulo.textContent = "Procurando o servidor de vídeo…";
    el.servidorTexto.textContent = baseApi();
    try {
      const resposta = await fetch(`${baseApi()}/video/saude`, { cache: "no-store" });
      if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
      const saude = await resposta.json();
      servidorOk = true;
      definirEstado(el.servidor, "sucesso");
      el.servidorTitulo.textContent = "Servidor pronto para analisar";
      const recursos = ["imagem"];
      if (saude.trajetoria_disponivel) recursos.push("movimento");
      if (saude.modelo_audio_disponivel) recursos.push("áudio");
      el.servidorTexto.textContent =
        `Até ${saude.tamanho_max_mb >= 1024 ? formatarTamanho(saude.tamanho_max_mb * 1024 * 1024) : Math.round(saude.tamanho_max_mb || 0) + " MB"} por vídeo · leituras ativas: ` +
        recursos.join(", ") + ".";
      el.servidor.title =
        `Core: ${saude.core_url} · áudio: ${saude.modelo_audio_disponivel ? "modelo treinado" : "sem modelo"}` +
        ` · movimento: ${saude.trajetoria_disponivel ? "ativo" : "desligado"}`;
      if (saude.max_frames) el.maxFrames.max = saude.max_frames;
      limiteMb = saude.tamanho_max_mb || null;
      if (arquivoAtual) escolherArquivo(arquivoAtual); // reavalia o tamanho
    } catch (_) {
      servidorOk = false;
      definirEstado(el.servidor, "indisponivel");
      el.servidorTexto.textContent = "";
      if (baseApi() === API_SPACE) {
        // O Space hiberna sem uso e leva alguns minutos para acordar.
        el.servidorTitulo.textContent = "Servidor de vídeo iniciando";
        el.servidorTexto.append(
          "O servidor pode estar acordando depois de um tempo sem uso. Tentando de novo em 20 segundos…"
        );
        novaTentativa = setTimeout(verificarServidor, 20000);
      } else {
        el.servidorTitulo.textContent = "Servidor de vídeo não encontrado";
        el.servidorTexto.append(
          "Na pasta AIDA.ON, rode ",
          criar("code", null, "python -m aida_video.servidor"),
          ` e recarregue a página. Endereço procurado: ${baseApi()}.`
        );
      }
    }
    atualizarBotao();
  }

  function grandeDemais(arquivo) {
    return Boolean(limiteMb && arquivo && arquivo.size > limiteMb * 1024 * 1024);
  }

  function formatarTamanho(bytes) {
    const mb = bytes / (1024 * 1024);
    return mb >= 1024 ? `${(mb / 1024).toFixed(2)} GB` : `${mb.toFixed(1)} MB`;
  }

  function atualizarBotao() {
    el.enviar.disabled = !(servidorOk && arquivoAtual && !tarefaAtual && !grandeDemais(arquivoAtual));
  }

  // ------------------------------------------------------------------ arquivo

  function escolherArquivo(arquivo) {
    if (!arquivo) return;
    arquivoAtual = arquivo;
    el.dropTitulo.textContent = arquivo.name;
    // Checa antes de enviar: o servidor recusaria só depois de receber o
    // arquivo inteiro, e o navegador costuma mostrar isso como falha de rede.
    const excede = grandeDemais(arquivo);
    el.dropTexto.textContent = excede
      ? `${formatarTamanho(arquivo.size)} · passa do limite de ${formatarTamanho(limiteMb * 1024 * 1024)} do servidor. ` +
        (EM_LOCALHOST ? "Corte o vídeo ou aumente AIDA_VIDEO_MAX_MB ao iniciar o servidor." : "Corte o vídeo e envie de novo.")
      : `${formatarTamanho(arquivo.size)} · clique para trocar`;
    el.drop.classList.add("vid-drop--cheio");
    el.drop.classList.toggle("vid-drop--erro", excede);
    if (urlPrevia) URL.revokeObjectURL(urlPrevia);
    urlPrevia = URL.createObjectURL(arquivo);
    el.previa.src = urlPrevia;
    el.previa.hidden = false;
    atualizarBotao();
  }

  el.arquivo.addEventListener("change", () => escolherArquivo(el.arquivo.files[0]));

  ["dragenter", "dragover"].forEach((evento) =>
    el.drop.addEventListener(evento, (e) => {
      e.preventDefault();
      el.drop.classList.add("vid-drop--sobre");
    })
  );
  ["dragleave", "drop"].forEach((evento) =>
    el.drop.addEventListener(evento, (e) => {
      e.preventDefault();
      el.drop.classList.remove("vid-drop--sobre");
    })
  );
  el.drop.addEventListener("drop", (e) => {
    const arquivo = e.dataTransfer && e.dataTransfer.files[0];
    if (arquivo) escolherArquivo(arquivo);
  });

  // ------------------------------------------------------------------ envio e consulta

  function mostrarProgresso(titulo, texto, fracao) {
    el.progresso.hidden = false;
    el.progressoTitulo.textContent = titulo;
    el.progressoTexto.textContent = texto || "";
    const pct = Math.round(Math.max(0, Math.min(1, fracao || 0)) * 100);
    el.barraPreenchida.style.width = `${pct}%`;
    el.barra.setAttribute("aria-valuenow", String(pct));
  }

  function mostrarErro(mensagem) {
    pararConsulta();
    tarefaAtual = null;
    el.progresso.hidden = true;
    el.resultado.hidden = false;
    definirEstado(el.veredito, "erro");
    el.vereditoTitulo.textContent = "Não foi possível analisar o vídeo";
    if (el.significado) el.significado.textContent = "";
    el.motivos.replaceChildren(criar("li", null, mensagem));
    [el.numeros, el.linha, el.frames, el.audioResultado].forEach((n) => n.replaceChildren());
    el.ressalva.textContent = "";
    el.baixar.hidden = true;
    atualizarBotao();
  }

  // fetch() não informa o progresso do upload; com vídeo de 1 GB a página
  // ficaria parada em "Enviando…" por minutos. XMLHttpRequest informa.
  function enviarComProgresso(url, dados, aoProgredir) {
    return new Promise((resolver, rejeitar) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url);
      xhr.responseType = "text";
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) aoProgredir(e.loaded, e.total);
      };
      xhr.onload = () => {
        let corpo = {};
        try { corpo = JSON.parse(xhr.responseText || "{}"); } catch (_) { /* corpo não-JSON */ }
        resolver({ status: xhr.status, corpo });
      };
      xhr.onerror = () => rejeitar(new Error("falha de rede"));
      xhr.onabort = () => rejeitar(new Error("envio cancelado"));
      xhr.send(dados);
    });
  }

  function pararConsulta() {
    if (consulta) clearTimeout(consulta);
    consulta = null;
  }

  el.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!arquivoAtual || !servidorOk || tarefaAtual) return;

    const dados = new FormData();
    dados.append("video", arquivoAtual, arquivoAtual.name);
    dados.append("intervalo_s", el.intervalo.value);
    dados.append("max_frames", el.maxFrames.value || "40");
    dados.append("audio", el.audio.checked ? "true" : "false");

    tarefaAtual = "enviando";
    relatorioAtual = null;
    atualizarBotao();
    el.resultado.hidden = true;
    [el.linha, el.frames].forEach((n) => n.replaceChildren());
    mostrarProgresso("Enviando o vídeo…", arquivoAtual.name, 0);

    let resposta;
    try {
      resposta = await enviarComProgresso(`${baseApi()}/video/analisar`, dados, (enviados, total) => {
        mostrarProgresso(
          `Enviando o vídeo… ${Math.round((enviados / total) * 100)}%`,
          `${formatarTamanho(enviados)} de ${formatarTamanho(total)}`,
          0.02 * (enviados / total)
        );
      });
    } catch (_) {
      mostrarErro(
        "O envio foi interrompido. Confira se o servidor de vídeo continua rodando" +
        (limiteMb ? ` e se o arquivo tem menos de ${formatarTamanho(limiteMb * 1024 * 1024)}.` : ".")
      );
      return;
    }
    const corpo = resposta.corpo;
    if (resposta.status !== 202 || !corpo.tarefa) {
      mostrarErro(corpo.erro || `O servidor recusou o envio (HTTP ${resposta.status}).`);
      return;
    }
    tarefaAtual = corpo.tarefa;
    mostrarProgresso("Extraindo frames…", "Separando os quadros e detectando cortes de cena.", 0.02);
    consultar(0);
  });

  async function consultar(falhas) {
    const id = tarefaAtual;
    let tarefa;
    try {
      const resposta = await fetch(`${baseApi()}/video/tarefa/${encodeURIComponent(id)}`, { cache: "no-store" });
      tarefa = await lerJson(resposta);
      if (!resposta.ok) throw new Error(tarefa.erro || `HTTP ${resposta.status}`);
    } catch (erro) {
      if (falhas + 1 >= FALHAS_CONSULTA_TOLERADAS) {
        mostrarErro(`Perdi o contato com o servidor de vídeo (${erro.message}).`);
        return;
      }
      consulta = setTimeout(() => consultar(falhas + 1), INTERVALO_CONSULTA_MS * 2);
      return;
    }
    if (id !== tarefaAtual) return; // o usuário já começou outra análise

    if (tarefa.estado === "erro") {
      mostrarErro(tarefa.erro || "Falha na análise.");
      return;
    }
    if (tarefa.estado === "concluida") {
      tarefaAtual = null;
      el.progresso.hidden = true;
      mostrarRelatorio(tarefa.relatorio, id);
      atualizarBotao();
      return;
    }

    const { feitos, total } = tarefa.progresso || {};
    if (total) {
      mostrarProgresso(
        `Analisando frames no AIDA Core… ${feitos} de ${total}`,
        "Os frames aparecem abaixo conforme o Core responde.",
        0.05 + 0.9 * (feitos / total)
      );
      desenharLinha(tarefa.frames, id);
      desenharFrames(tarefa.frames, id);
      el.resultado.hidden = false;
      definirEstado(el.veredito, "analisando");
      el.vereditoTitulo.textContent = "Análise em andamento";
      if (el.significado) el.significado.textContent = "Os quadros aparecem abaixo conforme são analisados.";
      el.motivos.replaceChildren();
      el.numeros.replaceChildren();
      el.audioResultado.textContent = "O áudio é analisado depois dos frames.";
      el.ressalva.textContent = "";
      el.baixar.hidden = true;
    }
    consulta = setTimeout(() => consultar(0), INTERVALO_CONSULTA_MS);
  }

  // ------------------------------------------------------------------ resultado

  function urlFrame(id, arquivo) {
    return `${baseApi()}/video/tarefa/${encodeURIComponent(id)}/frame/${encodeURIComponent(arquivo)}`;
  }

  function desenharLinha(frames, id) {
    el.linha.replaceChildren();
    if (!frames.length) return;
    const duracao = (relatorioAtual && relatorioAtual.metadados.duracao_s) ||
      Math.max(...frames.map((f) => f.tempo_s)) + 1;
    frames.forEach((frame, i) => {
      const proximo = frames[i + 1] ? frames[i + 1].tempo_s : duracao;
      const bloco = criar("button", `vid-linha__seg vid-cor--${classeFrame(frame)}`);
      bloco.type = "button";
      bloco.style.left = `${(frame.tempo_s / duracao) * 100}%`;
      bloco.style.width = `${Math.max(((proximo - frame.tempo_s) / duracao) * 100, 0.6)}%`;
      bloco.title = `${tempo(frame.tempo_s)} · ${rotuloFrame(frame)}`;
      bloco.setAttribute("aria-label", bloco.title);
      bloco.addEventListener("click", () => {
        const alvo = document.getElementById(`vidFrame-${i}`);
        if (alvo) {
          alvo.scrollIntoView({ behavior: "smooth", block: "nearest" });
          alvo.focus({ preventScroll: true });
        }
        if (!el.previa.hidden) el.previa.currentTime = frame.tempo_s;
      });
      el.linha.append(bloco);
    });
  }

  function desenharFrames(frames, id) {
    const existentes = el.frames.children.length;
    frames.slice(existentes).forEach((frame, j) => {
      const i = existentes + j;
      const cartao = criar("figure", `vid-frame vid-frame--${classeFrame(frame)}`);
      cartao.id = `vidFrame-${i}`;
      cartao.tabIndex = -1;
      const img = criar("img");
      img.src = urlFrame(id, frame.arquivo);
      img.alt = `Frame em ${tempo(frame.tempo_s)}`;
      img.loading = "lazy";
      img.decoding = "async";
      const legenda = criar("figcaption");
      legenda.append(
        criar("span", "vid-frame__tempo", tempo(frame.tempo_s)),
        criar("span", "vid-frame__rotulo", rotuloFrame(frame))
      );
      if (!frame.erro && !frame.fora_de_dominio && typeof frame.probabilidade_ia === "number") {
        legenda.append(criar("span", "vid-frame__prob", `IA ${porcentagem(frame.probabilidade_ia)}`));
      }
      cartao.append(img, legenda);
      if (frame.erro) cartao.title = frame.erro;
      el.frames.append(cartao);
    });
  }

  function numero(rotulo, valor) {
    const par = criar("div", "vid-numero");
    par.append(criar("dt", null, rotulo), criar("dd", null, valor));
    return par;
  }

  function explicarResultado(relatorio) {
    const v = relatorio.visual || {};
    const t = relatorio.trajetoria || {};
    const a = relatorio.audio || {};
    const fontes = [];
    if ((v.resultado_frames || v.resultado) === "IA/MANIPULADA") fontes.push("em vários quadros da imagem");
    if (t.disponivel && typeof t.probabilidade_ia === "number" && t.probabilidade_ia >= 0.65) fontes.push("no movimento da cena");
    if (a.resultado === "IA/MANIPULADA") fontes.push("no áudio");
    const juntar = (itens) => itens.length > 1 ? `${itens.slice(0, -1).join(", ")} e ${itens[itens.length - 1]}` : itens[0];

    if (relatorio.resultado === "IA/MANIPULADA") {
      return fontes.length
        ? `A AIDA encontrou sinais de geração por IA ${juntar(fontes)}. Isso indica que o vídeo, ou parte dele, pode ter sido criado ou alterado por inteligência artificial.`
        : "A AIDA encontrou sinais de geração por IA neste vídeo.";
    }
    if (relatorio.resultado === "REAL") {
      return "Nenhuma das leituras encontrou sinais relevantes de IA: os quadros, o movimento" +
        (a.resultado ? " e o áudio" : "") + " se comportam como os de uma gravação de câmera.";
    }
    return "Os sinais ficaram fracos ou divididos entre as leituras. Em vez de arriscar, a AIDA marcou o vídeo como inconclusivo; veja abaixo em que trechos cada leitura apontou.";
  }

  function mostrarRelatorio(relatorio, id) {
    relatorioAtual = relatorio;
    el.resultado.hidden = false;
    el.baixar.hidden = false;

    const tipo = { "REAL": "sucesso", "IA/MANIPULADA": "erro", "INCONCLUSIVO": "baixa-confianca" }[relatorio.resultado];
    definirEstado(el.veredito, tipo || "baixa-confianca");
    el.vereditoTitulo.textContent = `Resultado do vídeo: ${(ROTULOS[relatorio.resultado] || ROTULOS.INCONCLUSIVO).texto}`;
    if (el.significado) el.significado.textContent = explicarResultado(relatorio);
    el.motivos.replaceChildren(...(relatorio.motivos || []).map((m) => criar("li", null, m)));

    const v = relatorio.visual || {};
    const meta = relatorio.metadados || {};
    const itens = [
      numero("Duração", tempo(meta.duracao_s)),
      numero("Resolução", meta.largura ? `${meta.largura_exibida || meta.largura}×${meta.altura_exibida || meta.altura}` : "—"),
      numero("Frames analisados", `${v.frames_validos ?? 0} de ${v.frames_total ?? 0}`),
    ];
    if (v.contagem) {
      itens.push(
        numero("Real / IA / Inconcl.", `${v.contagem["REAL"]} / ${v.contagem["IA/MANIPULADA"]} / ${v.contagem["INCONCLUSIVO"]}`),
        numero("Prob. IA (mediana)", v.probabilidade_ia ? porcentagem(v.probabilidade_ia.mediana) : "—"),
        numero("Prob. IA (máxima)", v.probabilidade_ia ? porcentagem(v.probabilidade_ia.maxima) : "—")
      );
    }
    const t = relatorio.trajetoria;
    if (t && t.disponivel) {
      itens.push(numero("Movimento (prob. IA)", porcentagem(t.probabilidade_ia)));
    }
    itens.push(numero("Tempo de processamento", `${relatorio.duracao_processamento_s} s`));
    el.numeros.replaceChildren(...itens);

    desenharLinha(relatorio.frames, id);
    el.frames.replaceChildren();
    desenharFrames(relatorio.frames, id);
    (v.trechos_ia || []).forEach((trecho) => {
      el.motivos.append(criar("li", null, `Trecho com indício de IA: ${tempo(trecho.inicio_s)} a ${tempo(trecho.fim_s)} (${trecho.frames} frames)`));
    });

    desenharAudio(relatorio.audio || {});
    el.ressalva.textContent = relatorio.ressalva || "";
    if (el.painelEnvio) el.painelEnvio.hidden = true;
    el.resultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function desenharAudio(audio) {
    el.audioResultado.replaceChildren();
    if (audio.erro) {
      el.audioResultado.append(criar("p", "vid-audio__linha", `Erro ao ler o áudio: ${audio.erro}`));
      return;
    }
    const resultado = audio.resultado ? (ROTULOS[audio.resultado] || ROTULOS.INCONCLUSIVO) : null;
    const cabeca = criar("p", "vid-audio__linha");
    cabeca.append(
      criar("span", `vid-pilula vid-cor--${resultado ? resultado.classe : "neutro"}`, resultado ? resultado.texto : "Não avaliado"),
      typeof audio.probabilidade_ia === "number" ? ` Probabilidade de IA: ${porcentagem(audio.probabilidade_ia)}` : ""
    );
    el.audioResultado.append(cabeca);
    const q = audio.qualidade;
    if (q) {
      el.audioResultado.append(criar(
        "p", "aida-text--sm vid-audio__linha",
        `${q.duracao_s.toFixed(1)} s analisados · ${Math.round(q.fracao_silencio * 100)}% de silêncio` +
        (q.fracao_saturada > 0.01 ? ` · ${Math.round(q.fracao_saturada * 100)}% saturado` : "")
      ));
    }
    const notas = [...(audio.motivos || []), ...(audio.limitacoes || [])];
    if (notas.length) {
      el.audioResultado.append(criar("ul", "vid-motivos"));
      notas.forEach((n) => el.audioResultado.lastChild.append(criar("li", null, n)));
    }
  }

  // ------------------------------------------------------------------ ações

  el.baixar.addEventListener("click", () => {
    if (!relatorioAtual) return;
    const blob = new Blob([JSON.stringify(relatorioAtual, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `aida-video-${(relatorioAtual.video || "relatorio").replace(/\.[^.]+$/, "")}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });

  el.novo.addEventListener("click", () => {
    pararConsulta();
    tarefaAtual = null;
    relatorioAtual = null;
    el.resultado.hidden = true;
    el.arquivo.value = "";
    arquivoAtual = null;
    el.drop.classList.remove("vid-drop--cheio", "vid-drop--erro");
    el.dropTitulo.textContent = "Selecione seu vídeo";
    el.dropTexto.textContent = "Escolha um arquivo do seu celular ou arraste o vídeo para cá, se estiver no computador.";
    el.previa.hidden = true;
    el.previa.removeAttribute("src");
    if (el.painelEnvio) el.painelEnvio.hidden = false;
    atualizarBotao();
    (el.painelEnvio || el.form).scrollIntoView({ behavior: "smooth", block: "start" });
  });

  if (el.verComo) {
    el.verComo.addEventListener("click", (e) => {
      e.preventDefault();
      if (el.painelEnvio) el.painelEnvio.hidden = false;
      if (el.comoFunciona) {
        el.comoFunciona.open = true;
        el.comoFunciona.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }

  // ?video_api=http://host:porta sobrepõe o endereço (e fica lembrado).
  const daUrl = new URLSearchParams(location.search).get("video_api");
  // Um endereço local lembrado de testes antigos não vale no site publicado.
  const lembrado = lerPreferencia("AIDA_VideoApi");
  const lembradoUtil = lembrado && (EM_LOCALHOST || !/\/\/(127\.0\.0\.1|localhost)[:/]/.test(lembrado));
  el.api.value = daUrl || (lembradoUtil ? lembrado : "") || API_PADRAO;
  el.api.addEventListener("change", () => {
    gravarPreferencia("AIDA_VideoApi", baseApi());
    verificarServidor();
  });

  verificarServidor();
})();
