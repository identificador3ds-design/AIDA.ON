/* AIDA Documents — análise de documento (PDF, DOCX, DOC, TXT) na página index-documentos.html.
 *
 * Fala com o mesmo servidor do AIDA Video (Space aidaon/aida-video, ou o
 * servidor local na porta 7870), nas rotas /documento/saude e
 * /documento/analisar. A análise leva menos de um segundo, então a resposta
 * vem direto no POST, sem tarefa.
 *
 * Todo texto vindo do servidor entra por textContent: nome de arquivo e
 * motivos nunca são interpretados como HTML.
 */
(function () {
  "use strict";

  const API_SPACE = "https://aidaon-aida-video.hf.space";
  const API_LOCAL = "http://127.0.0.1:7870";
  const EM_LOCALHOST = ["localhost", "127.0.0.1", "[::1]", ""].includes(location.hostname);
  const API_PADRAO = EM_LOCALHOST ? API_LOCAL : API_SPACE;

  const $ = (id) => document.getElementById(id);
  const el = {
    servidor: $("docServidor"),
    servidorTitulo: $("docServidorTitulo"),
    servidorTexto: $("docServidorTexto"),
    form: $("docForm"),
    drop: $("docDrop"),
    arquivo: $("docArquivo"),
    dropTitulo: $("docDropTitulo"),
    dropTexto: $("docDropTexto"),
    api: $("docApi"),
    enviar: $("docEnviar"),
    progresso: $("docProgresso"),
    painelEnvio: $("docPainelEnvio"),
    resultado: $("docResultado"),
    veredito: $("docVeredito"),
    vereditoTitulo: $("docVereditoTitulo"),
    significado: $("docSignificado"),
    motivos: $("docMotivos"),
    numeros: $("docNumeros"),
    indicios: $("docIndicios"),
    benford: $("docBenford"),
    benfordAjuda: $("docBenfordAjuda"),
    limites: $("docLimites"),
    limitesBloco: $("docLimitesBloco"),
    ressalva: $("docRessalva"),
    baixar: $("docBaixar"),
    novo: $("docNovo"),
    verComo: $("docVerComo"),
    comoFunciona: $("docComoFunciona"),
  };
  if (!el.form) return;

  const ROTULOS = {
    "REAL": { texto: "Sem indícios de manipulação", curto: "Real", estado: "sucesso" },
    "IA/MANIPULADA": { texto: "Indícios de manipulação", curto: "IA/manipulada", estado: "erro" },
    "INCONCLUSIVO": { texto: "Inconclusivo", curto: "Inconclusivo", estado: "baixa-confianca" },
  };
  const FORCA = (peso) => (peso >= 0.5 ? "forte" : peso >= 0.25 ? "médio" : "fraco");
  const DIGITOS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];

  let servidorOk = false;
  let limiteMb = 20;
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

  function definirEstado(no, tipo) {
    no.className = `aida-state aida-state--${tipo}`;
  }

  function formatarTamanho(bytes) {
    const mb = bytes / (1024 * 1024);
    return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  function data(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleDateString("pt-BR");
  }

  // ------------------------------------------------------------------ servidor

  async function verificarServidor() {
    clearTimeout(novaTentativa);
    definirEstado(el.servidor, "carregando");
    el.servidorTitulo.textContent = "Procurando o servidor…";
    el.servidorTexto.textContent = baseApi();
    try {
      const resposta = await fetch(`${baseApi()}/documento/saude`, { cache: "no-store" });
      if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
      const saude = await resposta.json();
      servidorOk = true;
      limiteMb = saude.tamanho_max_mb || limiteMb;
      definirEstado(el.servidor, "sucesso");
      el.servidorTitulo.textContent = "Servidor pronto para analisar";
      el.servidorTexto.textContent = `PDF de até ${limiteMb} MB.`;
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

  function ehDocumento(arquivo) {
    return /\.(pdf|docx|doc|txt)$/i.test(arquivo.name);
  }

  function atualizarBotao() {
    el.enviar.disabled = !(servidorOk && arquivoAtual && !enviando && ehDocumento(arquivoAtual) && !grandeDemais(arquivoAtual));
  }

  // ------------------------------------------------------------------ arquivo

  function escolherArquivo(arquivo) {
    if (!arquivo) return;
    arquivoAtual = arquivo;
    el.dropTitulo.textContent = arquivo.name;
    let problema = "";
    if (!ehDocumento(arquivo)) problema = "formato não aceito (use PDF, DOCX, DOC ou TXT). Para fotos de documento, use a análise de imagem.";
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

  el.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (el.enviar.disabled) return;
    enviando = true;
    atualizarBotao();
    el.progresso.hidden = false;
    const dados = new FormData();
    dados.append("documento", arquivoAtual, arquivoAtual.name);
    try {
      const resposta = await fetch(`${baseApi()}/documento/analisar`, { method: "POST", body: dados });
      let corpo = {};
      try { corpo = await resposta.json(); } catch (_) { /* resposta sem JSON */ }
      if (!resposta.ok) throw new Error(corpo.erro || `O servidor respondeu com erro (HTTP ${resposta.status}).`);
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
    el.vereditoTitulo.textContent = "Não foi possível analisar o documento";
    el.significado.textContent = "";
    el.motivos.replaceChildren(criar("li", null, mensagem));
    [el.numeros, el.indicios, el.benford, el.limites].forEach((n) => n.replaceChildren());
    el.benfordAjuda.textContent = "";
    el.ressalva.textContent = "";
    el.baixar.hidden = true;
  }

  // ------------------------------------------------------------------ resultado

  function explicarResultado(r) {
    const n = (r.indicios || []).length;
    if (r.resultado === "IA/MANIPULADA") {
      return `A AIDA encontrou ${n} indício${n > 1 ? "s" : ""} de que este documento foi editado, montado ou gerado por IA ou fora de um sistema emissor. Confira o documento na fonte antes de aceitá-lo.`;
    }
    if (r.resultado === "REAL") {
      return "O arquivo não mostra sinais de edição e traz uma prova de origem (assinatura digital intacta ou chave de acesso de nota fiscal). Ainda assim, confira na fonte quando o valor for importante.";
    }
    return n
      ? "A AIDA encontrou indícios fracos, que sozinhos não bastam para afirmar manipulação, e nada no arquivo comprova de onde ele veio. Veja abaixo o que chamou atenção."
      : "Nenhum sinal de edição foi encontrado, mas nada no arquivo comprova de onde ele veio. Um documento inventado do zero também passa sem sinais de edição: confira com quem o emitiu.";
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
    el.significado.textContent = explicarResultado(r);
    el.motivos.replaceChildren(...(r.motivos || []).map((m) => criar("li", null, m)));

    const e = r.estrutura || {};
    const ids = r.identificadores || {};
    el.numeros.replaceChildren(
      numero("Suspeita combinada", porcentagem(r.suspeita)),
      numero("Formato", (r.formato || e.formato || "pdf").toUpperCase()),
      numero("Páginas", `${e.paginas ?? "—"}${e.paginas_sem_texto ? ` (${e.paginas_sem_texto} só imagem)` : ""}`),
      numero("Programa", e.produtor || e.criador || "não informado"),
      numero("Criado / modificado", `${data(e.criado_em)} / ${data(e.modificado_em)}`),
      numero("Revisões salvas", String(e.revisoes ?? "—")),
      numero("Assinaturas digitais", String(e.assinaturas ?? 0)),
      ...(e.tempo_edicao_min != null ? [numero("Tempo de edição", `${e.tempo_edicao_min} min`)] : []),
      ...(e.c2pa && e.c2pa.presente ? [numero("Credencial C2PA", [e.c2pa.gerador, e.c2pa.modelo].filter(Boolean).join(" / ") || "presente")] : []),
      numero("CNPJ / CPF / chaves", `${ids.cnpjs ?? 0} / ${ids.cpfs ?? 0} / ${ids.chaves_acesso ?? 0}`),
    );

    const indicios = r.indicios || [];
    el.indicios.replaceChildren(
      ...(indicios.length
        ? indicios.map((i) => {
            const item = criar("li", `doc-indicio doc-indicio--${FORCA(i.peso) === "forte" ? "forte" : FORCA(i.peso) === "médio" ? "medio" : "fraco"}`);
            item.append(criar("span", "doc-indicio__forca", FORCA(i.peso)), criar("span", null, i.descricao));
            return item;
          })
        : [criar("li", "doc-indicio doc-indicio--nenhum", "Nenhum indício de edição encontrado.")])
    );

    desenharBenford(r.benford || {});
    const limites = [...(r.limitacoes || []), ...(r.alertas_seguranca || [])];
    el.limites.replaceChildren(...limites.map((m) => criar("li", null, m)));
    el.limitesBloco.hidden = !limites.length;
    el.ressalva.textContent = r.ressalva || "";
    el.painelEnvio.hidden = true;
    el.resultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function desenharBenford(b) {
    el.benford.replaceChildren();
    if (!b.n) {
      el.benfordAjuda.textContent = "Nenhum valor em reais (formato 1.234,56) encontrado no texto do documento.";
      return;
    }
    const contou = (relatorioAtual.indicios || []).some((i) => i.indicio.startsWith("benford"));
    const desvio = `Desvio médio (MAD) ${b.mad.toFixed(3)}; só pelo acaso, com ${b.n} valores, seria cerca de ${b.mad_esperado_ao_acaso.toFixed(3)}.`;
    el.benfordAjuda.textContent = !b.suficiente
      ? `Só ${b.n} valores em reais: poucos para a Lei de Benford valer. O gráfico é mostrado, mas não entra na decisão.`
      : contou
        ? `${desvio} Os valores fogem do padrão mais do que o acaso explica: conta como indício.`
        : `${desvio} O desvio está dentro do que o acaso explica: não conta como indício.`;
    const maior = Math.max(...b.observado, ...b.esperado, 0.01);
    DIGITOS.forEach((d, i) => {
      const coluna = criar("div", "doc-benford__coluna");
      const barras = criar("div", "doc-benford__barras");
      const obs = criar("span", "doc-benford__barra doc-cor--observado");
      const esp = criar("span", "doc-benford__barra doc-cor--esperado");
      obs.style.height = `${(b.observado[i] / maior) * 100}%`;
      esp.style.height = `${(b.esperado[i] / maior) * 100}%`;
      obs.title = `Dígito ${d}: ${porcentagem(b.observado[i])} no documento`;
      esp.title = `Dígito ${d}: ${porcentagem(b.esperado[i])} esperado`;
      barras.append(obs, esp);
      coluna.append(barras, criar("span", "doc-benford__digito", d));
      el.benford.append(coluna);
    });
  }

  // ------------------------------------------------------------------ ações

  el.baixar.addEventListener("click", () => {
    if (!relatorioAtual) return;
    const blob = new Blob([JSON.stringify(relatorioAtual, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `aida-documento-${(relatorioAtual.documento || "relatorio").replace(/\.[^.]+$/, "")}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });

  el.novo.addEventListener("click", () => {
    relatorioAtual = null;
    el.resultado.hidden = true;
    el.arquivo.value = "";
    arquivoAtual = null;
    el.drop.classList.remove("vid-drop--cheio", "vid-drop--erro");
    el.dropTitulo.textContent = "Selecione o PDF";
    el.dropTexto.textContent = "Escolha o arquivo original, do jeito que você recebeu. Evite prints ou PDFs refeitos.";
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

  // ?doc_api=http://host:porta sobrepõe o endereço (e fica lembrado).
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
