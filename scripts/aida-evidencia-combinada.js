// Combinação de evidências quando a análise de imagem dá INCONCLUSIVO.
//
// Decisão da equipe (11/10/2026): o AIDA responde REAL, REAL EDITADA ou IA; quando
// não consegue, NÃO encerra em "inconclusivo" — pede outra evidência (o arquivo
// original, outra foto da mesma cena) e combina as respostas. Regras, na ordem:
//
//   1. Evidência fora do escopo (não fotográfica) não conta.
//   2. Se há evidências decididas e todas apontam o mesmo lado, esse é o veredito
//      (REAL EDITADA se alguma das reais registra editor). Confiança "media" se
//      houve inconclusivas no caminho, senão a da própria evidência.
//   3. Se as decididas se contradizem (uma IA, outra REAL), ou se nenhuma decidiu,
//      pede-se outra evidência — até MAX_EVIDENCIAS.
//   4. Atingido o máximo (ou se o usuário pede para concluir com o que tem), decide
//      pela MÉDIA das probabilidades calibradas de IA contra o limiar da política,
//      com confiança "baixa" — e a tela diz isso.
//
// Puro (sem DOM): roda no navegador (window.AIDAEvidencia) e no Node (testes).
(function (raiz, fabrica) {
  const api = fabrica();
  if (typeof module === "object" && module.exports) module.exports = api;
  else raiz.AIDAEvidencia = api;
})(typeof self !== "undefined" ? self : this, function () {
  const MAX_EVIDENCIAS = 3;
  const DECIDIDOS = new Set(["REAL", "REAL_EDITADA", "IA/MANIPULADA"]);

  function lado(resultado) {
    if (resultado === "IA/MANIPULADA") return "IA";
    if (resultado === "REAL" || resultado === "REAL_EDITADA") return "REAL";
    return null;
  }

  function veredictoReal(evidencias) {
    return evidencias.some((e) => e.resultado === "REAL_EDITADA" || e.editada === true)
      ? "REAL_EDITADA"
      : "REAL";
  }

  function mediaProbabilidade(evidencias) {
    const ps = evidencias.map((e) => Number(e.probabilidade_ia)).filter((p) => Number.isFinite(p));
    return ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : null;
  }

  // evidencias: respostas da API (resultado, probabilidade_ia, limiar, editada,
  // fora_de_dominio). concluirAgora: o usuário pediu decisão com o que já enviou.
  function combinar(evidencias, concluirAgora = false) {
    const validas = (evidencias || []).filter((e) => e && !e.fora_de_dominio);
    const ignoradas = (evidencias || []).length - validas.length;
    const base = { n: validas.length, ignoradas, max: MAX_EVIDENCIAS };
    if (!validas.length) {
      return { ...base, estado: "PEDIR_EVIDENCIA", resultado: "INCONCLUSIVO", confianca: null,
               motivo: "nenhuma evidência fotográfica válida ainda" };
    }
    const decididas = validas.filter((e) => DECIDIDOS.has(e.resultado));
    const lados = new Set(decididas.map((e) => lado(e.resultado)));
    const houveInconclusiva = decididas.length < validas.length;

    if (decididas.length && lados.size === 1) {
      const l = [...lados][0];
      const unica = validas.length === 1 ? validas[0].confianca : null;
      return {
        ...base,
        estado: "DECIDIDO",
        resultado: l === "IA" ? "IA/MANIPULADA" : veredictoReal(validas),
        confianca: houveInconclusiva ? "media" : unica || "media",
        motivo: houveInconclusiva
          ? "a nova evidência decidiu o que a anterior deixou em aberto"
          : "evidência conclusiva",
      };
    }

    const esgotou = validas.length >= MAX_EVIDENCIAS;
    if (!esgotou && !concluirAgora) {
      return {
        ...base,
        estado: "PEDIR_EVIDENCIA",
        resultado: "INCONCLUSIVO",
        confianca: null,
        motivo: lados.size > 1 ? "as evidências se contradizem" : "as evidências ainda não bastam",
      };
    }

    const media = mediaProbabilidade(validas);
    const limiar = Number(validas[0].limiar);
    const corte = Number.isFinite(limiar) ? limiar : 0.5;
    const ehIA = media !== null && media >= corte;
    return {
      ...base,
      estado: "DECIDIDO",
      resultado: ehIA ? "IA/MANIPULADA" : veredictoReal(validas),
      confianca: "baixa",
      media_probabilidade_ia: media,
      limiar: corte,
      motivo: `decisão pela média das ${validas.length} evidências (${(media * 100).toFixed(1)}% de IA; limiar ${(corte * 100).toFixed(1)}%)`,
    };
  }

  return { combinar, MAX_EVIDENCIAS };
});
