/* ==========================================================================
   AIDA — verificacao de acesso administrativo
   ==========================================================================

   Regra: o front-end NUNCA guarda senha e NUNCA decide sozinho quem e admin.
   Quem decide e o Supabase. O banco so responde como admin quando a sessao:

     - traz `app_metadata.role === "admin"` no JWT (gravado so pela service role);
     - passou pelo segundo fator TOTP (`aal2`);
     - pertence a uma conta listada em `public.admin_contas`.

   Ver `docs/migracao-admin-seguro.sql` (funcao `public.e_admin()`).

   As funcoes abaixo servem para escolher qual tela mostrar. Elas leem o JWT
   no navegador, entao sao DICA de interface: a protecao real dos dados fica
   nas policies de Row Level Security e nas funcoes do banco.
   ========================================================================== */

(function () {
  "use strict";

  /* Contato de suporte exibido nas paginas publicas. Nao e a conta que entra
     no painel: o e-mail administrativo nao e publicado no front-end. */
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

  /* Nivel de garantia da sessao: "aal1" (so senha) ou "aal2" (senha + TOTP).
     `proximo` e "aal2" quando a conta ja tem autenticador cadastrado. */
  async function nivelGarantia(client) {
    try {
      const { data, error } = await client.auth.mfa.getAuthenticatorAssuranceLevel();

      if (error) {
        return { atual: null, proximo: null };
      }

      return { atual: data?.currentLevel || null, proximo: data?.nextLevel || null };
    } catch (erro) {
      return { atual: null, proximo: null };
    }
  }

  window.AidaAdminAuth = {
    ADMIN_EMAIL_PADRAO,
    papeisDaSessao,
    sessaoEhAdmin,
    verificarAdmin,
    nivelGarantia,
  };
})();
