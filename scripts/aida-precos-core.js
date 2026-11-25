/* ==========================================================================
   AIDA — regras de preço (puro, sem DOM)
   ==========================================================================

   Tudo o que a página de preços calcula sai daqui, a partir de
   `config/pricing.json`: preço anual, créditos de vídeo, plano recomendado,
   formatação de moeda e mercado padrão. Não há valor de plano neste arquivo.

   Sem DOM de propósito: é exercitado pelo Node nos testes
   (testes/test_precos_core.py), como scripts/aida-evidencia-combinada.js.

   Estes números são só para EXIBIR. O preço cobrado vem sempre do servidor
   (aida_api/cobranca.py lê o mesmo JSON); nada que o navegador calcule vale
   como valor de cobrança.
   ========================================================================== */
(function (raiz, fabrica) {
  "use strict";
  var modulo = fabrica();
  if (typeof module === "object" && module.exports) {
    module.exports = modulo;
  } else {
    raiz.AidaPrecos = modulo;
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var SEGMENTOS = ["platform", "api"];
  var CICLOS = ["monthly", "annual"];

  /* Fusos do Brasil (IANA). Um site estático não vê o IP do visitante; o fuso
     é o melhor indício disponível no navegador, e o idioma desempata. */
  var FUSOS_BRASIL = [
    "America/Sao_Paulo", "America/Bahia", "America/Fortaleza", "America/Recife",
    "America/Belem", "America/Maceio", "America/Araguaina", "America/Santarem",
    "America/Manaus", "America/Cuiaba", "America/Campo_Grande", "America/Porto_Velho",
    "America/Boa_Vista", "America/Rio_Branco", "America/Eirunepe", "America/Noronha",
  ];

  /* Dinheiro em ponto flutuante: 0.1 + 0.2 não é 0.3. Arredondamos só na
     borda (exibição e comparação), em quatro casas, para o excedente de
     US$ 0,0035 não virar ruído. */
  function arredondar(valor, casas) {
    var fator = Math.pow(10, casas === undefined ? 2 : casas);
    return Math.round((valor + Number.EPSILON) * fator) / fator;
  }

  function moedaDe(config, mercado) {
    var m = config.markets[mercado];
    if (!m) throw new Error("mercado desconhecido: " + mercado);
    return m.currency;
  }

  function planosDe(config, mercado, segmento) {
    if (SEGMENTOS.indexOf(segmento) < 0) throw new Error("segmento desconhecido: " + segmento);
    return config.markets[mercado][segmento].slice();
  }

  function precoMensal(plano, moeda) {
    var valor = plano.price_monthly ? plano.price_monthly[moeda] : null;
    return typeof valor === "number" ? valor : null;
  }

  /* Anual = N meses do mensal (config.annual_months_charged; 10 = dois grátis). */
  function precoAnual(plano, moeda, config) {
    var mensal = precoMensal(plano, moeda);
    if (mensal === null) return null;
    return arredondar(mensal * config.annual_months_charged);
  }

  function precoDoCiclo(plano, moeda, ciclo, config) {
    if (CICLOS.indexOf(ciclo) < 0) throw new Error("ciclo desconhecido: " + ciclo);
    return ciclo === "annual" ? precoAnual(plano, moeda, config) : precoMensal(plano, moeda);
  }

  /* Mensal equivalente da cobrança anual (anual / 12), para comparar planos. */
  function mensalEquivalente(plano, moeda, ciclo, config) {
    var mensal = precoMensal(plano, moeda);
    if (mensal === null) return null;
    if (ciclo !== "annual") return mensal;
    return (mensal * config.annual_months_charged) / 12;
  }

  function percentualEconomia(config) {
    return Math.round((1 - config.annual_months_charged / 12) * 100);
  }

  /* Vídeo: créditos por minuto INICIADO. 61 s = 2 minutos = 20 créditos.
     Duração zero ou inválida não consome nada: não houve vídeo a analisar. */
  function creditosVideo(segundos, config) {
    var s = Number(segundos);
    if (!isFinite(s) || s <= 0) return 0;
    return Math.ceil(s / 60) * config.credit_rules.video_per_started_minute;
  }

  function creditosImagens(quantidade, config) {
    return inteiroNaoNegativo(quantidade) * config.credit_rules.image;
  }

  function inteiroNaoNegativo(valor) {
    var n = Number(valor);
    if (!isFinite(n) || n < 0 || Math.floor(n) !== n) {
      throw new RangeError("esperado inteiro >= 0: " + valor);
    }
    return n;
  }

  /* Calculadora: a pessoa informa o total de minutos já faturáveis por mês
     (a dica na tela explica o arredondamento por vídeo). */
  function creditosEstimados(uso, config) {
    var imagens = inteiroNaoNegativo(uso.imagens || 0);
    var minutos = inteiroNaoNegativo(uso.minutosVideo || 0);
    return creditosImagens(imagens, config) + creditosVideo(minutos * 60, config);
  }

  /* Custo mensal de um plano para um volume de créditos.
     Devolve { elegivel, motivo, base, excedente, creditosExtras, total }. */
  function custoDoPlano(plano, moeda, uso, ciclo, config) {
    var creditos = creditosEstimados(uso, config);
    var base = mensalEquivalente(plano, moeda, ciclo, config);
    var fora = function (motivo) {
      return { elegivel: false, motivo: motivo, base: base, excedente: 0, creditosExtras: 0, total: null };
    };

    if (plano.price_type === "contact" || plano.price_type === "validation") return fora("contato");
    if (base === null) return fora("sem_preco");

    // Limite diário (Cidadão/Free): estimativa de uma análise por imagem e por
    // minuto de vídeo. Pendência registrada no config (video_counts_as_analysis).
    if (plano.daily_limit) {
      var analises = inteiroNaoNegativo(uso.imagens || 0) + inteiroNaoNegativo(uso.minutosVideo || 0);
      var teto = plano.daily_limit * config.calculator.days_per_month;
      return analises <= teto
        ? { elegivel: true, motivo: null, base: base, excedente: 0, creditosExtras: 0, total: base }
        : fora("acima_do_limite_diario");
    }

    if (plano.credits_included === null || plano.credits_included === undefined) return fora("creditos_indefinidos");

    var extras = Math.max(0, creditos - plano.credits_included);
    if (extras > 0) {
      if (plano.overage !== "charge" || typeof plano.overage_price !== "number") return fora("bloqueia_no_limite");
      var excedente = extras * plano.overage_price;
      return {
        elegivel: true, motivo: null, base: base, excedente: excedente,
        creditosExtras: extras, total: base + excedente,
      };
    }
    return { elegivel: true, motivo: null, base: base, excedente: 0, creditosExtras: 0, total: base };
  }

  /* Plano mais barato que atende ao volume, entre os planos da lista (uma aba
     de um mercado). Empate: o que aparece antes no config. Enterprise entra
     como sugestão quando nada atende ou quando o volume passa do limiar. */
  function recomendarPlano(planos, moeda, uso, ciclo, config) {
    var creditos = creditosEstimados(uso, config);
    var candidatos = [];
    var indefinidos = [];

    planos.forEach(function (plano, ordem) {
      var custo = custoDoPlano(plano, moeda, uso, ciclo, config);
      if (custo.motivo === "creditos_indefinidos") indefinidos.push(plano.id);
      if (custo.elegivel) candidatos.push({ plano: plano, custo: custo, ordem: ordem });
    });

    candidatos.sort(function (a, b) {
      var diferenca = arredondar(a.custo.total, 4) - arredondar(b.custo.total, 4);
      return diferenca !== 0 ? diferenca : a.ordem - b.ordem;
    });

    var temEnterprise = planos.some(function (p) { return p.price_type === "contact"; });
    var limiar = config.enterprise_threshold_credits;
    var sugerirEnterprise = temEnterprise && (candidatos.length === 0 || (limiar && creditos >= limiar));

    return {
      creditos: creditos,
      recomendado: candidatos.length ? candidatos[0].plano : null,
      custo: candidatos.length ? candidatos[0].custo : null,
      alternativas: candidatos.slice(1).map(function (c) { return { plano: c.plano, custo: c.custo }; }),
      sugerirEnterprise: sugerirEnterprise,
      indefinidos: indefinidos,
    };
  }

  /* Moeda sempre no locale do mercado (pt-BR para BRL, en-US para USD),
     independente do idioma da página: "R$ 24,90" e "$19.00".
     `excedente` mostra até 4 casas (US$ 0,0035; R$ 0,030). */
  var cacheFormatadores = {};
  function formatarMoeda(valor, moeda, config, opcoes) {
    if (valor === null || valor === undefined) return "";
    var excedente = Boolean(opcoes && opcoes.excedente);
    var chave = moeda + (excedente ? ":x" : "");
    var formatador = cacheFormatadores[chave];
    if (!formatador) {
      formatador = new Intl.NumberFormat(config.currencies[moeda].locale, {
        style: "currency",
        currency: moeda,
        minimumFractionDigits: excedente ? 3 : 2,
        maximumFractionDigits: excedente ? 4 : 2,
      });
      cacheFormatadores[chave] = formatador;
    }
    return formatador.format(valor);
  }

  function formatarNumero(valor, locale) {
    return new Intl.NumberFormat(locale).format(valor);
  }

  function idiomaPadrao(idiomas) {
    var lista = (idiomas || []).map(function (i) { return String(i).toLowerCase(); });
    return lista.some(function (i) { return i.indexOf("pt") === 0; }) ? "pt-BR" : "en-US";
  }

  /* Só visual: o servidor decide a moeda do checkout pelo CPF/CNPJ e pelo
     endereço de cobrança (aida_api/cobranca.py). */
  function mercadoPadrao(ambiente) {
    var fuso = ambiente && ambiente.fusoHorario;
    if (fuso && FUSOS_BRASIL.indexOf(fuso) >= 0) return "BR";
    var idiomas = ((ambiente && ambiente.idiomas) || []).map(function (i) { return String(i).toLowerCase(); });
    if (idiomas[0] === "pt-br" || (!fuso && idiomas[0] && idiomas[0].indexOf("pt") === 0)) return "BR";
    return "INTL";
  }

  return {
    SEGMENTOS: SEGMENTOS,
    CICLOS: CICLOS,
    arredondar: arredondar,
    moedaDe: moedaDe,
    planosDe: planosDe,
    precoMensal: precoMensal,
    precoAnual: precoAnual,
    precoDoCiclo: precoDoCiclo,
    mensalEquivalente: mensalEquivalente,
    percentualEconomia: percentualEconomia,
    creditosVideo: creditosVideo,
    creditosImagens: creditosImagens,
    creditosEstimados: creditosEstimados,
    custoDoPlano: custoDoPlano,
    recomendarPlano: recomendarPlano,
    formatarMoeda: formatarMoeda,
    formatarNumero: formatarNumero,
    idiomaPadrao: idiomaPadrao,
    mercadoPadrao: mercadoPadrao,
  };
});
