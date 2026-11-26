/* Teste de componente da página de preços, em jsdom.
 *
 * Carrega pages/index-precos.html com os scripts de verdade, serve
 * config/pricing.json e i18n/*.json do disco por um fetch dublado, aciona
 * os controles como um usuário (troca de moeda, mensal/anual, idioma, abas,
 * calculadora, formulário) e imprime um JSON com o que a tela mostrou em cada
 * passo. As asserções ficam em testes/test_precos_pagina.py.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const RAIZ = path.resolve(__dirname, "..", "..");
const ler = (rel) => fs.readFileSync(path.join(RAIZ, rel), "utf8");

async function main() {
  const dom = new JSDOM(ler("pages/index-precos.html"), {
    url: "http://localhost/pages/index-precos.html",
    runScripts: "outside-only",
    pretendToBeVisual: true,
  });
  const { window } = dom;
  const { document } = window;

  // Começa em pt-BR / Brasil, como um visitante que já escolheu.
  window.localStorage.setItem("AIDA_PrecosIdioma", "pt-BR");
  window.localStorage.setItem("AIDA_PrecosMercado", "BR");

  const enviados = [];
  let respostaSupabase = { ok: true, status: 201, json: async () => ({}) };
  window.fetch = async (url, opcoes) => {
    const u = new URL(url, window.location.href);
    if (u.hostname.endsWith("supabase.co")) {
      enviados.push({ url: u.href, metodo: opcoes.method, corpo: JSON.parse(opcoes.body), cabecalhos: opcoes.headers });
      return respostaSupabase;
    }
    const arquivo = path.join(RAIZ, decodeURIComponent(u.pathname));
    if (!fs.existsSync(arquivo)) return { ok: false, status: 404, json: async () => ({}) };
    const texto = fs.readFileSync(arquivo, "utf8");
    return { ok: true, status: 200, json: async () => JSON.parse(texto) };
  };

  for (const script of ["scripts/aida-precos-core.js", "scripts/aida-i18n.js", "scripts/script-precos.js"]) {
    window.eval(ler(script));
  }
  await window.AidaPaginaPrecos.pronto;

  const limpo = (texto) => (texto || "").replace(/ | /g, " ").replace(/\s+/g, " ").trim();
  const card = (segmento, id) => document.querySelector(`[data-cards="${segmento}"] article[data-plano="${id}"]`);
  const preco = (segmento, id) => limpo(card(segmento, id).querySelector("[data-preco]").textContent);
  const nota = (segmento, id) => {
    const n = card(segmento, id).querySelector(".precos-card__nota");
    return n ? limpo(n.textContent) : null;
  };
  const clicar = (id) => document.getElementById(id).click();
  const esperar = () => new Promise((r) => setTimeout(r, 0));
  const passos = {};

  passos.inicial = {
    erro: window.AidaPaginaPrecos.estado.erro ? String(window.AidaPaginaPrecos.estado.erro) : null,
    lang: document.documentElement.lang,
    statusOculto: document.getElementById("precosStatus").hidden,
    criador: preco("platform", "criador"),
    cidadao: preco("platform", "cidadao"),
    apiStarter: preco("api", "api_starter"),
    excedenteStarter: limpo(card("api", "api_starter").querySelector(".precos-card__fatos").textContent),
    economia: limpo(document.getElementById("precosEconomia").textContent),
    mercadoMarcado: document.getElementById("mercado-BR").checked,
    linhasTabela: document.querySelectorAll("#precosTabela tbody tr").length,
  };

  clicar("mercado-INTL");
  passos.usdMensal = {
    pro: preco("platform", "pro"),
    team: preco("platform", "team"),
    apiScale: preco("api", "api_scale"),
    excedenteScale: limpo(card("api", "api_scale").querySelector(".precos-card__fatos").textContent),
    fatosPro: limpo(card("platform", "pro").querySelector(".precos-card__fatos").textContent),
    fatosTeam: limpo(card("platform", "team").querySelector(".precos-card__fatos").textContent),
    fatosEnterprise: limpo(card("api", "enterprise").querySelector(".precos-card__fatos").textContent),
    planosPlataforma: Array.from(document.querySelectorAll('[data-cards="platform"] article[data-plano]')).map((c) => c.getAttribute("data-plano")),
    preferencia: window.localStorage.getItem("AIDA_PrecosMercado"),
  };

  clicar("ciclo-annual");
  passos.usdAnual = { pro: preco("platform", "pro"), notaPro: nota("platform", "pro") };

  clicar("mercado-BR");
  passos.brlAnual = {
    criador: preco("platform", "criador"),
    notaCriador: nota("platform", "criador"),
    apiBusiness: preco("api", "api_business"),
  };

  clicar("ciclo-monthly");
  passos.brlMensal = { criador: preco("platform", "criador") };

  // Abas: clique e teclado (setas).
  clicar("aba-api");
  passos.abaApi = {
    selecionada: document.getElementById("aba-api").getAttribute("aria-selected"),
    painelApiOculto: document.getElementById("painel-api").hidden,
    painelPlataformaOculto: document.getElementById("painel-platform").hidden,
  };

  // Calculadora (aba API, BRL, mensal): 5000 imagens.
  const imagens = document.getElementById("calcImagens");
  const minutos = document.getElementById("calcMinutos");
  imagens.value = "5000";
  minutos.value = "0";
  imagens.dispatchEvent(new window.Event("input", { bubbles: true }));
  const recomendado = () => {
    const r = document.querySelector("#calcResultado [data-recomendado]");
    return r ? r.getAttribute("data-recomendado") : null;
  };
  passos.calc5000 = { recomendado: recomendado(), texto: limpo(document.getElementById("calcResultado").textContent) };

  imagens.value = "-3";
  imagens.dispatchEvent(new window.Event("input", { bubbles: true }));
  passos.calcInvalida = {
    invalido: imagens.getAttribute("aria-invalid"),
    texto: limpo(document.getElementById("calcResultado").textContent),
  };
  imagens.value = "50";
  imagens.dispatchEvent(new window.Event("input", { bubbles: true }));
  passos.calc50 = { recomendado: recomendado() };

  document.getElementById("aba-api").dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
  passos.teclado = {
    selecionadaPlataforma: document.getElementById("aba-platform").getAttribute("aria-selected"),
    foco: document.activeElement && document.activeElement.id,
    tabindexApi: document.getElementById("aba-api").tabIndex,
  };

  // Idioma.
  clicar("idioma-en-US");
  for (let i = 0; i < 5; i += 1) await esperar();
  passos.ingles = {
    lang: document.documentElement.lang,
    titulo: limpo(document.querySelector("h1").textContent),
    criador: preco("platform", "criador"),
    nomeCriador: limpo(card("platform", "criador").querySelector("h3").textContent),
    abaPlataforma: limpo(document.getElementById("aba-platform").textContent),
    tituloDocumento: document.title,
  };
  clicar("idioma-pt-BR");
  for (let i = 0; i < 5; i += 1) await esperar();

  // Formulário Enterprise (aba API).
  clicar("aba-api");
  card("api", "enterprise").querySelector("[data-contato]").click();
  const dialogo = document.getElementById("contatoDialogo");
  passos.dialogo = {
    aberto: dialogo.hasAttribute("open"),
    titulo: limpo(document.getElementById("contatoTitulo").textContent),
    tipo: document.getElementById("contatoTipo").value,
    foco: document.activeElement && document.activeElement.id,
  };

  const form = document.getElementById("contatoForm");
  form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
  await esperar();
  passos.formVazio = {
    resumoVisivel: !document.getElementById("contatoResumo").hidden,
    invalidos: Array.from(form.querySelectorAll('[aria-invalid="true"]')).map((c) => c.id),
    enviados: enviados.length,
  };

  document.getElementById("contatoNome").value = "Ana Souza";
  document.getElementById("contatoEmpresa").value = "Redação Exemplo";
  document.getElementById("contatoEmail").value = "ana@exemplo.com.br";
  document.getElementById("contatoVolume").value = "600000";
  document.getElementById("contatoMensagem").value = "Volume de eleição.";
  document.getElementById("contatoConsentimento").checked = true;
  form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
  for (let i = 0; i < 5; i += 1) await esperar();
  passos.formValido = {
    enviados: enviados.slice(),
    estado: limpo(document.getElementById("contatoEstado").textContent),
    invalidos: Array.from(form.querySelectorAll('[aria-invalid="true"]')).map((c) => c.id),
  };

  // Limite anti-spam da migração: PostgREST responde 400 com code P0001.
  respostaSupabase = { ok: false, status: 400, json: async () => ({ code: "P0001", message: "limite" }) };
  document.getElementById("contatoNome").value = "Ana Souza";
  document.getElementById("contatoEmpresa").value = "Redação Exemplo";
  document.getElementById("contatoEmail").value = "ana@exemplo.com.br";
  document.getElementById("contatoVolume").value = "600000";
  document.getElementById("contatoConsentimento").checked = true;
  form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
  for (let i = 0; i < 5; i += 1) await esperar();
  passos.formLimite = {
    estado: limpo(document.getElementById("contatoEstado").textContent),
    enviados: enviados.length,
  };

  process.stdout.write(JSON.stringify(passos));
}

main().catch((erro) => {
  process.stderr.write(String(erro && erro.stack ? erro.stack : erro));
  process.exit(1);
});
