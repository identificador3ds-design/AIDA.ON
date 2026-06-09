const ADMIN_EMAIL = "admin@gmail.com";

const favicon = document.getElementById("favicon");
const menuToggle = document.querySelector(".menu-toggle");
const navbar = document.querySelector(".navbar");
const overlay = document.querySelector(".menu-overlay");
const header = document.querySelector(".cabecalho");

let lastScrollY = window.scrollY;

function updateFavicon() {
  if (!favicon) {
    return;
  }

  favicon.href = window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "../assets/images/AIDABranco.ico"
    : "../assets/images/AIDAPreto.ico";
}

function usuarioEhAdmin() {
  const tipo = localStorage.getItem("usuarioTipo");
  const email = (localStorage.getItem("usuarioEmail") || "").trim().toLowerCase();
  return tipo === "admin" || email === ADMIN_EMAIL;
}

function abrirPainelAdmin(event) {
  if (event) {
    event.preventDefault();
  }

  window.location.href = "./index-admin.html";
}

function setUserName() {
  const savedName = localStorage.getItem("usuarioNome");
  const admin = usuarioEhAdmin();
  const label = admin ? "Admin" : savedName ? `Ola, ${savedName}` : "Minha conta";
  const mobileButton = document.getElementById("nome-usuario");
  const desktopButton = document.getElementById("nome-usuario2");

  [mobileButton, desktopButton].forEach((button) => {
    if (!button) {
      return;
    }

    button.textContent = label;

    if (admin) {
      button.addEventListener("click", abrirPainelAdmin);
    }
  });

  if (!admin) {
    return;
  }

  document.querySelectorAll(".dropdown-content .dropa").forEach((link) => {
    link.href = "./index-admin.html";
    link.textContent = "Painel admin";
  });
}

function setMenuState(isOpen) {
  if (!menuToggle || !navbar || !overlay) {
    return;
  }

  menuToggle.classList.toggle("active", isOpen);
  navbar.classList.toggle("active", isOpen);
  overlay.classList.toggle("active", isOpen);
  menuToggle.setAttribute("aria-expanded", String(isOpen));
  document.body.classList.toggle("menu-open", isOpen);
}

function setupNavigation() {
  if (menuToggle) {
    menuToggle.addEventListener("click", () => {
      const isOpen = !navbar.classList.contains("active");
      setMenuState(isOpen);
    });
  }

  if (overlay) {
    overlay.addEventListener("click", () => setMenuState(false));
  }

  document.querySelectorAll(".navbar a").forEach((link) => {
    link.addEventListener("click", () => setMenuState(false));
  });
}

function setupHeaderBehavior() {
  if (!header) {
    return;
  }

  const updateHeader = () => {
    const currentScrollY = window.scrollY;
    const scrollingDown = currentScrollY > lastScrollY;
    const shouldHide =
      currentScrollY > 160 &&
      scrollingDown &&
      !document.body.classList.contains("menu-open");

    header.classList.toggle("scrolled", currentScrollY > 30);
    header.classList.toggle("header-hidden", shouldHide);
    lastScrollY = currentScrollY;
  };

  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });

  document.addEventListener("mousemove", (event) => {
    if (event.clientY < 72) {
      header.classList.remove("header-hidden");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  updateFavicon();
  setUserName();
  setupNavigation();
  setupHeaderBehavior();
});
