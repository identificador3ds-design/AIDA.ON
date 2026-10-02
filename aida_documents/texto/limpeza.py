"""Limpeza do texto extraido: sobra so a prosa que o autor escreveu.

Cabecalho, rodape e numero de pagina se repetem em todas as paginas e, se ficarem,
entram no meio das frases (o PDF nao separa "corpo" de "rodape") e distorcem as
medidas: uma mesma linha vista 30 vezes parece texto muito previsivel. Tambem saem
titulos, sumario, tabelas e a lista de referencias, que nao sao texto corrido.

Tudo o que foi tirado e contado em `removidos`, para o relatorio poder mostrar.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from statistics import median

LINHAS_DE_BORDA = 3
MAX_CHARS_BORDA = 120
MIN_PALAVRAS_PROSA = 12
_LIGATURAS = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "­": "", " ": " ", "​": ""}
_NUMERO_PAGINA = re.compile(
    r"^(?:p[áa]g(?:ina|\.)?|page|p\.)?\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*(?:(?:de|of|/)\s*\d{1,4})?$", re.IGNORECASE
)
_TITULO_REFERENCIAS = re.compile(
    r"^(?:\d+\.?\s*)?(?:refer[êe]ncias(?: bibliogr[áa]ficas)?|bibliografia|references|bibliography|works cited)\s*:?$",
    re.IGNORECASE,
)
_FIM_DE_FRASE = re.compile(r"[.!?…:;][\"”’')\]]*$")
_PONTILHADO = re.compile(r"\.{4,}|(?:\. ){4,}|_{4,}")
_PALAVRA = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*")


def normalizar(texto):
    texto = unicodedata.normalize("NFC", texto)
    for de, para in _LIGATURAS.items():
        texto = texto.replace(de, para)
    return texto


def _chave(linha):
    """Forma da linha sem os numeros: "Relatorio 2026 - 3" e "Relatorio 2026 - 4" sao a mesma."""
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", linha.lower())).strip()


def _bordas(linhas):
    """Indices das primeiras e ultimas linhas nao vazias da pagina."""
    cheias = [i for i, linha in enumerate(linhas) if linha]
    return set(cheias[:LINHAS_DE_BORDA]) | set(cheias[-LINHAS_DE_BORDA:])


def _tirar_bordas(paginas):
    """Remove linhas repetidas nas bordas das paginas e numeros de pagina isolados."""
    removidos = Counter()
    com_texto = [p for p in paginas if any(p)]
    contagem = Counter()
    for linhas in com_texto:
        contagem.update({_chave(linhas[i]) for i in _bordas(linhas) if len(linhas[i]) <= MAX_CHARS_BORDA})
    # Repetida em pelo menos 40% das paginas (e no minimo 3): cabecalho de capitulo conta.
    minimo = max(3, math.ceil(0.4 * len(com_texto)))
    repetidas = {chave for chave, n in contagem.items() if n >= minimo}

    limpas = []
    for linhas in paginas:
        bordas = _bordas(linhas)
        saida = []
        for i, linha in enumerate(linhas):
            if i in bordas and _NUMERO_PAGINA.match(linha):
                removidos["numero_pagina"] += 1
            elif i in bordas and _chave(linha) in repetidas:
                removidos["cabecalho_rodape"] += 1
            else:
                saida.append(linha)
        limpas.append(saida)
    return limpas, removidos


def _paragrafos(paginas):
    """Remonta paragrafos a partir de linhas quebradas pelo PDF.

    Cada paragrafo guarda `marcas`: [(posicao no texto, pagina)], uma por linha, para
    que um trecho no meio de um paragrafo longo saiba em que pagina esta."""
    linhas = [(re.sub(r"\s+", " ", linha), n) for n, pagina in enumerate(paginas, 1) for linha in pagina + [""]]
    compridas = [len(linha) for linha, _ in linhas if len(linha) >= 30]
    tipico = median(compridas) if compridas else 80
    # Linhas muito longas: cada linha ja e um paragrafo (TXT sem quebra, DOCX).
    linha_e_paragrafo = tipico > 200

    paragrafos, atual, marcas, ultima = [], "", [], 0

    def fechar():
        nonlocal atual, marcas
        if atual:
            paragrafos.append({"texto": atual, "pagina": marcas[0][1], "marcas": marcas})
        atual, marcas = "", []

    anterior_vazia = False
    for linha, n in linhas:
        if not linha:
            # Fim de pagina (linha vazia que acrescentamos) nao fecha um paragrafo em aberto.
            if anterior_vazia or linha_e_paragrafo or not atual or _FIM_DE_FRASE.search(atual):
                fechar()
            anterior_vazia = True
            continue
        if atual:
            terminou = bool(_FIM_DE_FRASE.search(atual))
            comeca_novo = linha[:1].isupper() or linha[:1].isdigit()
            # Ultima linha do paragrafo e mais curta que as outras.
            fim_de_paragrafo = terminou and ultima < 0.75 * tipico
            # Titulo: linha curta, sem ponto, que comeca com maiuscula ou numero. Fecha o
            # que vinha antes (titulo depois de paragrafo) e o proprio titulo (texto depois dele).
            titulo_antes = not terminou and len(atual) < 0.6 * tipico and comeca_novo
            titulo_agora = terminou and comeca_novo and len(linha) < 0.6 * tipico and not _FIM_DE_FRASE.search(linha)
            if linha_e_paragrafo or fim_de_paragrafo or titulo_antes or titulo_agora:
                fechar()
        if atual and atual.endswith("-") and linha[:1].islower():
            atual = atual[:-1]  # palavra hifenizada na quebra de linha
        elif atual:
            atual += " "
        marcas.append((len(atual), n))
        atual += linha
        ultima = len(linha)
        anterior_vazia = False
    fechar()
    return paragrafos


def pagina_em(paragrafo, posicao):
    """Pagina em que esta o caractere `posicao` do texto do paragrafo."""
    pagina = paragrafo["pagina"]
    for inicio, n in paragrafo.get("marcas", ()):
        if inicio > posicao:
            break
        pagina = n
    return pagina


def contar_palavras(texto):
    return len(_PALAVRA.findall(texto))


def _e_prosa(texto):
    if contar_palavras(texto) < MIN_PALAVRAS_PROSA or _PONTILHADO.search(texto):
        return False
    if not re.search(r"[.!?…]", texto):
        return False
    letras = sum(c.isalpha() for c in texto)
    digitos = sum(c.isdigit() for c in texto)
    visiveis = sum(not c.isspace() for c in texto) or 1
    return letras / visiveis >= 0.6 and digitos / visiveis < 0.25


def limpar(paginas):
    """paginas: lista de textos brutos. Devolve {"paragrafos", "removidos", "palavras"}."""
    linhas = [[linha.strip() for linha in normalizar(p).splitlines()] for p in paginas]
    linhas, removidos = _tirar_bordas(linhas)
    paragrafos = _paragrafos(linhas)

    # Lista de referencias: so vale como corte na segunda metade (no sumario ha um titulo igual).
    for i, par in enumerate(paragrafos):
        if i >= 0.4 * len(paragrafos) and _TITULO_REFERENCIAS.match(par["texto"]):
            removidos["referencias"] = len(paragrafos) - i
            paragrafos = paragrafos[:i]
            break

    prosa = [p for p in paragrafos if _e_prosa(p["texto"])]
    removidos["nao_prosa"] = len(paragrafos) - len(prosa)
    return {
        "paragrafos": prosa,
        "removidos": {k: removidos.get(k, 0) for k in ("cabecalho_rodape", "numero_pagina", "nao_prosa", "referencias")},
        "palavras": sum(contar_palavras(p["texto"]) for p in prosa),
    }
