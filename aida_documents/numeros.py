"""Valores e identificadores no texto de um documento brasileiro.

Duas coisas saem daqui:
- os valores "naturais" (precos, totais, quantidades) para a Lei de Benford. CNPJ,
  CPF, datas, horas, CEP e chaves de acesso sao retirados antes, porque sao codigos,
  nao grandezas, e distorceriam a distribuicao;
- a checagem dos digitos verificadores de CNPJ (inclusive o alfanumerico, em vigor
  desde jul/2026), CPF e chave de acesso de NF-e/NFC-e (44 digitos). Um DV errado num
  documento "oficial" e o indicio mais forte e barato que existe: sistemas emissores
  nunca erram o DV, quem edita a mao ou pede a uma IA erra.
"""

from __future__ import annotations

import re

# Codigos de UF do IBGE aceitos na chave de acesso.
UFS_IBGE = {11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 32, 33, 35, 41, 42, 43, 50, 51, 52, 53}

_CNPJ = re.compile(r"\b([0-9A-Z]{2})\.([0-9A-Z]{3})\.([0-9A-Z]{3})/([0-9A-Z]{4})-(\d{2})\b")
_CPF = re.compile(r"\b(\d{3})\.(\d{3})\.(\d{3})-(\d{2})\b")
_CHAVE = re.compile(r"(?<![\d])(\d{4}(?:[ .]?\d{4}){10})(?![\d])")
_RUIDO = [
    re.compile(r"\b\d{2}/\d{2}/\d{2,4}\b"),  # datas
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),  # horas
    re.compile(r"\b\d{5}-\d{3}\b"),  # CEP
    re.compile(r"\(?\b\d{2}\)?\s?\d{4,5}-\d{4}\b"),  # telefone
]
_NUMERO = re.compile(r"(?<![\w.,])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+|\d+\.\d+|\d+)(?![\w])")
_MONETARIO = re.compile(r"(?<![\w.,])(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})(?![\w,])")
VALOR_MINIMO = 10.0


def _valor(token):
    if "," in token:  # formato brasileiro: 1.234,56
        return float(token.replace(".", "").replace(",", "."))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):  # 1.234 -> milhar
        return float(token.replace(".", ""))
    return float(token)


def extrair_numeros(texto, valor_minimo=VALOR_MINIMO, apenas_monetarios=False):
    """Valores >= valor_minimo, sem identificadores. Valores < 10 nao tem primeiro
    digito informativo (sao quase sempre quantidades 1, 2, 3).

    apenas_monetarios=True fica so com valores no formato 1.234,56: e o que interessa
    para Benford numa nota. Em texto corrido (artigo, contrato) anos, paginas e numeros
    de secao dominam e a distribuicao foge de Benford sem haver fraude nenhuma."""
    limpo = texto
    for padrao in (_CNPJ, _CPF, _CHAVE, *_RUIDO):
        limpo = padrao.sub(" ", limpo)
    valores = []
    for token in (_MONETARIO if apenas_monetarios else _NUMERO).findall(limpo):
        try:
            v = _valor(token)
        except ValueError:
            continue
        # Sequencias longas sem separador sao codigos (EAN, protocolo, numero da nota).
        if v >= valor_minimo and len(token.replace(".", "").replace(",", "")) <= 9:
            valores.append(v)
    return valores


def _dv_mod11(corpo, pesos):
    soma = sum((ord(c) - 48) * p for c, p in zip(corpo, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def cnpj_valido(cnpj):
    s = re.sub(r"[./-]", "", cnpj.upper())
    if len(s) != 14 or not s[-2:].isdigit() or len(set(s)) == 1:
        return False
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = _dv_mod11(s[:12], p1)
    d2 = _dv_mod11(s[:12] + str(d1), [6] + p1)
    return s[-2:] == f"{d1}{d2}"


def cpf_valido(cpf):
    s = re.sub(r"\D", "", cpf)
    if len(s) != 11 or len(set(s)) == 1:
        return False
    d1 = _dv_mod11(s[:9], range(10, 1, -1))
    d2 = _dv_mod11(s[:9] + str(d1), range(11, 1, -1))
    return s[-2:] == f"{d1}{d2}"


def chave_acesso_valida(chave):
    """Chave de NF-e/NFC-e/CT-e: 43 digitos + DV modulo 11 (pesos 2..9 da direita)."""
    s = re.sub(r"\D", "", chave)
    if len(s) != 44:
        return False
    pesos = [2 + (i % 8) for i in range(43)][::-1]
    return int(s[43]) == _dv_mod11(s[:43], pesos)


def _problemas_chave(s):
    problemas = []
    if not chave_acesso_valida(s):
        problemas.append("DV da chave de acesso não confere")
    if int(s[:2]) not in UFS_IBGE:
        problemas.append(f"código de UF inválido na chave ({s[:2]})")
    if not 1 <= int(s[4:6]) <= 12:
        problemas.append(f"mês de emissão inválido na chave ({s[4:6]})")
    if s[20:22] not in {"55", "65", "57", "67", "59"}:
        problemas.append(f"modelo de documento incomum na chave ({s[20:22]})")
    return problemas


def verificar_identificadores(texto):
    cnpjs = ["".join(m) for m in _CNPJ.findall(texto.upper())]
    cpfs = ["".join(m) for m in _CPF.findall(texto)]
    chaves = [re.sub(r"\D", "", m) for m in _CHAVE.findall(texto)]

    alertas = []
    for c in sorted(set(cnpjs)):
        if not cnpj_valido(c):
            alertas.append(f"CNPJ com dígito verificador inválido: {c}")
    for c in sorted(set(cpfs)):
        if not cpf_valido(c):
            alertas.append(f"CPF com dígito verificador inválido: {c[:3]}.***.***-{c[-2:]}")
    for ch in sorted(set(chaves)):
        for p in _problemas_chave(ch):
            alertas.append(f"{p}: {ch[:4]}…{ch[-4:]}")
        # O CNPJ do emitente esta nas posicoes 7-20 da chave e deve aparecer no documento.
        emitente = ch[6:20]
        if cnpjs and emitente not in cnpjs and cnpj_valido(emitente):
            alertas.append("CNPJ do emitente na chave de acesso não aparece no documento")

    return {
        "cnpjs": len(set(cnpjs)),
        "cpfs": len(set(cpfs)),
        "chaves_acesso": len(set(chaves)),
        "alertas": alertas,
    }
