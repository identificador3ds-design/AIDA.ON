/* Envio unificado (index-enviar.html): descobre o tipo do arquivo e leva à página
 * do detector certo, com o arquivo já escolhido (scripts/aida-encaminhar.js). */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const drop = $("envDrop");
  const input = $("envArquivo");
  const botao = $("envEscolher");
  const erro = $("envErro");
  const destino = $("envDestino");
  const enc = window.AIDAEncaminhar;
  if (!drop || !input || !enc) return;

  const NOMES = {
    imagem: { artigo: "uma imagem", detector: "AIDA Image" },
    video: { artigo: "um vídeo", detector: "AIDA Video" },
    audio: { artigo: "um áudio", detector: "AIDA Audio" },
    documento: { artigo: "um PDF", detector: "AIDA Documents" },
  };
  const reduzirMovimento = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  function mostrarErro(texto) {
    erro.textContent = texto;
    erro.hidden = false;
    destino.hidden = true;
    document.querySelectorAll("[data-tipo].ativo").forEach((n) => n.classList.remove("ativo"));
  }

  async function processar(arquivo) {
    if (!arquivo) return;
    erro.hidden = true;
    const tipo = enc.tipoDe(arquivo);
    if (!tipo) {
      mostrarErro("Formato não reconhecido. Envie uma imagem, um vídeo, um áudio ou um PDF.");
      return;
    }
    // Realça o detector escolhido antes de sair da página: o usuário vê para onde vai.
    document.querySelectorAll("[data-tipo]").forEach((n) => n.classList.toggle("ativo", n.dataset.tipo === tipo));
    drop.classList.add("env-drop--detectado");
    destino.textContent = `Detectamos ${NOMES[tipo].artigo}: abrindo o ${NOMES[tipo].detector}…`;
    destino.hidden = false;
    try {
      await new Promise((r) => setTimeout(r, reduzirMovimento ? 0 : 900));
      await enc.encaminhar(arquivo, tipo);
    } catch (_) {
      mostrarErro(`Não foi possível abrir o ${NOMES[tipo].detector} com este arquivo. Abra o detector pelo cartão abaixo.`);
    }
  }

  botao.addEventListener("click", () => { input.value = ""; input.click(); });
  drop.addEventListener("click", (e) => { if (e.target === drop) { input.value = ""; input.click(); } });
  drop.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.value = ""; input.click(); }
  });
  input.addEventListener("change", () => processar(input.files[0]));

  // Arquivo solto fora do cartão faria o navegador abri-lo e descartar a página.
  ["dragover", "drop"].forEach((ev) => document.addEventListener(ev, (e) => e.preventDefault()));
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.add("env-drop--sobre")));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("env-drop--sobre")));
  drop.addEventListener("drop", (e) => processar(e.dataTransfer && e.dataTransfer.files[0]));
})();
