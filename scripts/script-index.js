/* Pagina raiz. Normalmente so encaminha para a apresentacao (o meta refresh
   cobre quem esta sem JavaScript). A excecao e o retorno do OAuth: se o
   Supabase devolver o ?code= (ou ?error=) para a raiz em vez de /login, a
   query precisa ser preservada, senao o code nunca vira sessao e o usuario
   volta deslogado. O vercel.json faz o mesmo na borda; aqui cobre o uso local. */
(function () {
  var busca = new URLSearchParams(window.location.search);
  var hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  var retornoOAuth =
    busca.has("code") || busca.has("error") ||
    hash.has("access_token") || hash.has("error");

  if (retornoOAuth) {
    window.location.replace(
      "pages/index-login.html" + window.location.search + window.location.hash
    );
  }
})();
