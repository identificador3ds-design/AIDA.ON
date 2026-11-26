/* ==========================================================================
   AIDA — página de preços (pages/index-precos.html)
   ==========================================================================

   Desenha cards, tabela comparativa e calculadora a partir de
   config/pricing.json e dos textos em i18n/precos.<idioma>.json. Nenhum
   preço ou texto de interface é escrito aqui.

   O seletor de mercado é só visual: a moeda cobrada é decidida no servidor
   (aida_api/cobranca.py), pelo CPF/CNPJ e pelo endereço de cobrança.

   Depende de scripts/aida-precos-core.js e scripts/aida-i18n.js, carregados
   antes. `window.AidaPaginaPrecos.pronto` resolve quando a primeira pintura
   termina (usado pelo teste de componente).
   ========================================================================== */
(function () {
  "use strict";

  const P = window.AidaPrecos;
  const I = window.AidaI18n;
  const raiz = document.querySelector("[data-precos]");
  if (!raiz || !P || !I) return;

  const BASE = raiz.getAttribute("data-base") || "..";
  const PAGINA_I18N = "precos";
  const PREF_MERCADO = "AIDA_PrecosMercado";
  const PREF_IDIOMA = "AIDA_PrecosIdioma";

  // Formulário comercial: insert direto na tabela `contatos_comerciais`
  // (docs/migracao-cobranca.sql). A chave anon é pública por desenho; o RLS
  // só permite INSERT, com os limites de tamanho conferidos no banco.
  const URL_SUPABASE = "https://nwzijdudhemuibsyzpub.supabase.co";
  const CHAVE_ANON =
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";

  const PADRAO_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const LIMITES = { nome: 120, empresa: 160, email: 254, mensagem: 2000 };
  const VOLUME_MAX = 1000000000;

  const $ = (id) => document.getElementById(id);

  const estado = {
    config: null,
    dicionarios: {},
    t: null,
    idioma: "pt-BR",
    mercado: "BR",
    ciclo: "monthly",
    segmento: "platform",
  };

  // ------------------------------------------------------------------ //
  // Preferências (localStorage pode faltar: modo privado, bloqueio)
  // ------------------------------------------------------------------ //
  function lerPreferencia(chave) {
    try { return localStorage.getItem(chave); } catch (_) { return null; }
  }

  function gravarPreferencia(chave, valor) {
    try { localStorage.setItem(chave, valor); } catch (_) { /* só conveniência */ }
  }

  function fusoHorario() {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || null; } catch (_) { return null; }
  }

  function idiomasDoNavegador() {
    return (navigator.languages && navigator.languages.length) ? navigator.languages : [navigator.language || ""];
  }

  // ------------------------------------------------------------------ //
  // Montagem de DOM sem innerHTML
  // ------------------------------------------------------------------ //
  function el(tag, atributos, filhos) {
    const no = document.createElement(tag);
    Object.entries(atributos || {}).forEach(([nome, valor]) => {
      if (valor === null || valor === undefined || valor === false) return;
      if (nome === "texto") no.textContent = valor;
      else if (nome === "classe") no.className = valor;
      else no.setAttribute(nome, valor === true ? "" : valor);
    });
    (filhos || []).forEach((filho) => { if (filho) no.appendChild(filho); });
    return no;
  }

  // ------------------------------------------------------------------ //
  // Textos de preço
  // ------------------------------------------------------------------ //
  const moeda = () => P.moedaDe(estado.config, estado.mercado);
  const dinheiro = (valor, opcoes) => P.formatarMoeda(valor, moeda(), estado.config, opcoes);
  const numero = (valor) => P.formatarNumero(valor, estado.idioma);
  const nomeDoPlano = (plano) => estado.t(plano.name_key);

  function precoPrincipal(plano) {
    const t = estado.t;
    if (plano.price_type === "contact") return { valor: t("card.contact_price") };
    if (plano.price_type === "validation") {
      return { valor: t("card.validation_price", { percent: plano.discount_percent }), nota: t("card.validation_note") };
    }
    const mensal = P.precoMensal(plano, moeda());
    if (mensal === null) return { valor: t("card.tbd") };
    if (mensal === 0) return { valor: t("card.free") };

    if (estado.ciclo === "annual") {
      const anual = P.precoAnual(plano, moeda(), estado.config);
      const equivalente = P.mensalEquivalente(plano, moeda(), "annual", estado.config);
      return {
        valor: dinheiro(anual),
        sufixo: t("card.per_year"),
        nota: t("card.annual_equiv", {
          monthly: dinheiro(equivalente),
          saved: dinheiro(P.arredondar(mensal * 12 - anual)),
        }),
      };
    }
    return { valor: dinheiro(mensal), sufixo: t("card.per_month") };
  }

  function linhaCreditos(plano) {
    const t = estado.t;
    if (plano.daily_limit) return t("card.daily_limit", { limit: numero(plano.daily_limit) });
    if (typeof plano.credits_included === "number") return t("card.credits", { credits: numero(plano.credits_included) });
    if (typeof plano.min_credits === "number") return t("card.min_credits", { credits: numero(plano.min_credits) });
    if (pendente(plano, "credits_included")) return `${t("row.credits")}: ${t("card.tbd")}`;
    return null;
  }

  function linhaExcedente(plano) {
    const t = estado.t;
    if (plano.overage === "charge" && typeof plano.overage_price === "number") {
      return t("card.overage", { price: dinheiro(plano.overage_price, { excedente: true }) });
    }
    if (plano.overage === "block") {
      return pendente(plano, "overage_policy") ? null : t("card.overage_block");
    }
    if (plano.overage === "negotiated") return t("card.overage_negotiated");
    return null;
  }

  function linhaUsuarios(plano) {
    const t = estado.t;
    if (typeof plano.users === "number") {
      return plano.users === 1 ? t("card.users_one") : t("card.users", { users: numero(plano.users) });
    }
    if (pendente(plano, "users")) return `${t("row.users")}: ${t("card.tbd")}`;
    return null;
  }

  const pendente = (plano, campo) => Array.isArray(plano.pending) && plano.pending.indexOf(campo) >= 0;

  // ------------------------------------------------------------------ //
  // Cards
  // ------------------------------------------------------------------ //
  function botaoDoPlano(plano) {
    const t = estado.t;
    const rotulo = t(plano.cta.label_key);
    const classe = plano.highlighted ? "aida-btn aida-btn--block" : "aida-btn aida-btn--ghost aida-btn--block";

    if (plano.cta.type === "signup") {
      return el("a", { classe, href: "./index-login.html", texto: rotulo });
    }
    // Sem gateway (config.checkout.enabled = false), contratar também abre o
    // formulário comercial; com gateway, aqui entra a chamada ao checkout.
    const tipo = plano.cta.type === "subscribe" ? "subscribe" : plano.id;
    return el("button", {
      type: "button", classe, texto: rotulo,
      "data-contato": tipo, "data-plano": plano.id,
    });
  }

  function cartao(plano, segmento) {
    const t = estado.t;
    const idTitulo = `plano-${segmento}-${plano.id}`;
    const preco = precoPrincipal(plano);
    const fatos = [linhaCreditos(plano), linhaExcedente(plano), linhaUsuarios(plano)].filter(Boolean);

    return el("article", {
      classe: "precos-card" + (plano.highlighted ? " precos-card--destaque" : ""),
      "aria-labelledby": idTitulo,
      "data-plano": plano.id,
    }, [
      plano.highlighted ? el("span", { classe: "aida-status aida-status--disponivel precos-card__selo", texto: t("card.highlight") }) : null,
      el("h3", { classe: "precos-card__nome", id: idTitulo, texto: nomeDoPlano(plano) }),
      el("p", { classe: "precos-card__publico", texto: t(plano.audience_key) }),
      el("p", { classe: "precos-card__preco", "data-preco": "" }, [
        el("span", { classe: "precos-card__valor", texto: preco.valor }),
        preco.sufixo ? el("span", { classe: "precos-card__sufixo", texto: preco.sufixo }) : null,
      ]),
      preco.nota ? el("p", { classe: "precos-card__nota", texto: preco.nota }) : null,
      fatos.length ? el("ul", { classe: "precos-card__fatos" }, fatos.map((f) => el("li", { texto: f }))) : null,
      el("ul", {
        classe: "precos-card__recursos",
        "aria-label": t("card.features_aria", { plan: nomeDoPlano(plano) }),
      }, plano.features.map((f) => el("li", { texto: t(`feature.${f}`) }))),
      el("div", { classe: "precos-card__acao" }, [botaoDoPlano(plano)]),
    ]);
  }

  function desenharCards() {
    P.SEGMENTOS.forEach((segmento) => {
      const alvo = raiz.querySelector(`[data-cards="${segmento}"]`);
      alvo.replaceChildren(...P.planosDe(estado.config, estado.mercado, segmento).map((p) => cartao(p, segmento)));
    });
    $("precosCheckoutAviso").hidden = Boolean(estado.config.checkout && estado.config.checkout.enabled);
  }

  // ------------------------------------------------------------------ //
  // Tabela comparativa (segmento ativo)
  // ------------------------------------------------------------------ //
  function celula(linha, plano) {
    const t = estado.t;
    const traco = "—";
    switch (linha) {
      case "price": {
        const p = precoPrincipal(plano);
        return (p.valor || "") + (p.sufixo || "");
      }
      case "credits":
        if (typeof plano.credits_included === "number") return numero(plano.credits_included);
        if (typeof plano.min_credits === "number") return `≥ ${numero(plano.min_credits)}`;
        return pendente(plano, "credits_included") ? t("card.tbd") : traco;
      case "daily_limit":
        return plano.daily_limit ? numero(plano.daily_limit) : traco;
      case "users":
        if (typeof plano.users === "number") return numero(plano.users);
        return pendente(plano, "users") ? t("card.tbd") : traco;
      case "overage_price":
        return typeof plano.overage_price === "number" ? dinheiro(plano.overage_price, { excedente: true }) : traco;
      default:
        return null; // recurso: marcado abaixo
    }
  }

  function desenharTabela() {
    const t = estado.t;
    const planos = P.planosDe(estado.config, estado.mercado, estado.segmento);
    const linhas = estado.config.comparison_rows[estado.segmento];
    const nomeSegmento = t(`segment.${estado.segmento}`);

    const cabecalho = el("tr", {}, [
      el("th", { scope: "col", texto: t("compare.feature") }),
      ...planos.map((p) => el("th", { scope: "col", texto: nomeDoPlano(p) })),
    ]);

    const corpo = linhas.map((linha) => {
      const recurso = !Object.prototype.hasOwnProperty.call({ price: 1, credits: 1, daily_limit: 1, users: 1, overage_price: 1 }, linha);
      const rotulo = recurso ? t(`feature.${linha}`) : t(`row.${linha}`);
      return el("tr", {}, [
        el("th", { scope: "row", texto: rotulo }),
        ...planos.map((plano) => {
          if (!recurso) return el("td", { texto: celula(linha, plano) });
          const tem = plano.features.indexOf(linha) >= 0;
          return el("td", { classe: tem ? "precos-tabela__sim" : "precos-tabela__nao" }, [
            el("span", { "aria-hidden": "true", texto: tem ? "✓" : "—" }),
            el("span", { classe: "aida-visually-hidden", texto: tem ? t("compare.yes") : t("compare.no") }),
          ]);
        }),
      ]);
    });

    const tabela = el("table", {}, [
      el("caption", { classe: "aida-visually-hidden", texto: t("compare.caption", { segment: nomeSegmento }) }),
      el("thead", {}, [cabecalho]),
      el("tbody", {}, corpo),
    ]);
    const regiao = $("precosTabela");
    regiao.setAttribute("aria-label", t("compare.region_aria", { segment: nomeSegmento }));
    regiao.replaceChildren(tabela);
  }

  // ------------------------------------------------------------------ //
  // Calculadora
  // ------------------------------------------------------------------ //
  function lerInteiro(campo) {
    const bruto = campo.value.trim();
    if (bruto === "") return 0;
    const n = Number(bruto);
    return Number.isInteger(n) && n >= 0 ? n : null;
  }

  function desenharCalculadora() {
    const t = estado.t;
    const saida = $("calcResultado");
    const campoImagens = $("calcImagens");
    const campoMinutos = $("calcMinutos");
    $("calcSegmento").textContent = t("calc.segment_note", { segment: t(`segment.${estado.segmento}`) });

    const imagens = lerInteiro(campoImagens);
    const minutos = lerInteiro(campoMinutos);
    campoImagens.setAttribute("aria-invalid", imagens === null ? "true" : "false");
    campoMinutos.setAttribute("aria-invalid", minutos === null ? "true" : "false");
    if (imagens === null || minutos === null) {
      saida.replaceChildren(el("p", { classe: "precos-form__erro", texto: t("calc.invalid") }));
      return;
    }

    const planos = P.planosDe(estado.config, estado.mercado, estado.segmento);
    const r = P.recomendarPlano(planos, moeda(), { imagens, minutosVideo: minutos }, estado.ciclo, estado.config);
    const partes = [el("p", { classe: "precos-calc__total", texto: t("calc.total", { credits: numero(r.creditos) }) })];

    if (r.recomendado) {
      const c = r.custo;
      const chaveCusto = estado.ciclo === "annual" && c.base > 0 ? "calc.cost_annual" : "calc.cost";
      let detalhe;
      if (c.creditosExtras > 0) {
        detalhe = t("calc.breakdown", {
          base: dinheiro(P.arredondar(c.base)),
          overage: dinheiro(P.arredondar(c.excedente)),
          extra: numero(c.creditosExtras),
        });
      } else {
        detalhe = c.total === 0 ? t("calc.free_fits") : t("calc.within");
      }
      partes.push(el("div", { classe: "precos-calc__recomendado", "data-recomendado": r.recomendado.id }, [
        el("span", { classe: "aida-eyebrow", texto: t("calc.recommend") }),
        el("p", { classe: "precos-calc__plano", texto: nomeDoPlano(r.recomendado) }),
        el("p", { classe: "precos-calc__custo", texto: t(chaveCusto, { price: dinheiro(P.arredondar(c.total)) }) }),
        el("p", { classe: "aida-text--sm", texto: detalhe }),
      ]));
    }

    if (r.sugerirEnterprise) {
      partes.push(el("p", { classe: "aida-text--sm", texto: t("calc.enterprise") }));
      partes.push(el("button", {
        type: "button", classe: "aida-btn aida-btn--ghost aida-btn--sm",
        "data-contato": "enterprise", "data-plano": "enterprise", texto: t("cta.talk_to_us"),
      }));
    } else if (!r.recomendado) {
      partes.push(el("p", { classe: "aida-text--sm", texto: t("calc.none") }));
    }

    if (r.indefinidos.length) {
      const nomes = r.indefinidos.map((id) => nomeDoPlano(planos.find((p) => p.id === id))).join(", ");
      partes.push(el("p", { classe: "aida-text--sm precos-calc__aviso", texto: t("calc.excluded_tbd", { plans: nomes }) }));
    }

    saida.replaceChildren(...partes);
  }

  // ------------------------------------------------------------------ //
  // Controles
  // ------------------------------------------------------------------ //
  function sincronizarControles() {
    const marcar = (nome, valor) => {
      const radio = raiz.querySelector(`input[name="${nome}"][value="${valor}"]`);
      if (radio) radio.checked = true;
    };
    marcar("mercado", estado.mercado);
    marcar("ciclo", estado.ciclo);
    marcar("idioma", estado.idioma);
    $("precosEconomia").textContent = estado.t("billing.save", { percent: P.percentualEconomia(estado.config) });

    raiz.querySelectorAll('[role="tab"]').forEach((aba) => {
      const ativa = aba.getAttribute("data-segmento") === estado.segmento;
      aba.setAttribute("aria-selected", ativa ? "true" : "false");
      aba.tabIndex = ativa ? 0 : -1;
      $(aba.getAttribute("aria-controls")).hidden = !ativa;
    });
  }

  function desenharTudo() {
    sincronizarControles();
    desenharCards();
    desenharTabela();
    desenharCalculadora();
  }

  function aplicarIdioma() {
    estado.t = I.criar(estado.dicionarios[estado.idioma]);
    document.documentElement.lang = estado.idioma;
    document.title = estado.t("meta.title");
    I.aplicar(document, estado.t);
  }

  async function trocarIdioma(idioma) {
    if (!estado.dicionarios[idioma]) {
      estado.dicionarios[idioma] = await I.carregar(PAGINA_I18N, idioma, BASE);
    }
    estado.idioma = idioma;
    gravarPreferencia(PREF_IDIOMA, idioma);
    aplicarIdioma();
    desenharTudo();
  }

  function ativarAba(segmento, focar) {
    estado.segmento = segmento;
    sincronizarControles();
    desenharTabela();
    desenharCalculadora();
    if (focar) $(`aba-${segmento}`).focus();
  }

  function ligarEventos() {
    raiz.addEventListener("change", (evento) => {
      const alvo = evento.target;
      if (alvo.name === "mercado") {
        estado.mercado = alvo.value;
        gravarPreferencia(PREF_MERCADO, alvo.value);
        desenharTudo();
      } else if (alvo.name === "ciclo") {
        estado.ciclo = alvo.value;
        desenharTudo();
      } else if (alvo.name === "idioma") {
        trocarIdioma(alvo.value).catch(mostrarFalhaDeCarga);
      }
    });

    $("calcForm").addEventListener("input", desenharCalculadora);
    $("calcForm").addEventListener("submit", (evento) => evento.preventDefault());

    const abas = Array.from(raiz.querySelectorAll('[role="tab"]'));
    abas.forEach((aba, indice) => {
      aba.addEventListener("click", () => ativarAba(aba.getAttribute("data-segmento"), false));
      // Padrão WAI-ARIA de abas: setas, Home e End movem e ativam.
      aba.addEventListener("keydown", (evento) => {
        const destinos = { ArrowRight: indice + 1, ArrowLeft: indice - 1, Home: 0, End: abas.length - 1 };
        if (!(evento.key in destinos)) return;
        evento.preventDefault();
        const proxima = abas[(destinos[evento.key] + abas.length) % abas.length];
        ativarAba(proxima.getAttribute("data-segmento"), true);
      });
    });

    document.addEventListener("click", (evento) => {
      const gatilho = evento.target.closest("[data-contato]");
      if (gatilho) abrirContato(gatilho.getAttribute("data-contato"), gatilho.getAttribute("data-plano"), gatilho);
    });
  }

  // ------------------------------------------------------------------ //
  // Formulário comercial
  // ------------------------------------------------------------------ //
  const dialogo = $("contatoDialogo");
  const formulario = $("contatoForm");
  let gatilhoDoDialogo = null;

  function tituloDoContato(tipo, planoId) {
    const t = estado.t;
    if (tipo === "subscribe") {
      const plano = P.SEGMENTOS
        .flatMap((s) => P.planosDe(estado.config, estado.mercado, s))
        .find((p) => p.id === planoId);
      return t("contact.title.subscribe", { plan: plano ? nomeDoPlano(plano) : planoId });
    }
    return t(`contact.title.${tipo}`);
  }

  function abrirContato(tipo, planoId, gatilho) {
    gatilhoDoDialogo = gatilho || null;
    limparErros();
    $("contatoEstado").textContent = "";
    $("contatoTipo").value = tipo;
    $("contatoPlano").value = planoId || "";
    $("contatoTitulo").textContent = tituloDoContato(tipo, planoId);
    $("contatoEnviar").disabled = false;

    if (typeof dialogo.showModal === "function") dialogo.showModal();
    else dialogo.setAttribute("open", "");
    $("contatoNome").focus();
  }

  function fecharContato() {
    if (typeof dialogo.close === "function") dialogo.close();
    else dialogo.removeAttribute("open");
  }

  function limparErros() {
    formulario.querySelectorAll(".precos-form__erro").forEach((p) => { p.hidden = true; p.textContent = ""; });
    formulario.querySelectorAll("[aria-invalid]").forEach((campo) => campo.removeAttribute("aria-invalid"));
    $("contatoResumo").hidden = true;
  }

  function validarContato() {
    const t = estado.t;
    const valor = (id) => $(id).value.trim();
    const erros = [];
    const exigir = (id, limite) => {
      const v = valor(id);
      if (!v) erros.push([id, t("contact.err.required")]);
      else if (v.length > limite) erros.push([id, t("contact.err.too_long", { max: limite })]);
    };

    exigir("contatoNome", LIMITES.nome);
    exigir("contatoEmpresa", LIMITES.empresa);
    const email = valor("contatoEmail");
    if (!email) erros.push(["contatoEmail", t("contact.err.required")]);
    else if (email.length > LIMITES.email || !PADRAO_EMAIL.test(email)) erros.push(["contatoEmail", t("contact.err.email")]);

    const volume = Number(valor("contatoVolume"));
    if (!Number.isInteger(volume) || volume < 1 || volume > VOLUME_MAX) {
      erros.push(["contatoVolume", t("contact.err.volume")]);
    }
    if (valor("contatoMensagem").length > LIMITES.mensagem) {
      erros.push(["contatoMensagem", t("contact.err.too_long", { max: LIMITES.mensagem })]);
    }
    if (!$("contatoConsentimento").checked) erros.push(["contatoConsentimento", t("contact.err.consent")]);
    return erros;
  }

  function mostrarErros(erros) {
    erros.forEach(([id, mensagem]) => {
      $(id).setAttribute("aria-invalid", "true");
      const destino = $(`erro-${id}`);
      destino.textContent = mensagem;
      destino.hidden = false;
    });
    const resumo = $("contatoResumo");
    resumo.textContent = estado.t("contact.err.summary");
    resumo.hidden = false;
    $(erros[0][0]).focus();
  }

  async function enviarContato(evento) {
    evento.preventDefault();
    limparErros();
    const erros = validarContato();
    if (erros.length) {
      mostrarErros(erros);
      return;
    }

    const t = estado.t;
    const situacao = $("contatoEstado");
    const botao = $("contatoEnviar");

    // Robô preencheu a armadilha: finge sucesso e não envia nada.
    if ($("contatoSite").value) {
      situacao.textContent = t("contact.success");
      formulario.reset();
      return;
    }

    const corpo = {
      tipo: $("contatoTipo").value,
      plano_id: $("contatoPlano").value || null,
      mercado: estado.mercado,
      idioma: estado.idioma,
      nome: $("contatoNome").value.trim(),
      empresa: $("contatoEmpresa").value.trim(),
      email: $("contatoEmail").value.trim(),
      volume_estimado: Number($("contatoVolume").value),
      mensagem: $("contatoMensagem").value.trim() || null,
      consentimento: true,
    };

    botao.disabled = true;
    botao.classList.add("is-busy");
    situacao.textContent = t("contact.sending");
    try {
      const resposta = await fetch(`${URL_SUPABASE}/rest/v1/contatos_comerciais`, {
        method: "POST",
        headers: {
          apikey: CHAVE_ANON,
          Authorization: `Bearer ${CHAVE_ANON}`,
          "Content-Type": "application/json",
          Prefer: "return=minimal",
        },
        body: JSON.stringify(corpo),
      });
      if (!resposta.ok) {
        // P0001 = limite anti-spam da migração (3 por e-mail / 20 no total por hora).
        const erro = await resposta.json().catch(() => null);
        const falha = new Error(`HTTP ${resposta.status}`);
        falha.limite = Boolean(erro && erro.code === "P0001");
        throw falha;
      }
      situacao.textContent = t("contact.success");
      formulario.reset();
    } catch (falha) {
      situacao.textContent = t(falha && falha.limite ? "contact.error_rate_limit" : "contact.error");
      botao.disabled = false;
    } finally {
      botao.classList.remove("is-busy");
    }
  }

  formulario.addEventListener("submit", enviarContato);
  dialogo.querySelector("[data-fechar]").addEventListener("click", fecharContato);
  dialogo.addEventListener("close", () => {
    if (gatilhoDoDialogo && document.contains(gatilhoDoDialogo)) gatilhoDoDialogo.focus();
  });
  // Sem showModal (navegador antigo), Esc ainda precisa fechar.
  dialogo.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape" && typeof dialogo.showModal !== "function") fecharContato();
  });

  // ------------------------------------------------------------------ //
  // Início
  // ------------------------------------------------------------------ //
  function mostrarFalhaDeCarga() {
    // O texto de erro já vem no HTML (pré-preenchido do i18n): a falha pode
    // ter sido justamente carregar o dicionário.
    const status = $("precosStatus");
    status.hidden = false;
    status.className = "aida-state aida-state--erro precos-status";
    $("precosStatusTexto").hidden = true;
    $("precosStatusErro").hidden = false;
  }

  async function iniciar() {
    const preferidoIdioma = lerPreferencia(PREF_IDIOMA);
    estado.idioma = I.IDIOMAS.indexOf(preferidoIdioma) >= 0 ? preferidoIdioma : P.idiomaPadrao(idiomasDoNavegador());

    const [config, dicionario] = await Promise.all([
      fetch(`${BASE}/config/pricing.json`, { cache: "no-cache" }).then((r) => {
        if (!r.ok) throw new Error(`pricing.json: HTTP ${r.status}`);
        return r.json();
      }),
      I.carregar(PAGINA_I18N, estado.idioma, BASE),
    ]);
    estado.config = config;
    estado.dicionarios[estado.idioma] = dicionario;

    const preferidoMercado = lerPreferencia(PREF_MERCADO);
    estado.mercado = config.markets[preferidoMercado]
      ? preferidoMercado
      : P.mercadoPadrao({ idiomas: idiomasDoNavegador(), fusoHorario: fusoHorario() });

    aplicarIdioma();
    ligarEventos();
    desenharTudo();
    $("precosStatus").hidden = true;
  }

  const pronto = iniciar().catch((erro) => {
    estado.erro = erro;
    mostrarFalhaDeCarga();
  });
  window.AidaPaginaPrecos = { pronto, estado };
})();
