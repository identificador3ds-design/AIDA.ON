const members = [
  {
    name: "Alexandre",
    role: "Head of Documentation",
    description:
      "Responsavel pela estruturacao e manutencao da documentacao tecnica do projeto. Atua na organizacao das metodologias utilizadas, registro dos processos de desenvolvimento e elaboracao de relatorios e materiais explicativos. Seu trabalho garante que todas as etapas do projeto estejam bem documentadas, facilitando a compreensao, replicacao e evolucao da pesquisa.",
    image: "../img/alex-exec.png",
  },
  {
    name: "Arthur",
    role: "Head of Detection Methodologies",
    description:
      "Responsavel pelo estudo, desenvolvimento e implementacao das metodologias de deteccao de conteudo gerado ou manipulado por inteligencia artificial. Atua na analise de diferentes abordagens e algoritmos, avaliando sua eficacia e aplicabilidade no contexto do projeto. Seu foco e garantir precisao, confiabilidade e inovacao nas tecnicas utilizadas.",
    image: "../img/thur-exec.png",
  },
  {
    name: "Eduardo",
    role: "Data Acquisition Lead",
    description:
      "Responsavel pela coleta, selecao e organizacao dos conjuntos de dados utilizados no projeto. Atua na busca por bases confiaveis de imagens e videos, alem de realizar a curadoria e preparacao dos dados para testes e analises. Seu trabalho e fundamental para garantir qualidade, diversidade e consistencia nos dados utilizados pelos metodos de deteccao.",
    image: "../img/nidu-exec.png",
  },
  {
    name: "Iago",
    role: "Project Manager & Lead Backend",
    description:
      "Responsavel pela coordenacao geral do projeto e pelo desenvolvimento da arquitetura backend da plataforma. Atua na organizacao das tarefas da equipe, integracao dos sistemas e implementacao das funcionalidades que processam e gerenciam os dados. Seu trabalho garante o funcionamento estrutural da aplicacao e a integracao entre todas as partes do sistema.",
    image: "../img/iago-exec.png",
  },
  {
    name: "Pedro",
    role: "UX/UI Designer & Lead Frontend",
    description:
      "Responsavel pelo design da interface e pela experiencia do usuario da plataforma. Atua no planejamento visual, prototipagem e desenvolvimento do frontend do site, garantindo uma navegacao intuitiva, moderna e funcional. Seu trabalho conecta a tecnologia desenvolvida no projeto com uma interface clara e acessivel para os usuarios.",
    image: "../img/pedrao-exec.png",
  },
];

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
  const label = savedName ? `Ola, ${savedName}` : "Minha conta";
  const mobileButton = document.getElementById("nome-usuario");
  const desktopButton = document.getElementById("nome-usuario2");

  if (mobileButton) {
    mobileButton.textContent = label;
  }

  if (desktopButton) {
    desktopButton.textContent = label;
  }
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
