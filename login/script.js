// Conexao com o banco
const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

const signinForm = document.querySelector(".form.signin");
const signupForm = document.querySelector(".form.signup");
const formsStage = document.querySelector(".forms-stage");
const modeButtons = document.querySelectorAll("[data-mode-target]");
const heading = document.querySelector("[data-mode-heading]");
const description = document.querySelector("[data-mode-description]");
const authCard = document.querySelector(".auth-card");
const brandSigninCopy = document.querySelector("[data-copy-signin]");
const brandSignupCopy = document.querySelector("[data-copy-signup]");

const modeContent = {
  signin: {
    heading: "Entrar no AIDA",
    description: "Acesse sua conta para continuar com suas analises e acompanhar seu ambiente de trabalho.",
  },
  signup: {
    heading: "Criar conta no AIDA",
    description: "Configure seu acesso em poucos passos e entre na plataforma com seguranca e praticidade.",
  },
};

const mostrarAviso = (texto, tipo = "sucesso") => {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");

  toast.className = `toast-msg ${tipo === "erro" ? "erro" : ""}`;
  toast.innerText = texto;

  container.innerHTML = "";
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 280);
  }, 3200);
};

const setMode = (mode) => {
  const isSignin = mode === "signin";

  if (formsStage) {
    formsStage.dataset.authMode = mode;
  }

  if (authCard) {
    authCard.dataset.authMode = mode;
  }

  signinForm.classList.toggle("active", isSignin);
  signupForm.classList.toggle("active", !isSignin);
  signinForm.setAttribute("aria-hidden", String(!isSignin));
  signupForm.setAttribute("aria-hidden", String(isSignin));

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
};

const toggleView = () => {
  const nextMode = formsStage.dataset.authMode === "signin" ? "signup" : "signin";
  setMode(nextMode);
};

modeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setMode(button.dataset.modeTarget);
  });
});

document.getElementById("registerForm").addEventListener("submit", async (event) => {
  event.preventDefault();

  const email = document.getElementById("regEmail").value.trim();
  const password = document.getElementById("regPassword").value;
  const nome = document.getElementById("regName").value.trim();

  const { error } = await _supabase.auth.signUp({
    email,
    password,
    options: { data: { full_name: nome } },
  });

  if (error) {
    mostrarAviso("Erro no cadastro: " + error.message, "erro");
    return;
  }

  const { error: insertError } = await _supabase.from("usuarios").insert([{ nome, email }]);

  if (insertError) {
    mostrarAviso("Conta criada, mas houve um erro ao salvar seus dados complementares.", "erro");
    setTimeout(() => {
      setMode("signin");
    }, 1800);
    return;
  }

  mostrarAviso("Cadastro finalizado! Faca seu login.");

  setTimeout(() => {
    setMode("signin");
  }, 1800);
});

document.getElementById("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();

  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  const { data, error } = await _supabase.auth.signInWithPassword({ email, password });

  if (error) {
    mostrarAviso("Email ou senha invalidos.", "erro");
    return;
  }

  const nomeUsuario = data.user.user_metadata.full_name || "usuario";
  localStorage.setItem("usuarioNome", nomeUsuario);

  mostrarAviso(`Bem-vindo, ${nomeUsuario}!`);

  setTimeout(() => {
    window.location.href = "../Tela-apresenta%C3%A7%C3%A3o/index-apresenta%C3%A7%C3%A3o.html";
  }, 1250);
});

setMode("signin");
