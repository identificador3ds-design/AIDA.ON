const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

const EXEMPLOS_LSB = [
  {
    rotulo: "IA",
    classe: "ia",
    titulo: "Referencia de imagem gerada por IA",
    imagem: "../Imagens%20exemplos/exemplo-lsb-ia.png",
    descricao:
      "Neste mapa LSB, o ruido aparece mais concentrado e com padroes repetitivos. Esse comportamento costuma indicar uma distribuicao artificial dos bits menos significativos.",
  },
  {
    rotulo: "Real",
    classe: "real",
    titulo: "Referencia de imagem real",
    imagem: "../Imagens%20exemplos/exemplo-lsb-real.png",
    descricao:
      "Aqui a distribuicao dos pixels ativos fica mais irregular e organica, sem blocos tao consistentes. Esse comportamento tende a combinar melhor com fotos reais.",
  },
];

function base64ToBlob(base64, mime) {
  const byteString = atob(base64.split(",")[1]);
  const bytes = new Uint8Array(byteString.length);

  for (let index = 0; index < byteString.length; index += 1) {
    bytes[index] = byteString.charCodeAt(index);
  }

  return new Blob([bytes], { type: mime });
}

function obterMimeType(base64) {
  const correspondencia = base64.match(/^data:(.*?);base64,/);
  return correspondencia ? correspondencia[1] : "image/png";
}

function mostrarAlerta(mensagem) {
  let container = document.getElementById("toast-container");

  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = "toast-card";
  toast.innerText = mensagem;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("fadeOut");
    setTimeout(() => toast.remove(), 350);
  }, 3200);
}

function montarDescricaoMetodo(dados) {
  const metodoRetornado = String(dados.metodo || "").toLowerCase();

  if (metodoRetornado.includes("marca visual")) {
    const iaNome = dados.metodo.replace("Marca Visual (", "").replace(")", "");
    return `Marca visual encontrada\n\nEncontramos uma marca visivel no canto inferior direito da imagem, ligada a ferramenta ${iaNome}. Isso e um sinal forte de que a imagem foi gerada por IA.`;
  }

  if (metodoRetornado.includes("metadados")) {
    const iaNome = dados.metodo.replace("Metadados (", "").replace(")", "");
    return `Metadados encontrados\n\nO arquivo traz informacoes internas ligadas a ferramenta ${iaNome}. Isso sugere que a imagem foi exportada por um gerador de imagem.`;
  }

  if (metodoRetornado.includes("lsb")) {
    return `Resultado do metodo LSB\n\nO metodo encontrou ${dados.energia} pixels ativos nas partes menos visiveis da imagem. Quando esse numero fica muito concentrado, pode haver sinais artificiais ou marcas digitais escondidas.`;
  }

  if (
    metodoRetornado.includes("gradiente") ||
    metodoRetornado.includes("laplaciano") ||
    metodoRetornado.includes("neon")
  ) {
    return `Resultado do gradiente\n\nO metodo destacou bordas e areas com mudancas fortes na imagem. A intensidade media encontrada foi ${dados.energia}, o que ajuda a revelar texturas artificiais e padroes de geracao por IA.`;
  }

  if (
    metodoRetornado.includes("frequencia") ||
    metodoRetornado.includes("fft") ||
    metodoRetornado.includes("consistencia")
  ) {
    return `Resultado da frequencia\n\nA leitura de frequencia encontrou energia ${dados.energia}. Quando esse valor foge do esperado, a imagem pode ter sido criada ou alterada de forma artificial.`;
  }

  return `Resumo da analise\n\nMetodo utilizado: ${dados.metodo}\nChance de IA: ${dados.probabilidade}\nEnergia encontrada: ${dados.energia}`;
}

function limparExemplosMetodo(bloco, titulo, descricao, lista) {
  if (bloco) {
    bloco.hidden = true;
  }

  if (titulo) {
    titulo.innerText = "Referencias para comparacao";
  }

  if (descricao) {
    descricao.innerText = "";
  }

  if (lista) {
    lista.innerHTML = "";
  }
}

