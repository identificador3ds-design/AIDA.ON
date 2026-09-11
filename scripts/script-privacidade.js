/* O botao "voltar" precisa levar de volta a tela de origem: o perfil, quando o
   usuario ja esta logado, e o login quando ainda nao esta. Quem chama passa
   isso em `?from=`. */
(function () {
  "use strict";

  const botaoVoltar = document.getElementById("privacyBackLink");

  if (!botaoVoltar) {
    return;
  }

  const origem = new URLSearchParams(window.location.search).get("from");
  botaoVoltar.href = origem === "perfil" ? "./index-perfil.html" : "./index-login.html";
})();
