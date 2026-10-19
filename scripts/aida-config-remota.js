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
      // admin_config deixou de publicar `accountStates` (tinha e-mails e era público).
      // O estado vem de `usuarios.status`, só da própria conta (ver abaixo).
      // Mantém só a entrada da própria conta: o mapa antigo, vindo da configuração
      // pública, podia guardar e-mails de outras pessoas neste navegador.
      var anteriores = lerConfigLocal().accountStates || {};
      var proprio = emailDaSessao();
      remoto.accountStates = {};
      if (proprio && anteriores[proprio]) {
        remoto.accountStates[proprio] = anteriores[proprio];
      }
      localStorage.setItem(CHAVE_CONFIG, JSON.stringify(remoto));
      recalcularTrava(remoto);
      return aplicarStatusDaPropriaConta();
    })
    .catch(function () {
      /* Sem rede ou sem a tabela: fica valendo o cache local. */
    });

  /* Lê `usuarios.status` da conta logada e grava em accountStates[email], que é o que as
     páginas consultam para bloquear. Sem filtro por e-mail na URL: o RLS só devolve a
     própria linha (o admin recebe todas e escolhe a dele). O bloqueio de verdade é no
     servidor — o RLS do histórico recusa conta que não está 'active'. */
  function lerSessao() {
    try {
      return JSON.parse(localStorage.getItem("sb-nwzijdudhemuibsyzpub-auth-token") || "null");
    } catch (erro) {
      return null;
    }
  }

  function emailDaSessao() {
    var sessao = lerSessao();
    return sessao && sessao.user ? String(sessao.user.email || "").trim().toLowerCase() : "";
  }

  function aplicarStatusDaPropriaConta() {
    var sessao = lerSessao();
    var token = sessao && sessao.access_token;
    var email = emailDaSessao();
    if (!token || !email) {
      return;
    }
    return fetch(URL_SUPABASE + "/rest/v1/usuarios?select=email,status", {
      headers: { apikey: CHAVE_ANON, Authorization: "Bearer " + token },
    })
      .then(function (resposta) {
        return resposta.ok ? resposta.json() : null;
      })
      .then(function (linhas) {
        if (!Array.isArray(linhas)) {
          return;
        }
        var propria = linhas.filter(function (l) {
          return String(l.email || "").trim().toLowerCase() === email;
        })[0];
        var config = lerConfigLocal();
        config.accountStates = config.accountStates || {};
        if (propria && propria.status && propria.status !== "active") {
          config.accountStates[email] = { status: propria.status };
        } else {
          delete config.accountStates[email];
        }
        localStorage.setItem(CHAVE_CONFIG, JSON.stringify(config));
      });
  }
})();
