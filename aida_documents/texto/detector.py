"""Deteccao de texto gerado por IA num documento (PDF, DOCX, TXT).

Fluxo: extrair -> limpar -> idioma -> segmentos de ~120 palavras -> medidas de cada
segmento (perplexidade + estilo) -> probabilidade por segmento -> documento.

A probabilidade vem de uma regressao logistica sobre as medidas, com os parametros
em `calibracao.json` (gerado por `python -m aida_documents.texto.calibrar`). Enquanto
nao houver calibracao para o idioma, os parametros abaixo sao um chute de partida: o
relatorio mostra o indicador e os trechos, marca `calibrado: false` e o resultado
fica INCONCLUSIVO. Acusar alguem de ter usado IA com um limiar que nunca foi medido
seria o erro mais caro que esta ferramenta pode cometer.

Tres estados, como no resto do AIDA: HUMANO, IA e INCONCLUSIVO.

Uso:
    python -m aida_documents.texto.detector trabalho.pdf
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from statistics import pstdev

from .estilo import detectar_idioma, dividir_frases, medir_estilo
from .extracao import extrair
from .limpeza import contar_palavras, limpar, pagina_em
from .perplexidade import obter_modelo, surpresa_por_frase

ALVO_PALAVRAS_SEGMENTO = 120
MIN_PALAVRAS_SEGMENTO = 60
MIN_PALAVRAS_DOCUMENTO = 150
MAX_PALAVRAS_DOCUMENTO = 12000
# Fracao do texto em trechos suspeitos que impede o veredito HUMANO.
MAX_FRACAO_SUSPEITA_HUMANO = 0.10
FEATURES = ("log_ppl", "burst_ppl", "burst_frases", "marcadores_por_mil")
ARQUIVO_CALIBRACAO = Path(__file__).with_name("calibracao.json")
RESSALVA = (
    "Indício estatístico, não prova de autoria. Detectores de texto erram, sobretudo com textos formais, "
    "técnicos, traduzidos ou revisados por corretor. Não use este resultado sozinho para punir ninguém."
)

# Ponto de partida SEM calibracao. Sinais: perplexidade baixa, perplexidade e frases
# pouco variadas e muitos marcadores apontam para IA.
_PADRAO = {
    "calibrado": False,
    "features": list(FEATURES),
    "centro": {"log_ppl": 3.5, "burst_ppl": 0.9, "burst_frases": 0.5, "marcadores_por_mil": 6.0},
    "escala": {"log_ppl": 0.5, "burst_ppl": 0.3, "burst_frases": 0.15, "marcadores_por_mil": 5.0},
    "pesos": {"log_ppl": -1.6, "burst_ppl": -0.6, "burst_frases": -0.5, "marcadores_por_mil": 0.4},
    "vies": 0.0,
    "limiares": {"segmento": 0.75, "ia": 0.85, "humano": 0.25},
}


def carregar_calibracao(caminho=None):
    caminho = Path(caminho or os.environ.get("AIDA_TEXTO_CALIBRACAO") or ARQUIVO_CALIBRACAO)
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def parametros(idioma, calibracao=None, modelo=None):
    """Parametros do idioma. Calibracao feita com outro modelo de linguagem nao vale."""
    calibracao = carregar_calibracao() if calibracao is None else calibracao
    cal = calibracao.get(idioma)
    if cal and cal.get("calibrado") and cal.get("modelo") in (None, modelo):
        return cal
    return dict(_PADRAO)


# ---------------------------------------------------------------- segmentos


def segmentar(paragrafos):
    """Junta frases em segmentos de ~ALVO palavras, sem cortar frase no meio."""
    segmentos, frases, palavras, pagina = [], [], 0, None

    def emitir():
        nonlocal frases, palavras, pagina
        if frases:
            segmentos.append({"texto": " ".join(frases), "pagina": pagina, "palavras": palavras})
        frases, palavras, pagina = [], 0, None

    for par in paragrafos:
        texto = par["texto"]
        for a, b in dividir_frases(texto):
            if pagina is None:
                pagina = pagina_em(par, a)
            frases.append(texto[a:b])
            palavras += contar_palavras(texto[a:b])
            if palavras >= ALVO_PALAVRAS_SEGMENTO:
                emitir()
        if palavras >= MIN_PALAVRAS_SEGMENTO:
            emitir()  # fim de paragrafo: fecha se ja tem tamanho; senao continua no proximo
    if frases:
        if segmentos and palavras < MIN_PALAVRAS_SEGMENTO:
            ultimo = segmentos[-1]
            ultimo["texto"] += " " + " ".join(frases)
            ultimo["palavras"] += palavras
        else:
            emitir()
    return segmentos


def medir_segmento(texto, idioma, modelo):
    frases = dividir_frases(texto)
    medidas = medir_estilo(texto, idioma, frases)
    medidas["log_ppl"] = medidas["burst_ppl"] = None
    if modelo is not None:
        pontos = modelo.pontuar(texto)
        if pontos:
            medidas["log_ppl"] = sum(s for _, _, s in pontos) / len(pontos)
            por_frase = [m for m in surpresa_por_frase(pontos, frases) if m is not None]
            medidas["burst_ppl"] = pstdev(por_frase) if len(por_frase) >= 3 else None
    return medidas


# ---------------------------------------------------------------- pontuacao


def _sigmoide(x):
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def logit(medidas, cal):
    """Soma ponderada das medidas padronizadas. Medida ausente vale o centro (neutra)."""
    total = cal["vies"]
    for nome in cal["features"]:
        valor = medidas.get(nome)
        if valor is not None:
            total += cal["pesos"][nome] * (valor - cal["centro"][nome]) / (cal["escala"][nome] or 1.0)
    return total


def _media_ponderada(pares):
    peso = sum(p for _, p in pares)
    return sum(v * p for v, p in pares) / peso if peso else None


def agregar(segmentos, cal):
    """Probabilidade do documento e fracao do texto em segmentos suspeitos."""
    total = sum(s["palavras"] for s in segmentos)
    prob = _sigmoide(_media_ponderada([(s["logit"], s["palavras"]) for s in segmentos]))
    suspeitas = sum(s["palavras"] for s in segmentos if s["probabilidade"] >= cal["limiares"]["segmento"])
    return prob, suspeitas / total if total else 0.0


def decidir(prob, fracao, cal):
    """(resultado, motivos) a partir da probabilidade do documento e da fracao suspeita."""
    limiares = cal["limiares"]
    if not cal["calibrado"]:
        return "INCONCLUSIVO", [
            "detector ainda não calibrado para este idioma: os números abaixo são um indicador de partida, "
            "sem taxa de erro medida"
        ]
    if prob >= limiares["ia"]:
        return "IA", []
    if prob <= limiares["humano"] and fracao <= MAX_FRACAO_SUSPEITA_HUMANO:
        return "HUMANO", []
    if fracao > MAX_FRACAO_SUSPEITA_HUMANO:
        return "INCONCLUSIVO", [f"{round(100 * fracao)}% do texto está em trechos com sinal de IA: uso parcial é possível"]
    return "INCONCLUSIVO", ["o sinal ficou entre os dois limiares: não dá para afirmar nem um lado nem o outro"]


def _nivel(prob, cal):
    if prob >= cal["limiares"]["segmento"]:
        return "alto"
    return "medio" if prob >= 0.5 else "baixo"


def _arredondar(medidas):
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in medidas.items()}


# ---------------------------------------------------------------- analise


def preparar(dados, nome):
    """Extrai, limpa, detecta o idioma e segmenta. Nao usa modelo de linguagem."""
    bruto = extrair(dados, nome)
    limpo = limpar(bruto["paginas"])
    texto = " ".join(p["texto"] for p in limpo["paragrafos"])
    return {
        "formato": bruto["formato"],
        "paginas": len(bruto["paginas"]),
        "avisos": bruto["avisos"],
        "limpeza": limpo["removidos"],
        "palavras": limpo["palavras"],
        "idioma": detectar_idioma(texto),
        "segmentos": segmentar(limpo["paragrafos"]),
    }


def _inconclusivo(base, motivo):
    return {
        **base,
        "resultado": "INCONCLUSIVO",
        "inconclusivo": True,
        "probabilidade_ia": None,
        "fracao_suspeita": None,
        "calibrado": False,
        "motivos": [motivo],
        "segmentos": [],
        "medidas": {},
    }


def analisar_texto_bytes(dados: bytes, nome="documento.pdf", modelo=None, calibracao=None, progresso=None):
    """modelo: objeto com `pontuar(texto)` e `nome` (os testes passam um falso); None
    carrega o modelo do idioma. progresso: callable(feitos, total), chamado a cada segmento."""
    doc = preparar(dados, nome)
    segmentos = doc.pop("segmentos")
    base = {
        "formato": doc["formato"],
        "paginas": doc["paginas"],
        "palavras": doc["palavras"],
        "idioma": doc["idioma"],
        "limpeza": doc["limpeza"],
        "limitacoes": list(doc["avisos"]),
        "modelo": None,
        "ressalva": RESSALVA,
    }
    if doc["palavras"] < MIN_PALAVRAS_DOCUMENTO:
        return _inconclusivo(
            base,
            f"só {doc['palavras']} palavras de texto corrido: com menos de {MIN_PALAVRAS_DOCUMENTO} as medidas não são confiáveis",
        )
    if doc["idioma"] is None:
        return _inconclusivo(base, "idioma não reconhecido: a análise cobre português e inglês")

    motivo_modelo = None
    if modelo is None:
        modelo, motivo_modelo = obter_modelo(doc["idioma"])
    base["modelo"] = getattr(modelo, "nome", None)
    cal = parametros(doc["idioma"], calibracao, base["modelo"])

    # Documento muito longo: analisa o comeco e avisa.
    usados, acumulado = [], 0
    for seg in segmentos:
        if acumulado >= MAX_PALAVRAS_DOCUMENTO:
            break
        usados.append(seg)
        acumulado += seg["palavras"]
    if len(usados) < len(segmentos):
        base["limitacoes"].append(
            f"documento longo: foram analisadas as primeiras {acumulado} palavras de {doc['palavras']}"
        )

    resultado_segmentos = []
    for i, seg in enumerate(usados):
        medidas = medir_segmento(seg["texto"], doc["idioma"], modelo)
        valor = logit(medidas, cal)
        prob = _sigmoide(valor)
        resultado_segmentos.append({
            "indice": i,
            "pagina": seg["pagina"],
            "palavras": seg["palavras"],
            "texto": seg["texto"],
            "logit": valor,
            "probabilidade": round(prob, 4),
            "nivel": _nivel(prob, cal),
            "medidas": _arredondar(medidas),
        })
        if progresso:
            progresso(i + 1, len(usados))

    # Medidas do documento inteiro, para o relatorio (a decisao usa os segmentos).
    medidas_doc = medir_estilo(" ".join(s["texto"] for s in usados), doc["idioma"])
    com_ppl = [(s["medidas"]["log_ppl"], s["palavras"]) for s in resultado_segmentos if s["medidas"]["log_ppl"] is not None]
    medidas_doc["log_ppl"] = _media_ponderada(com_ppl)
    medidas_doc["perplexidade"] = math.exp(medidas_doc["log_ppl"]) if medidas_doc["log_ppl"] is not None else None

    if modelo is None and "log_ppl" in cal["features"]:
        relatorio = _inconclusivo(base, f"modelo de linguagem indisponível ({motivo_modelo}): sem perplexidade não há decisão")
        relatorio["medidas"] = _arredondar(medidas_doc)
        return relatorio

    prob, fracao = agregar(resultado_segmentos, cal)
    resultado, motivos = decidir(prob, fracao, cal)

    for seg in resultado_segmentos:
        del seg["logit"]
    return {
        **base,
        "resultado": resultado,
        "inconclusivo": resultado == "INCONCLUSIVO",
        "probabilidade_ia": round(prob, 4),
        "fracao_suspeita": round(fracao, 4),
        "calibrado": bool(cal["calibrado"]),
        "calibracao": {k: cal[k] for k in ("data", "documentos", "metricas_teste", "fpr_alvo") if k in cal},
        "limiares": cal["limiares"],
        "motivos": motivos,
        "medidas": _arredondar(medidas_doc),
        "segmentos": resultado_segmentos,
    }


def analisar_texto(caminho, **kwargs):
    caminho = Path(caminho)
    return analisar_texto_bytes(caminho.read_bytes(), caminho.name, **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Detecção de texto gerado por IA em PDF, DOCX ou TXT.")
    parser.add_argument("arquivo")
    parser.add_argument("--sem-texto", action="store_true", help="omite o texto dos segmentos na saída")
    args = parser.parse_args(argv)
    relatorio = analisar_texto(args.arquivo)
    if args.sem_texto:
        for seg in relatorio["segmentos"]:
            seg.pop("texto", None)
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
