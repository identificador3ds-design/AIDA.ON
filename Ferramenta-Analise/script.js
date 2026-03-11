const supabaseUrl = "https://nwzijdudhemuibsyzpub.supabase.co";
const supabaseKey =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im53emlqZHVkaGVtdWlic3l6cHViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMjk5MTAsImV4cCI6MjA4NzYwNTkxMH0.aDHymYEKtyY5m2eaOHoBy4QRpaAvtafi_PVDtrL9gQc";
const _supabase = supabase.createClient(supabaseUrl, supabaseKey);

function base64ToBlob(base64, mime) {
  const byteString = atob(base64.split(",")[1]);
  const buffer = new ArrayBuffer(byteString.length);
  const view = new Uint8Array(buffer);

  for (let index = 0; index < byteString.length; index += 1) {
    view[index] = byteString.charCodeAt(index);
  }

  return new Blob([buffer], { type: mime });
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
  toast.textContent = mensagem;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("fadeOut");
    setTimeout(() => toast.remove(), 350);
  }, 3200);
}

function getDescricaoMetodo(dados) {
  const metodo = String(dados.metodo || "").toLowerCase();

  if (metodo.includes("marca visual")) {
    const iaNome = dados.metodo.replace("Marca Visual (", "").replace(")", "");
    return `Deteccao por marca visual\n\nFoi identificada uma marca d'agua visual no canto inferior direito da imagem, caracteristica da ferramenta ${iaNome}. Esta e uma assinatura visual explicita inserida por geradores de imagem.`;
  }

  if (metodo.includes("metadados")) {
    const iaNome = dados.metodo.replace("Metadados (", "").replace(")", "");
    return `Deteccao por metadados\n\nOs metadados da imagem contem assinaturas digitais caracteristicas da ferramenta ${iaNome}.`;
  }

  if (metodo.includes("lsb")) {
    return `Analise LSB (Plano de Bits)\n\nO plano de bits menos significativos apresenta ${dados.energia} pixels ativos. Uma alta concentracao de bits alterados pode indicar a presenca de marcas d'agua digitais ou esteganografia.`;
  }

  if (metodo.includes("gradiente") || metodo.includes("laplaciano") || metodo.includes("neon")) {
    return `Analise de Gradiente Laplaciano\n\nO filtro Laplaciano detectou bordas com intensidade media de ${dados.energia}. O efeito neon destaca regioes de maior variacao na imagem, que podem corresponder a texturas sinteticas ou artefatos caracteristicos de imagens geradas por IA.`;
  }

  if (metodo.includes("frequencia") || metodo.includes("fft") || metodo.includes("consistencia")) {
    return `Analise de Frequencia (FFT)\n\nA analise tecnica de frequencias detectou uma energia de ${dados.energia}. Valores fora da faixa tipica podem indicar manipulacao sintetica.`;
  }

  return `Resultado da analise\n\nMetodo utilizado: ${dados.metodo}\nProbabilidade: ${dados.probabilidade}\nEnergia detectada: ${dados.energia}`;
}

async function salvarHistorico(imagemBase64, dados) {
  const {
    data: { user },
  } = await _supabase.auth.getUser();

  if (!user) {
    return;
  }

  const blob = base64ToBlob(imagemBase64, "image/png");
  const fileName = `${user.id}/${Date.now()}_original.png`;

  const { error: uploadError } = await _supabase.storage.from("evidencias").upload(fileName, blob);

  if (uploadError) {
    console.error("Erro no upload:", uploadError.message);
    return;
  }

  const {
    data: { publicUrl },
  } = _supabase.storage.from("evidencias").getPublicUrl(fileName);

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
    console.error("Erro ao salvar historico:", dbError.message);
    return;
  }

  localStorage.removeItem("AIDA_ImagemSelecionada");
}

document.addEventListener("DOMContentLoaded", async () => {
  const nomeSalvo = localStorage.getItem("usuarioNome");
  const botaoUsuario = document.getElementById("nome-usuario2");
  const btnSair = document.getElementById("btn-sair");

  if (nomeSalvo && botaoUsuario) {
    botaoUsuario.textContent = `Ola, ${nomeSalvo}`;
  }

  if (btnSair) {
    btnSair.addEventListener("click", (event) => {
      event.preventDefault();
      localStorage.removeItem("usuarioNome");
      localStorage.removeItem("usuarioEmail");
      window.location.href = "../login/index-login.html";
    });
  }

  const imagemPreview = document.getElementById("imagemPreview");
  const placeholderImagem = document.getElementById("placeholderImagem");
  const btnVerificar = document.getElementById("btnVerificar");
  const metodoAnalise = document.getElementById("metodoAnalise");
  const imagemSalva = localStorage.getItem("AIDA_ImagemSelecionada");

  if (!imagemSalva) {
    window.location.href = "../Ferramenta/index-seleciona.html";
    return;
  }

  if (imagemPreview) {
    imagemPreview.src = imagemSalva;
    imagemPreview.hidden = false;
  }

  if (placeholderImagem) {
    placeholderImagem.hidden = true;
  }

  if (!btnVerificar || !metodoAnalise) {
    return;
  }

  btnVerificar.addEventListener("click", async () => {
    const metodoSelecionado = metodoAnalise.value;
    const imagemBase64 = localStorage.getItem("AIDA_ImagemSelecionada");
    const loading = document.getElementById("loading");
    const areaResultado = document.getElementById("areaResultado");

    if (!metodoSelecionado || !imagemBase64) {
      mostrarAlerta("Selecione o metodo e uma imagem.");
      return;
    }

    areaResultado.style.display = "none";
    loading.style.display = "block";

    try {
      const response = await fetch("https://aida-on.onrender.com/analisar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imagem: imagemBase64, metodo: metodoSelecionado }),
      });

      const dados = await response.json();

      if (dados.status !== "sucesso") {
        throw new Error("Resposta invalida");
      }

      loading.style.display = "none";
      areaResultado.style.display = "block";

      document.getElementById("imagemProcessada").src = dados.imagem_fft;
      document.getElementById("porcentagemIA").textContent = dados.probabilidade;
      document.getElementById("tituloMetodo").textContent = dados.metodo;
      document.getElementById("textoMetodo").textContent = getDescricaoMetodo(dados);

      mostrarAlerta("Analise concluida.");
      await salvarHistorico(imagemBase64, dados);
    } catch (error) {
      loading.style.display = "none";
      mostrarAlerta("Erro ao processar imagem.");
    }
  });
});