function criarCardExemplo(exemplo) {
  const card = document.createElement("article");
  card.className = "card-exemplo";

  const visual = document.createElement("div");
  visual.className = "visual-exemplo";

  const etiqueta = document.createElement("span");
  etiqueta.className = `etiqueta-exemplo ${exemplo.classe || ""}`.trim();
  etiqueta.innerText = exemplo.rotulo || "";
  visual.appendChild(etiqueta);

  const imagem = document.createElement("img");
  imagem.className = "imagem-exemplo";
  imagem.src = exemplo.imagem;
  imagem.alt = exemplo.titulo || exemplo.rotulo || "Exemplo";
  visual.appendChild(imagem);

  const corpo = document.createElement("div");
  corpo.className = "corpo-exemplo";

  const titulo = document.createElement("h5");
  titulo.className = "titulo-card-exemplo";
  titulo.innerText = exemplo.titulo || "";
  corpo.appendChild(titulo);

  const descricao = document.createElement("p");
  descricao.className = "descricao-card-exemplo";
  descricao.innerText = exemplo.descricao || "";
  corpo.appendChild(descricao);

  card.appendChild(visual);
  card.appendChild(corpo);

  return card;
}

function renderizarCardsExemplo(bloco, titulo, descricao, lista, conteudo) {
  if (!bloco || !titulo || !descricao || !lista) {
    return;
  }

  titulo.innerText = conteudo.titulo;
  descricao.innerText = conteudo.descricao;
  lista.innerHTML = "";

  conteudo.itens.forEach((item) => {
    lista.appendChild(criarCardExemplo(item));
  });

  bloco.hidden = conteudo.itens.length === 0;
}

function carregarImagem(src) {
  return new Promise((resolve, reject) => {
    const imagem = new Image();
    imagem.onload = () => resolve(imagem);
    imagem.onerror = () =>
      reject(new Error("Nao foi possivel carregar a imagem para gerar o recorte."));
    imagem.src = src;
  });
}

function numeroSeguro(valor, padrao = 0) {
  const numero = Number(valor);
  return Number.isFinite(numero) ? numero : padrao;
}

function normalizarCaixa(caixa, larguraMaxima, alturaMaxima) {
  if (!caixa) {
    return null;
  }

  const x = numeroSeguro(caixa.x);
  const y = numeroSeguro(caixa.y);
  const width = numeroSeguro(caixa.width);
  const height = numeroSeguro(caixa.height);

  if (width <= 0 || height <= 0 || larguraMaxima <= 0 || alturaMaxima <= 0) {
    return null;
  }

  const xLimitado = Math.max(0, Math.min(x, larguraMaxima - 1));
  const yLimitado = Math.max(0, Math.min(y, alturaMaxima - 1));
  const widthLimitado = Math.max(1, Math.min(width, larguraMaxima - xLimitado));
  const heightLimitado = Math.max(1, Math.min(height, alturaMaxima - yLimitado));

  return {
    x: xLimitado,
    y: yLimitado,
    width: widthLimitado,
    height: heightLimitado,
  };
}

function expandirCaixa(caixa, escala, larguraMaxima, alturaMaxima, tamanhoMinimo = 0) {
  if (!caixa) {
    return null;
  }

  const centroX = caixa.x + caixa.width / 2;
  const centroY = caixa.y + caixa.height / 2;
  let width = Math.max(caixa.width * escala, tamanhoMinimo);
  let height = Math.max(caixa.height * escala, tamanhoMinimo);

  width = Math.min(width, larguraMaxima);
  height = Math.min(height, alturaMaxima);

  const x = Math.max(0, Math.min(centroX - width / 2, larguraMaxima - width));
  const y = Math.max(0, Math.min(centroY - height / 2, alturaMaxima - height));

  return normalizarCaixa({ x, y, width, height }, larguraMaxima, alturaMaxima);
}

function cortarImagemParaDataUrl(imagem, caixa) {
  if (!imagem || !caixa) {
    return "";
  }

  const canvas = document.createElement("canvas");
  const largura = Math.max(1, Math.round(caixa.width));
  const altura = Math.max(1, Math.round(caixa.height));
  const ctx = canvas.getContext("2d");

  if (!ctx) {
    return "";
  }

  canvas.width = largura;
  canvas.height = altura;

  ctx.drawImage(
    imagem,
    Math.round(caixa.x),
    Math.round(caixa.y),
    largura,
    altura,
    0,
    0,
    largura,
    altura
  );

  return canvas.toDataURL("image/png");
}

