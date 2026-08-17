/* ==========================================================================
   AIDA — Soluções (microdemonstrações dos quatro cards)
   ==========================================================================

   Um módulo por card, cada um devolvendo timelines GSAP pausadas. Quem decide
   quando tocar é o observador de viewport, não o módulo: fora da tela nada
   roda, e uma aba em segundo plano derruba tudo.

   Nenhum processamento de imagem acontece aqui. Os mapas forenses do card do
   Forensics são arquivos pré-gerados pelas funções reais do pipeline
   (`aida-space/ferramentas/gerar_assets_demo.py`); o navegador só os exibe.

   Restrições que orientaram o código:

     * só `transform`, `opacity` e `stroke-dashoffset` são animados em laço,
       mais uma custom property (`--split`) no divisor do Forensics;
     * porcentagens de `translateX` se resolvem contra a largura do próprio
       elemento — por isso o playhead e o divisor são trilhos de largura total
       com o desenho na borda esquerda. Sem medição em JavaScript, sem
       recálculo no `resize`;
     * hover é refinamento, e é **específico de cada produto**: o scanner do
       Image, o divisor do Forensics, o playhead do Video e o par
       request/response da API. O que é comum fica na casca (elevação, borda);
     * `prefers-reduced-motion` e ausência de GSAP levam ao mesmo caminho: a
       seção ganha `is-static` e o CSS assume o estado de repouso.

   Nenhum card exibe resultado de análise: não há porcentagem nem valor
   fabricado em lugar nenhum.
   ========================================================================== */

