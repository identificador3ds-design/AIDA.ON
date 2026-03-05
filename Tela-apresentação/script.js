// =============================
// GSAP
// =============================
gsap.registerPlugin(SplitText);

// =============================
// LOGIN / NOME DO USUÁRIO
// =============================
document.addEventListener("DOMContentLoaded", () => {

    const nomeSalvo = localStorage.getItem("usuarioNome");

    const botaoUsuario1 = document.getElementById("nome-usuario");
    const botaoUsuario2 = document.getElementById("nome-usuario2");

    if (nomeSalvo) {

        if (botaoUsuario1) {
            botaoUsuario1.innerText = `Olá, ${nomeSalvo}`;
            gsap.from("#nome-usuario", { opacity: 0, duration: 1, y: -10 });
        }

        if (botaoUsuario2) {
            botaoUsuario2.innerText = `Olá, ${nomeSalvo}`;
            gsap.from("#nome-usuario2", { opacity: 0, duration: 1, y: -10 });
        }

    }

    const btnSair = document.getElementById("btn-sair");

    if (btnSair) {
        btnSair.addEventListener("click", (e) => {
            e.preventDefault();
            localStorage.removeItem("usuarioNome");
            window.location.href = "../login/index-login.html";
        });
    }

});


// =============================
// ANIMAÇÃO DO TEXTO
// =============================
let split = SplitText.create(".text", {
    type: "chars, words"
});

gsap.from(split.chars, {
    y: 100,
    autoAlpha: 0,
    stagger: 0.009
});


// =============================
// ANIMAÇÃO DOS CARDS
// =============================
gsap.from(".card", {
    duration: 1,
    y: 60,
    opacity: 0,
    stagger: 0.2,
    ease: "power4.out"
});


// =============================
// EFEITO HOVER NOS CARDS
// =============================
document.querySelectorAll('.card').forEach(card => {

    card.addEventListener('mouseenter', () => {

        const btn = card.querySelector('.floating-btn');

        if(btn){
            gsap.to(btn,{
                scale:1.1,
                duration:0.3
            });
        }

    });

    card.addEventListener('mouseleave', () => {

        const btn = card.querySelector('.floating-btn');

        if(btn){
            gsap.to(btn,{
                scale:1,
                duration:0.3
            });
        }

    });

});


// =============================
// ICONES TECNOLOGIA (efeito aleatório)
// =============================
const icons = document.querySelectorAll('.icon-wrapper');

function getRandomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function highlightRandomIcons(){

    icons.forEach(el => el.classList.remove('active'));

    const count = getRandomInt(1,3);

    const selected = new Set();

    while(selected.size < count){
        selected.add(getRandomInt(0,icons.length - 1));
    }

    selected.forEach(index=>{
        icons[index].classList.add("active");
    });

}

function loop(){

    highlightRandomIcons();

    const nextDelay = getRandomInt(900,1600);

    setTimeout(loop,nextDelay);

}

loop();


// =============================
// MENU MOBILE
// =============================
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


// =============================
// HEADER INTELIGENTE
// =============================
const header = document.querySelector("header");
let lastScroll = 0;

window.addEventListener("scroll", () => {

    const currentScroll = window.scrollY;

    // mostrar quando voltar para a HERO (topo da página)
    if(currentScroll < 100){
        header.classList.remove("header-hidden");
    }

    // esconder apenas quando descer
    else if (currentScroll > lastScroll && currentScroll > 120) {
        header.classList.add("header-hidden");
    }

    // efeito glass
    if(currentScroll > 20){
        header.classList.add("scrolled");
    }else{
        header.classList.remove("scrolled");
    }

    lastScroll = currentScroll;

});


// =============================
// MOSTRAR NAVBAR COM MOUSE NO TOPO
// =============================
document.addEventListener("mousemove",(e)=>{

    if(e.clientY < 60){

        header.classList.remove("header-hidden");

    }

});


// =============================
// ESCONDER BOTÃO RPG AO CHEGAR NA FERRAMENTA
// =============================
window.addEventListener('scroll', function() {

    const scrollIcon = document.querySelector('.rolarpg');
    const targetSection = document.querySelector('#ferramentaaida');

    const sectionPos = targetSection.getBoundingClientRect().top;

    if (sectionPos < window.innerHeight * 0.8) {

        scrollIcon.classList.add('hidden');

    } else {

        scrollIcon.classList.remove('hidden');

    }

});