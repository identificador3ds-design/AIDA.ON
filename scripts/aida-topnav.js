/* Menu do topo: o mesmo comportamento em todas as páginas.
 * Sem login, "Histórico" some e "Minha conta" vira "Entrar" (antes só a tela de
 * análise fazia isso; nas outras o visitante caía no perfil vazio). */
(function () {
  "use strict";
  const nav = document.querySelector(".aida-topnav");
  if (!nav) return;
  let logado = false;
  try {
    logado = Boolean(localStorage.getItem("usuarioNome") || localStorage.getItem("usuarioEmail"));
  } catch (_) { /* modo privado: trata como visitante */ }
  if (logado) return;
  const historico = nav.querySelector('[data-nav="historico"]');
  if (historico) historico.hidden = true;
  const conta = nav.querySelector('[data-nav="conta"]');
  if (conta) {
    conta.textContent = "Entrar";
    conta.href = "./index-login.html";
  }
})();