(function () {
  "use strict";

  var secao = document.querySelector("[data-solucoes]");
  if (!secao) return;

  var reduzirMovimento = window.matchMedia("(prefers-reduced-motion: reduce)");
  var hoverFino = window.matchMedia("(hover: hover) and (pointer: fine)");

  // Sem GSAP não há degradação parcial: o CSS já descreve um estado de
  // repouso legível, e meia animação seria pior que nenhuma.
  if (!window.gsap || reduzirMovimento.matches) {
    secao.classList.add("is-static");
    return;
  }

  var gsap = window.gsap;
  var cards = Array.prototype.slice.call(secao.querySelectorAll("[data-sol]"));
  var instancias = [];

  function limitar(valor, minimo, maximo) {
    return Math.min(maximo, Math.max(minimo, valor));
  }

  /* ---------------------------------------------------------------------
     Card 1 — AIDA Image: a fotografia sendo analisada

     A faixa percorre a foto; os pontos de amostragem acendem conforme ela
     passa por eles; o rodapé troca a família de medida em curso. Todas as
     famílias citadas existem no pipeline — espectro, textura, ruído e
     proveniência —, então o rótulo não inventa etapa nenhuma.
     --------------------------------------------------------------------- */

  var FAMILIAS_DE_MEDIDA = ["espectro", "textura", "ruído", "proveniência"];

  function montarImage(card) {
    var fx = card.querySelector(".fx-img");
    if (!fx) return null;

    var banda = fx.querySelector(".fx-img__band");
    var foto = fx.querySelector(".fx-img__foto");
    var cantos = fx.querySelectorAll(".fx-img__canto");
    var pontos = Array.prototype.slice.call(fx.querySelectorAll(".fx-img__ponto"));
    var familia = fx.querySelector("[data-familia]");

    gsap.set(pontos, { opacity: 0, scale: 0.5 });

    var percurso = 4.2;
    // A faixa tem 34% da altura do quadro: -100% a coloca inteiramente acima,
    // 294% inteiramente abaixo.
    var tl = gsap.timeline({ repeat: -1, paused: true, defaults: { ease: "none" } });
    tl.fromTo(banda, { yPercent: -100 }, { yPercent: 294, duration: percurso }, 0);

    // Cada ponto acende quando a varredura cruza a sua altura — é isso que lê
    // como "está medindo aqui, agora". A posição vem do layout (o CSS define
    // `top` em porcentagem), não de uma tabela duplicada aqui.
    var quadro = fx.querySelector(".sol-fx__quadro");
    var alturaQuadro = Math.max((quadro || fx).clientHeight, 1);

    pontos.forEach(function (ponto) {
      var proporcao = ponto.offsetTop / alturaQuadro;
      var quando = limitar(proporcao, 0, 1) * percurso * 0.9 + 0.2;

      tl.to(ponto, { opacity: 0.95, scale: 1, duration: 0.34, ease: "back.out(2)" }, quando);
      tl.to(ponto, { opacity: 0.35, duration: 0.6, ease: "power1.inOut" }, quando + 0.9);
    });

    tl.to(pontos, { opacity: 0, scale: 0.5, duration: 0.4, stagger: 0.04 }, percurso + 0.1);
    tl.to({}, { duration: 0.6 }, percurso + 0.5);

    // Ciclo próprio para a família de medida: dessincronizado da varredura de
    // propósito, porque as medidas não acompanham a posição da faixa.
    var indice = 0;
    var ciclo = gsap.timeline({ repeat: -1, paused: true });
    ciclo.to({}, {
      duration: 2.1,
      onComplete: function () {
        indice = (indice + 1) % FAMILIAS_DE_MEDIDA.length;
        if (familia) {
          gsap.fromTo(
            familia,
            { opacity: 0, y: -4 },
            { opacity: 1, y: 0, duration: 0.3, ease: "power2.out" }
          );
          familia.textContent = FAMILIAS_DE_MEDIDA[indice];
        }
      },
    });

    return {
      timelines: [tl, ciclo],
      entrar: function () {
        gsap.to(tl, { timeScale: 1.7, duration: 0.4, overwrite: true });
        gsap.to(cantos, { opacity: 1, duration: 0.3, overwrite: "auto" });
        // Leve profundidade: a foto avança um pouco sob a varredura.
        gsap.to(foto, { scale: 1.05, duration: 0.6, ease: "power2.out", overwrite: true });
      },
      mover: function (proporcaoX, proporcaoY) {
        // Deslocamento mínimo da fotografia na direção do cursor. Intensidade
        // baixa de propósito: isto é profundidade, não efeito 3D.
        gsap.to(foto, {
          xPercent: (proporcaoX - 0.5) * -2.2,
          yPercent: (proporcaoY - 0.5) * -2.2,
          duration: 0.7,
          ease: "power2.out",
          overwrite: "auto",
        });
      },
      sair: function () {
        gsap.to(tl, { timeScale: 1, duration: 0.5, overwrite: true });
        gsap.to(cantos, { opacity: 0.5, duration: 0.35, overwrite: "auto" });
        gsap.to(foto, {
          scale: 1,
          xPercent: 0,
          yPercent: 0,
          duration: 0.6,
          ease: "power2.out",
          overwrite: true,
        });
      },
    };
  }

  /* ---------------------------------------------------------------------
     Card 2 — AIDA Forensics: original contra as saídas reais do AIDA
     --------------------------------------------------------------------- */

  function montarForensics(card) {
    var fx = card.querySelector(".fx-for");
    if (!fx) return null;

    var camadas = Array.prototype.slice.call(fx.querySelectorAll(".fx-for__layer"));
    var rotulo = fx.querySelector("[data-metodo-atual]");
    var indice = 0;
    if (!camadas.length) return null;

    gsap.set(fx, { "--split": 0.4 });
    camadas.forEach(function (camada, i) {
      gsap.set(camada, { opacity: i === 0 ? 1 : 0 });
    });

    // Vaivém lento do divisor. É o movimento automático que faz o card
    // funcionar no toque, onde não existe cursor para arrastar.
    var vaivem = gsap.to(fx, {
      "--split": 0.72,
      duration: 3.6,
      ease: "sine.inOut",
      yoyo: true,
      repeat: -1,
      paused: true,
    });

    function trocarMetodo() {
      var anterior = camadas[indice];
      indice = (indice + 1) % camadas.length;
      var proxima = camadas[indice];

      gsap.to(anterior, { opacity: 0, duration: 0.55, ease: "power1.inOut" });
      gsap.to(proxima, { opacity: 1, duration: 0.55, ease: "power1.inOut" });

      if (rotulo) {
        rotulo.textContent = proxima.getAttribute("data-metodo") || "";
        gsap.fromTo(
          rotulo,
          { opacity: 0, y: -4 },
          { opacity: 1, y: 0, duration: 0.3, ease: "power2.out" }
        );
      }
    }

    var ciclo = gsap.timeline({ repeat: -1, paused: true });
    ciclo.to({}, { duration: 3.4, onComplete: trocarMetodo });

    var seguindoCursor = false;

    return {
      timelines: [vaivem, ciclo],
      entrar: function () {
        seguindoCursor = true;
        vaivem.pause();
        gsap.to(ciclo, { timeScale: 1.9, duration: 0.4, overwrite: true });
      },
      mover: function (proporcaoX) {
        if (!seguindoCursor) return;
        // Limitado a 10%..90%: nas pontas o card viraria só uma das leituras, e
        // a comparação — que é o assunto do produto — desapareceria.
        gsap.to(fx, {
          "--split": limitar(proporcaoX, 0.1, 0.9),
          duration: 0.45,
          ease: "power2.out",
          overwrite: true,
        });
      },
      sair: function () {
        seguindoCursor = false;
        gsap.to(ciclo, { timeScale: 1, duration: 0.4, overwrite: true });
        // Retoma o vaivém a partir de onde o cursor deixou o divisor, em vez de
        // saltar para o começo do ciclo.
        gsap.to(fx, {
          "--split": 0.4,
          duration: 0.7,
          ease: "power2.inOut",
          overwrite: true,
          onComplete: function () {
            vaivem.play();
          },
        });
      },
    };
  }

  /* ---------------------------------------------------------------------
     Card 3 — AIDA Video: frames reais lidos ao longo do tempo
     --------------------------------------------------------------------- */

  function montarVideo(card) {
    var fx = card.querySelector(".fx-vid");
    if (!fx) return null;

    var playhead = fx.querySelector(".fx-vid__playhead");
    var frames = Array.prototype.slice.call(fx.querySelectorAll(".fx-vid__frame"));
    var pontos = Array.prototype.slice.call(fx.querySelectorAll(".fx-vid__dot"));
    if (!frames.length) return null;

    gsap.set(frames, { opacity: 0.42, y: 0, scale: 1 });
    gsap.set(pontos, { opacity: 0, y: 4 });

    var percurso = 4.4;
    var tl = gsap.timeline({ repeat: -1, paused: true, defaults: { ease: "none" } });
    tl.fromTo(playhead, { xPercent: 0 }, { xPercent: 100, duration: percurso }, 0);

    frames.forEach(function (frame, i) {
      var quando = (i / frames.length) * percurso;

      tl.to(frame, { opacity: 1, y: -4, duration: 0.3, ease: "power2.out" }, quando);
      tl.call(function () { frame.classList.add("is-lido"); }, null, quando);
      tl.to(frame, { y: 0, duration: 0.5, ease: "power2.inOut" }, quando + 0.45);

      if (pontos[i]) {
        tl.to(pontos[i], { opacity: 1, y: 0, duration: 0.3, ease: "power2.out" }, quando + 0.1);
      }
    });

    // Pausa curta no fim e volta ao estado inicial: sem isso o laço reinicia
    // com todos os frames acesos e a leitura de progresso se perde.
    tl.to({}, { duration: 0.6 }, percurso);
    tl.call(function () {
      frames.forEach(function (frame) { frame.classList.remove("is-lido"); });
    }, null, percurso + 0.3);
    tl.to(frames, { opacity: 0.42, duration: 0.4 }, percurso + 0.3);
    tl.to(pontos, { opacity: 0, y: 4, duration: 0.4 }, percurso + 0.3);

    var maisProximo = null;

    return {
      timelines: [tl],
      entrar: function () {
        gsap.to(tl, { timeScale: 1.8, duration: 0.4, overwrite: true });
      },
      mover: function (proporcaoX) {
        // O frame sob o cursor ganha destaque — a resposta específica deste
        // produto é a leitura quadro a quadro.
        var alvo = frames[limitar(Math.floor(proporcaoX * frames.length), 0, frames.length - 1)];
        if (alvo === maisProximo) return;

        if (maisProximo) {
          gsap.to(maisProximo, { scale: 1, duration: 0.3, ease: "power2.out", overwrite: "auto" });
        }
        maisProximo = alvo;
        gsap.to(alvo, { scale: 1.12, duration: 0.3, ease: "back.out(2)", overwrite: "auto" });
      },
      sair: function () {
        gsap.to(tl, { timeScale: 1, duration: 0.5, overwrite: true });
        gsap.to(frames, { scale: 1, duration: 0.35, ease: "power2.out", overwrite: "auto" });
        maisProximo = null;
      },
    };
  }

  /* ---------------------------------------------------------------------
     Card 4 — AIDA API: requisição e resposta entre sistemas
     --------------------------------------------------------------------- */

  function montarApi(card) {
    var fx = card.querySelector(".fx-api");
    if (!fx) return null;

    var pulso = fx.querySelector(".fx-api__pulse");
    var nos = Array.prototype.slice.call(fx.querySelectorAll(".fx-api__node"));
    var endpoint = fx.querySelector(".fx-api__endpoint");
    var campos = Array.prototype.slice.call(fx.querySelectorAll(".fx-api__campo"));
    if (!pulso) return null;

    // O comprimento vem do próprio caminho: o pulso percorre exatamente o
    // trilho, qualquer que seja a geometria desenhada no SVG.
    var comprimento = pulso.getTotalLength();
    var tamanhoPulso = Math.max(10, comprimento * 0.14);
    gsap.set(pulso, {
      strokeDasharray: tamanhoPulso + " " + comprimento,
      strokeDashoffset: comprimento,
    });
    gsap.set(nos, { opacity: 0.72, scale: 1 });
    gsap.set(campos, { opacity: 0, x: -6 });

    var tl = gsap.timeline({ repeat: -1, paused: true });

    // Ida: APP → AIDA. Volta: AIDA → RESPONSE. O pulso some atrás do nó
    // central, o que lê como "entrou no AIDA e saiu do outro lado".
    tl.to(pulso, { strokeDashoffset: -tamanhoPulso, duration: 2.1, ease: "power1.inOut" }, 0);

    nos.forEach(function (no, i) {
      var quando = 0.1 + i * 0.78;
      tl.to(no, { opacity: 1, scale: 1.08, duration: 0.22, ease: "power2.out" }, quando);
      tl.to(no, { opacity: 0.72, scale: 1, duration: 0.4, ease: "power2.inOut" }, quando + 0.3);
    });

    // Os campos da resposta entram em cascata, como um corpo sendo recebido.
    campos.forEach(function (campo, i) {
      tl.to(campo, { opacity: 1, x: 0, duration: 0.26, ease: "power2.out" }, 1.7 + i * 0.16);
    });
    tl.to(campos, { opacity: 0, x: -6, duration: 0.3, stagger: 0.05 }, 4.1);
    tl.to({}, { duration: 0.5 }, 4.5);

    return {
      timelines: [tl],
      entrar: function () {
        gsap.to(tl, { timeScale: 1.6, duration: 0.4, overwrite: true });
        gsap.to(pulso, { opacity: 1, strokeWidth: 2.1, duration: 0.3, overwrite: "auto" });
        if (endpoint) endpoint.style.color = "var(--sol-accent)";
      },
      sair: function () {
        gsap.to(tl, { timeScale: 1, duration: 0.5, overwrite: true });
        gsap.to(pulso, { opacity: 0.9, strokeWidth: 1.6, duration: 0.35, overwrite: "auto" });
        if (endpoint) endpoint.style.color = "";
      },
    };
  }

  var CONSTRUTORES = {
    image: montarImage,
    forensics: montarForensics,
    video: montarVideo,
    api: montarApi,
  };

  /* ---------------------------------------------------------------------
     Montagem, viewport e ponteiro
     --------------------------------------------------------------------- */

  cards.forEach(function (card) {
    var construtor = CONSTRUTORES[card.getAttribute("data-sol")];
    if (!construtor) return;

    var instancia;
    try {
      instancia = construtor(card);
    } catch (erro) {
      // Um palco com marcação incompleta não pode derrubar os outros três.
      if (window.console) console.warn("[AIDA] palco não montado:", erro);
      return;
    }
    if (!instancia) return;

    instancia.card = card;
    instancia.visivel = false;
    instancias.push(instancia);
  });

  if (!instancias.length) return;

  function tocar(instancia) {
    instancia.timelines.forEach(function (tl) { tl.play(); });
  }

  function pausar(instancia) {
    instancia.timelines.forEach(function (tl) { tl.pause(); });
  }

  // Fora da viewport nenhum card consome quadro. O limiar de 0.15 evita que a
  // timeline arranque com o card ainda cortado pela borda da tela.
  var observador = new IntersectionObserver(
    function (entradas) {
      entradas.forEach(function (entrada) {
        var instancia = instancias.filter(function (i) {
          return i.card === entrada.target;
        })[0];
        if (!instancia) return;

        instancia.visivel = entrada.isIntersecting;
        if (entrada.isIntersecting && !document.hidden) tocar(instancia);
        else pausar(instancia);
      });
    },
    { threshold: 0.15 }
  );

  instancias.forEach(function (instancia) {
    observador.observe(instancia.card);
  });

  document.addEventListener("visibilitychange", function () {
    instancias.forEach(function (instancia) {
      if (document.hidden || !instancia.visivel) pausar(instancia);
      else tocar(instancia);
    });
  });

  // Se o usuário ligar a redução de movimento com a página aberta, as
  // timelines param e o CSS estático assume.
  if (typeof reduzirMovimento.addEventListener === "function") {
    reduzirMovimento.addEventListener("change", function (evento) {
      if (!evento.matches) return;
      instancias.forEach(pausar);
      secao.classList.add("is-static");
    });
  }

  /* ---------------------------------------------------------------------
     Ponteiro

     Um único rAF por quadro atualiza a posição usada pela borda reativa e pela
     resposta interna do palco. Registrar isto em telas de toque não faria
     sentido: lá o `pointermove` chega apenas junto do toque, e a borda
     piscaria a cada rolagem.
     --------------------------------------------------------------------- */

  if (!hoverFino.matches) return;

  instancias.forEach(function (instancia) {
    var card = instancia.card;
    var pendente = null;

    function aplicar(clientX, clientY) {
      pendente = null;
      var caixa = card.getBoundingClientRect();
      if (!caixa.width || !caixa.height) return;

      card.style.setProperty("--sol-mx", (((clientX - caixa.left) / caixa.width) * 100).toFixed(2) + "%");
      card.style.setProperty("--sol-my", (((clientY - caixa.top) / caixa.height) * 100).toFixed(2) + "%");

      if (typeof instancia.mover === "function") {
        // A proporção é medida sobre o palco, não sobre o card: senão o divisor
        // do Forensics nunca alcançaria as bordas da comparação.
        var palco = card.querySelector(".sol-card__stage");
        var caixaPalco = palco ? palco.getBoundingClientRect() : caixa;
        instancia.mover(
          (clientX - caixaPalco.left) / caixaPalco.width,
          (clientY - caixaPalco.top) / caixaPalco.height
        );
      }
    }

    card.addEventListener("pointermove", function (evento) {
      if (evento.pointerType === "touch") return;
      // As coordenadas são copiadas agora: guardar o evento e lê-lo no quadro
      // seguinte funciona hoje, mas depende de o navegador não reciclar o
      // objeto — e não há motivo para depender disso.
      var clientX = evento.clientX;
      var clientY = evento.clientY;
      if (pendente) cancelAnimationFrame(pendente);
      pendente = requestAnimationFrame(function () {
        aplicar(clientX, clientY);
      });
    });

    card.addEventListener("pointerenter", function (evento) {
      if (evento.pointerType === "touch") return;
      if (typeof instancia.entrar === "function") instancia.entrar();
    });

    card.addEventListener("pointerleave", function (evento) {
      if (evento.pointerType === "touch") return;
      if (pendente) {
        cancelAnimationFrame(pendente);
        pendente = null;
      }
      if (typeof instancia.sair === "function") instancia.sair();
    });

    // Navegação por teclado recebe a mesma intensificação do hover: quem chega
    // ao CTA pelo Tab vê o mesmo card que quem chega pelo mouse.
    card.addEventListener("focusin", function () {
      if (typeof instancia.entrar === "function") instancia.entrar();
    });

    card.addEventListener("focusout", function (evento) {
      if (card.contains(evento.relatedTarget)) return;
      if (typeof instancia.sair === "function") instancia.sair();
    });
  });
})();
