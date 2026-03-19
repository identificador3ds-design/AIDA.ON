const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

const ADMIN_EMAIL = "admin@gmail.com";
const ADMIN_PASSWORD = "admin3ds";
const CHAVE_ADMIN_AUTH = "AIDA_ADMIN_AUTH";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const CHAVE_ADMIN_REDIRECT_MESSAGE = "AIDA_ADMIN_REDIRECT_MESSAGE";
const CHAVE_LOGIN_FEEDBACK = "AIDA_LOGIN_FEEDBACK";
const CONFIG_ADMIN_PADRAO = {
  allowRegistrations: true,
  enableInstallPrompt: true,
  maintenanceMode: false,
  supportEmail: ADMIN_EMAIL,
  announcementMessage: "",
  accountStates: {},
};

function restaurarCredenciaisAdmin() {
  const credenciais = {
    email: ADMIN_EMAIL,
    password: ADMIN_PASSWORD,
  };

  localStorage.setItem(CHAVE_ADMIN_AUTH, JSON.stringify(credenciais));
  return credenciais;
}

function obterCredenciaisAdmin() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_ADMIN_AUTH) || "{}");

    return {
      email: String(salvo.email || "").trim().toLowerCase() || ADMIN_EMAIL,
      password: String(salvo.password || "") || ADMIN_PASSWORD,
    };
  } catch (erro) {
    return restaurarCredenciaisAdmin();
  }
}

