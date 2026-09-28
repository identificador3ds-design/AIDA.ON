// Previa de HEIC/HEIF no navegador (compartilhado por index-seleciona e
// index-analise). Nenhum navegador de desktop exibe HEIC no <img>; o backend
// le o formato via pillow-heif e analisa normalmente, entao o problema e so
// visual. Este modulo gera um JPEG reduzido, apenas para exibicao, num worker
// com libheif (WASM). O File original nao e tocado e e ele que vai para a API.
//
// Fluxo tipico: a tela de selecao chama `gerar()` no instante em que o arquivo
// e escolhido/arrastado; o resultado fica em sessionStorage e a tela de analise
// o recupera com `recuperar()` sem converter de novo. Se por qualquer motivo a
// previa nao estiver la, `gerar()` na propria tela de analise resolve.
(() => {
  const EXTENSOES_HEIC = ["heic", "heif"];
  const CHAVE_PREVIA = "AIDA_PreviaSelecionada";
  const MAX_LADO_PADRAO = 1280;
  const QUALIDADE_PADRAO = 0.82;

  // URL do worker relativa a este script, nao a pagina: com os rewrites do
  // Vercel (/analise -> /pages/index-analise) o caminho da pagina engana.
  const urlWorker = new URL(
    "aida-previa-heic-worker.js",
    (document.currentScript && document.currentScript.src) || window.location.href
  ).href;

  let worker = null;
  let sequencia = 0;
  const pendentes = new Map();
  // Conversoes em andamento por (nome:tamanho): a tela de selecao dispara a
  // conversao, e se a de analise pedir a mesma imagem recebe a mesma promise.
  const emAndamento = new Map();

  function extensaoDe(nome) {
    return (nome || "").split(".").pop()?.toLowerCase() || "";
  }

  function ehHeic(nomeOuArquivo) {
    const nome = typeof nomeOuArquivo === "string" ? nomeOuArquivo : nomeOuArquivo?.name;
    return EXTENSOES_HEIC.includes(extensaoDe(nome));
  }

  function chaveDe(nome, tamanho) {
    return `${nome || ""}:${tamanho || 0}`;
  }

  function falharTodas(erro) {
    pendentes.forEach(({ reject }) => reject(erro));
    pendentes.clear();
  }

  function obterWorker() {
    if (worker) return worker;
    if (typeof Worker === "undefined") {
      throw new Error("Este navegador nao suporta Web Workers.");
    }

    worker = new Worker(urlWorker);
    worker.onmessage = (evento) => {
      const { id, ok, dataUrl, bruto, erro } = evento.data || {};
      const pendente = pendentes.get(id);
      if (!pendente) return;
      pendentes.delete(id);

      if (!ok) {
        pendente.reject(new Error(erro || "Falha ao converter o HEIC."));
        return;
      }
      if (dataUrl) {
        pendente.resolve(dataUrl);
        return;
      }
      // Worker sem OffscreenCanvas: reduz na thread principal.
      reduzirNaPagina(bruto, pendente.maxLado, pendente.qualidade)
        .then(pendente.resolve)
        .catch(pendente.reject);
    };
    worker.onerror = (evento) => {
      // Um erro de carga (CSP, CDN fora) derruba o worker inteiro; descarta a
      // instancia para que a proxima tentativa recrie do zero.
      const erro = new Error(evento.message || "O worker de previa HEIC falhou.");
      falharTodas(erro);
      try {
        worker.terminate();
      } catch (e) {
        /* ja encerrado */
      }
      worker = null;
    };
    return worker;
  }

  function reduzirNaPagina(bruto, maxLado, qualidade) {
    return new Promise((resolve, reject) => {
      try {
        const { dados, largura, altura } = bruto;
        const escala = Math.min(1, maxLado / Math.max(largura, altura));
        const origem = document.createElement("canvas");
        origem.width = largura;
        origem.height = altura;
        origem.getContext("2d").putImageData(new ImageData(dados, largura, altura), 0, 0);

        const destino = document.createElement("canvas");
        destino.width = Math.max(1, Math.round(largura * escala));
        destino.height = Math.max(1, Math.round(altura * escala));
        destino.getContext("2d").drawImage(origem, 0, 0, destino.width, destino.height);
        resolve(destino.toDataURL("image/jpeg", qualidade));
      } catch (erro) {
        reject(erro);
      }
    });
  }

  // Sobe o worker (download do libheif + instanciacao do WASM) antes de haver
  // arquivo. Chamado ao arrastar sobre a area ou clicar em "Selecionar": o
  // tempo que o usuario gasta no dialogo de arquivos paga o carregamento.
  function precarregar() {
    try {
      obterWorker();
    } catch (erro) {
      /* sem worker: `gerar` reportara o erro quando for chamado */
    }
  }

  function guardar(nome, tamanho, dataUrl) {
    try {
      sessionStorage.setItem(CHAVE_PREVIA, JSON.stringify({ nome, tamanho, dataUrl }));
    } catch (erro) {
      /* cota estourada: a tela de analise converte de novo */
    }
  }

  // So devolve a previa se for da mesma imagem (nome + tamanho): evita mostrar
  // a foto anterior quando o usuario trocou de arquivo e a conversao falhou.
  function recuperar(nome, tamanho) {
    try {
      const salvo = JSON.parse(sessionStorage.getItem(CHAVE_PREVIA) || "null");
      if (salvo && salvo.nome === nome && salvo.tamanho === tamanho && salvo.dataUrl) {
        return salvo.dataUrl;
      }
    } catch (erro) {
      /* JSON invalido: trata como ausente */
    }
    return null;
  }

  function limpar() {
    try {
      sessionStorage.removeItem(CHAVE_PREVIA);
    } catch (erro) {
      /* nada a limpar */
    }
  }

  // Gera (ou reaproveita) a previa JPEG de um Blob/File HEIC. Resolve com um
  // data URL pronto para o <img>. Nunca modifica o arquivo recebido.
  function gerar(arquivo, opcoes = {}) {
    const nome = arquivo?.name || "";
    const tamanho = arquivo?.size || 0;
    const chave = chaveDe(nome, tamanho);

    const guardada = recuperar(nome, tamanho);
    if (guardada) return Promise.resolve(guardada);
    if (emAndamento.has(chave)) return emAndamento.get(chave);

    const maxLado = opcoes.maxLado || MAX_LADO_PADRAO;
    const qualidade = opcoes.qualidade || QUALIDADE_PADRAO;

    const promessa = (async () => {
      const instancia = obterWorker();
      const buffer = await arquivo.arrayBuffer();
      const id = ++sequencia;

      const dataUrl = await new Promise((resolve, reject) => {
        pendentes.set(id, { resolve, reject, maxLado, qualidade });
        // Transfere o buffer em vez de copiar: e uma copia do arquivo, nao o
        // File em si, entao o original continua integro para o upload.
        instancia.postMessage({ id, buffer, maxLado, qualidade }, [buffer]);
      });

      guardar(nome, tamanho, dataUrl);
      return dataUrl;
    })();

    emAndamento.set(chave, promessa);
    promessa.finally(() => emAndamento.delete(chave)).catch(() => {});
    return promessa;
  }

  window.AidaPreviaHeic = { ehHeic, precarregar, gerar, guardar, recuperar, limpar };
})();
