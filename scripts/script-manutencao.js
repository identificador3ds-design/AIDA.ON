const ADMIN_EMAIL = "admin@gmail.com";
const CHAVE_ADMIN_CONFIG = "AIDA_ADMIN_CONFIG";
const DESTINOS_LIBERADOS = new Set(["./index-seleciona.html", "./index-analise.html"]);
const CONFIG_ADMIN_PADRAO = {
  maintenanceMode: false,
  allowUploadPage: true,
  supportEmail: ADMIN_EMAIL,
  announcementMessage: "",
};
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
function obterAdminConfig() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_ADMIN_CONFIG) || "{}");
    return { ...CONFIG_ADMIN_PADRAO, ...salvo };
  } catch (erro) {
    return { ...CONFIG_ADMIN_PADRAO };
  }
}

function usuarioEhAdmin() {
  const tipo = localStorage.getItem("usuarioTipo");
  const email = (localStorage.getItem("usuarioEmail") || "").trim().toLowerCase();
  return tipo === "admin" || email === ADMIN_EMAIL;
}

/* Catalogo das ferramentas: scripts/aida-manutencao-ferramenta.js. */
function catalogo() {
  return window.AidaFerramentas || null;
}

function destinosLiberados() {
  const lista = catalogo()?.lista || {};
  const destinos = new Set(["./index-seleciona.html", "./index-analise.html"]);
  Object.values(lista).forEach((ferramenta) => ferramenta.paginas.forEach((p) => destinos.add(p)));
  return destinos;
}

function obterDestinoSeguro() {
  const params = new URLSearchParams(window.location.search);
  const destino = String(params.get("redirect") || "./index-seleciona.html").trim();
  return destinosLiberados().has(destino) ? destino : "./index-seleciona.html";
}

/* Ferramenta em manutencao: a do parametro, se for conhecida, senao a dona do destino. */
function obterFerramenta(destino) {
  const lista = catalogo()?.lista || {};
  const pedida = new URLSearchParams(window.location.search).get("ferramenta");
  if (pedida && lista[pedida]) {
    return pedida;
  }
  return catalogo()?.ferramentaDoDestino(destino) || "image";
}

function descreverDestino(destino, ferramenta) {
  const nome = catalogo()?.lista?.[ferramenta]?.nome;
  if (destino === "./index-analise.html") {
    return nome ? `${nome} — etapa de análise` : "Etapa de analise";
  }

  return nome || "Selecao de imagem";
}

/* Manutencao vale para a ferramenta (painel: geral ou so ela). Sem o catalogo
   carregado, cai na regra antiga: so o modo geral. */
function ferramentaEmManutencao(ferramenta, configuracao) {
  const api = catalogo();
  return api ? api.emManutencao(ferramenta, configuracao) : Boolean(configuracao.maintenanceMode);
}

function redirecionarParaDestino(destino) {
  window.location.href = destino;
}

document.addEventListener("DOMContentLoaded", () => {
  const configuracao = obterAdminConfig();
  const destino = obterDestinoSeguro();
  const ferramenta = obterFerramenta(destino);
  const nomeFerramenta = catalogo()?.lista?.[ferramenta]?.nome || "A ferramenta";
  const supportEmail = document.getElementById("maintenanceSupportEmail");
  const targetLabel = document.getElementById("maintenanceTargetLabel");
  const message = document.getElementById("maintenanceMessage");
  const status = document.getElementById("maintenanceStatus");

  if (supportEmail) {
    supportEmail.textContent = configuracao.supportEmail || ADMIN_EMAIL;
  }

  if (targetLabel) {
    targetLabel.textContent = descreverDestino(destino, ferramenta);
  }

  if (message) {
    message.textContent = configuracao.announcementMessage
      ? configuracao.announcementMessage
      : `${nomeFerramenta} está em manutenção e voltará a ficar disponível em breve.`;
  }

  if (status) {
    status.textContent =
      `${nomeFerramenta} está temporariamente bloqueada para usuários comuns. As outras ferramentas do AIDA continuam disponíveis.`;
  }

  const liberarSeAcabou = () => {
    if (usuarioEhAdmin() || !ferramentaEmManutencao(ferramenta, obterAdminConfig())) {
      redirecionarParaDestino(destino);
      return true;
    }
    return false;
  };

  if (liberarSeAcabou()) {
    return;
  }

  // A manutencao pode ter sido desligada no painel: aida-config-remota.js
  // avisa quando trouxer a configuracao nova do Supabase.
  window.addEventListener("aida:config-atualizada", liberarSeAcabou);
});
