/* ==========================================================================
   AIDA Forensics — investigação de uma análise já executada
   ==========================================================================

   A página não analisa nada. Ela pede `GET /forense/<id>` e desenha o dossiê
   que o servidor montou a partir do resultado em cache. Isso é deliberado:
   recalcular aqui poderia produzir números diferentes dos que o usuário viu no
   AIDA Image — e uma investigação que contradiz o resultado que a originou é
   pior do que investigação nenhuma.

   De onde vem o `id`:
     1. `?id=` na URL (é assim que o histórico abre uma análise);
     2. o repasse gravado pelo AIDA Image em `sessionStorage`, quando o usuário
        clica em "Ver análise forense" logo após o resultado.

   A imagem original NÃO vem do servidor — ele não a guarda. Quando o navegador
   ainda tem o arquivo escolhido, a comparação lado a lado aparece; quando não
   tem, os mapas são exibidos sozinhos e a página continua completa.
   ========================================================================== */

(function () {
  "use strict";

  // Mesma lista e mesma ordem do AIDA Image: o dossiê precisa vir da base que
  // atendeu a análise, senão o id não existe do outro lado.
  var BASES_API = [
    "https://aidaon-aida-api.hf.space",
    "http://127.0.0.1:7860",
    "http://localhost:7860",
  ];

  var CHAVE_REPASSE = "AIDA_Forense";
  var CHAVE_IMAGEM_SELECIONADA = "AIDA_ImagemSelecionada";
  var DB_IMAGEM_SELECIONADA = "AIDA_ImagemSelecionada_DB";
  var STORE_IMAGEM_SELECIONADA = "imagem";

  var el = function (id) {
    return document.getElementById(id);
  };

  var estados = {
    carregando: el("foCarregando"),
    esqueleto: el("foEsqueleto"),
    semAnalise: el("foSemAnalise"),
    erro: el("foErro"),
    dossie: el("foDossie"),
    ressalva: el("foRessalva"),
    acoes: el("foAcoes"),
    identificacao: el("foIdentificacao"),
  };

  function mostrar(quais) {
    Object.keys(estados).forEach(function (nome) {
      var no = estados[nome];
      if (no) no.hidden = quais.indexOf(nome) === -1;
    });
  }

  function texto(valor, alternativa) {
    var bruto = valor === 0 || valor ? String(valor) : "";
    return bruto.trim() || alternativa || "—";
  }

  function porcentagem(valor, casas) {
    var numero = Number(valor);
    if (!isFinite(numero)) return "—";
    return (numero * 100).toFixed(casas === undefined ? 1 : casas) + "%";
  }

  function bytesLegiveis(bytes) {
    var numero = Number(bytes) || 0;
    if (numero < 1024) return numero + " B";
    if (numero < 1024 * 1024) return (numero / 1024).toFixed(1) + " kB";
    return (numero / (1024 * 1024)).toFixed(2) + " MB";
  }

  /* ---------------------------------------------------------------------
     Identificação da análise
     --------------------------------------------------------------------- */

  function lerRepasse() {
    try {
      var bruto = sessionStorage.getItem(CHAVE_REPASSE);
      return bruto ? JSON.parse(bruto) : null;
    } catch (erro) {
      return null;
    }
  }

  function resolverAlvo() {
    var parametros = new URLSearchParams(window.location.search);
    var idNaUrl = (parametros.get("id") || "").trim();
    var repasse = lerRepasse();

    if (idNaUrl) {
      // A base só é reaproveitada quando o repasse fala da MESMA análise;
      // caso contrário, seria a base de outra execução.
      var mesma = repasse && repasse.id_analise === idNaUrl;
      return {
        id: idNaUrl,
        base: (mesma && repasse.base_api) || parametros.get("base") || "",
        nome: (mesma && repasse.nome_imagem) || "",
      };
    }

    if (repasse && repasse.id_analise) {
      return {
        id: String(repasse.id_analise),
        base: repasse.base_api || "",
        nome: repasse.nome_imagem || "",
      };
    }

    return null;
  }

  /* ---------------------------------------------------------------------
     Busca do dossiê
     --------------------------------------------------------------------- */

  async function buscarDossie(alvo) {
    // A base conhecida é tentada primeiro; as demais existem para o caso de o
    // usuário reabrir a página noutro ambiente (local x publicado).
    var bases = [];
    if (alvo.base) bases.push(alvo.base.replace(/\/+$/, ""));
    BASES_API.forEach(function (base) {
      if (bases.indexOf(base) === -1) bases.push(base);
    });

    var ultimoErro = null;
    var erro404 = null;

    for (var i = 0; i < bases.length; i++) {
      var base = bases[i];
      try {
        var resposta = await fetch(base + "/forense/" + encodeURIComponent(alvo.id), {
          method: "GET",
          headers: { Accept: "application/json" },
        });

        if (resposta.ok) {
          return { dossie: await resposta.json(), base: base };
        }

        if (resposta.status === 404) {
          // 404 não encerra a busca: uma análise feita no backend local não
          // existe no publicado, e vice-versa. Guardamos a mensagem e seguimos
          // — só depois de TODAS as bases negarem é que a análise realmente
          // não está disponível em lugar nenhum.
          var corpo = null;
          try {
            corpo = await resposta.json();
          } catch (erro) {
            corpo = null;
          }
          erro404 = new Error((corpo && corpo.motivo) || "Análise não encontrada.");
          erro404.expirada = true;
          erro404.acao = (corpo && corpo.acao) || "";
          continue;
        }

        ultimoErro = new Error("A API respondeu " + resposta.status + ".");
      } catch (erro) {
        ultimoErro = erro;
      }
    }

    if (erro404) throw erro404;
    throw ultimoErro || new Error("Nenhuma base da API respondeu.");
  }

  /* ---------------------------------------------------------------------
     Imagem original (só do navegador — o servidor não a guarda)
     --------------------------------------------------------------------- */

  function abrirBancoImagem() {
    return new Promise(function (resolve, reject) {
      if (!window.indexedDB) {
        reject(new Error("IndexedDB indisponível."));
        return;
      }
      var pedido = indexedDB.open(DB_IMAGEM_SELECIONADA, 1);
      pedido.onupgradeneeded = function () {
        pedido.result.createObjectStore(STORE_IMAGEM_SELECIONADA);
      };
      pedido.onsuccess = function () {
        resolve(pedido.result);
      };
      pedido.onerror = function () {
        reject(pedido.error || new Error("Banco indisponível."));
      };
    });
  }

  async function obterImagemOriginal() {
    var daSessao = null;
    try {
      daSessao = sessionStorage.getItem(CHAVE_IMAGEM_SELECIONADA) ||
        localStorage.getItem(CHAVE_IMAGEM_SELECIONADA);
    } catch (erro) {
      daSessao = null;
    }
    if (daSessao) return daSessao;

    try {
      var banco = await abrirBancoImagem();
      return await new Promise(function (resolve) {
        var transacao = banco.transaction(STORE_IMAGEM_SELECIONADA, "readonly");
        var pedido = transacao.objectStore(STORE_IMAGEM_SELECIONADA).get(CHAVE_IMAGEM_SELECIONADA);
        pedido.onsuccess = function () {
          banco.close();
          resolve(pedido.result || null);
        };
        pedido.onerror = function () {
          banco.close();
          resolve(null);
        };
      });
    } catch (erro) {
      return null;
    }
  }

  /* ---------------------------------------------------------------------
     Renderização
     --------------------------------------------------------------------- */

  function renderizarIdentificacao(dossie) {
    el("foId").textContent = texto(dossie.id_analise);
    el("foArquivo").textContent = texto(dossie.arquivo && dossie.arquivo.nome);
    el("foData").textContent = texto(dossie.arquivo && dossie.arquivo.analisado_em);
  }

  function renderizarLeitura(dossie) {
    var r = dossie.resultado || {};
    var estado = r.fora_de_dominio ? "FORA_DE_DOMINIO" : (r.resultado || "INCONCLUSIVO");

    var veredito = el("foVeredito");
    veredito.dataset.estado = estado;
    veredito.textContent = r.fora_de_dominio
      ? "Fora do escopo da análise"
      : texto(r.resultado);

    el("foConfianca").textContent = texto(r.confianca).toUpperCase();
    el("foExplicacao").textContent = texto(r.explicacao, "");

    // Fora de domínio: a imagem não é fotográfica e as probabilidades não têm
    // significado. Exibi-las convidaria à leitura de um número sem sentido.
    if (r.fora_de_dominio) {
      el("foProbExibicao").textContent = "não se aplica";
      el("foProbCalibrada").textContent = "não se aplica";
      el("foRegua").hidden = true;
      el("foReguaInfo").textContent = "sem escala aplicável";
    } else {
      el("foProbExibicao").textContent = porcentagem(r.probabilidade_ia_exibicao);
      el("foProbCalibrada").textContent = porcentagem(r.probabilidade_ia_calibrada);
      desenharRegua(r);
    }

    var motivos = r.motivos || [];
    var bloco = el("foMotivosBloco");
    var lista = el("foMotivos");
    lista.innerHTML = "";
    if (motivos.length) {
      motivos.forEach(function (motivo) {
        var item = document.createElement("li");
        item.textContent = motivo;
        lista.appendChild(item);
      });
      bloco.hidden = false;
    } else {
      bloco.hidden = true;
    }
  }

  function desenharRegua(r) {
    // A régua usa a escala CALIBRADA, que é onde limiar e banda foram
    // definidos. Misturar as duas escalas aqui colocaria o marcador num ponto
    // que não corresponde ao limiar desenhado ao lado.
    var banda = r.banda_inconclusiva || [];
    var limiar = Number(r.limiar);
    var valor = Number(r.probabilidade_ia_calibrada);

    var noBanda = el("foReguaBanda");
    if (banda.length === 2) {
      var inicio = Math.max(0, Math.min(1, Number(banda[0])));
      var fim = Math.max(0, Math.min(1, Number(banda[1])));
      noBanda.style.left = (inicio * 100).toFixed(2) + "%";
      noBanda.style.width = Math.max(0, (fim - inicio) * 100).toFixed(2) + "%";
      noBanda.hidden = false;
    } else {
      noBanda.hidden = true;
    }

    if (isFinite(limiar)) {
      el("foReguaLimiar").style.left = (limiar * 100).toFixed(2) + "%";
    }
    if (isFinite(valor)) {
      el("foReguaMarcador").style.left = (Math.max(0, Math.min(1, valor)) * 100).toFixed(2) + "%";
    }

    el("foReguaInfo").textContent =
      "limiar " + (isFinite(limiar) ? limiar.toFixed(3) : "—") +
      (banda.length === 2
        ? " · abstenção " + Number(banda[0]).toFixed(2) + "–" + Number(banda[1]).toFixed(2)
        : "");
  }

  function renderizarMetodos(dossie) {
    var alvo = el("foMetodos");
    alvo.innerHTML = "";

    var metodos = dossie.metodos || [];
    var fusao = dossie.fusao || {};

    el("foFusao").textContent = fusao.calibrado
      ? "Fusão calibrada (" + texto(fusao.metodo) + ")"
      : "Fusão não calibrada (" + texto(fusao.metodo) + ")";

    if (!metodos.length) {
      var vazio = document.createElement("p");
      vazio.className = "fo-bloco__nota";
      vazio.textContent = "Nenhum módulo registrou score nesta análise.";
      alvo.appendChild(vazio);
      return;
    }

    metodos.forEach(function (metodo) {
      var bloco = document.createElement("article");
      bloco.className = "fo-metodo";

      var topo = document.createElement("div");
      topo.className = "fo-metodo__topo";

      var nome = document.createElement("h3");
      nome.className = "fo-metodo__nome";
      nome.textContent = metodo.nome || metodo.chave;

      var score = document.createElement("span");
      score.className = "fo-metodo__score";
      score.textContent = Number(metodo.score).toFixed(3);

      topo.appendChild(nome);
      topo.appendChild(score);

      var barra = document.createElement("div");
      barra.className = "fo-barra";
      var preenchimento = document.createElement("span");
      preenchimento.className = "fo-barra__preenchimento";
      preenchimento.style.width = "0%";
      barra.appendChild(preenchimento);

      var descricao = document.createElement("p");
      descricao.className = "fo-metodo__descricao";
      descricao.textContent = metodo.descricao || "";

      bloco.appendChild(topo);
      bloco.appendChild(barra);
      bloco.appendChild(descricao);
      alvo.appendChild(bloco);

      // Largura aplicada no quadro seguinte para a transição do CSS acontecer.
      requestAnimationFrame(function () {
        var proporcao = Math.max(0, Math.min(1, Number(metodo.score)));
        preenchimento.style.width = (proporcao * 100).toFixed(1) + "%";
      });
    });

    var desacordo = Number(fusao.desacordo);
    if (isFinite(desacordo) && desacordo > 0) {
      var nota = document.createElement("p");
      nota.className = "fo-bloco__nota";
      nota.style.marginTop = "20px";
      nota.textContent =
        "Distância entre o maior e o menor score: " + desacordo.toFixed(3) +
        ". Desacordo alto entre módulos costuma acompanhar leituras de baixa confiança.";
      alvo.appendChild(nota);
    }
  }

  function renderizarMapas(dossie, base, imagemOriginal) {
    var evidencias = dossie.evidencias || {};
    var mapas = evidencias.mapas || [];
    var alvo = el("foMapas");
    alvo.innerHTML = "";

    el("foMapasInfo").textContent = mapas.length
      ? mapas.length + (mapas.length === 1 ? " mapa" : " mapas")
      : "sem mapas";

    if (!mapas.length) {
      el("foSemMapas").hidden = false;
      return;
    }
    el("foSemMapas").hidden = true;

    mapas.forEach(function (mapa, indice) {
      alvo.appendChild(montarMapa(mapa, base, imagemOriginal, indice));
    });
  }

  function montarMapa(mapa, base, imagemOriginal, indice) {
    var figura = document.createElement("figure");
    figura.className = "fo-mapa";

    var palco = document.createElement("div");
    palco.className = "fo-mapa__palco";
    palco.style.setProperty("--fo-split", "50%");

    var imagemMapa = document.createElement("img");
    imagemMapa.src = base + mapa.url;
    imagemMapa.alt = "Mapa de " + mapa.nome + " da imagem analisada";
    imagemMapa.decoding = "async";
    palco.appendChild(imagemMapa);

    // A comparação só faz sentido nos mapas alinhados aos pixels da imagem.
    // Nos espectrais, os eixos são frequências: sobrepor o original ali
    // produziria uma imagem sem significado.
    var comparavel = mapa.alinhado_a_pixels && !!imagemOriginal;

    if (comparavel) {
      var original = document.createElement("img");
      original.className = "fo-mapa__original";
      original.src = imagemOriginal;
      original.alt = "Imagem original enviada";
      palco.appendChild(original);

      var divisor = document.createElement("span");
      divisor.className = "fo-mapa__divisor";
      palco.appendChild(divisor);

      var controle = document.createElement("input");
      controle.type = "range";
      controle.min = "0";
      controle.max = "100";
      controle.value = "50";
      controle.step = "1";
      controle.className = "fo-mapa__controle";
      controle.id = "foSplit" + indice;
      controle.setAttribute("aria-label", "Comparar o original com o mapa de " + mapa.nome);
      controle.addEventListener("input", function () {
        palco.style.setProperty("--fo-split", controle.value + "%");
      });
      palco.appendChild(controle);
    }

    var legenda = document.createElement("figcaption");

    var tag = document.createElement("span");
    tag.className = "fo-mapa__tag";
    tag.textContent = comparavel
      ? "comparação com o original"
      : (mapa.alinhado_a_pixels ? "alinhado à imagem" : "domínio da frequência");

    var nome = document.createElement("span");
    nome.className = "fo-mapa__nome";
    nome.textContent = rotularMapa(mapa.nome);

    var descricao = document.createElement("p");
    descricao.className = "fo-mapa__legenda";
    descricao.textContent = mapa.legenda || "";

    legenda.appendChild(tag);
    legenda.appendChild(nome);
    legenda.appendChild(descricao);

    figura.appendChild(palco);
    figura.appendChild(legenda);
    return figura;
  }

  var ROTULOS_MAPAS = {
    gradiente: "Mapa de gradiente",
    bordas: "Mapa de bordas",
    ruido_residual: "Ruído residual",
    espectro_magnitude: "Espectro — magnitude",
    espectro_fase: "Espectro — fase",
    clip_tokens: "Atenção do CLIP",
  };

  function rotularMapa(nome) {
    return ROTULOS_MAPAS[nome] || nome;
  }

  function itemDado(termo, valor) {
    var bloco = document.createElement("div");
    bloco.className = "fo-dado";
    var dt = document.createElement("dt");
    dt.textContent = termo;
    var dd = document.createElement("dd");
    dd.textContent = texto(valor);
    bloco.appendChild(dt);
    bloco.appendChild(dd);
    return bloco;
  }

  function renderizarArquivo(dossie) {
    var a = dossie.arquivo || {};
    var alvo = el("foArquivoDados");
    alvo.innerHTML = "";

    var campos = [
      ["Nome", a.nome],
      ["Formato", a.formato || a.extensao],
      ["Dimensões", a.largura && a.altura ? a.largura + " × " + a.altura + " px" : "—"],
      ["Tamanho", bytesLegiveis(a.bytes)],
      ["Modo de cor", a.modo_de_cor],
      ["Bits por pixel", Number(a.bits_por_pixel).toFixed(3)],
      // Zero aqui significa "não estimado" — o arquivo não é JPEG ou não trouxe
      // tabelas de quantização. Dizer "0" seria lido como qualidade péssima.
      ["Qualidade JPEG estimada", a.jpeg_qualidade_estimada ? a.jpeg_qualidade_estimada : "não estimada"],
      ["JPEG progressivo", a.jpeg_progressivo ? "sim" : "não"],
      ["SHA-256", a.hash_sha256 ? a.hash_sha256.slice(0, 16) + "…" : "—"],
      ["Duração da análise", isFinite(Number(a.duracao_s)) ? Number(a.duracao_s).toFixed(2) + " s" : "—"],
    ];

    campos.forEach(function (campo) {
      alvo.appendChild(itemDado(campo[0], campo[1]));
    });

    // EXIF e ICC ficam fora desta lista de propósito: aqui descrevemos a imagem
    // como o modelo a mediu, e a normalização pode ter removido os metadados do
    // arquivo enviado. Quem responde por eles é o bloco de proveniência.
    if (a.observacao) el("foArquivoNota").textContent = a.observacao;
  }

  var RESUMO_PROVENIENCIA = {
    AI_PROVENANCE_CONFIRMED: "O arquivo carrega uma credencial assinada declarando geração por IA.",
    AI_EDIT_PROVENANCE: "A credencial assinada declara que partes da imagem foram criadas ou alteradas por IA.",
    AI_PROVENANCE_LIKELY: "Os metadados declaram origem em IA, sem assinatura que garanta a declaração.",
    METADATA_AI_SIGNAL: "Os metadados mencionam uma ferramenta de IA. Esses campos são texto livre.",
    C2PA_PRESENT: "Há Content Credentials no arquivo, mas elas não dizem se houve IA.",
    C2PA_INVALID: "Há uma credencial, mas ela não passou na verificação de integridade.",
    CAPTURE_PROVENANCE_CONFIRMED: "Uma credencial assinada declara captura por câmera.",
    NO_PROVENANCE_FOUND:
      "Nenhuma informação de proveniência foi encontrada. Isso não significa que a imagem seja " +
      "real: print, recorte, recompressão e envio por aplicativo removem esses dados.",
    UNKNOWN: "O arquivo não pôde ser lido o suficiente para uma conclusão sobre a origem.",
  };

  function renderizarProveniencia(dossie) {
    var p = dossie.proveniencia || {};
    var status = p.status || "UNKNOWN";

    el("foProvStatus").textContent = status;
    el("foProvResumo").textContent = RESUMO_PROVENIENCIA[status] || RESUMO_PROVENIENCIA.UNKNOWN;

    var alvo = el("foProvDados");
    alvo.innerHTML = "";

    var metadados = p.metadados_presentes || {};
    var campos = [
      ["C2PA presente", p.c2pa_presente ? "sim" : "não"],
      ["Assinatura íntegra", p.c2pa_presente ? (p.c2pa_valido ? "sim" : "não") : "não se aplica"],
      ["Cadeia confiável", p.c2pa_presente ? (p.c2pa_cadeia_confiavel ? "sim" : "não") : "não se aplica"],
      ["Declara IA", p.declaracao_ia ? "sim" : "não"],
      ["Tipo de fonte digital", p.tipo_fonte_digital || "não declarado"],
      ["EXIF", metadados.exif ? "presente" : "ausente"],
      ["XMP", metadados.xmp ? "presente" : "ausente"],
      ["IPTC", metadados.iptc ? "presente" : "ausente"],
      ["Campos de metadados", metadados.campos],
      ["Software declarado", (p.softwares || []).join(", ") || "nenhum"],
      ["Atribuição", (p.atribuicao && p.atribuicao.gerador) || "desconhecido"],
      ["Biblioteca C2PA", p.c2pa_biblioteca_disponivel ? "disponível" : "indisponível"],
    ];

    campos.forEach(function (campo) {
      alvo.appendChild(itemDado(campo[0], campo[1]));
    });

    var lista = el("foProvEvidencias");
    lista.innerHTML = "";
    (p.evidencias || []).forEach(function (evidencia) {
      var item = document.createElement("li");
      var chave = document.createElement("strong");
      chave.textContent = texto(evidencia.chave || evidencia.fonte);
      item.appendChild(chave);
      item.appendChild(
        document.createTextNode(texto(evidencia.descricao || evidencia.valor, ""))
      );
      lista.appendChild(item);
    });
  }

  var ROTULOS_QUALIDADE = {
    qualidade_score: "Índice geral de qualidade",
    qualidade_lado_menor: "Menor lado (px)",
    qualidade_bits_por_pixel: "Bits por pixel",
    qualidade_jpeg_estimada: "Qualidade JPEG estimada",
    qualidade_nitidez: "Nitidez",
    qualidade_ruido: "Ruído",
  };

  function renderizarQualidade(dossie) {
    var alvo = el("foQualidade");
    alvo.innerHTML = "";

    var qualidade = dossie.qualidade || {};
    Object.keys(qualidade).forEach(function (chave) {
      var valor = Number(qualidade[chave]);
      alvo.appendChild(
        itemDado(ROTULOS_QUALIDADE[chave] || chave, isFinite(valor) ? valor.toFixed(3) : qualidade[chave])
      );
    });

    var lista = el("foLimitacoes");
    lista.innerHTML = "";
    var itens = (dossie.limitacoes || []).concat(dossie.avisos_qualidade || []);
    itens.forEach(function (limitacao) {
      var item = document.createElement("li");
      item.textContent = limitacao;
      lista.appendChild(item);
    });
  }

  function renderizar(dossie, base, imagemOriginal) {
    renderizarIdentificacao(dossie);
    renderizarLeitura(dossie);
    renderizarMetodos(dossie);
    renderizarMapas(dossie, base, imagemOriginal);
    renderizarProveniencia(dossie);
    renderizarArquivo(dossie);
    renderizarQualidade(dossie);

    var ressalva = dossie.ressalva || "";
    if (ressalva) el("foRessalvaTexto").textContent = ressalva;

    mostrar(["dossie", "identificacao", "acoes"].concat(ressalva ? ["ressalva"] : []));
  }

  function mostrarErro(erro) {
    el("foErroTitulo").textContent = erro && erro.expirada
      ? "Esta análise não está mais disponível"
      : "Não foi possível abrir a investigação";
    el("foErroTexto").textContent =
      ((erro && erro.message) || "Erro desconhecido.") +
      (erro && erro.acao ? " " + erro.acao : "");
    mostrar(["erro"]);
  }

  /* ---------------------------------------------------------------------
     Início
     --------------------------------------------------------------------- */

  async function iniciar() {
    var alvo = resolverAlvo();
    if (!alvo) {
      mostrar(["semAnalise"]);
      return;
    }

    mostrar(["carregando", "esqueleto"]);

    var resultado;
    try {
      resultado = await buscarDossie(alvo);
    } catch (erro) {
      mostrarErro(erro);
      return;
    }

    // A imagem original é opcional: sem ela a página perde a comparação lado a
    // lado, não o dossiê.
    var imagemOriginal = null;
    try {
      imagemOriginal = await obterImagemOriginal();
    } catch (erro) {
      imagemOriginal = null;
    }

    try {
      renderizar(resultado.dossie, resultado.base, imagemOriginal);
    } catch (erro) {
      if (window.console) console.error("[AIDA Forensics]", erro);
      mostrarErro(new Error("O dossiê veio em um formato que esta tela não reconhece."));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
