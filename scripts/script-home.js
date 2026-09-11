gsap.registerPlugin(SplitText);


let split = SplitText.create(".text", {
    type: "chars, words"
});

gsap.from(split.chars, {
    y: 100,
    autoAlpha: 0,
    stagger: 0.009,
});
const favicon = document.getElementById('favicon');

function updateFavicon() {

  /* Nem toda pagina declara <link id="favicon">. Sem esta guarda, o erro
     interrompe o script inteiro — inclusive o que vem depois. */
  if (!favicon) {
    return;
  }

  if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    favicon.href = '../assets/images/AIDABranco.ico';
  } else {
    favicon.href = '../assets/images/AIDAPreto.ico';
  }
}


updateFavicon();
