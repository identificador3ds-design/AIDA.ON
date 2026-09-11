"""Camada 04: o contrato /v1.

Duas responsabilidades, e nenhuma delas e decidir:

1. `mapear_analise` traduz a resposta do Core (campos em portugues) para o
   contrato publico (campos em ingles). Nenhum valor e recalculado — `result`
   e `confidence` sao exatamente o que o Core respondeu. Se a borda reescreve
   um veredito, ela deixou de ser borda.
2. `CONTRATO` descreve a rota. A documentacao (`/v1/docs`) e gerada dele, para
   nao existir uma segunda verdade que envelhece sozinha.

Os NOMES dos campos sao em ingles porque a pagina /api mostra o exemplo assim.
Os VALORES continuam como o Core produz ("REAL", "IA/MANIPULADA",
"INCONCLUSIVO", "baixa"/"media"/"alta"): traduzi-los criaria um segundo
vocabulario para a mesma decisao, e integrador nenhum ganha com isso.
"""

from __future__ import annotations

VERSAO_CONTRATO = "v1"

RESULTADOS = ("REAL", "IA/MANIPULADA", "INCONCLUSIVO")

RESSALVA_PADRAO = (
    "Resultado tecnico de apoio: indicio, nao prova. Nao use isoladamente para "
    "decidir sobre a autenticidade de uma imagem."
)


def _num(valor, padrao=None):
    try:
        if valor is None:
            return padrao
        return float(valor)
    except (TypeError, ValueError):
        return padrao


def _lista(valor):
    return list(valor) if isinstance(valor, (list, tuple)) else []


def _dict(valor):
    return dict(valor) if isinstance(valor, dict) else {}


def mapear_evidencias(evidencias, analysis_id, prefixo_url):
    """Reescreve os mapas de evidencia para URLs desta API.

    O Core devolve caminhos relativos ('/evidencia/<id>/<mapa>') validos apenas
    na origem dele. Quem integra recebe a URL da borda, que faz o proxy — assim
    o cliente nunca precisa conhecer nem alcancar o Core.
    """
    evidencias = _dict(evidencias)
    urls = _dict(evidencias.get("urls"))
    mapas = {nome: f"{prefixo_url}/{analysis_id}/{nome}" for nome in urls}
    return {
        "maps": mapas,
        "suspect_patches": _lista(evidencias.get("patches_suspeitos")),
    }


