// Conexao com o banco
const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const CHAVE_LOGIN_FEEDBACK = "AIDA_LOGIN_FEEDBACK";
const CHAVE_ADMIN_REDIRECT_MESSAGE = "AIDA_ADMIN_REDIRECT_MESSAGE";



const signinForm = document.querySelector(".form.signin");
const signupForm = document.querySelector(".form.signup");
const formsStage = document.querySelector(".forms-stage");
const modeButtons = document.querySelectorAll("[data-mode-target]");
const heading = document.querySelector("[data-mode-heading]");
const description = document.querySelector("[data-mode-description]");
const authCard = document.querySelector(".auth-card");
const brandSigninCopy = document.querySelector("[data-copy-signin]");
const brandSignupCopy = document.querySelector("[data-copy-signup]");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const favicon = document.getElementById('favicon');
const googleAuthButtons = document.querySelectorAll("[data-google-auth]");
const privacyAgreement = document.getElementById("privacyAgreement");

function updateFavicon() {

  if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    favicon.href = '../assets/images/AIDABranco.ico';
  } else {
    favicon.href = '../assets/images/AIDAPreto.ico';
  }
}


updateFavicon();
const CONFIG_ADMIN_PADRAO = {
  accountStates: {},
};

const modeContent = {
  signin: {
    heading: "Entrar no AIDA",
    description:
      "Acesse sua conta para continuar com suas analises e acompanhar seu ambiente de trabalho.",
  },
  signup: {
    heading: "Criar conta no AIDA",
    description:
      "Configure seu acesso em poucos passos e entre na plataforma com seguranca e praticidade.",
  },
};

const limparSessaoLocal = () => {
  localStorage.removeItem("usuarioNome");
  localStorage.removeItem("usuarioEmail");
  localStorage.removeItem("usuarioTipo");
};

function normalizarEstadosConta(salvo = {}) {
  const accountStates = {};

  if (!salvo || typeof salvo !== "object" || Array.isArray(salvo)) {
    return accountStates;
  }

  Object.entries(salvo).forEach(([email, dados]) => {
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

  return accountStates;
}

function obterAdminConfig() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_ADMIN_CONFIG) || "{}");

    return {
      ...CONFIG_ADMIN_PADRAO,
      ...salvo,
      accountStates: normalizarEstadosConta(salvo.accountStates),
    };
  } catch (erro) {
    return { ...CONFIG_ADMIN_PADRAO };
  }
}

function obterStatusConta(email) {
  const emailNormalizado = String(email || "").trim().toLowerCase();

  if (!emailNormalizado || emailNormalizado === ADMIN_EMAIL) {
    return "active";
  }

  return obterAdminConfig().accountStates[emailNormalizado]?.status || "active";
}

function contaSemAcesso(email) {
  return ["blocked", "deleted"].includes(obterStatusConta(email));
}

function mostrarAviso(texto, tipo = "sucesso") {
  const container = document.getElementById("toast-container");

  if (!container) {
    return;
  }

  const toast = document.createElement("div");
  const tipoClasse = {
    erro: "erro",
    cadastro: "cadastro",
    "cadastro-erro": "cadastro erro",
  };

  toast.className = `toast-msg ${tipoClasse[tipo] || ""}`.trim();
  toast.innerText = texto;

  container.innerHTML = "";
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 280);
  }, 3200);
}

function consumirAvisosPendentes() {
  const feedbackLogin = localStorage.getItem(CHAVE_LOGIN_FEEDBACK);

  if (feedbackLogin) {
    localStorage.removeItem(CHAVE_LOGIN_FEEDBACK);
    mostrarAviso(feedbackLogin);
    return;
  }

  const feedbackAdmin = localStorage.getItem(CHAVE_ADMIN_REDIRECT_MESSAGE);

  if (feedbackAdmin) {
    localStorage.removeItem(CHAVE_ADMIN_REDIRECT_MESSAGE);
    mostrarAviso(feedbackAdmin, "erro");
  }
}

function setMode(mode) {
  const isSignin = mode === "signin";

  if (formsStage) {
    formsStage.dataset.authMode = mode;
  }

  if (authCard) {
    authCard.dataset.authMode = mode;
  }

  if (signinForm && signupForm) {
    signinForm.classList.toggle("active", isSignin);
    signupForm.classList.toggle("active", !isSignin);
    signinForm.setAttribute("aria-hidden", String(!isSignin));
    signupForm.setAttribute("aria-hidden", String(isSignin));
  }

  if (brandSigninCopy) {
    brandSigninCopy.classList.toggle("active", !isSignin);
  }

  if (brandSignupCopy) {
    brandSignupCopy.classList.toggle("active", isSignin);
  }

  modeButtons.forEach((button) => {
    const active = button.dataset.modeTarget === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });

  if (heading) {
    heading.textContent = modeContent[mode].heading;
  }

  if (description) {
    description.textContent = modeContent[mode].description;
  }
}

function toggleView() {
  const modoAtual = authCard?.dataset.authMode || "signin";
  const nextMode = modoAtual === "signin" ? "signup" : "signin";
  setMode(nextMode);
}

function obterUrlRetornoOAuth() {
  return `${window.location.origin}${window.location.pathname}`;
}

function obterNomeUsuario(user) {
  const nomeMetadados =
    user?.user_metadata?.full_name ||
    user?.user_metadata?.name ||
    user?.identities?.[0]?.identity_data?.full_name ||
    user?.identities?.[0]?.identity_data?.name;

  if (nomeMetadados) {
    return nomeMetadados;
  }

  return user?.email?.split("@")[0] || "usuario";
}

