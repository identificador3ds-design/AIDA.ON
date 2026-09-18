/* ==========================================================================
   AIDA — sincronização da configuração administrativa
   ==========================================================================

   As páginas leem a configuração do admin em localStorage (AIDA_ADMIN_CONFIG).
   Este script busca a linha única de `public.admin_config` no Supabase e
   grava ali, para o que o painel decide valer em qualquer navegador — não só
   no do administrador. Também recalcula a trava de análise sem login a partir
   de `unloggedAnalysisLimit`.

   É best-effort e síncrono na ordem de carga: por isso deve vir ANTES do
   script da página. A busca em si é assíncrona; a página atual usa o que já
   estava em cache e a próxima navegação usa o valor novo.
   ========================================================================== */
(function () {
  "use strict";

  var URL_SUPABASE = "https://nwzijdudhemuibsyzpub.supabase.co";
  var CHAVE_ANON =
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";
  var CHAVE_CONFIG = "AIDA_ADMIN_CONFIG";
  var CHAVE_QTD_DESLOGADO = "AIDA_AnalisesDeslogadoQtd";
  var CHAVE_TRAVA_DESLOGADO = "AIDA_AnaliseUnlogged";

  function lerConfigLocal() {
    try {
      return JSON.parse(localStorage.getItem(CHAVE_CONFIG) || "{}") || {};
    } catch (erro) {
      return {};
    }
  }

  function limiteDeslogado(config) {
    var n = parseInt(config.unloggedAnalysisLimit, 10);
    return isNaN(n) || n < 0 ? 1 : n;
  }

  /* Trava = já usou o número de análises sem login que o admin permite. */
  function recalcularTrava(config) {
    var usadas = parseInt(localStorage.getItem(CHAVE_QTD_DESLOGADO) || "0", 10) || 0;
    var limite = limiteDeslogado(config);
    localStorage.setItem(CHAVE_TRAVA_DESLOGADO, usadas >= limite ? "true" : "false");
  }

  window.aidaRegistrarAnaliseDeslogada = function () {
    var usadas = (parseInt(localStorage.getItem(CHAVE_QTD_DESLOGADO) || "0", 10) || 0) + 1;
    localStorage.setItem(CHAVE_QTD_DESLOGADO, String(usadas));
    recalcularTrava(lerConfigLocal());
  };

  recalcularTrava(lerConfigLocal());

  if (typeof fetch !== "function") {
    return;
  }

  fetch(URL_SUPABASE + "/rest/v1/admin_config?id=eq.1&select=config", {
    headers: { apikey: CHAVE_ANON, Authorization: "Bearer " + CHAVE_ANON },
  })
    .then(function (resposta) {
      return resposta.ok ? resposta.json() : null;
    })
    .then(function (linhas) {
      var remoto = linhas && linhas[0] && linhas[0].config;
      if (!remoto || typeof remoto !== "object") {
        return;
      }
      localStorage.setItem(CHAVE_CONFIG, JSON.stringify(remoto));
      recalcularTrava(remoto);
    })
    .catch(function () {
      /* Sem rede ou sem a tabela: fica valendo o cache local. */
    });
})();
