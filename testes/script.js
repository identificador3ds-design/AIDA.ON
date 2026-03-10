const nomeSalvo = localStorage.getItem("usuarioNome");
const emailSalvo = localStorage.getItem("usuarioEmail");

    const botaoUsuario1 = document.getElementById("nome-usuario");
    const botaoUsuario2 = document.getElementById("email-usuario");

    if (nomeSalvo) {

        if (botaoUsuario1) {
            botaoUsuario1.innerText = `Olá, ${nomeSalvo}`;
            gsap.from("#nome-usuario", { opacity: 0, duration: 1, y: -10 });
        }

    }
    if (emailSalvo) {
        if (botaoUsuario2) {
            botaoUsuario2.innerText = `Olá, ${emailSalvo}`;
            gsap.from("#email-usuaio", { opacity: 0, duration: 1, y: -10 });
        }
    }