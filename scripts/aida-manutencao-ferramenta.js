/* ==========================================================================
   AIDA — tela de manutenção por ferramenta
   ==========================================================================

   O painel admin grava em `admin_config.config`:
     maintenanceMode            → manutenção geral: todas as ferramentas;
     toolsMaintenance.<chave>   → manutenção de UMA ferramenta.

   Uso numa página de ferramenta, no <head>:
     <script src="../scripts/aida-manutencao-ferramenta.js" data-ferramenta="video"></script>

   Sem `data-ferramenta`, o script só publica o catálogo (window.AidaFerramentas),
   usado pelo painel admin e pela própria tela de manutenção.

   A configuração vem do localStorage (AIDA_ADMIN_CONFIG), que
   aida-config-remota.js atualiza do Supabase. Quando a busca remota termina,
   ele dispara `aida:config-atualizada` e a trava é reavaliada — senão a
   manutenção recém-ligada só valeria a partir da segunda visita.

   É uma trava de experiência, não de segurança: quem abre o console passa por
   ela. O que precisa ser protegido de verdade é protegido no servidor.
   ========================================================================== */
(function () {
  "use strict";

  var CHAVE_CONFIG = "AIDA_ADMIN_CONFIG";

  var FERRAMENTAS = {
    image: {
      nome: "AIDA Image",
      descricao: "Seleção e análise de imagens.",
      destino: "./index-seleciona.html",
      paginas: ["./index-seleciona.html", "./index-analise.html"],
    },
    forensics: {
      nome: "AIDA Forensics",
      descricao: "Análise forense detalhada da imagem.",
      destino: "./index-forensics.html",
      paginas: ["./index-forensics.html"],
    },
    video: {
      nome: "AIDA Video",
      descricao: "Análise de vídeos.",
      destino: "./index-video.html",
      paginas: ["./index-video.html"],
    },
    audio: {
      nome: "AIDA Audio",
      descricao: "Análise de áudios.",
      destino: "./index-audio.html",
      paginas: ["./index-audio.html"],
    },
    documents: {
      nome: "AIDA Documents",
      descricao: "Análise de documentos (PDF, Word e outros).",
      destino: "./index-documentos.html",
      paginas: ["./index-documentos.html"],
    },
  };

  function lerConfig() {
    try {
      return JSON.parse(localStorage.getItem(CHAVE_CONFIG) || "{}") || {};
    } catch (erro) {
      return {};
    }
  }

  function usuarioEhAdmin() {
    try {
      return localStorage.getItem("usuarioTipo") === "admin";
    } catch (erro) {
      return false;
    }
  }

  function emManutencao(chave, config) {
    config = config || lerConfig();
    if (!FERRAMENTAS[chave]) {
      return false;
    }
    var porFerramenta = config.toolsMaintenance && typeof config.toolsMaintenance === "object"
      ? config.toolsMaintenance
      : {};
    return Boolean(config.maintenanceMode) || Boolean(porFerramenta[chave]);
  }

  /* Ferramenta dona de um destino "./index-x.html" (usado pela tela de manutenção). */
  function ferramentaDoDestino(destino) {
    var chaves = Object.keys(FERRAMENTAS);
    for (var i = 0; i < chaves.length; i += 1) {
      if (FERRAMENTAS[chaves[i]].paginas.indexOf(destino) !== -1) {
        return chaves[i];
      }
    }
    return null;
  }

  window.AidaFerramentas = {
    lista: FERRAMENTAS,
    emManutencao: emManutencao,
    ferramentaDoDestino: ferramentaDoDestino,
    usuarioEhAdmin: usuarioEhAdmin,
  };

  var script = document.currentScript;
  var chave = script && script.dataset ? script.dataset.ferramenta : "";
  if (!chave || !FERRAMENTAS[chave]) {
    return;
  }

  // A Vercel serve com cleanUrls (/pages/index-video) e atalhos (/video): o
  // destino guardado é sempre a forma "./index-x.html" que a tela de
  // manutenção aceita; atalho desconhecido volta ao destino da ferramenta.
  var segmento = (window.location.pathname.split("/").pop() || "").replace(/\.html$/, "");
  var destinoAtual = "./" + segmento + ".html";
  if (FERRAMENTAS[chave].paginas.indexOf(destinoAtual) === -1) {
    destinoAtual = FERRAMENTAS[chave].destino;
  }

  function avaliar() {
    if (usuarioEhAdmin() || !emManutencao(chave)) {
      return;
    }
    window.location.replace(
      "./index-manutencao.html?ferramenta=" + encodeURIComponent(chave) +
      "&redirect=" + encodeURIComponent(destinoAtual)
    );
  }

  avaliar();
  window.addEventListener("aida:config-atualizada", avaliar);
})();