async function salvarUsuarioNaTabela(user) {
  const email = String(user?.email || "").trim().toLowerCase();

  if (!email) {
    return;
  }

  const nome = obterNomeUsuario(user);

  try {
    const { error } = await _supabase
      .from("usuarios")
      .upsert([{ nome, email }], { onConflict: "email" });

    if (error) {
      console.warn("Nao foi possivel salvar o usuario na tabela usuarios:", error);
    }
  } catch (erro) {
    console.warn("Nao foi possivel sincronizar o usuario:", erro);
  }
}

async function finalizarLoginUsuario(user, mensagemBoasVindas = true) {
  const emailUsuario = String(user?.email || "").trim().toLowerCase();

  if (!emailUsuario) {
    mostrarAviso("Nao foi possivel identificar o email da conta.", "erro");
    return false;
  }

  if (contaSemAcesso(emailUsuario)) {
    limparSessaoLocal();

    try {
      await _supabase.auth.signOut();
    } catch (erro) {
      console.warn("Nao foi possivel encerrar a sessao bloqueada do Supabase:", erro);
    }

    mostrarAviso("Esta conta foi bloqueada pelo administrador.", "erro");
    return false;
  }

  const nomeUsuario = obterNomeUsuario(user);

  await salvarUsuarioNaTabela(user);
  limparSessaoLocal();
  localStorage.setItem("usuarioNome", nomeUsuario);
  localStorage.setItem("usuarioEmail", emailUsuario);

  if (emailUsuario === ADMIN_EMAIL) {
    localStorage.setItem("usuarioTipo", "admin");
  }

  localStorage.removeItem(CHAVE_LOGIN_FEEDBACK);
  localStorage.removeItem(CHAVE_ADMIN_REDIRECT_MESSAGE);

  if (mensagemBoasVindas) {
    mostrarAviso(`Bem-vindo, ${nomeUsuario}!`);
  }

  setTimeout(() => {
    window.location.href = "./index-apresentacao.html";
  }, 1250);

  return true;
}

async function processarRetornoOAuth() {
  const possuiRetornoOAuth =
    window.location.search.includes("code=") ||
    window.location.hash.includes("access_token") ||
    window.location.hash.includes("error");

  if (!possuiRetornoOAuth) {
    return;
  }

  const {
    data: { session },
    error,
  } = await _supabase.auth.getSession();

  if (error) {
    mostrarAviso("Nao foi possivel concluir o login com Google.", "erro");
    return;
  }

  if (session?.user) {
    await finalizarLoginUsuario(session.user);
  }
}

modeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setMode(button.dataset.modeTarget);
  });
});

googleAuthButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    if (button.closest(".signup") && privacyAgreement && !privacyAgreement.checked) {
      mostrarAviso("Leia e aceite o Aviso de Privacidade para continuar com Google.", "cadastro-erro");
      return;
    }

    googleAuthButtons.forEach((item) => {
      item.disabled = true;
    });

    const { error } = await _supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: obterUrlRetornoOAuth(),
        queryParams: {
          prompt: "select_account",
        },
      },
    });

    if (error) {
      googleAuthButtons.forEach((item) => {
        item.disabled = false;
      });
      mostrarAviso("Nao foi possivel iniciar o login com Google.", "erro");
    }
  });
});

registerForm?.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (privacyAgreement && !privacyAgreement.checked) {
    mostrarAviso("Leia e aceite o Aviso de Privacidade para criar a conta.", "cadastro-erro");
    return;
  }

  const email = document.getElementById("regEmail")?.value.trim() || "";
  const password = document.getElementById("regPassword")?.value || "";
  const nome = document.getElementById("regName")?.value.trim() || "";

  const { error } = await _supabase.auth.signUp({
    email,
    password,
    options: { data: { full_name: nome } },
  });

  if (error) {
    mostrarAviso("Erro no cadastro: " + error.message, "cadastro-erro");
    return;
  }

  const { error: insertError } = await _supabase.from("usuarios").insert([{ nome, email }]);

  if (insertError) {
    mostrarAviso(
      "Conta criada, mas houve um erro ao salvar seus dados complementares.",
      "cadastro-erro"
    );

    setTimeout(() => {
      setMode("signin");
    }, 1800);
    return;
  }

  mostrarAviso("Cadastro finalizado! Faca seu login.", "cadastro");

  setTimeout(() => {
    setMode("signin");
  }, 1800);
});

loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();

  const email = document.getElementById("loginEmail")?.value.trim() || "";
  const password = document.getElementById("loginPassword")?.value || "";

  const { data, error } = await _supabase.auth.signInWithPassword({ email, password });

  if (error) {
    mostrarAviso("E-mail ou senha invalidos.", "erro");
    return;
  }

  const emailUsuario = (data.user?.email || email).trim().toLowerCase();

  if (contaSemAcesso(emailUsuario)) {
    limparSessaoLocal();

    try {
      await _supabase.auth.signOut();
    } catch (erro) {
      console.warn("Nao foi possivel encerrar a sessao bloqueada do Supabase:", erro);
    }

    mostrarAviso("Esta conta foi bloqueada pelo administrador.");
    return;
  }

  await finalizarLoginUsuario(data.user);
});

setMode("signin");
consumirAvisosPendentes();
processarRetornoOAuth();