function obterCaixaGemini(dados, larguraImagem, alturaImagem) {
  const caixaBackend = normalizarCaixa(
    dados?.marca_visual?.bounding_box,
    larguraImagem,
    alturaImagem
  );

  if (caixaBackend) {
    return caixaBackend;
  }

  return normalizarCaixa(
    {
      x: larguraImagem * 0.8,
      y: alturaImagem * 0.8,
      width: larguraImagem * 0.2,
      height: alturaImagem * 0.2,
    },
    larguraImagem,
    alturaImagem
  );
}

async function montarExemplosGemini(dados, imagemBase64) {
  if (!imagemBase64) {
    return [];
  }

  try {
    const imagem = await carregarImagem(imagemBase64);
    const larguraImagem = imagem.naturalWidth || imagem.width;
    const alturaImagem = imagem.naturalHeight || imagem.height;
    const caixaBase = obterCaixaGemini(dados, larguraImagem, alturaImagem);

    if (!caixaBase) {
      return [];
    }

    const recorteContexto = cortarImagemParaDataUrl(
      imagem,
      expandirCaixa(caixaBase, 3.4, larguraImagem, alturaImagem, 180)
    );
    const recorteDetalhe = cortarImagemParaDataUrl(
      imagem,
      expandirCaixa(caixaBase, 1.8, larguraImagem, alturaImagem, 90)
    );

    return [
      {
        rotulo: "Recorte",
        classe: "recorte",
        titulo: "Regiao usada para confirmar a marca visual",
        imagem: recorteContexto || imagemBase64,
        descricao:
          "O detector procura a assinatura do Gemini no canto inferior direito. Este recorte mostra a area principal usada na confirmacao.",
      },
      {
        rotulo: "Logo",
        classe: "recorte",
        titulo: "Ampliacao da evidencia encontrada",
        imagem: recorteDetalhe || recorteContexto || imagemBase64,
        descricao:
          "Este zoom ajuda a verificar se o simbolo esta consistente com a marca do Gemini. Quando a assinatura aparece nitida, a evidencia fica mais forte.",
      },
    ];
  } catch (erro) {
    console.error("Erro ao montar os recortes do Gemini:", erro);
    return [];
  }
}

async function renderizarExemplosMetodo(dados, imagemBase64, elementos) {
  const metodoRetornado = String(dados?.metodo || "").toLowerCase();

  limparExemplosMetodo(
    elementos.bloco,
    elementos.titulo,
    elementos.descricao,
    elementos.lista
  );

  if (metodoRetornado.includes("lsb")) {
    renderizarCardsExemplo(
      elementos.bloco,
      elementos.titulo,
      elementos.descricao,
      elementos.lista,
      {
        titulo: "Referencias visuais do LSB",
        descricao:
          "Compare o seu resultado com estes exemplos. Padroes mais concentrados e repetitivos tendem a favorecer IA; distribuicoes mais organicas e irregulares tendem a favorecer imagem real.",
        itens: EXEMPLOS_LSB,
      }
    );
    return;
  }

  if (metodoRetornado.includes("marca visual") && metodoRetornado.includes("gemini")) {
    const exemplosGemini = await montarExemplosGemini(dados, imagemBase64);

    if (exemplosGemini.length > 0) {
      renderizarCardsExemplo(
        elementos.bloco,
        elementos.titulo,
        elementos.descricao,
        elementos.lista,
        {
          titulo: "Recortes da evidencia detectada",
          descricao:
            "A leitura por marca visual encontrou a assinatura do Gemini. Os recortes abaixo mostram a regiao usada para confirmar essa evidencia.",
          itens: exemplosGemini,
        }
      );
    }
  }
}

