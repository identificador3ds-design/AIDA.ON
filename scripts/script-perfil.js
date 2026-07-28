const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);
const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const CHAVE_LOGIN_FEEDBACK = "AIDA_LOGIN_FEEDBACK";
const CONFIG_ADMIN_PADRAO = {
  allowRegistrations: true,
  enableInstallPrompt: true,
  maintenanceMode: false,
  allowProfilePage: true,
  supportEmail: ADMIN_EMAIL,
  announcementMessage: "",
  accountStates: {},
};
const favicon = document.getElementById('favicon');

function updateFavicon() {
  if (!favicon) {
    return;
  }

  if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    favicon.href = '../assets/images/AIDABranco.ico';
  } else {
    favicon.href = '../assets/images/AIDAPreto.ico';
  }
}


updateFavicon();

function limparSessaoLocal() {
  localStorage.removeItem("usuarioNome");
  localStorage.removeItem("usuarioEmail");
  localStorage.removeItem("usuarioTipo");
}

function limparDadosLocaisUsuario() {
  limparSessaoLocal();
  localStorage.removeItem("AIDA_ImagemSelecionada");
  sessionStorage.removeItem("AIDA_ImagemSelecionada");

  if (window.indexedDB) {
    indexedDB.deleteDatabase("AIDA_ImagemSelecionada_DB");
  }
}

async function removerEvidenciasUsuario(userId) {
  const { data, error } = await _supabase.storage.from("evidencias").list(userId, {
    limit: 1000,
  });

  if (error) {
    throw error;
  }

  const caminhos = (data || [])
    .filter((item) => item?.name && item.name !== ".emptyFolderPlaceholder")
    .map((item) => `${userId}/${item.name}`);

  if (!caminhos.length) {
    return;
  }

  const { error: removeError } = await _supabase.storage.from("evidencias").remove(caminhos);

  if (removeError) {
    throw removeError;
  }
}

async function excluirContaEDados() {
  const {
    data: { user },
    error: userError,
  } = await _supabase.auth.getUser();

  if (userError || !user) {
    throw new Error("Sua sessao expirou. Entre novamente para excluir a conta.");
  }

  await removerEvidenciasUsuario(user.id);

  const { error } = await _supabase.rpc("excluir_minha_conta");

  if (error) {
    throw new Error(
      error.message?.includes("excluir_minha_conta")
        ? "A exclusao ainda nao esta configurada no servidor. Contate o suporte."
        : error.message || "Nao foi possivel excluir sua conta agora."
    );
  }

  limparDadosLocaisUsuario();

  try {
    await _supabase.auth.signOut({ scope: "local" });
  } catch (erro) {
    console.warn("A conta foi excluida, mas a sessao local ja estava encerrada:", erro);
  }
}

async function sairParaLogin(destino = "./index-login.html") {
  limparSessaoLocal();

  try {
    await _supabase.auth.signOut();
  } catch (erro) {
    console.warn("Nao foi possivel encerrar a sessao do Supabase:", erro);
  }

  window.location.href = destino;
}

function obterAdminConfig() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_ADMIN_CONFIG) || "{}");
    const accountStates = {};

    if (salvo.accountStates && typeof salvo.accountStates === "object") {
      Object.entries(salvo.accountStates).forEach(([email, dados]) => {
        const emailNormalizado = String(email || "").trim().toLowerCase();

        if (!emailNormalizado || emailNormalizado === ADMIN_EMAIL) {
          return;
        }

        accountStates[emailNormalizado] = {
          status: ["active", "blocked", "deleted"].includes(dados?.status)
            ? dados.status
            : "active",
        };
      });
    }

    return { ...CONFIG_ADMIN_PADRAO, ...salvo, accountStates };
  } catch (erro) {
    return { ...CONFIG_ADMIN_PADRAO };
  }
}

function contaAtualSemAcesso() {
  const email = (localStorage.getItem("usuarioEmail") || "").trim().toLowerCase();

  if (!email || email === ADMIN_EMAIL) {
    return false;
  }

  const status = obterAdminConfig().accountStates[email]?.status || "active";
  return ["blocked", "deleted"].includes(status);
}

