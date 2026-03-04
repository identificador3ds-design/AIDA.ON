gsap.registerPlugin(SplitText);

// Coloque isto no topo do scripta.js
document.addEventListener('DOMContentLoaded', () => {
    // 1. Tenta recuperar o nome que o login guardou
    const nomeSalvo = localStorage.getItem('usuarioNome');
    const botaoUsuario = document.getElementById('nome-usuario');

    console.log("Nome recuperado do localStorage:", nomeSalvo); // Para teste no F12

    if (nomeSalvo && botaoUsuario) {
        // 2. Muda o texto do botão
        botaoUsuario.innerText = `Olá, ${nomeSalvo}`;
        gsap.from("#nome-usuario", { opacity: 0, duration: 1, y: -10 });
    } 

    // 3. Lógica do botão Sair (Logout)
    const btnSair = document.getElementById('btn-sair');
    if (btnSair) {
        btnSair.addEventListener('click', (e) => {
            e.preventDefault();
            localStorage.removeItem('usuarioNome');
            window.location.href = "../login/index-login.html";
        });
    }
});
document.addEventListener('DOMContentLoaded', () => {
    // 1. Tenta recuperar o nome que o login guardou
    const nomeSalvo = localStorage.getItem('usuarioNome');
    const botaoUsuario = document.getElementById('nome-usuario2');

    console.log("Nome recuperado do localStorage:", nomeSalvo); // Para teste no F12

    if (nomeSalvo && botaoUsuario) {
        // 2. Muda o texto do botão
        botaoUsuario.innerText = `Olá, ${nomeSalvo}`;
        gsap.from("#nome-usuario2", { opacity: 0, duration: 1, y: -10 });
    } 

    // 3. Lógica do botão Sair (Logout)
    const btnSair = document.getElementById('btn-sair');
    if (btnSair) {
        btnSair.addEventListener('click', (e) => {
            e.preventDefault();
            localStorage.removeItem('usuarioNome');
            window.location.href = "../login/index-login.html";
        });
    }
});

let split = SplitText.create(".text", {
    type: "chars, words"
});

gsap.from(split.chars, {
    y: 100,
    autoAlpha: 0,
    stagger: 0.009,
});
// Certifique-se de incluir o script do GSAP no seu HTML
// <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>

gsap.from(".card", {
  duration: 1,
  y: 60,          // Vem de baixo
  opacity: 0,     // Começa invisível
  stagger: 0.2,   // Anima um por um com atraso
  ease: "power4.out" // Transição suave e elegante
});

// Efeito de pulso no botão de seta ao passar o mouse no card
document.querySelectorAll('.card').forEach(card => {
  card.addEventListener('mouseenter', () => {
    gsap.to(card.querySelector('.floating-btn'), {
      scale: 1.1,
      duration: 0.3
    });
  });
  
  card.addEventListener('mouseleave', () => {
    gsap.to(card.querySelector('.floating-btn'), {
      scale: 1,
      duration: 0.3
    });
  });
});

const icons = document.querySelectorAll('.icon-wrapper');

function getRandomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function highlightRandomIcons() {
  // Remove active de todos
  icons.forEach(el => el.classList.remove('active'));

  // Quantos ícones vamos destacar (1 a 3)
  const count = getRandomInt(1, 3);

  // Escolhe índices únicos
  const selected = new Set();
  while (selected.size < count) {
    selected.add(getRandomInt(0, icons.length - 1));
  }

  // Ativa os selecionados
  selected.forEach(index => {
    icons[index].classList.add('active');
  });
}

// Inicia imediatamente e repete
function loop() {
  highlightRandomIcons();
  const nextDelay = getRandomInt(900, 1600); // 0.9s a 1.6s
  setTimeout(loop, nextDelay);
}

loop();


window.addEventListener('scroll', function() {
    const scrollIcon = document.querySelector('.rolarpg');
    const targetSection = document.querySelector('#ferramentaaida');
    
    // Pega a posição do topo da seção da ferramenta em relação à janela
    const sectionPos = targetSection.getBoundingClientRect().top;
    
    // Se o topo da seção estiver visível ou acima do meio da tela, esconde o ícone
    if (sectionPos < window.innerHeight * 0.8) {
        scrollIcon.classList.add('hidden');
    } else {
        scrollIcon.classList.remove('hidden');
    }
});

const header = document.querySelector('header');
    let lastScroll = 0;
    
    // Altere este valor (em pixels) para decidir o quão perto 
    // do topo a pessoa deve estar para o header reaparecer
    const limiarDoTopo = 250; 

    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;

        // 1. Se estiver descendo, esconde o header
        if (currentScroll > lastScroll && currentScroll > 100) {
            header.classList.add('header-hidden');
        } 
        
        // 2. Só remove a classe 'header-hidden' se o scroll for menor que o limiar
        // Ou seja: ele só reaparece quando estiver chegando no topo
        if (currentScroll < limiarDoTopo) {
            header.classList.remove('header-hidden');
        }

        lastScroll = currentScroll;
});
const toggle = document.querySelector('.menu-toggle');
const nav = document.querySelector('.navbar');

toggle.addEventListener('click', () => {
    toggle.classList.toggle('active');
    nav.classList.toggle('active');
});

document.querySelectorAll('.navbar a').forEach(link => {
    link.addEventListener('click', () => {
        nav.classList.remove('active');
        toggle.classList.remove('active');
    });
});
window.addEventListener('scroll', () => {
    const header = document.querySelector('header');

    if (window.scrollY > 20) {
        header.classList.add('scrolled');
    } else {
        header.classList.remove('scrolled');
    }
});