def mapear_analise(bruto, analysis_id=None, prefixo_evidencia="/v1/evidence", duracao_borda_s=None):
    """Resposta do Core -> corpo de 200 de POST /v1/analyze/image."""
    bruto = _dict(bruto)
    analysis_id = analysis_id or bruto.get("id_analise") or ""

    prob_ia_exibicao = _num(bruto.get("probabilidade_ia_exibicao"), _num(bruto.get("probabilidade_ia"), 0.0))
    prob_real_exibicao = _num(bruto.get("probabilidade_real_exibicao"))
    if prob_real_exibicao is None and prob_ia_exibicao is not None:
        prob_real_exibicao = 1.0 - prob_ia_exibicao

    resultado = bruto.get("resultado")
    if resultado not in RESULTADOS:
        # O Core e a autoridade sobre o veredito. Um valor fora do vocabulario
        # significa que o contrato mudou do outro lado: a borda declara
        # indeterminado em vez de escolher um dos lados por conta propria.
        resultado = "INCONCLUSIVO"

    return {
        "api_version": VERSAO_CONTRATO,
        "analysis_id": analysis_id,
        "result": resultado,
        "inconclusive": bool(bruto.get("inconclusivo", resultado == "INCONCLUSIVO")),
        "out_of_domain": bool(bruto.get("fora_de_dominio", False)),
        "confidence": bruto.get("confianca"),
        # Escala de exibicao: corte em 0,50 por construcao. E a que se mostra
        # ao usuario final e a unica que casa com o veredito.
        "ai_probability": prob_ia_exibicao,
        "real_probability": prob_real_exibicao,
        "reasons": _lista(bruto.get("motivos")),
        "module_scores": _dict(bruto.get("scores_modulos")),
        "quality": _dict(bruto.get("qualidade")),
        "limitations": _lista(bruto.get("limitacoes")),
        "provenance": _dict(bruto.get("proveniencia")) or None,
        "generator_attribution": _dict(bruto.get("atribuicao_gerador")) or None,
        "divergence": bruto.get("divergencia"),
        "evidence": mapear_evidencias(bruto.get("evidencias"), analysis_id, prefixo_evidencia),
        "title": bruto.get("titulo"),
        "explanation": bruto.get("explicacao"),
        # Campo obrigatorio na saida: viaja junto com o resultado e nao deve ser
        # omitido por quem integra.
        "disclaimer": bruto.get("ressalva") or RESSALVA_PADRAO,
        "model_version": bruto.get("versao_modelo"),
        "fast_mode": bool(bruto.get("modo_rapido", False)),
        # Numeros calibrados: servem para metrica e auditoria, nao para tela.
        "calibration": {
            "ai_probability_calibrated": _num(bruto.get("probabilidade_ia")),
            "ai_probability_content_only": _num(bruto.get("probabilidade_ia_conteudo")),
            "threshold": _num(bruto.get("limiar")),
            "display_threshold": _num(bruto.get("limiar_exibicao"), 0.5),
            "inconclusive_band": _lista(bruto.get("banda_inconclusiva")),
            "inconclusive_band_display": _lista(bruto.get("banda_inconclusiva_exibicao")),
            "fusion": _dict(bruto.get("fusao")) or None,
        },
        "timing": {
            "core_seconds": _num(bruto.get("duracao_s")),
            "total_seconds": _num(duracao_borda_s),
        },
    }


def erro(codigo, mensagem, detalhes=None):
    """Corpo de erro unico do /v1 — sempre com `error.code` estavel."""
    corpo = {
        "api_version": VERSAO_CONTRATO,
        "error": {"code": codigo, "message": mensagem},
    }
    if detalhes:
        corpo["error"]["details"] = detalhes
    return corpo


CODIGOS_DE_ERRO = {
    "missing_image": "400 — campo `image` ausente na requisicao.",
    "invalid_image": "400 — arquivo ilegivel ou nao e uma imagem.",
    "unsupported_format": "400 — extensao fora da lista aceita.",
    "invalid_field": "400 — valor invalido em um campo do formulario.",
    "missing_credentials": "401 — cabecalho Authorization ausente ou malformado.",
    "invalid_key": "401 — chave inexistente, revogada ou expirada.",
    "rate_limited": "429 — cota da chave esgotada na janela atual. Ver Retry-After.",
    "payload_too_large": "413 — arquivo acima do limite de tamanho.",
    "not_found": "404 — analise ou mapa de evidencia inexistente.",
    "auth_unavailable": "503 — autenticacao nao configurada no servidor.",
    "core_unavailable": "503 — o AIDA Core nao respondeu.",
    "core_error": "502 — o AIDA Core respondeu com erro.",
    "busy": "503 — fila cheia; a analise nao foi iniciada. Ver Retry-After.",
    "internal_error": "500 — falha interna; o detalhe fica no log do servidor.",
}


