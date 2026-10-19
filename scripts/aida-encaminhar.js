/* Envio unificado: um único campo de upload que descobre o tipo do arquivo e o
 * entrega à página do detector certo (imagem, vídeo, áudio ou documento).
 *
 * Cada detector continua com a sua página, para quem quer ver como ele funciona.
 * O envio unificado só guarda o arquivo no IndexedDB do navegador (o File vai
 * inteiro, sem virar base64) e abre a página; lá, `entregarEm(input)` coloca o
 * arquivo no campo de upload e dispara o mesmo "change" que o usuário dispararia,
 * então a validação e o fluxo de cada página continuam os de sempre.
 *
 * Nada sai do navegador aqui. O registro expira em 10 minutos e é apagado ao ser
 * lido, para um arquivo antigo não reaparecer numa visita futura.
 */
(function (raiz) {
  "use strict";

  const DB = "AIDA_Encaminhamento";
  const STORE = "arquivos";
  const CHAVE = "pendente";
  const VALIDADE_MS = 10 * 60 * 1000;

  const EXTENSOES = {
    imagem: ["jpg", "jpeg", "png", "webp", "bmp", "heic", "heif", "avif", "tif", "tiff"],
    video: ["mp4", "mov", "m4v", "webm", "mkv", "avi", "3gp"],
    audio: ["wav", "mp3", "m4a", "aac", "ogg", "opus", "flac", "amr"],
    documento: ["pdf"],
  };
  const PAGINAS = {
    imagem: "./index-seleciona.html",
    video: "./index-video.html",
    audio: "./index-audio.html",
    documento: "./index-documentos.html",
  };

  function extensao(arquivo) {
    const nome = (arquivo && arquivo.name) || "";
    return nome.includes(".") ? nome.split(".").pop().toLowerCase() : "";
  }

  // O tipo MIME manda quando existe; sem ele (HEIC e AVIF no Windows, .opus em
  // vários sistemas), a extensão é a única pista.
  function tipoDe(arquivo) {
    if (!arquivo) return null;
    const mime = (arquivo.type || "").toLowerCase();
    if (mime === "application/pdf") return "documento";
    if (mime.startsWith("image/")) return "imagem";
    if (mime.startsWith("video/")) {
      // .webm e .3gp podem ser só áudio, mas o sistema os rotula como vídeo:
      // o servidor de vídeo também lê a trilha de áudio, então o destino serve.
      return "video";
    }
    if (mime.startsWith("audio/")) return "audio";
    const ext = extensao(arquivo);
    for (const [tipo, lista] of Object.entries(EXTENSOES)) {
      if (lista.includes(ext)) return tipo;
    }
    return null;
  }

  function abrir() {
    return new Promise((resolve, reject) => {
      if (!raiz.indexedDB) return reject(new Error("IndexedDB indisponível"));
      const req = raiz.indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error || new Error("IndexedDB falhou"));
    });
  }

  async function guardar(arquivo, tipo) {
    const db = await abrir();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put({ arquivo, tipo, quando: Date.now() }, CHAVE);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  }

  async function retirar(tipo) {
    let db;
    try {
      db = await abrir();
    } catch (_) {
      return null;
    }
    const registro = await new Promise((resolve) => {
      const tx = db.transaction(STORE, "readwrite");
      const loja = tx.objectStore(STORE);
      const req = loja.get(CHAVE);
      req.onsuccess = () => {
        loja.delete(CHAVE);
        resolve(req.result || null);
      };
      req.onerror = () => resolve(null);
    });
    db.close();
    if (!registro || registro.tipo !== tipo || Date.now() - registro.quando > VALIDADE_MS) return null;
    return registro.arquivo || null;
  }

  // Na página de destino: se veio do envio unificado (?de=envio), põe o arquivo
  // no <input type=file> e dispara "change". Devolve o File entregue ou null.
  async function entregarEm(input, tipo) {
    if (!input || new URLSearchParams(raiz.location.search).get("de") !== "envio") return null;
    const arquivo = await retirar(tipo);
    if (!arquivo) return null;
    try {
      const dt = new DataTransfer();
      dt.items.add(arquivo);
      input.files = dt.files;
    } catch (_) {
      return null;                                // navegador sem DataTransfer construtível
    }
    input.dispatchEvent(new Event("change", { bubbles: true }));
    return arquivo;
  }

  async function encaminhar(arquivo, tipo) {
    await guardar(arquivo, tipo);
    raiz.location.href = `${PAGINAS[tipo]}?de=envio`;
  }

  raiz.AIDAEncaminhar = { tipoDe, guardar, retirar, entregarEm, encaminhar, PAGINAS, EXTENSOES };
})(typeof window !== "undefined" ? window : this);
