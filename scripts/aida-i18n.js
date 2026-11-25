/* ==========================================================================
   AIDA — textos traduzidos
   ==========================================================================

   Os textos vivem em `i18n/<pagina>.<idioma>.json` (chave plana -> texto).
   No HTML, o elemento declara a chave:

     <h2 data-i18n="faq.title"></h2>
     <button data-i18n-attr="aria-label:contact.close"></button>

   O HTML publicado já sai preenchido em pt-BR por docs/gerar_pagina_precos.py
   (SEO e primeira pintura sem esperar o JS); este script reaplica no idioma
   escolhido. `{nome}` no texto é trocado pelo valor passado em `t`.
   ========================================================================== */
(function (raiz, fabrica) {
  "use strict";
  var modulo = fabrica();
  if (typeof module === "object" && module.exports) {
    module.exports = modulo;
  } else {
    raiz.AidaI18n = modulo;
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var IDIOMAS = ["pt-BR", "en-US"];

  function criar(dicionario) {
    /* Chave ausente aparece como a própria chave: um texto faltando fica
       visível na tela e nos testes, em vez de sumir em silêncio. */
    return function t(chave, valores) {
      var texto = Object.prototype.hasOwnProperty.call(dicionario, chave) ? dicionario[chave] : chave;
      if (!valores) return texto;
      return texto.replace(/\{(\w+)\}/g, function (inteiro, nome) {
        return Object.prototype.hasOwnProperty.call(valores, nome) ? String(valores[nome]) : inteiro;
      });
    };
  }

  function aplicar(raizDom, t) {
    raizDom.querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
    raizDom.querySelectorAll("[data-i18n-attr]").forEach(function (el) {
      el.getAttribute("data-i18n-attr").split(";").forEach(function (par) {
        var partes = par.split(":");
        if (partes.length === 2) el.setAttribute(partes[0].trim(), t(partes[1].trim()));
      });
    });
  }

  function carregar(pagina, idioma, base) {
    if (IDIOMAS.indexOf(idioma) < 0) idioma = IDIOMAS[0];
    return fetch((base || "..") + "/i18n/" + pagina + "." + idioma + ".json", { cache: "no-cache" })
      .then(function (resposta) {
        if (!resposta.ok) throw new Error("i18n " + idioma + ": HTTP " + resposta.status);
        return resposta.json();
      });
  }

  return { IDIOMAS: IDIOMAS, criar: criar, aplicar: aplicar, carregar: carregar };
});