CONTRATO = {
    "api": "AIDA API",
    "version": VERSAO_CONTRATO,
    "status": "em desenvolvimento",
    "notice": (
        "Camada publica sobre o AIDA Core. A deteccao acontece no Core; esta "
        "camada autentica, valida, limita, delega e formata."
    ),
    "auth": {
        "scheme": "Authorization: Bearer <chave>",
        "issuance": "Fora de banda (CLI gerenciar_chaves.py). Nao ha cadastro publico.",
    },
    "endpoints": {
        "POST /v1/analyze/image": {
            "summary": "Analisa uma imagem e devolve o resultado no contrato v1.",
            "content_type": "multipart/form-data",
            "fields": {
                "image": "arquivo (obrigatorio). Um por chamada.",
                "evidence": "'true' | 'false' (opcional, padrao 'true'). 'false' nao gera mapas e responde mais rapido.",
            },
            "response": "objeto de analise (ver `analysis_object`)",
        },
        "GET /v1/analysis/{analysis_id}": {
            "summary": "Recupera uma analise ja feita, enquanto ela estiver no cache da borda.",
            "response": "objeto de analise",
        },
        "GET /v1/evidence/{analysis_id}/{map}": {
            "summary": "PNG de um mapa de explicabilidade, servido por proxy do Core.",
            "response": "image/png",
        },
        "GET /v1/contract": {"summary": "Este documento.", "auth": "nao exige chave"},
        "GET /v1/docs": {"summary": "Referencia legivel, gerada deste contrato.", "auth": "nao exige chave"},
        "GET /v1/health": {"summary": "Disponibilidade da borda e do Core, com latencia por etapa.", "auth": "nao exige chave"},
    },
    "analysis_object": {
        "analysis_id": "str — use em GET /v1/analysis/{id}",
        "result": "'REAL' | 'IA/MANIPULADA' | 'INCONCLUSIVO' — TRES estados",
        "inconclusive": "bool — atalho para result == 'INCONCLUSIVO'",
        "out_of_domain": "bool — a imagem nao e fotografica. Quando true, as probabilidades nao tem significado; mostre `title`",
        "confidence": "'baixa' | 'media' | 'alta'",
        "ai_probability": "float 0..1 — escala de EXIBICAO, corte em 0,50. E esta que se mostra",
        "real_probability": "float 0..1 (= 1 - ai_probability)",
        "reasons": "list[str] — por que foi inconclusivo (vazio se decidiu)",
        "module_scores": "{modulo: float} — score por modulo do Core",
        "quality": "{indicador: float} — indicadores de qualidade do arquivo, 0..1",
        "limitations": "list[str] — limitacoes do arquivo analisado",
        "provenance": "objeto|null — C2PA/metadados. NO_PROVENANCE_FOUND NAO significa imagem real",
        "generator_attribution": "objeto|null — 'desconhecido' quando nao ha evidencia. Nao force atribuicao",
        "divergence": "objeto|null — presente quando proveniencia e conteudo discordam",
        "evidence": "{maps: {nome: url}, suspect_patches: [...]} — vazio quando evidence=false",
        "title": "str — titulo pronto para exibicao",
        "explanation": "str — texto pronto, ja com a ressalva",
        "disclaimer": "str — OBRIGATORIO na saida. Nao omitir",
        "model_version": "str — versao do modelo que decidiu",
        "fast_mode": "bool — se true, o modulo forense nao participou",
        "calibration": (
            "{ai_probability_calibrated, ai_probability_content_only, threshold, "
            "display_threshold, inconclusive_band, inconclusive_band_display, fusion} "
            "— para metrica e auditoria, nao para tela"
        ),
        "timing": "{core_seconds, total_seconds}",
    },
    "integration_warnings": [
        "result tem TRES valores. Codigo com if/else binario rotula como IA aquilo que o sistema declarou indeterminado.",
        "`disclaimer` e obrigatorio na interface: o retorno e indicio tecnico, nao prova.",
        "Quando out_of_domain for true, as probabilidades nao tem significado.",
        "Exiba `ai_probability`, nao `calibration.ai_probability_calibrated`: o limiar calibrado nao cai em 0,50 e produziria telas como '28% de IA' ao lado do veredito 'IA/MANIPULADA'.",
        "Trate 429: a cota e por chave e por janela. Respeite o Retry-After em vez de repetir a chamada.",
        "Nao ha endpoint publico de emissao de chave. Chaves sao emitidas fora de banda.",
    ],
    "errors": CODIGOS_DE_ERRO,
    "versioning": (
        "Mudanca incompativel entra em uma versao nova de caminho (/v2). Dentro "
        "de /v1 so entram campos novos, e campo novo nunca vira obrigatorio."
    ),
}
