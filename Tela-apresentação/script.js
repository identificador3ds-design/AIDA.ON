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
// =========================
// equipe card 
//----------------------------

gsap.registerPlugin(ScrollTrigger);

const members = [
{
name:"Alexandre",
role:"Head of Documentation",
description:"Responsável pela estruturação e manutenção da documentação técnica do projeto. Atua na organização das metodologias utilizadas, registro dos processos de desenvolvimento e elaboração de relatórios e materiais explicativos. Seu trabalho garante que todas as etapas do projeto estejam bem documentadas, facilitando a compreensão, replicação e evolução da pesquisa.",
image:"../img/Alex 1.png"
},
{
name:"Eduardo",
role:"Data Acquisition Lead",
description:"Responsável pela coleta, seleção e organização dos conjuntos de dados utilizados no projeto. Atua na busca por bases confiáveis de imagens e vídeos, além de realizar a curadoria e preparação dos dados para testes e análises. Seu trabalho é fundamental para garantir qualidade, diversidade e consistência nos dados utilizados pelos métodos de detecção.",
image:"../img/Nidulu 1.png"
},
{
name:"Arthur",
role:"Head of Detection Methodologies",
description:"Responsável pelo estudo, desenvolvimento e implementação das metodologias de detecção de conteúdo gerado ou manipulado por inteligência artificial. Atua na análise de diferentes abordagens e algoritmos, avaliando sua eficácia e aplicabilidade no contexto do projeto. Seu foco é garantir precisão, confiabilidade e inovação nas técnicas utilizadas.",
image:"../img/Arthur 1.png"
},
{
name:"Pedro",
role:"UX/UI Designer & Lead Frontend",
description:"Responsável pelo design da interface e pela experiência do usuário da plataforma. Atua no planejamento visual, prototipagem e desenvolvimento do frontend do site, garantindo uma navegação intuitiva, moderna e funcional. Seu trabalho conecta a tecnologia desenvolvida no projeto com uma interface clara e acessível para os usuários.",
image:"../img/Pedro 1.png"
},
{
name:"Iago",
role:"Project Manager & Lead Backend",
description:"Responsável pela coordenação geral do projeto e pelo desenvolvimento da arquitetura backend da plataforma. Atua na organização das tarefas da equipe, integração dos sistemas e implementação das funcionalidades que processam e gerenciam os dados. Seu trabalho garante o funcionamento estrutural da aplicação e a integração entre todas as partes do sistema.",
image:"../img/Iago 2.png"
}
];

const photo = document.getElementById("memberPhoto");
const bigName = document.getElementById("memberBigName");
const name = document.getElementById("memberName");
const role = document.getElementById("memberRole");
const description = document.getElementById("memberDescription");

let currentIndex = -1;

function changeMember(index){

if(index === currentIndex) return;

currentIndex = index;

const member = members[index];

const tl = gsap.timeline();

tl.to("#memberPhoto",{
x:-150,
opacity:0,
duration:0.35,
ease:"power2.out"
})

.to(".team-card",{
y:40,
opacity:0,
duration:0.25
},"<")

.add(()=>{

photo.src = member.image;

bigName.textContent = member.name.toUpperCase();
name.textContent = member.name;
role.textContent = member.role;
description.textContent = member.description;

document.querySelectorAll(".icon").forEach(i=>{
i.classList.remove("active");
});

document.getElementById("icon"+index).classList.add("active");

})

.fromTo("#memberPhoto",
{ x:150, opacity:0 },
{ x:0, opacity:1, duration:0.5, ease:"power3.out" }
)

.fromTo(".team-card",
{ y:40, opacity:0 },
{ y:0, opacity:1, duration:0.45 },
"<");

}

ScrollTrigger.create({

trigger:".team-section",
start:"top top",
end:"+=5000",
scrub:1,
pin:true,


onUpdate:(self)=>{

const progress = self.progress;

let index = Math.floor(progress * members.length);

if(index >= members.length) index = members.length - 1;

changeMember(index);

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
// =============================
// HEADER INTELIGENTE
// =============================

// =============================
// HEADER INTELIGENTE (estável com GSAP)
// =============================

// =============================
// HEADER INTELIGENTE (compatível com GSAP)
// =============================

const header = document.querySelector("header");
const hero = document.querySelector(".hero");

window.addEventListener("scroll", () => {

    const heroBottom = hero.getBoundingClientRect().bottom;

    // enquanto estiver na hero
    if(heroBottom > 0){

        header.classList.remove("header-hidden");

    }else{

        header.classList.add("header-hidden");

    }

});


// mostrar header com mouse no topo
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