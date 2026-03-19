const members = [
  {
    name: "Alexandre",
    role: "Head of Documentation",
    description:
      "Responsável pela documentação técnica do projeto, organizando metodologias, processos de desenvolvimento e relatórios para garantir clareza, replicação e evolução da pesquisa.",
    image: "../img/alex-exec.png",
  },
  {
    name: "Arthur",
    role: "Head of Detection Methodologies",
    description:
      "Responsável pelo desenvolvimento e aplicação de metodologias de detecção de conteúdo gerado ou manipulado por IA, buscando precisão, confiabilidade e inovação nas técnicas utilizadas.",
    image: "../img/thur-exec.png",
  },
  {
    name: "Eduardo",
    role: "Data Acquisition Lead",
    description:
      "Responsável pela coleta, organização e preparação dos dados do projeto, garantindo qualidade, diversidade e consistência para testes e análises.",
    image: "../img/nidu-exec.png",
  },
  {
    name: "Iago",
    role: "Project Manager & Lead Backend",
    description:
      "Responsável pela coordenação do projeto e pelo desenvolvimento do backend, garantindo organização, integração e funcionamento eficiente da plataforma.",
    image: "../img/iago-exec.png",
  },
  {
    name: "Pedro",
    role: "UX/UI Designer & Lead Frontend",
    description:
      "Responsável pela coleta, seleção e organização dos dados do projeto, garantindo qualidade, diversidade e consistência para testes e análises.",
    image: "../img/pedrao-exec.png",
  },
];

const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const CONFIG_ADMIN_PADRAO = {
  allowRegistrations: true,
  enableInstallPrompt: true,
  maintenanceMode: false,
  supportEmail: ADMIN_EMAIL,
  announcementMessage: "",
};

const menuToggle = document.querySelector(".menu-toggle");
const navbar = document.querySelector(".navbar");
const overlay = document.querySelector(".menu-overlay");
const header = document.querySelector(".cabecalho");
const hero = document.querySelector(".hero");
const scrollBadge = document.querySelector(".rolarpg");
const toolSection = document.querySelector("#ferramentaaida");

const photo = document.getElementById("memberPhoto");
const bigName = document.getElementById("memberBigName");
const memberName = document.getElementById("memberName");
const memberRole = document.getElementById("memberRole");
const memberDescription = document.getElementById("memberDescription");
const teamMobileCarousel = document.getElementById("teamMobileCarousel");

let currentIndex = -1;
let teamTrigger = null;

function obterAdminConfig() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_ADMIN_CONFIG) || "{}");
    return { ...CONFIG_ADMIN_PADRAO, ...salvo };
  } catch (erro) {
    return { ...CONFIG_ADMIN_PADRAO };
  }
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

  window.location.href = "../Administrador/index-admin.html";
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

  const main = document.querySelector("main");

  if (!main || document.getElementById("systemNotice")) {
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

  main.insertBefore(aviso, main.firstChild);
}

function ajustarAcessoPrincipalFerramenta() {
  const configuracao = obterAdminConfig();
  const ctaPrincipal = document.querySelector('.btn-group-ferr .btn-main');
  const badgeNovidade = document.querySelector(".new-feature-badge");
  const admin = usuarioEhAdmin();

  if (!ctaPrincipal) {
    return;
  }

  if (!ctaPrincipal.dataset.defaultLabel) {
    ctaPrincipal.dataset.defaultLabel = ctaPrincipal.textContent.trim();
  }

  const restaurarLabel = () => {
    ctaPrincipal.textContent = ctaPrincipal.dataset.defaultLabel || "Experimentar ferramenta";
  };

  if (configuracao.allowUploadPage || admin) {
    ctaPrincipal.href = "../Ferramenta/index-seleciona.html";
    ctaPrincipal.classList.remove("is-disabled");
    ctaPrincipal.removeAttribute("aria-disabled");
    restaurarLabel();

    if (badgeNovidade) {
      badgeNovidade.hidden = false;
    }

    return;
  }

  ctaPrincipal.href = "#topo";
  ctaPrincipal.classList.add("is-disabled");
  ctaPrincipal.setAttribute("aria-disabled", "true");
  ctaPrincipal.textContent = "Entrada temporariamente fechada";

  if (badgeNovidade) {
    badgeNovidade.hidden = true;
  }
}

function registerGsapPlugins() {
  if (!window.gsap) {
    return;
  }

  const plugins = [];

  if (window.ScrollTrigger) {
    plugins.push(ScrollTrigger);
  }

  if (plugins.length) {
    gsap.registerPlugin(...plugins);
  }
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

  if (mobileButton) {
    mobileButton.textContent = label;
  }

  if (desktopButton) {
    desktopButton.textContent = label;
  }

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
    link.href = "../Administrador/index-admin.html";
    link.textContent = "Painel admin";
  });
}

function updateActiveNav() {
  const links = document.querySelectorAll(".ancoranav");
  const sections = Array.from(links)
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);

  if (!sections.length) {
    return;
  }

  const onScroll = () => {
    const offset = window.scrollY + 140;

    sections.forEach((section, index) => {
      const link = links[index];
      const isActive =
        offset >= section.offsetTop &&
        offset < section.offsetTop + section.offsetHeight;

      link.classList.toggle("active", isActive);
    });
  };

  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });
}