function renderizarAvisoSistema() {
  const configuracao = obterAdminConfig();
  const mensagem = String(configuracao.announcementMessage || "").trim();
  const mensagens = [];
  let possuiAvisoPrincipal = false;

  if (configuracao.maintenanceMode) {
    mensagens.push("Modo manutencao ativo.");
    possuiAvisoPrincipal = true;
  }

  if (mensagem) {
    mensagens.push(mensagem);
    possuiAvisoPrincipal = true;
  }

  if (possuiAvisoPrincipal && configuracao.supportEmail) {
    mensagens.push(`Contato: ${configuracao.supportEmail}.`);
  }

  if (!mensagens.length) {
    return;
  }

  if (document.getElementById("systemNotice")) {
    return;
  }

  const aviso = document.createElement("section");
  aviso.id = "systemNotice";
  aviso.className = "system-notice";
  const conteudo = document.createElement("div");
  conteudo.className = "system-notice-inner";

  const etiqueta = document.createElement("span");
  etiqueta.className = "system-notice-kicker";
  etiqueta.textContent = "Aviso do sistema";

  const texto = document.createElement("p");
  texto.textContent = mensagens.join(" ");

  conteudo.appendChild(etiqueta);
  conteudo.appendChild(texto);
  aviso.appendChild(conteudo);

  document.body.appendChild(aviso);
}

async function obterQuantidadeAnalisesUsuario() {
  try {
    const {
      data: { user },
    } = await _supabase.auth.getUser();

    if (!user) {
      return 0;
    }

    const { count, error } = await _supabase
      .from("historico_analises")
      .select("*", { count: "exact", head: true })
      .eq("user_id", user.id);

    if (error) {
      console.error("Erro ao buscar quantidade de analises:", error);
      return 0;
    }

    return Number(count || 0);
  } catch (erro) {
    console.error("Erro ao consultar analises do usuario:", erro);
    return 0;
  }
}

async function atualizarPerfilUsuario({ nome, email, tipoUsuarioAtual }) {
  if (tipoUsuarioAtual === "admin") {
    localStorage.setItem("usuarioNome", nome);
    localStorage.setItem("usuarioEmail", email);
    return { ok: true, mensagem: "Informações atualizadas com sucesso." };
  }

  const {
    data: { user },
  } = await _supabase.auth.getUser();

  if (!user) {
    localStorage.setItem("usuarioNome", nome);
    localStorage.setItem("usuarioEmail", email);
    return { ok: true, mensagem: "Informações atualizadas localmente." };
  }

  const emailAlterado = user.email !== email;
  const { error: authUpdateError } = await _supabase.auth.updateUser(
    emailAlterado
      ? { email, data: { full_name: nome } }
      : { data: { full_name: nome } }
  );

  if (authUpdateError) {
    return { ok: false, mensagem: authUpdateError.message };
  }

  const { error: userTableError } = await _supabase
    .from("usuarios")
    .update({ nome, email })
    .eq("email", user.email);

  if (userTableError) {
    console.error("Erro ao atualizar tabela de usuarios:", userTableError);
  }

  localStorage.setItem("usuarioNome", nome);
  localStorage.setItem("usuarioEmail", email);

  return {
    ok: true,
    mensagem: emailAlterado
      ? "Informações atualizadas. Confira seu email para confirmar a troca de endereço."
      : "Informações atualizadas com sucesso.",
  };
}