function obterAdminConfig() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_ADMIN_CONFIG) || "{}");
    const estadosConta = {};

    if (salvo.accountStates && typeof salvo.accountStates === "object") {
      Object.entries(salvo.accountStates).forEach(([email, dados]) => {
        const emailNormalizado = String(email || "").trim().toLowerCase();

        if (!emailNormalizado || emailNormalizado === ADMIN_EMAIL) {
          return;
        }

        estadosConta[emailNormalizado] = {
          status: ["active", "blocked", "deleted"].includes(dados?.status)
            ? dados.status
            : "active",
        };
      });
    }

    return {
      ...CONFIG_ADMIN_PADRAO,
      ...salvo,
      accountStates: estadosConta,
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

function contaTemAcesso(email) {
  return !["blocked", "deleted"].includes(obterStatusConta(email));
}

function salvarSessaoUsuario({ nome, email, tipo }) {
  localStorage.setItem("usuarioNome", nome);
  localStorage.setItem("usuarioEmail", email);
  localStorage.setItem("usuarioTipo", tipo);
}

function limparSessaoUsuario() {
  localStorage.removeItem("usuarioNome");
  localStorage.removeItem("usuarioEmail");
  localStorage.removeItem("usuarioTipo");
}

function mostrarAviso(texto, tipo = "sucesso") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast-msg ${tipo === "erro" ? "erro" : ""}`;
  toast.innerText = texto;

  container.innerHTML = "";
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 400);
  }, 3000);
}

function loginAdmin(email, password) {
  const credenciaisAdmin = obterCredenciaisAdmin();
  return (
    email.trim().toLowerCase() === credenciaisAdmin.email &&
    password === credenciaisAdmin.password
  );
}

function aplicarEstadoCadastro() {
  const registerForm = document.getElementById("registerForm");

  if (!registerForm) {
    return;
  }

  const configuracao = obterAdminConfig();
  const cadastroLiberado = configuracao.allowRegistrations;
  const campos = registerForm.querySelectorAll("input, button");
  let aviso = document.getElementById("adminRegisterNotice");

  if (!aviso) {
    aviso = document.createElement("p");
    aviso.id = "adminRegisterNotice";
    aviso.style.margin = "0 0 14px";
    aviso.style.fontSize = "0.92rem";
    aviso.style.color = "rgba(255, 235, 167, 0.92)";
    registerForm.insertBefore(aviso, registerForm.querySelector("input"));
  }

  campos.forEach((campo) => {
    campo.disabled = !cadastroLiberado;
  });

  aviso.hidden = cadastroLiberado;
  aviso.innerText = "Novos cadastros estao desativados pelo administrador.";
}

document.getElementById("registerForm").addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!obterAdminConfig().allowRegistrations) {
    mostrarAviso("Novos cadastros estao desativados pelo administrador.", "erro");
    return;
  }

  const email = document.getElementById("regEmail").value.trim();
  const password = document.getElementById("regPassword").value;
  const nome = document.getElementById("regName").value.trim();

  if (!contaTemAcesso(email)) {
    mostrarAviso("Esta conta foi bloqueada pelo administrador.", "erro");
    return;
  }

  const { error } = await _supabase.auth.signUp({
    email,
    password,
    options: { data: { full_name: nome } },
  });

  if (error) {
    mostrarAviso(`Erro no cadastro: ${error.message}`, "erro");
    return;
  }

  await _supabase.from("usuarios").insert([{ nome, email }]);
  mostrarAviso("Cadastro finalizado! Faca seu login.");

  setTimeout(() => {
    toggleView();
  }, 2000);
});

document.getElementById("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();

  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  if (loginAdmin(email, password)) {
    try {
      await _supabase.auth.signOut();
    } catch (erro) {
      console.warn("Nao foi possivel encerrar a sessao anterior:", erro);
    }

    salvarSessaoUsuario({
      nome: "Admin",
      email: ADMIN_EMAIL,
      tipo: "admin",
    });

    mostrarAviso("Bem-vindo, Admin!");

    setTimeout(() => {
      window.location.href = "../Tela-apresenta%C3%A7%C3%A3o/index-apresenta%C3%A7%C3%A3o.html";
    }, 1250);
    return;
  }

  if (!contaTemAcesso(email)) {
    mostrarAviso("Seu acesso foi bloqueado pelo administrador.", "erro");
    return;
  }

  const { data, error } = await _supabase.auth.signInWithPassword({ email, password });

  if (error) {
    mostrarAviso("Email ou senha invalidos.", "erro");
    return;
  }

  const nomeUsuario = data.user.user_metadata.full_name || email;

  if (!contaTemAcesso(email)) {
    try {
      await _supabase.auth.signOut();
    } catch (erroLogout) {
      console.warn("Nao foi possivel encerrar a sessao bloqueada:", erroLogout);
    }

    mostrarAviso("Seu acesso foi bloqueado pelo administrador.", "erro");
    return;
  }

  salvarSessaoUsuario({
    nome: nomeUsuario,
    email,
    tipo: "usuario",
  });

  mostrarAviso(`Bem-vindo, ${nomeUsuario}!`);

  setTimeout(() => {
    window.location.href = "../Tela-apresenta%C3%A7%C3%A3o/index-apresenta%C3%A7%C3%A3o.html";
  }, 1250);
});

const signinForm = document.querySelector(".form.signin");
const signupForm = document.querySelector(".form.signup");
const cardBg1 = document.querySelector(".card-bg-1");
const cardBg2 = document.querySelector(".card-bg-2");

const toggleView = () => {
  const signinActive = signinForm.classList.contains("active");

  signinForm.classList.toggle("active", !signinActive);
  signupForm.classList.toggle("active", signinActive);

  [cardBg1, cardBg2].forEach((elemento) =>
    elemento.classList.toggle("signin", signinActive)
  );
  [cardBg1, cardBg2].forEach((elemento) =>
    elemento.classList.toggle("signup", !signinActive)
  );
};

window.toggleView = toggleView;

limparSessaoUsuario();
restaurarCredenciaisAdmin();
aplicarEstadoCadastro();

const avisoRedirecionamentoAdmin = localStorage.getItem(CHAVE_ADMIN_REDIRECT_MESSAGE);
const avisoFeedbackLogin = localStorage.getItem(CHAVE_LOGIN_FEEDBACK);

if (avisoRedirecionamentoAdmin) {
  mostrarAviso(avisoRedirecionamentoAdmin, "erro");
  localStorage.removeItem(CHAVE_ADMIN_REDIRECT_MESSAGE);
}

if (avisoFeedbackLogin) {
  mostrarAviso(avisoFeedbackLogin, "erro");
  localStorage.removeItem(CHAVE_LOGIN_FEEDBACK);
}
