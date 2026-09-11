/* ==========================================================================
   AIDA — verificacao de acesso administrativo
   ==========================================================================

   Regra: o front-end NUNCA guarda senha e NUNCA decide sozinho quem e admin.
   Quem decide e o Supabase, atraves do papel gravado no JWT da sessao:

     - `app_metadata.role === "admin"`  (gravado apenas com a service_role key)
     - ou `app_metadata.claims_admin === true`

   `app_metadata` nao pode ser alterado pelo proprio usuario nem pelo navegador,
   e vem assinado dentro do token. Por isso e um sinal confiavel, ao contrario
   do antigo `localStorage.usuarioTipo`, que qualquer visitante podia forjar
   pelo console.

   A checagem no navegador serve para esconder a interface. A protecao real dos
   dados fica nas policies de Row Level Security do banco — ver
   `docs/supabase-admin-setup.sql`.
   ========================================================================== */

(function () {
  "use strict";

  /* E-mail institucional do administrador. E identificacao, nao credencial:
     pode ficar publico, pois sozinho nao da acesso a nada. */
  const ADMIN_EMAIL_PADRAO = "admin@gmail.com";

  function papeisDaSessao(session) {
    const user = session?.user || null;

    if (!user) {
      return [];
    }

    const appMetadata = user.app_metadata || {};
    const papeis = [];

    if (appMetadata.role) {
      papeis.push(String(appMetadata.role).toLowerCase());
    }

    if (Array.isArray(appMetadata.roles)) {
      appMetadata.roles.forEach((papel) => papeis.push(String(papel).toLowerCase()));
    }

    if (appMetadata.claims_admin === true) {
      papeis.push("admin");
    }

    return papeis;
  }

  function sessaoEhAdmin(session) {
    return papeisDaSessao(session).includes("admin");
  }

  /* Consulta a sessao atual no Supabase e responde se ela tem papel de admin.
     Sempre assincrono: nunca ha resposta "confiavel" sem falar com o backend. */
  async function verificarAdmin(client) {
    if (!client?.auth) {
      return { autenticado: false, admin: false, session: null };
    }

    try {
      const { data, error } = await client.auth.getSession();

      if (error) {
        console.warn("Nao foi possivel verificar a sessao:", error);
        return { autenticado: false, admin: false, session: null };
      }

      const session = data?.session || null;

      return {
        autenticado: Boolean(session?.user),
        admin: sessaoEhAdmin(session),
        session,
      };
    } catch (erro) {
      console.warn("Falha ao verificar a sessao administrativa:", erro);
      return { autenticado: false, admin: false, session: null };
    }
  }

  window.AidaAdminAuth = {
    ADMIN_EMAIL_PADRAO,
    papeisDaSessao,
    sessaoEhAdmin,
    verificarAdmin,
  };
})();