document.addEventListener("DOMContentLoaded", async () => {
  const configuracaoAdmin = obterAdminConfig();

  if (!configuracaoAdmin.allowProfilePage && !localStorage.getItem("usuarioTipo")?.includes("admin")) {
    window.location.href = "./index-apresentacao.html";
    return;
  }

  if (contaAtualSemAcesso()) {
    limparSessaoLocal();
    localStorage.setItem(
      CHAVE_LOGIN_FEEDBACK,
      "Seu acesso foi bloqueado pelo administrador."
    );
    window.location.href = "./index-login.html";
    return;
  }

  renderizarAvisoSistema();
  const nomeSalvo = localStorage.getItem("usuarioNome");
  const emailSalvo = localStorage.getItem("usuarioEmail");
  const tipoSalvo = localStorage.getItem("usuarioTipo");
  const nome = document.getElementById("nome-usuario");
  const email = document.getElementById("email-usuario");
  const infoNome = document.getElementById("profile-info-name");
  const infoEmail = document.getElementById("profile-info-email");
  const infoPerfil = document.getElementById("profile-info-role");
  const infoAnalises = document.getElementById("profile-info-analyses");
  const editButton = document.getElementById("edit-profile-button");
  const editModal = document.getElementById("profile-edit-modal");
  const editForm = document.getElementById("profile-edit-form");
  const editNameInput = document.getElementById("edit-profile-name");
  const editEmailInput = document.getElementById("edit-profile-email");
  const editFeedback = document.getElementById("profile-edit-feedback");
  const logoutLink = document.getElementById("logout-link");
  const switchAccountLink = document.getElementById("switch-account-link");
  const deleteAccountZone = document.getElementById("profile-delete-zone");
  const deleteAccountButton = document.getElementById("delete-account-button");
  const deleteAccountModal = document.getElementById("delete-account-modal");
  const deleteAccountForm = document.getElementById("delete-account-form");
  const deleteAccountConfirmation = document.getElementById("delete-account-confirmation");
  const deleteAccountFeedback = document.getElementById("delete-account-feedback");
  const confirmDeleteAccount = document.getElementById("confirm-delete-account");
  const adminLink = document.createElement("a");
  const rotuloPerfil = tipoSalvo === "admin" ? "Administrador" : "Usuario";
  let nomeExibicao = tipoSalvo === "admin" ? "Admin" : nomeSalvo || "Usuario";
  let emailExibicao = emailSalvo || "usuarioaida@gmail.com";

  const aplicarDadosPerfil = () => {
    if (nome) {
      nome.textContent = nomeExibicao;
    }

    if (email) {
      email.textContent = emailExibicao;
    }

    if (infoNome) {
      infoNome.textContent = nomeExibicao;
    }

    if (infoEmail) {
      infoEmail.textContent = emailExibicao;
    }

    if (infoPerfil) {
      infoPerfil.textContent = rotuloPerfil;
    }
  };

  aplicarDadosPerfil();

  if (infoAnalises) {
    infoAnalises.textContent = String(await obterQuantidadeAnalisesUsuario());
  }

  const fecharModalEdicao = () => {
    if (!editModal || !editFeedback) {
      return;
    }

    editModal.hidden = true;
    editFeedback.hidden = true;
    editFeedback.textContent = "";
    editFeedback.classList.remove("error");
  };

  const abrirModalEdicao = () => {
    if (!editModal || !editNameInput || !editEmailInput || !editFeedback) {
      return;
    }

    editNameInput.value = nomeExibicao;
    editEmailInput.value = emailExibicao;
    editModal.hidden = false;
    editFeedback.hidden = true;
    editFeedback.textContent = "";
    editFeedback.classList.remove("error");
    editNameInput.focus();
  };

  if (editButton) {
    editButton.addEventListener("click", abrirModalEdicao);
  }

  document.querySelectorAll("[data-close-profile-modal]").forEach((elemento) => {
    elemento.addEventListener("click", fecharModalEdicao);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && editModal && !editModal.hidden) {
      fecharModalEdicao();
    }

    if (event.key === "Escape" && deleteAccountModal && !deleteAccountModal.hidden) {
      fecharModalExclusao();
    }
  });

  if (editForm && editNameInput && editEmailInput && editFeedback) {
    editForm.addEventListener("submit", async (event) => {
      event.preventDefault();

      const nomeAtualizado = editNameInput.value.trim();
      const emailAtualizado = editEmailInput.value.trim().toLowerCase();

      if (!nomeAtualizado || !emailAtualizado) {
        editFeedback.hidden = false;
        editFeedback.textContent = "Preencha nome e email para continuar.";
        editFeedback.classList.add("error");
        return;
      }

      const botaoSalvar = editForm.querySelector('button[type="submit"]');

      if (botaoSalvar) {
        botaoSalvar.disabled = true;
      }

      const resultado = await atualizarPerfilUsuario({
        nome: nomeAtualizado,
        email: emailAtualizado,
        tipoUsuarioAtual: tipoSalvo,
      });

      if (botaoSalvar) {
        botaoSalvar.disabled = false;
      }

      if (!resultado.ok) {
        editFeedback.hidden = false;
        editFeedback.textContent = resultado.mensagem || "Nao foi possivel atualizar suas informacoes.";
        editFeedback.classList.add("error");
        return;
      }

      nomeExibicao = nomeAtualizado;
      emailExibicao = emailAtualizado;
      aplicarDadosPerfil();
      fecharModalEdicao();
    });
  }

  if (tipoSalvo === "admin") {
    if (deleteAccountZone) {
      deleteAccountZone.hidden = true;
    }

    adminLink.href = "./index-admin.html";
    adminLink.className = "profile-action glass-card";
    adminLink.innerHTML = `
      <span class="action-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M12 3L4 7V12C4 17 7.4 21.2 12 22C16.6 21.2 20 17 20 12V7L12 3Z" />
          <path d="M9.5 12L11.2 13.7L14.8 10.1" />
        </svg>
      </span>
      <strong>Painel admin</strong>
    `;

    const actions = document.querySelector(".profile-actions");

    if (actions) {
      actions.insertBefore(adminLink, actions.firstChild);
    }
  }

  const fecharModalExclusao = () => {
    if (!deleteAccountModal || !deleteAccountForm || !deleteAccountFeedback) {
      return;
    }

    deleteAccountModal.hidden = true;
    deleteAccountForm.reset();
    deleteAccountFeedback.hidden = true;
    deleteAccountFeedback.textContent = "";
    deleteAccountFeedback.classList.remove("error");

    if (confirmDeleteAccount) {
      confirmDeleteAccount.disabled = true;
    }
  };

  if (deleteAccountButton && deleteAccountModal && deleteAccountConfirmation) {
    deleteAccountButton.addEventListener("click", () => {
      deleteAccountModal.hidden = false;
      deleteAccountConfirmation.focus();
    });
  }

  document.querySelectorAll("[data-close-delete-modal]").forEach((elemento) => {
    elemento.addEventListener("click", fecharModalExclusao);
  });

  if (deleteAccountConfirmation && confirmDeleteAccount) {
    deleteAccountConfirmation.addEventListener("input", () => {
      confirmDeleteAccount.disabled = deleteAccountConfirmation.value.trim() !== "EXCLUIR";
    });
  }

  if (deleteAccountForm && deleteAccountConfirmation && deleteAccountFeedback && confirmDeleteAccount) {
    deleteAccountForm.addEventListener("submit", async (event) => {
      event.preventDefault();

      if (deleteAccountConfirmation.value.trim() !== "EXCLUIR") {
        return;
      }

      confirmDeleteAccount.disabled = true;
      deleteAccountConfirmation.disabled = true;
      deleteAccountFeedback.hidden = false;
      deleteAccountFeedback.textContent = "Excluindo seus dados. Aguarde...";
      deleteAccountFeedback.classList.remove("error");

      try {
        await excluirContaEDados();
        window.location.replace("./index-login.html?conta_excluida=1");
      } catch (erro) {
        deleteAccountConfirmation.disabled = false;
        confirmDeleteAccount.disabled = false;
        deleteAccountFeedback.textContent = erro.message || "Nao foi possivel excluir sua conta agora.";
        deleteAccountFeedback.classList.add("error");
      }
    });
  }

  if (logoutLink) {
    logoutLink.addEventListener("click", (event) => {
      event.preventDefault();
      sairParaLogin("./index-login.html");
    });
  }

  if (switchAccountLink) {
    switchAccountLink.addEventListener("click", (event) => {
      event.preventDefault();
      sairParaLogin("./index-login.html?trocar_conta=1");
    });
  }
});


