document.addEventListener("DOMContentLoaded", () => {
  const nomeSalvo = localStorage.getItem("usuarioNome");
  const emailSalvo = localStorage.getItem("usuarioEmail");
  const nome = document.getElementById("nome-usuario");
  const email = document.getElementById("email-usuario");
  const logoutLink = document.getElementById("logout-link");

  if (nomeSalvo && nome) {
    nome.textContent = nomeSalvo;
  }

  if (emailSalvo && email) {
    email.textContent = emailSalvo;
  }

  if (logoutLink) {
    logoutLink.addEventListener("click", () => {
      localStorage.removeItem("usuarioNome");
      localStorage.removeItem("usuarioEmail");
    });
  }
});
