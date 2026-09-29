/* AIDA API — status ao vivo na página index-api.html.
 *
 * Consulta GET /v1/health no host da API e mostra se o serviço responde. O
 * texto da página descreve o contrato real (aida_api/contrato.py); este
 * script só diz, sem exagero, se ele está no ar agora.
 *
 * Host: window.AIDA_API_V1_BASE (se definido) ou o padrão abaixo. Ao publicar
 * a API em outro endereço, troque API_V1_PADRAO e libere o host em
 * connect-src no vercel.json.
 */
(function () {
  "use strict";

  var API_V1_PADRAO = "https://aidaon-aida-api.hf.space";
  var base = String(window.AIDA_API_V1_BASE || API_V1_PADRAO).replace(/\/+$/, "");

  var caixa = document.getElementById("apiStatus");
  var titulo = document.getElementById("apiStatusTitulo");
  var texto = document.getElementById("apiStatusTexto");
  if (!caixa || !titulo || !texto) return;

  function estado(tipo, t, d) {
    caixa.className = "aida-state aida-state--" + tipo;
    titulo.textContent = t;
    texto.textContent = d;
  }

  var controle = typeof AbortController === "function" ? new AbortController() : null;
  var prazo = setTimeout(function () { if (controle) controle.abort(); }, 15000);

  fetch(base + "/v1/health", { cache: "no-store", signal: controle ? controle.signal : undefined })
    .then(function (resposta) {
      return resposta.json().catch(function () { return {}; }).then(function (corpo) {
        return { ok: resposta.ok, corpo: corpo };
      });
    })
    .then(function (r) {
      clearTimeout(prazo);
      var corpo = r.corpo || {};
      // /v1/health responde 200 com status "ok" e 503 com "degraded" (aida_api/app.py).
      if (r.ok && corpo.status === "ok") {
        var latencia = corpo.core && (corpo.core.latency_ms || corpo.core.latencia_ms);
        estado("sucesso", "API no ar",
          "O serviço respondeu agora" + (latencia ? " (Core em " + Math.round(latencia) + " ms)" : "") +
          ". Com uma chave, você já pode integrar.");
      } else if (corpo.status === "degraded") {
        estado("baixa-confianca", "API no ar com restrições",
          "O serviço responde, mas algum módulo ou o Core está degradado. Os resultados podem demorar.");
      } else {
        estado("desenvolvimento", "API temporariamente indisponível",
          "O serviço não respondeu à verificação de saúde. O contrato abaixo continua valendo; tente de novo mais tarde.");
      }
    })
    .catch(function () {
      clearTimeout(prazo);
      estado("desenvolvimento", "API temporariamente indisponível",
        "Não foi possível falar com o serviço agora. O contrato abaixo continua valendo; tente de novo mais tarde.");
    });
})();
