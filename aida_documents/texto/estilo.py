"""Medidas de estilo que nao precisam de modelo de linguagem.

- idioma: portugues ou ingles, pela proporcao de palavras funcionais;
- frases: divisao com cuidado para abreviaturas (Dr., art., e.g.);
- burstiness das frases: coeficiente de variacao do comprimento. Gente alterna frase
  curta e longa; texto de LLM costuma ficar numa faixa estreita;
- diversidade lexical (MATTR): proporcao de palavras distintas em janelas de 50, que
  ao contrario do type-token ratio nao depende do tamanho do texto;
- marcadores: conectivos e formulas que os LLMs repetem ("alem disso", "vale
  destacar", "furthermore"). E o sinal mais fraco e o que envelhece mais rapido:
  muda a cada geracao de modelo e aparece em texto formal de gente.

Nenhuma dessas medidas decide sozinha. Elas entram, junto com a perplexidade, no
classificador calibrado de `detector.py`.
"""

from __future__ import annotations

import re
from collections import Counter
from statistics import mean, pstdev

_PALAVRA = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*")
_FUNCIONAIS = {
    "pt": set(
        "de a o que e do da em um para é com não uma os no se na por mais as dos como mas foi ao ele das tem à seu sua "
        "ou ser quando muito há nos já está eu também só pelo pela até isso ela entre era depois sem mesmo aos ter seus "
        "quem nas me esse eles estão você essa num nem suas meu às minha têm numa pelos elas são".split()
    ),
    "en": set(
        "the of and to in is that it was for on are as with his they at be this from have or one had by but not what "
        "all were we when your can said there use an each which she do how their if will up other about out many then "
        "them these so some her would make like him into has more than been its who now could".split()
    ),
}
_ABREVIATURAS = (
    "dr dra sr sra srs prof profa art arts cap fig tab ex vol núm pág pag p pp eds cf vs "
    "mr mrs jr inc ltd eg ie e.g i.e"
).split()
_PROTEGE = re.compile(r"\b(" + "|".join(re.escape(a) for a in _ABREVIATURAS) + r")\.", re.IGNORECASE)
_FRONTEIRA = re.compile(r"(?<=[.!?…])[\"”’')\]]*\s+(?=[\"“‘'(\[]?[A-ZÀ-ÖØ-Þ0-9])")
MARCADORES = {
    "pt": [
        "além disso", "ademais", "em suma", "em resumo", "em conclusão", "por fim", "nesse sentido", "nesse contexto",
        "diante disso", "dessa forma", "desse modo", "vale destacar", "vale ressaltar", "é importante ressaltar",
        "é importante destacar", "é importante notar", "é fundamental", "é crucial", "é essencial", "cabe destacar",
        "desempenha um papel", "papel fundamental", "papel crucial", "no cenário atual", "em um mundo cada vez mais",
        "não apenas", "mas também", "por outro lado", "em última análise", "de maneira geral",
    ],
    "en": [
        "furthermore", "moreover", "additionally", "in conclusion", "in summary", "overall", "it is important to note",
        "it is worth noting", "it's important to note", "it's worth noting", "plays a crucial role", "plays a vital role",
        "plays a key role", "delve", "tapestry", "landscape of", "in today's", "ever-evolving", "not only", "but also",
        "on the other hand", "ultimately", "a testament to", "navigate the", "underscores", "multifaceted",
    ],
}


def palavras(texto):
    return [p.lower() for p in _PALAVRA.findall(texto)]


def detectar_idioma(texto):
    """"pt", "en" ou None quando nenhum dos dois explica o texto."""
    amostra = palavras(texto)[:3000]
    if len(amostra) < 20:
        return None
    taxa = {idioma: sum(p in lista for p in amostra) / len(amostra) for idioma, lista in _FUNCIONAIS.items()}
    idioma = max(taxa, key=taxa.get)
    outro = min(taxa, key=taxa.get)
    if taxa[idioma] < 0.20 or taxa[idioma] < 1.3 * taxa[outro]:
        return None
    return idioma


def dividir_frases(texto):
    """Lista de (inicio, fim) das frases dentro de `texto`."""
    protegido = _PROTEGE.sub(lambda m: m.group(1) + "\x00", texto)
    cortes = [m.end() for m in _FRONTEIRA.finditer(protegido)]
    trechos, inicio = [], 0
    for corte in cortes + [len(texto)]:
        bruto = texto[inicio:corte]
        limpo = bruto.strip()
        if limpo:
            ini = inicio + bruto.index(limpo[0])
            trechos.append((ini, ini + len(limpo)))
        inicio = corte
    return trechos


def burstiness(valores):
    """Coeficiente de variacao (desvio / media). None com menos de 3 valores."""
    valores = list(valores)
    if len(valores) < 3 or not mean(valores):
        return None
    return pstdev(valores) / mean(valores)


def mattr(tokens, janela=50):
    if len(tokens) < janela:
        return len(set(tokens)) / len(tokens) if tokens else None
    contagem = Counter(tokens[:janela])
    soma = len(contagem)
    for i in range(janela, len(tokens)):
        sai, entra = tokens[i - janela], tokens[i]
        contagem[sai] -= 1
        if not contagem[sai]:
            del contagem[sai]
        contagem[entra] += 1
        soma += len(contagem)
    return soma / (len(tokens) - janela + 1) / janela


def achar_marcadores(texto, idioma):
    minusculo = texto.lower()
    achados = Counter()
    for marcador in MARCADORES.get(idioma, []):
        n = len(re.findall(r"(?<!\w)" + re.escape(marcador) + r"(?!\w)", minusculo))
        if n:
            achados[marcador] = n
    return achados


def medir_estilo(texto, idioma, frases=None):
    """Medidas de um trecho. `frases`: lista de (inicio, fim) ja calculada, se houver."""
    frases = frases if frases is not None else dividir_frases(texto)
    tokens = palavras(texto)
    tamanhos = [len(palavras(texto[a:b])) for a, b in frases]
    tamanhos = [t for t in tamanhos if t]
    marcadores = achar_marcadores(texto, idioma)
    return {
        "palavras": len(tokens),
        "frases": len(tamanhos),
        "palavras_por_frase": round(mean(tamanhos), 2) if tamanhos else None,
        "burst_frases": burstiness(tamanhos),
        "mattr": mattr(tokens),
        "marcadores_por_mil": 1000 * sum(marcadores.values()) / len(tokens) if tokens else None,
        "marcadores": dict(marcadores.most_common(8)),
    }