function changeMember(index) {
  if (
    index === currentIndex ||
    !photo ||
    !bigName ||
    !memberName ||
    !memberRole ||
    !memberDescription
  ) {
    return;
  }

  currentIndex = index;
  const member = members[index];

  const applyContent = () => {
    photo.src = member.image;
    photo.alt = `Foto de ${member.name}`;
    bigName.textContent = member.name.toUpperCase();
    memberName.textContent = member.name;
    memberRole.textContent = member.role;
    memberDescription.textContent = member.description;

    document.querySelectorAll(".icon").forEach((icon, iconIndex) => {
      icon.classList.toggle("active", iconIndex === index);
    });
  };

  if (!window.gsap) {
    applyContent();
    return;
  }

  gsap
    .timeline()
    .to([photo, ".card-team"], {
      opacity: 0,
      y: 18,
      duration: 0.18,
      stagger: 0.04,
      ease: "power2.out",
    })
    .add(applyContent)
    .to([photo, ".card-team"], {
      opacity: 1,
      y: 0,
      duration: 0.24,
      stagger: 0.04,
      ease: "power2.out",
    });
}

function renderMobileTeamCards() {
  if (!teamMobileCarousel) {
    return;
  }

  teamMobileCarousel.innerHTML = members
    .map(
      (member) => `
        <article class="team-mobile-card">
          <img src="${member.image}" alt="Foto de ${member.name}">
          <div class="team-mobile-card-body">
            <h3>${member.name}</h3>
            <h4>${member.role}</h4>
            <p>${member.description}</p>
          </div>
        </article>
      `
    )
    .join("");
}

function setupTeamRotation() {
  const teamSection = document.querySelector(".team-section");

  if (!photo || !teamSection) {
    return;
  }

  changeMember(0);

  if (teamTrigger) {
    teamTrigger.kill();
    teamTrigger = null;
  }

  if (!window.gsap || !window.ScrollTrigger || window.innerWidth <= 900) {
    return;
  }

  teamTrigger = ScrollTrigger.create({
    trigger: teamSection,
    start: "top top",
    end: () => `+=${Math.max(window.innerHeight * (members.length - 1), 1800)}`,
    pin: true,
    scrub: 1,
    anticipatePin: 1,
    invalidateOnRefresh: true,
    onUpdate: (self) => {
      let index = Math.round(self.progress * (members.length - 1));
      if (index >= members.length) {
        index = members.length - 1;
      }
      changeMember(index);
    },
    onLeaveBack: () => changeMember(0),
  });
}

function setupHeaderBehavior() {
  if (!header || !hero) {
    return;
  }

  const updateHeader = () => {
    const heroBottom = hero.getBoundingClientRect().bottom;
    header.classList.toggle("scrolled", window.scrollY > 30);
    header.classList.toggle("header-hidden", heroBottom <= 0 && window.scrollY > 120);
  };

  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });

  document.addEventListener("mousemove", (event) => {
    if (event.clientY < 72) {
      header.classList.remove("header-hidden");
    }
  });
}

function setupScrollBadge() {
  if (!scrollBadge || !toolSection) {
    return;
  }

  const toggleBadge = () => {
    const sectionTop = toolSection.getBoundingClientRect().top;
    scrollBadge.classList.toggle("hidden", sectionTop < window.innerHeight * 0.8);
  };

  toggleBadge();
  window.addEventListener("scroll", toggleBadge, { passive: true });
}

