"""Credenciais de conteudo (C2PA) embutidas no documento.

ChatGPT, Adobe Firefly e outros geradores gravam um manifesto C2PA no arquivo que
declaram "criado por IA" (digitalSourceType trainedAlgorithmicMedia). No PDF ele vai
como anexo /AF com Subtype application/c2pa, numa revisao incremental; no .docx (ZIP)
em META-INF/content_credential.c2pa; em texto puro, codificado em seletores de
variacao Unicode invisiveis (ver texto_puro.py). O 0015 da
coleta de 09/10 (prova "A Cartomante" do ChatGPT, ReportLab) trazia um, assinado pela
OpenAI, e a v0 so via "biblioteca de programacao" e "revisao incremental".

A assinatura NAO e verificada aqui (isso pede a cadeia de certificados e o pacote
c2pa). Lemos o que o manifesto declara: quem gerou, com que modelo e o tipo de
origem. Um manifesto que se declara IA e indicio forte: ninguem forja isso para
incriminar um documento verdadeiro, e quem quer esconder a IA apaga o manifesto.
"""

from __future__ import annotations

import re

# Vocabulario IPTC de digitalSourceType que significa geracao ou edicao por IA.
FONTES_IA = {
    "trainedAlgorithmicMedia": "gerado por IA",
    "compositeWithTrainedAlgorithmicMedia": "editado com IA",
}
_ORGANIZACAO = re.compile(rb"\x06\x03\x55\x04\x0a[\x0c\x13](.)", re.S)  # OID 2.5.4.10 (O=)


def _texto_cbor(dados, inicio):
    """Le a string CBOR (major type 3) que comeca em `inicio`."""
    if inicio >= len(dados):
        return None
    cab = dados[inicio]
    if 0x60 <= cab <= 0x77:
        n, pos = cab - 0x60, inicio + 1
    elif cab == 0x78 and inicio + 1 < len(dados):
        n, pos = dados[inicio + 1], inicio + 2
    else:
        return None
    try:
        return dados[pos:pos + n].decode("utf-8")
    except UnicodeDecodeError:
        return None


def _nome_depois(dados, chave):
    """Valor do campo "name" no mapa CBOR que segue `chave` (ex.: claim_generator_info)."""
    i = dados.find(chave)
    if i < 0:
        return None
    j = dados.find(b"dname", i, i + 200)  # "dname" = string CBOR de 4 letras "name"
    return _texto_cbor(dados, j + 5) if j >= 0 else None


def _organizacoes(dados):
    vistas = []
    for m in _ORGANIZACAO.finditer(dados):
        n = m.group(1)[0]
        nome = dados[m.end():m.end() + n].decode("utf-8", "replace")
        if nome not in vistas:
            vistas.append(nome)
    return vistas


def _manifestos(reader, dados):
    achados = []
    try:
        for anexos in reader.attachments.values():
            achados += [a for a in anexos if eh_manifesto(a)]
    except Exception:  # anexos malformados nao podem derrubar a analise
        pass
    if not achados and b"c2pa.claim" in dados:  # manifesto sem compressao fora de /EmbeddedFiles
        achados.append(dados)
    return achados


def ler_c2pa(reader, dados: bytes):
    """Resumo do primeiro manifesto C2PA do PDF, ou presente=False."""
    manifestos = _manifestos(reader, dados)
    return resumir_manifesto(manifestos[0]) if manifestos else {"presente": False}


def eh_manifesto(dados: bytes):
    return b"jumb" in dados and b"c2pa" in dados


def resumir_manifesto(m: bytes):
    """Gerador, modelo e origem declarados num manifesto C2PA (JUMBF/CBOR) ja extraido."""
    fontes = [nome for nome in FONTES_IA if f"digitalsourcetype/{nome}".encode() in m]
    return {
        "presente": True,
        "gerador": _nome_depois(m, b"claim_generator_info"),
        "modelo": _nome_depois(m, b"softwareAgent"),
        "declara_ia": bool(fontes),
        "origem_declarada": FONTES_IA[fontes[0]] if fontes else None,
        "certificado_de": _organizacoes(m)[:3],
        "assinatura_verificada": False,
    }
