// Worker de previa HEIC/HEIF. Roda o libheif (WASM) fora da thread principal:
// decodifica o arquivo, reduz para o tamanho de miniatura e devolve um JPEG.
// O arquivo original nunca e alterado — o que sai daqui serve so para o <img>.
//
// Nao usa SRI: importScripts nao suporta `integrity`. A versao fica fixada na
// URL, e o CSP do site restringe o worker a cdn.jsdelivr.net.
importScripts("https://cdn.jsdelivr.net/npm/libheif-js@1.23.2/libheif-wasm/libheif-bundle.js");

// Instancia o WASM na hora em que o worker sobe, nao na primeira imagem: quem
// cria o worker cedo (ao arrastar/clicar) ganha esse tempo de graca.
const moduloPronto = libheif();

function decodificarPrimaria(modulo, buffer) {
  const decodificador = new modulo.HeifDecoder();
  const imagens = decodificador.decode(new Uint8Array(buffer));
  if (!imagens || !imagens.length) {
    throw new Error("O arquivo HEIC nao contem imagem.");
  }

  // Um HEIC pode trazer varias imagens (burst, live photo); a primaria e a foto.
  const imagem = imagens.find((i) => i.is_primary()) || imagens[0];
  const largura = imagem.get_width();
  const altura = imagem.get_height();

  return new Promise((resolve, reject) => {
    imagem.display(
      { data: new Uint8ClampedArray(largura * altura * 4), width: largura, height: altura },
      (resultado) => {
        imagens.forEach((i) => i.free());
        if (!resultado) {
          reject(new Error("Falha ao decodificar o HEIC."));
          return;
        }
        resolve({ dados: resultado.data, largura, altura });
      }
    );
  });
}

function dimensoesReduzidas(largura, altura, maxLado) {
  const escala = Math.min(1, maxLado / Math.max(largura, altura));
  return {
    largura: Math.max(1, Math.round(largura * escala)),
    altura: Math.max(1, Math.round(altura * escala)),
  };
}

// Reduz e codifica aqui mesmo quando o navegador oferece OffscreenCanvas no
// worker. O createImageBitmap com resize evita desenhar a foto inteira (12 MP)
// num canvas so para encolher depois — era o passo mais caro.
async function reduzirParaJpeg(decodificada, maxLado, qualidade) {
  const { dados, largura, altura } = decodificada;
  const alvo = dimensoesReduzidas(largura, altura, maxLado);

  const bitmap = await createImageBitmap(new ImageData(dados, largura, altura), {
    resizeWidth: alvo.largura,
    resizeHeight: alvo.altura,
    resizeQuality: "medium",
  });
  const canvas = new OffscreenCanvas(alvo.largura, alvo.altura);
  canvas.getContext("2d").drawImage(bitmap, 0, 0);
  bitmap.close();

  const blob = await canvas.convertToBlob({ type: "image/jpeg", quality: qualidade });
  return new Promise((resolve, reject) => {
    const leitor = new FileReader();
    leitor.onload = () => resolve(leitor.result);
    leitor.onerror = () => reject(new Error("Falha ao serializar a previa."));
    leitor.readAsDataURL(blob);
  });
}

self.onmessage = async (evento) => {
  const { id, buffer, maxLado = 1280, qualidade = 0.82 } = evento.data || {};

  try {
    const modulo = await moduloPronto;
    const decodificada = await decodificarPrimaria(modulo, buffer);

    if (typeof OffscreenCanvas === "undefined" || typeof createImageBitmap === "undefined") {
      // Navegador sem canvas no worker: devolve os pixels crus e a pagina reduz.
      self.postMessage(
        {
          id,
          ok: true,
          bruto: { dados: decodificada.dados, largura: decodificada.largura, altura: decodificada.altura },
          largura: decodificada.largura,
          altura: decodificada.altura,
        },
        [decodificada.dados.buffer]
      );
      return;
    }

    const dataUrl = await reduzirParaJpeg(decodificada, maxLado, qualidade);
    self.postMessage({ id, ok: true, dataUrl, largura: decodificada.largura, altura: decodificada.altura });
  } catch (erro) {
    self.postMessage({ id, ok: false, erro: String((erro && erro.message) || erro) });
  }
};
