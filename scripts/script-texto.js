/* AIDA Documents · texto — detecção de texto gerado por IA (index-texto.html).
 *
 * Fala com o mesmo servidor do AIDA Video e do AIDA Documents (Space
 * aidaon/aida-video, ou o servidor local na porta 7870):
 *
 *   GET  /documento/texto/saude
 *   POST /documento/texto/analisar     -> 202 {tarefa}
 *   GET  /documento/texto/tarefa/<id>  -> estado, progresso e relatório
 *
 * Um documento longo leva de segundos a minutos, então a página acompanha a
 * tarefa de segundo em segundo.
 *
 * Todo texto vindo do servidor entra por textContent: nome de arquivo, motivos
 * e os trechos do documento nunca são interpretados como HTML.
 */
(function () {
  "use strict";

  const API_SPACE = "https://aidaon-aida-video.hf.space";
  const API_LOCAL = "http://127.0.0.1:7870";
  const EM_LOCALHOST = ["localhost", "127.0.0.1", "[::1]", ""].includes(location.hostname);
  const API_PADRAO = EM_LOCALHOST ? API_LOCAL : API_SPACE;
  const INTERVALO_MS = 1000;
  const EXTENSOES_PADRAO = [".pdf", ".docx", ".txt", ".md"];

  const $ = (id) => document.getElementById(id);
  const el = {
    servidor: $("txtServidor"),
    servidorTitulo: $("txtServidorTitulo"),
    servidorTexto: $("txtServidorTexto"),
    form: $("txtForm"),
    drop: $("txtDrop"),
    arquivo: $("txtArquivo"),
    dropTitulo: $("txtDropTitulo"),
    dropTexto: $("txtDropTexto"),
    formatos: $("txtFormatos"),
    api: $("txtApi"),
    enviar: $("txtEnviar"),
    progresso: $("txtProgresso"),
    progressoTitulo: $("txtProgressoTitulo"),
    progressoTexto: $("txtProgressoTexto"),
    barra: $("txtBarra"),
    barraPreenchida: $("txtBarraPreenchida"),
    painelEnvio: $("txtPainelEnvio"),
    resultado: $("txtResultado"),
    veredito: $("txtVeredito"),
    vereditoTitulo: $("txtVereditoTitulo"),
    significado: $("txtSignificado"),
    motivos: $("txtMotivos"),
    numeros: $("txtNumeros"),
    trechosBloco: $("txtTrechosBloco"),
    trechosAjuda: $("txtTrechosAjuda"),
    mapa: $("txtMapa"),
    soSuspeitos: $("txtSoSuspeitos"),
    trechos: $("txtTrechos"),
    limpeza: $("txtLimpeza"),
    limpezaBloco: $("txtLimpezaBloco"),
    limites: $("txtLimites"),
    limitesBloco: $("txtLimitesBloco"),
    ressalva: $("txtRessalva"),
    baixar: $("txtBaixar"),
    novo: $("txtNovo"),
    verComo: $("txtVerComo"),
    comoFunciona: $("txtComoFunciona"),
  };
  if (!el.form) return;

  const ROTULOS = {
    "HUMANO": { texto: "Sem sinal de texto gerado por IA", estado: "sucesso" },
    "IA": { texto: "Sinal forte de texto gerado por IA", estado: "erro" },
    "INCONCLUSIVO": { texto: "Inconclusivo", estado: "baixa-confianca" },
  };
  const NIVEIS = { alto: "sinal forte", medio: "sinal moderado", baixo: "sem sinal" };
  const IDIOMAS = { pt: "Português", en: "Inglês" };
  const TEXTO_DROP = "Funciona melhor com pelo menos uma página de texto corrido, em português ou inglês.";

  let servidorOk = false;
  let limiteMb = 20;
  let extensoes = EXTENSOES_PADRAO;
  let arquivoAtual = null;
  let relatorioAtual = null;
  let enviando = false;
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

  function decimal(valor, casas) {
    return typeof valor === "number" ? valor.toLocaleString("pt-BR", { maximumFractionDigits: casas }) : "—";
  }

  function definirEstado(no, tipo) {
    no.className = `aida-state aida-state--${tipo}`;
  }

  function formatarTamanho(bytes) {
    const mb = bytes / (1024 * 1024);
    return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  const esperar = (ms) => new Promise((resolver) => setTimeout(resolver, ms));

  // ------------------------------------------------------------------ servidor

  async function verificarServidor() {
    clearTimeout(novaTentativa);
    definirEstado(el.servidor, "carregando");
    el.servidorTitulo.textContent = "Procurando o servidor…";
    el.servidorTexto.textContent = baseApi();
    try {
      const resposta = await fetch(`${baseApi()}/documento/texto/saude`, { cache: "no-store" });
      if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
      const saude = await resposta.json();
      servidorOk = true;
      limiteMb = saude.tamanho_max_mb || limiteMb;
      extensoes = saude.extensoes || extensoes;
      const calibrados = Object.entries(saude.idiomas || {}).filter(([, i]) => i.calibrado).map(([i]) => IDIOMAS[i] || i);
      if (!saude.modelo_de_linguagem) {
        definirEstado(el.servidor, "baixa-confianca");
        el.servidorTitulo.textContent = "Servidor sem o modelo de linguagem";
        el.servidorTexto.textContent = "A leitura e a limpeza funcionam, mas sem o modelo o resultado será sempre inconclusivo.";
      } else if (!calibrados.length) {
        definirEstado(el.servidor, "baixa-confianca");
        el.servidorTitulo.textContent = "Servidor pronto, detector ainda sem calibração";
        el.servidorTexto.textContent = "A análise mostra o indicador e os trechos, mas o resultado final fica inconclusivo até a calibração.";
      } else {
        definirEstado(el.servidor, "sucesso");
        el.servidorTitulo.textContent = "Servidor pronto para analisar";
        el.servidorTexto.textContent = `Calibrado para: ${calibrados.join(" e ")}. Arquivos de até ${limiteMb} MB.`;
      }
      if (arquivoAtual) escolherArquivo(arquivoAtual);
    } catch (_) {
      servidorOk = false;
      definirEstado(el.servidor, "indisponivel");
      el.servidorTexto.textContent = "";
      if (baseApi() === API_SPACE) {
        el.servidorTitulo.textContent = "Servidor iniciando";
        el.servidorTexto.append("O servidor pode estar acordando depois de um tempo sem uso. Tentando de novo em 20 segundos…");
        novaTentativa = setTimeout(verificarServidor, 20000);
      } else {
        el.servidorTitulo.textContent = "Servidor não encontrado";
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
    return Boolean(arquivo && arquivo.size > limiteMb * 1024 * 1024);
  }

  function formatoAceito(arquivo) {
    const nome = arquivo.name.toLowerCase();
    return extensoes.some((ext) => nome.endsWith(ext));
  }

  function atualizarBotao() {
    el.enviar.disabled = !(servidorOk && arquivoAtual && !enviando && formatoAceito(arquivoAtual) && !grandeDemais(arquivoAtual));
  }

  // ------------------------------------------------------------------ arquivo

  function escolherArquivo(arquivo) {
    if (!arquivo) return;
    arquivoAtual = arquivo;
    el.dropTitulo.textContent = arquivo.name;
    let problema = "";
    if (/\.doc$/i.test(arquivo.name)) problema = "arquivo .doc (Word antigo): salve como .docx ou PDF.";
    else if (!formatoAceito(arquivo)) problema = "formato não aceito. Envie PDF, DOCX ou TXT.";
    else if (grandeDemais(arquivo)) problema = `passa do limite de ${limiteMb} MB.`;
    el.dropTexto.textContent = `${formatarTamanho(arquivo.size)} · ${problema || "clique para trocar"}`;
    el.drop.classList.add("vid-drop--cheio");
    el.drop.classList.toggle("vid-drop--erro", Boolean(problema));
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

  // ------------------------------------------------------------------ envio

  function mostrarProgresso(titulo, texto, fracao) {
    el.progressoTitulo.textContent = titulo;
    el.progressoTexto.textContent = texto || "";
    const valor = Math.round((fracao || 0) * 100);
    el.barraPreenchida.style.width = `${valor}%`;
    el.barra.setAttribute("aria-valuenow", String(valor));
  }

  async function lerJson(resposta) {
    let corpo = {};
    try { corpo = await resposta.json(); } catch (_) { /* resposta sem JSON */ }
    if (!resposta.ok) throw new Error(corpo.erro || `O servidor respondeu com erro (HTTP ${resposta.status}).`);
    return corpo;
  }

  async function acompanhar(id) {
    for (;;) {
      const tarefa = await lerJson(await fetch(`${baseApi()}/documento/texto/tarefa/${id}`, { cache: "no-store" }));
      if (tarefa.estado === "concluida") return tarefa.relatorio;
      if (tarefa.estado === "erro") throw new Error(tarefa.erro || "A análise falhou.");
      const { feitos, total } = tarefa.progresso || {};
      if (tarefa.estado === "fila") {
        mostrarProgresso("Na fila…", "O servidor analisa um documento por vez.", 0);
      } else if (total) {
        mostrarProgresso("Medindo o texto…", `Trecho ${feitos} de ${total}.`, feitos / total);
      } else {
        mostrarProgresso("Lendo o documento…", "Extraindo o texto e carregando o modelo de linguagem.", 0.03);
      }
      await esperar(INTERVALO_MS);
    }
  }

  el.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (el.enviar.disabled) return;
    enviando = true;
    atualizarBotao();
    el.progresso.hidden = false;
    mostrarProgresso("Enviando o documento…", arquivoAtual.name, 0);
    const dados = new FormData();
    dados.append("documento", arquivoAtual, arquivoAtual.name);
    try {
      const { tarefa } = await lerJson(await fetch(`${baseApi()}/documento/texto/analisar`, { method: "POST", body: dados }));
      mostrarRelatorio(await acompanhar(tarefa));
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
    el.vereditoTitulo.textContent = "Não foi possível analisar o documento";
    el.significado.textContent = "";
    el.motivos.replaceChildren(criar("li", null, mensagem));
    [el.numeros, el.mapa, el.trechos, el.limpeza, el.limites].forEach((n) => n.replaceChildren());
    [el.trechosBloco, el.limpezaBloco, el.limitesBloco].forEach((n) => { n.hidden = true; });
    el.ressalva.textContent = "";
    el.baixar.hidden = true;
    el.resultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ------------------------------------------------------------------ resultado

  function explicarResultado(r) {
    if (r.resultado === "IA") {
      return `O texto é previsível e regular como um texto gerado por IA: ${porcentagem(r.fracao_suspeita)} das palavras estão em trechos com sinal forte. Isso é um indício estatístico, não uma prova de autoria: converse com o autor antes de concluir.`;
    }
    if (r.resultado === "HUMANO") {
      return "O texto varia de ritmo e de vocabulário como um texto escrito por uma pessoa, e nenhum trecho relevante mostrou sinal de IA. Um texto de IA bastante reescrito também pode chegar a este resultado.";
    }
    if (typeof r.probabilidade_ia !== "number") {
      return "Não houve material suficiente para medir. Veja o motivo abaixo.";
    }
    if (!r.calibrado) {
      return "A AIDA mediu o texto e mostra abaixo o indicador e os trechos, mas este detector ainda não tem taxa de erro medida. Por isso o resultado não aponta nem para um lado nem para o outro.";
    }
    return "O sinal não foi forte o bastante para apontar IA nem fraco o bastante para descartar. Veja abaixo quais trechos chamaram atenção.";
  }

  function numero(rotulo, valor) {
    const par = criar("div", "vid-numero");
    par.append(criar("dt", null, rotulo), criar("dd", null, valor));
    return par;
  }

  function focarTrecho(indice) {
    el.soSuspeitos.checked = false;
    el.trechos.classList.remove("txt-trechos--so-suspeitos");
    const alvo = el.trechos.querySelector(`[data-indice="${indice}"]`);
    if (!alvo) return;
    el.trechos.querySelectorAll(".txt-trecho--foco").forEach((n) => n.classList.remove("txt-trecho--foco"));
    alvo.classList.add("txt-trecho--foco");
    alvo.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function desenharTrechos(r) {
    const segmentos = r.segmentos || [];
    el.trechosBloco.hidden = !segmentos.length;
    el.mapa.replaceChildren();
    el.trechos.replaceChildren();
    if (!segmentos.length) return;

    const comSinal = segmentos.filter((s) => s.nivel !== "baixo").length;
    el.trechosAjuda.textContent =
      `${segmentos.length} trechos de cerca de 120 palavras, na ordem do documento; ${comSinal} com sinal. ` +
      (r.calibrado
        ? "A porcentagem é a estimativa de cada trecho. Clique num bloco da faixa para ir até ele."
        : "A porcentagem é um indicador ainda não calibrado. Clique num bloco da faixa para ir até o trecho.");

    segmentos.forEach((s) => {
      const rotulo = `Trecho ${s.indice + 1}${s.pagina ? `, página ${s.pagina}` : ""}: ${porcentagem(s.probabilidade)}, ${NIVEIS[s.nivel]}`;
      const bloco = criar("button", `txt-mapa__bloco txt-cor--${s.nivel}`);
      bloco.type = "button";
      bloco.style.setProperty("--_peso", String(s.palavras || 1));
      bloco.title = rotulo;
      bloco.setAttribute("aria-label", rotulo);
      bloco.addEventListener("click", () => focarTrecho(s.indice));
      el.mapa.append(bloco);

      const item = criar("li", `txt-trecho txt-cor--${s.nivel}`);
      item.dataset.indice = String(s.indice);
      const lado = criar("div", "txt-trecho__lado");
      lado.append(
        criar("span", "txt-trecho__valor", porcentagem(s.probabilidade)),
        criar("span", "txt-trecho__rotulo", NIVEIS[s.nivel]),
        criar("span", "txt-trecho__pagina", r.formato === "pdf" && s.pagina ? `pág. ${s.pagina}` : `trecho ${s.indice + 1}`)
      );
      const m = s.medidas || {};
      const medidas = [
        typeof m.log_ppl === "number" ? `perplexidade ${decimal(Math.exp(m.log_ppl), 1)}` : null,
        typeof m.burst_frases === "number" ? `variação das frases ${decimal(m.burst_frases, 2)}` : null,
        Object.keys(m.marcadores || {}).length ? `marcadores: ${Object.keys(m.marcadores).join(", ")}` : null,
      ].filter(Boolean);
      item.append(lado, criar("p", "txt-trecho__texto", s.texto), criar("p", "txt-trecho__medidas", medidas.join(" · ")));
      el.trechos.append(item);
    });
    el.trechos.append(criar("li", "txt-trechos__vazio", "Fim do texto analisado."));
  }

  function mostrarRelatorio(r) {
    relatorioAtual = r;
    const rotulo = ROTULOS[r.resultado] || ROTULOS.INCONCLUSIVO;
    el.resultado.hidden = false;
    el.baixar.hidden = false;
    definirEstado(el.veredito, rotulo.estado);
    el.vereditoTitulo.textContent = `Resultado: ${rotulo.texto}`;
    el.significado.textContent = explicarResultado(r);
    el.motivos.replaceChildren(...(r.motivos || []).map((m) => criar("li", null, m)));

    const m = r.medidas || {};
    el.numeros.replaceChildren(
      numero(r.calibrado ? "Probabilidade de IA" : "Indicador (não calibrado)", porcentagem(r.probabilidade_ia)),
      numero("Texto em trechos com sinal forte", porcentagem(r.fracao_suspeita)),
      numero("Idioma", IDIOMAS[r.idioma] || "não reconhecido"),
      numero("Palavras analisadas", (r.palavras ?? 0).toLocaleString("pt-BR")),
      numero("Perplexidade média", decimal(m.perplexidade, 1)),
      numero("Variação das frases", decimal(m.burst_frases, 2)),
      numero("Palavras por frase", decimal(m.palavras_por_frase, 1)),
    );

    desenharTrechos(r);

    const l = r.limpeza || {};
    const removidos = [
      l.cabecalho_rodape ? `${l.cabecalho_rodape} linha(s) de cabeçalho ou rodapé repetido` : null,
      l.numero_pagina ? `${l.numero_pagina} número(s) de página` : null,
      l.nao_prosa ? `${l.nao_prosa} bloco(s) que não são texto corrido (títulos, sumário, legendas, tabelas)` : null,
      l.referencias ? `a lista de referências (${l.referencias} bloco(s))` : null,
    ].filter(Boolean);
    el.limpeza.replaceChildren(...removidos.map((t) => criar("li", null, t)));
    el.limpezaBloco.hidden = !removidos.length;

    const limites = r.limitacoes || [];
    el.limites.replaceChildren(...limites.map((t) => criar("li", null, t)));
    el.limitesBloco.hidden = !limites.length;
    el.ressalva.textContent = r.ressalva || "";
    el.painelEnvio.hidden = true;
    el.resultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ------------------------------------------------------------------ ações

  el.soSuspeitos.addEventListener("change", () => {
    el.trechos.classList.toggle("txt-trechos--so-suspeitos", el.soSuspeitos.checked);
  });

  el.baixar.addEventListener("click", () => {
    if (!relatorioAtual) return;
    const blob = new Blob([JSON.stringify(relatorioAtual, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `aida-texto-${(relatorioAtual.documento || "relatorio").replace(/\.[^.]+$/, "")}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });

  el.novo.addEventListener("click", () => {
    relatorioAtual = null;
    el.resultado.hidden = true;
    el.arquivo.value = "";
    arquivoAtual = null;
    el.drop.classList.remove("vid-drop--cheio", "vid-drop--erro");
    el.dropTitulo.textContent = "Arraste o documento ou selecione";
    el.dropTexto.textContent = TEXTO_DROP;
    el.soSuspeitos.checked = false;
    el.trechos.classList.remove("txt-trechos--so-suspeitos");
    el.painelEnvio.hidden = false;
    atualizarBotao();
    el.painelEnvio.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  el.verComo.addEventListener("click", (e) => {
    e.preventDefault();
    el.painelEnvio.hidden = false;
    el.comoFunciona.open = true;
    el.comoFunciona.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  // ?doc_api=http://host:porta sobrepõe o endereço (e fica lembrado), como na página de PDF.
  const daUrl = new URLSearchParams(location.search).get("doc_api");
  const lembrado = lerPreferencia("AIDA_DocApi");
  const lembradoUtil = lembrado && (EM_LOCALHOST || !/\/\/(127\.0\.0\.1|localhost)[:/]/.test(lembrado));
  el.api.value = daUrl || (lembradoUtil ? lembrado : "") || API_PADRAO;
  el.api.addEventListener("change", () => {
    gravarPreferencia("AIDA_DocApi", baseApi());
    verificarServidor();
  });

  verificarServidor();
})();