function setupIconLoop() {
  const icons = document.querySelectorAll(".icon-wrapper");

  if (!icons.length) {
    return;
  }

  const activateIcons = () => {
    icons.forEach((icon) => icon.classList.remove("active"));

    const quantity = Math.floor(Math.random() * 3) + 1;
    const selected = new Set();

    while (selected.size < quantity) {
      selected.add(Math.floor(Math.random() * icons.length));
    }

    selected.forEach((index) => icons[index].classList.add("active"));
  };

  activateIcons();
  window.setInterval(activateIcons, 1400);
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

function setupGsapIntro() {
  if (!window.gsap) {
    return;
  }

  gsap.from(".hero-copy > *", {
    y: 24,
    opacity: 0,
    duration: 0.6,
    stagger: 0.08,
    ease: "power2.out",
  });

  gsap.from(".hero-visual", {
    x: 32,
    opacity: 0,
    duration: 0.8,
    delay: 0.16,
    ease: "power2.out",
  });
}

function setupCardScrollAnimations() {
  if (!window.gsap || !window.ScrollTrigger) {
    return;
  }

  const groups = [
    {
      trigger: ".cards-sobre",
      items: gsap.utils.toArray(".sobre-card"),
      start: "top 76%",
      y: 38,
      stagger: 0.12,
    },
    {
      trigger: ".func-grid",
      items: gsap.utils.toArray(".func-card"),
      start: "top 82%",
      y: 38,
      stagger: 0.1,
    },
    {
      trigger: ".cards",
      items: gsap.utils.toArray(".card-content"),
      start: "top 72%",
      y: 42,
      stagger: 0.14,
    },
  ];

  if (window.innerWidth <= 900) {
    groups.push({
      trigger: ".team-mobile-carousel",
      items: gsap.utils.toArray(".team-mobile-card"),
      start: "top 82%",
      y: 30,
      stagger: 0.1,
    });
  }

  groups.forEach(({ trigger, items, start, y, stagger }) => {
    if (!items.length) {
      return;
    }

    gsap.set(items, {
      autoAlpha: 0,
      y,
    });

    gsap.to(items, {
      y: 0,
      autoAlpha: 1,
      duration: 0.72,
      stagger,
      ease: "power2.out",
      overwrite: "auto",
      scrollTrigger: {
        trigger,
        start: start ?? "top 82%",
        once: true,
      },
    });
  });
}

function setupSiteScrollAnimations() {
  if (!window.gsap || !window.ScrollTrigger) {
    return;
  }

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (reduceMotion) {
    return;
  }

  const animateGroup = (targets, options = {}) => {
    const items = gsap.utils.toArray(targets);

    if (!items.length) {
      return;
    }

    gsap.from(items, {
      y: options.y ?? 32,
      x: options.x ?? 0,
      opacity: 0,
      duration: options.duration ?? 0.78,
      stagger: options.stagger ?? 0.1,
      ease: options.ease ?? "power2.out",
      scrollTrigger: {
        trigger: options.trigger ?? items[0],
        start: options.start ?? "top 84%",
        once: true,
      },
    });
  };

  animateGroup(".sobre-visual", {
    trigger: ".sobre",
    x: -36,
    y: 0,
    duration: 0.85,
  });

  animateGroup(".sobre-copy > .section-label, .sobre-copy > .section-title, .sobre-copy > .section-text", {
    trigger: ".sobre",
    y: 30,
    stagger: 0.12,
  });

  animateGroup(".func-heading > *, .subtitle-func", {
    trigger: ".func-header",
    y: 28,
    stagger: 0.12,
  });

  animateGroup(".func-footer", {
    trigger: ".func-footer",
    y: 26,
    duration: 0.7,
  });

  animateGroup(".icons-section .section-heading > *", {
    trigger: ".icons-section",
    y: 28,
    stagger: 0.12,
  });

  animateGroup(".icons-grid", {
    trigger: ".tech-layout",
    x: 34,
    y: 0,
    duration: 0.82,
  });

  animateGroup(".icon-wrapper", {
    trigger: ".icons-grid",
    y: 22,
    stagger: 0.06,
    duration: 0.62,
    start: "top 86%",
  });

  if (window.innerWidth > 900) {
    animateGroup(".team-photo", {
      trigger: ".team-section",
      x: -26,
      y: 0,
      duration: 0.82,
      start: "top 70%",
    });

    animateGroup(".team-info > .section-label, .team-info > .team-big-name, .team-info > .card-team", {
      trigger: ".team-section",
      x: 28,
      y: 0,
      stagger: 0.12,
      duration: 0.8,
      start: "top 70%",
    });
  } else {
    animateGroup(".team-mobile-header > *", {
      trigger: ".team-mobile",
      y: 28,
      stagger: 0.12,
    });
  }

  animateGroup(".new-feature-badge, .contentferr > *, .btn-group-ferr", {
    trigger: ".ferramenta",
    y: 30,
    stagger: 0.12,
  });

  animateGroup(".foot-column", {
    trigger: ".footer",
    y: 24,
    stagger: 0.12,
    duration: 0.72,
    start: "top 88%",
  });
}

function setupTeamControls() {
  document.querySelectorAll(".icon").forEach((icon, index) => {
    icon.addEventListener("click", () => changeMember(index));
  });
}

function setupParallax() {
  const items = document.querySelectorAll(".parallax-item");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (!items.length || reduceMotion || window.innerWidth <= 768) {
    items.forEach((item) => {
      item.style.transform = "";
    });
    return;
  }

  const updateParallax = () => {
    items.forEach((item) => {
      const speed = Number(item.dataset.parallaxSpeed || 0.12);
      const rect = item.getBoundingClientRect();
      const centerOffset = rect.top + rect.height / 2 - window.innerHeight / 2;
      const translateY = centerOffset * -speed;

      item.style.transform = `translate3d(0, ${translateY}px, 0)`;
    });
  };

  updateParallax();
  window.addEventListener("scroll", updateParallax, { passive: true });
  window.addEventListener("resize", updateParallax);
}

document.addEventListener("DOMContentLoaded", () => {
  registerGsapPlugins();
  renderizarAvisoSistema();
  ajustarAcessoPrincipalFerramenta();
  setUserName();
  setupNavigation();
  updateActiveNav();
  setupHeaderBehavior();
  setupScrollBadge();
  setupIconLoop();
  renderMobileTeamCards();
  setupTeamControls();
  setupTeamRotation();
  setupGsapIntro();
  setupCardScrollAnimations();
  setupSiteScrollAnimations();
  setupParallax();
  window.addEventListener("resize", setupTeamRotation);
});
