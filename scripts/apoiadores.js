const ADMIN_EMAIL = "admin@gmail.com";
const fictionalPartners = [
  { name: "Nexa", short: "NX", colors: ["#276ef1", "#8ab4ff"], accent: "#0e1f44" },
  { name: "Lumina", short: "LU", colors: ["#ff7b54", "#ffd56f"], accent: "#5f2d1e" },
  { name: "Vertex", short: "VX", colors: ["#6d5dfc", "#4fd1c5"], accent: "#221b57" },
  { name: "Bravia", short: "BR", colors: ["#e94f64", "#ff9c8f"], accent: "#571624" },
  { name: "Origo", short: "OR", colors: ["#16a085", "#7ed6c4"], accent: "#103d37" },
  { name: "Atlas", short: "AT", colors: ["#f4b400", "#ffe082"], accent: "#5f4300" },
  { name: "Pulse", short: "PL", colors: ["#00b8d9", "#7ce7ff"], accent: "#083844" },
];
const favicon = document.getElementById('favicon');

function updateFavicon() {

  if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    favicon.href = '../assets/images/AIDABranco.ico';
  } else {
    favicon.href = '../assets/images/AIDAPreto.ico';
  }
}


updateFavicon();
const menuToggle = document.querySelector(".menu-toggle");
const navbar = document.querySelector(".navbar");
const overlay = document.querySelector(".menu-overlay");
const header = document.querySelector(".cabecalho");
const revealElements = document.querySelectorAll("[data-reveal]");
const partnersTrack = document.getElementById("partnersTrack");
const partnersMarquee = document.getElementById("partnersMarquee");

let lastScrollY = window.scrollY;
let marqueeFrame = null;
let marqueePosition = 0;
let marqueeSpeed = 0.55;
let baseGroupWidth = 0;

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
  });

  if (!admin) {
    return;
  }

  [mobileButton, desktopButton].forEach((button) => {
    if (!button) {
      return;
    }

    button.addEventListener("click", abrirPainelAdmin);
  });

  document.querySelectorAll(".dropdown-content .dropa").forEach((link) => {
    link.href = "./index-admin.html";
    link.textContent = "Painel admin";
  });
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

function buildPlaceholderLogo(partner) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="320" height="120" viewBox="0 0 320 120" role="img" aria-label="${partner.name}">
      <defs>
        <linearGradient id="grad-${partner.short}" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="${partner.colors[0]}" />
          <stop offset="100%" stop-color="${partner.colors[1]}" />
        </linearGradient>
      </defs>
      <rect x="8" y="8" width="304" height="104" rx="28" fill="rgba(255,255,255,0.9)" />
      <circle cx="66" cy="60" r="28" fill="url(#grad-${partner.short})" />
      <text x="66" y="67" text-anchor="middle" font-family="Afacad, Arial, sans-serif" font-size="24" font-weight="700" fill="#ffffff">${partner.short}</text>
      <text x="114" y="56" font-family="Afacad, Arial, sans-serif" font-size="34" font-weight="700" fill="${partner.accent}">${partner.name}</text>
      <text x="114" y="80" font-family="Afacad, Arial, sans-serif" font-size="14" font-weight="600" letter-spacing="2" fill="${partner.colors[0]}">PARCEIRO EXEMPLO</text>
    </svg>
  `.trim();

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function buildPartnerCard(partner, hidden = false) {
  const variantClasses = ["variant-1", "variant-2", "variant-3", "variant-4", "variant-5"];
  const variant = variantClasses[partner.index % variantClasses.length];

  return `
    <article class="apoio-logo-card ${variant}"${hidden ? ' aria-hidden="true"' : ""}>
      <img src="${partner.src}" alt="Logo de exemplo da empresa ficticia ${partner.name}">
    </article>
  `;
}

function renderPartners() {
  if (!partnersTrack) {
    return;
  }

  const partnerItems = fictionalPartners.map((partner) => ({
    ...partner,
    index: fictionalPartners.indexOf(partner),
    src: buildPlaceholderLogo(partner),
  }));

  const primaryMarkup = partnerItems.map((partner) => buildPartnerCard(partner)).join("");
  const clonesMarkup = partnerItems.map((partner) => buildPartnerCard(partner, true)).join("");

  partnersTrack.innerHTML = `${primaryMarkup}${clonesMarkup}`;
}

function measureMarquee() {
  if (!partnersTrack) {
    return;
  }

  const cards = Array.from(partnersTrack.children);
  const groupLength = cards.length / 2;
  const primaryCards = cards.slice(0, groupLength);

  baseGroupWidth = primaryCards.reduce((total, card) => total + card.offsetWidth, 0);
  baseGroupWidth += Math.max(0, groupLength - 1) * 18;
}

function getMarqueeSpeed() {
  if (window.innerWidth <= 640) {
    return 0.38;
  }

  if (window.innerWidth <= 900) {
    return 0.46;
  }

  return 0.55;
}

function startInfiniteMarquee() {
  if (!partnersTrack || !partnersMarquee) {
    return;
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (reducedMotion) {
    partnersTrack.style.transform = "translate3d(0,0,0)";
    return;
  }

  marqueeSpeed = getMarqueeSpeed();
  measureMarquee();

  if (!baseGroupWidth) {
    return;
  }

  cancelAnimationFrame(marqueeFrame);

  const animate = () => {
    marqueePosition -= marqueeSpeed;

    if (Math.abs(marqueePosition) >= baseGroupWidth) {
      marqueePosition = 0;
    }

    partnersTrack.style.transform = `translate3d(${marqueePosition}px, 0, 0)`;
    marqueeFrame = window.requestAnimationFrame(animate);
  };

  marqueeFrame = window.requestAnimationFrame(animate);
}

function setupReveal() {
  if (!revealElements.length) {
    return;
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (reducedMotion) {
    revealElements.forEach((element) => element.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }

        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.16, rootMargin: "0px 0px -10% 0px" }
  );

  revealElements.forEach((element) => observer.observe(element));
}

document.addEventListener("DOMContentLoaded", () => {
  setUserName();
  setupNavigation();
  setupHeaderBehavior();
  renderPartners();
  startInfiniteMarquee();
  setupReveal();

  window.addEventListener("resize", startInfiniteMarquee);
});