async function salvarHistorico(imagemBase64, dados) {
  const {
    data: { user },
  } = await _supabase.auth.getUser();

  if (!user) {
    console.warn("Nenhum usuario logado. O historico nao sera salvo.");
    return;
  }

  const mimeType = obterMimeType(imagemBase64);
  const subtipo = mimeType.split("/")[1] || "png";
  const extensao = subtipo === "jpeg" ? "jpg" : subtipo;
  const blob = base64ToBlob(imagemBase64, mimeType);
  const nomeArquivo = `${user.id}/${Date.now()}_original.${extensao}`;

  const { error: uploadError } = await _supabase.storage
    .from("evidencias")
    .upload(nomeArquivo, blob);

  if (uploadError) {
    console.error("Erro no upload do storage:", uploadError.message);
    return;
  }

  const {
    data: { publicUrl },
  } = _supabase.storage.from("evidencias").getPublicUrl(nomeArquivo);

  const { error: dbError } = await _supabase.from("historico_analises").insert([
    {
      user_id: user.id,
      metodo: dados.metodo,
      probabilidade: dados.probabilidade,
      imagem_original: publicUrl,
      resultado_img: dados.imagem_fft,
    },
  ]);

  if (dbError) {
    console.error("Erro ao salvar na tabela:", dbError.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const nomeSalvo = localStorage.getItem("usuarioNome");
  const botaoUsuario = document.getElementById("nome-usuario2");
  const btnSair = document.getElementById("btn-sair");
  const imagemPreview = document.getElementById("imagemPreview");
  const previewStatus = document.getElementById("previewStatus");
  const btnVerificar = document.getElementById("btnVerificar");
  const btnTrocar = document.getElementById("btnTrocar");
  const inputTrocarImagem = document.getElementById("inputTrocarImagem");
  const tipoImagemInput = document.getElementById("tipoImagem");
  const metodoAnalise = document.getElementById("metodoAnalise");
  const checkMarcaDagua = document.getElementById("checkMarcaDagua");
  const checkMetadados = document.getElementById("checkMetadados");
  const loading = document.getElementById("loading");
  const areaResultado = document.getElementById("areaResultado");
  const imagemProcessada = document.getElementById("imagemProcessada");
  const porcentagemIA = document.getElementById("porcentagemIA");
  const tituloMetodo = document.getElementById("tituloMetodo");
  const textoMetodo = document.getElementById("textoMetodo");
  const blocoExemplosMetodo = document.getElementById("blocoExemplosMetodo");
  const tituloExemplosMetodo = document.getElementById("tituloExemplosMetodo");
  const descricaoExemplosMetodo = document.getElementById("descricaoExemplosMetodo");
  const exemplosMetodo = document.getElementById("exemplosMetodo");

  let imagemAtual = localStorage.getItem("AIDA_ImagemSelecionada") || "";

  if (nomeSalvo && botaoUsuario) {
    botaoUsuario.innerText = `Ola, ${nomeSalvo}`;
  }

  if (window.gsap) {
    gsap.from(".page-header", { opacity: 0, duration: 0.6, y: -18, ease: "power2.out" });
    gsap.from(".card-analise", { opacity: 0, duration: 0.7, y: 24, ease: "power2.out" });
  }

  if (btnSair) {
    btnSair.addEventListener("click", async (event) => {
      event.preventDefault();
      localStorage.removeItem("usuarioNome");
      localStorage.removeItem("usuarioEmail");
      localStorage.removeItem("AIDA_ImagemSelecionada");

      try {
        await _supabase.auth.signOut();
      } catch (erro) {
        console.warn("Nao foi possivel encerrar a sessao do Supabase:", erro);
      }

      window.location.href = "../login/index-login.html";
    });
  }

  function limparResultado() {
    if (loading) {
      loading.style.display = "none";
    }

    if (areaResultado) {
      areaResultado.style.display = "none";
    }

    if (imagemProcessada) {
      imagemProcessada.src = "#";
    }

    if (porcentagemIA) {
      porcentagemIA.innerText = "0%";
    }

    if (tituloMetodo) {
      tituloMetodo.innerText = "Sobre o resultado";
    }

    if (textoMetodo) {
      textoMetodo.innerText = "Aguardando processamento...";
    }

    limparExemplosMetodo(
      blocoExemplosMetodo,
      tituloExemplosMetodo,
      descricaoExemplosMetodo,
      exemplosMetodo
    );
  }

  function atualizarPreviewImagem(imagemBase64) {
    if (!imagemPreview) {
      return;
    }

    if (imagemBase64) {
      imagemPreview.src = imagemBase64;
      imagemPreview.hidden = false;

      if (previewStatus) {
        previewStatus.innerText = "Imagem pronta";
      }

      return;
    }

    imagemPreview.src = "#";
    imagemPreview.hidden = true;

    if (previewStatus) {
      previewStatus.innerText = "Sem imagem";
    }
  }

  function definirImagemAtual(imagemBase64) {
    imagemAtual = imagemBase64 || "";

    if (imagemAtual) {
      localStorage.setItem("AIDA_ImagemSelecionada", imagemAtual);
    } else {
      localStorage.removeItem("AIDA_ImagemSelecionada");
    }

    atualizarPreviewImagem(imagemAtual);
    limparResultado();
  }

  atualizarPreviewImagem(imagemAtual);
  limparResultado();

  if (btnTrocar && inputTrocarImagem) {
    btnTrocar.addEventListener("click", () => {
      inputTrocarImagem.value = "";
      inputTrocarImagem.click();
    });

    inputTrocarImagem.addEventListener("change", () => {
      const arquivo = inputTrocarImagem.files[0];

      if (!arquivo) {
        return;
      }

      const reader = new FileReader();
      reader.onload = (evento) => {
        definirImagemAtual(evento.target.result);

        if (tipoImagemInput) {
          tipoImagemInput.value = "";
        }

        mostrarAlerta("Imagem trocada. Escolha o metodo e analise novamente.");
      };
      reader.readAsDataURL(arquivo);
    });
  }

  if (metodoAnalise) {
    metodoAnalise.addEventListener("change", limparResultado);
  }

  if (checkMarcaDagua) {
    checkMarcaDagua.addEventListener("change", limparResultado);
  }

  if (checkMetadados) {
    checkMetadados.addEventListener("change", limparResultado);
  }

  if (!btnVerificar) {
    return;
  }

  btnVerificar.addEventListener("click", async () => {
    const metodoSelecionado = metodoAnalise ? metodoAnalise.value : "";
    const analisarMarcaDagua = checkMarcaDagua ? checkMarcaDagua.checked : true;
    const analisarMetadados = checkMetadados ? checkMetadados.checked : true;

    if (!imagemAtual) {
      mostrarAlerta("Selecione uma imagem antes de analisar.");
      return;
    }

    if (!metodoSelecionado) {
      mostrarAlerta("Selecione o metodo de analise.");
      return;
    }

    limparResultado();
    btnVerificar.disabled = true;

    if (loading) {
      loading.style.display = "flex";
    }

    try {
      const response = await fetch("https://aida-on.onrender.com/analisar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          imagem: imagemAtual,
          metodo: metodoSelecionado,
          analisarMarcaDagua,
          analisarMetadados,
        }),
      });

      const dados = await response.json();

      if (!response.ok || dados.status !== "sucesso") {
        throw new Error(dados.mensagem || "Falha ao analisar a imagem.");
      }

      if (loading) {
        loading.style.display = "none";
      }

      if (areaResultado) {
        areaResultado.style.display = "block";
      }

      if (imagemProcessada) {
        imagemProcessada.src = dados.imagem_fft || "#";
      }

      if (porcentagemIA) {
        porcentagemIA.innerText = dados.probabilidade || "0%";
      }

      if (tituloMetodo) {
        tituloMetodo.innerText = dados.metodo || "Sobre o resultado";
      }

      if (textoMetodo) {
        textoMetodo.innerText = montarDescricaoMetodo(dados);
      }

      await renderizarExemplosMetodo(dados, imagemAtual, {
        bloco: blocoExemplosMetodo,
        titulo: tituloExemplosMetodo,
        descricao: descricaoExemplosMetodo,
        lista: exemplosMetodo,
      });

      await salvarHistorico(imagemAtual, dados);
      mostrarAlerta("Analise concluida!");
    } catch (erro) {
      console.error("Erro ao processar imagem:", erro);

      if (loading) {
        loading.style.display = "none";
      }

      mostrarAlerta("Erro ao processar imagem.");
    } finally {
      btnVerificar.disabled = false;
    }
  });
});
