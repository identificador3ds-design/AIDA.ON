"""Pré-preenche pages/index-precos.html a partir do config e das traduções.

O site não tem build. Sem este passo, a página de preços chegaria vazia até o
JavaScript carregar: ruim para quem está sem JS, para a primeira pintura e para
buscadores. Aqui:

* todo elemento com `data-i18n` recebe o texto em pt-BR de
  i18n/precos.pt-BR.json, e todo `data-i18n-attr` recebe os atributos;
* o bloco `gerado:meta` recebe título, descrição, Open Graph e Twitter;
* o bloco `gerado:jsonld` recebe os planos como `schema.org/Offer`, tirados
  de config/pricing.json.

Os textos e os preços continuam vivendo só nos JSON; o HTML é saída. O teste
`test_pagina_precos_em_sincronia` falha se alguém editar um JSON e esquecer de
rodar:

    python docs/gerar_pagina_precos.py
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = RAIZ / "pages" / "index-precos.html"
CONFIG = RAIZ / "config" / "pricing.json"
I18N = RAIZ / "i18n" / "precos.pt-BR.json"
I18N_EN = RAIZ / "i18n" / "precos.en-US.json"
URL = "https://aida-on.com.br/precos"
IMAGEM = "https://aida-on.com.br/assets/images/pwa-icon-512.png"

_TEXTO = re.compile(
    r'(?P<abre><(?P<tag>[a-z][a-z0-9]*)\b[^>]*?\sdata-i18n="(?P<chave>[^"]+)"[^>]*>)'
    r"(?P<texto>[^<]*)"
    r"(?P<fecha></(?P=tag)>)"
)
_TAG_COM_ATRIBUTOS = re.compile(r'<[a-z][a-z0-9]*\b[^>]*\sdata-i18n-attr="(?P<pares>[^"]+)"[^>]*>')


def _bloco(nome, conteudo, documento):
    padrao = re.compile(
        rf"(?P<abre>[ \t]*<!-- gerado:{nome}\b[^>]*-->\n)(?P<miolo>.*?)(?P<fecha>[ \t]*<!-- /gerado:{nome} -->)",
        re.S,
    )
    if not padrao.search(documento):
        raise ValueError(f"marcador gerado:{nome} ausente em {PAGINA.name}")
    return padrao.sub(lambda m: m.group("abre") + conteudo + m.group("fecha"), documento, count=1)


def _preencher_textos(documento, t):
    def texto(m):
        return m.group("abre") + html.escape(t[m.group("chave")], quote=False) + m.group("fecha")

    def atributos(m):
        tag = m.group(0)
        for par in m.group("pares").split(";"):
            nome, chave = (p.strip() for p in par.split(":"))
            valor = html.escape(t[chave], quote=True)
            existente = re.compile(rf'\s{re.escape(nome)}="[^"]*"')
            if existente.search(tag):
                tag = existente.sub(f' {nome}="{valor}"', tag, count=1)
            else:
                tag = tag.replace(" data-i18n-attr=", f' {nome}="{valor}" data-i18n-attr=', 1)
        return tag

    return _TAG_COM_ATRIBUTOS.sub(atributos, _TEXTO.sub(texto, documento))


def _meta(t):
    e = lambda chave: html.escape(t[chave], quote=True)  # noqa: E731
    linhas = [
        f"<title>{html.escape(t['meta.title'], quote=False)}</title>",
        f'<meta name="description" content="{e("meta.description")}">',
        f'<link rel="canonical" href="{URL}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="AIDA.ON">',
        f'<meta property="og:locale" content="{e("meta.og_locale")}">',
        '<meta property="og:locale:alternate" content="en_US">',
        f'<meta property="og:title" content="{e("meta.og_title")}">',
        f'<meta property="og:description" content="{e("meta.og_description")}">',
        f'<meta property="og:url" content="{URL}">',
        f'<meta property="og:image" content="{IMAGEM}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{e("meta.og_title")}">',
        f'<meta name="twitter:description" content="{e("meta.og_description")}">',
        f'<meta name="twitter:image" content="{IMAGEM}">',
    ]
    return "".join(f"    {linha}\n" for linha in linhas)


def _preco_texto(valor):
    # schema.org espera ponto decimal e sem símbolo; duas casas no mínimo.
    texto = f"{valor:.4f}".rstrip("0")
    inteiro, _, casas = texto.partition(".")
    return f"{inteiro}.{casas.ljust(2, '0')}"


def ofertas(config, dicionarios):
    """Uma Offer por plano com preço publicado (contato/validação ficam fora)."""
    saida = []
    for codigo, mercado in config["markets"].items():
        moeda = mercado["currency"]
        t = dicionarios["pt-BR" if codigo == "BR" else "en-US"]
        for segmento in ("platform", "api"):
            for plano in mercado[segmento]:
                preco = (plano.get("price_monthly") or {}).get(moeda)
                if not isinstance(preco, (int, float)):
                    continue
                oferta = {
                    "@type": "Offer",
                    "name": t[plano["name_key"]],
                    "category": "API" if segmento == "api" else "Web platform",
                    "price": _preco_texto(preco),
                    "priceCurrency": moeda,
                    "url": URL,
                    "availability": "https://schema.org/InStock",
                    "priceSpecification": {
                        "@type": "UnitPriceSpecification",
                        "price": _preco_texto(preco),
                        "priceCurrency": moeda,
                        "referenceQuantity": {"@type": "QuantitativeValue", "value": 1, "unitCode": "MON"},
                    },
                }
                if codigo == "BR":
                    oferta["eligibleRegion"] = {"@type": "Country", "name": "BR"}
                if isinstance(plano.get("credits_included"), int):
                    oferta["description"] = f"{plano['credits_included']} credits/month"
                saida.append(oferta)
    return saida


def _jsonld(config, dicionarios):
    dados = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "AIDA",
        "applicationCategory": "SecurityApplication",
        "operatingSystem": "Web",
        "url": URL,
        "description": dicionarios["pt-BR"]["meta.description"],
        "offers": ofertas(config, dicionarios),
    }
    corpo = json.dumps(dados, ensure_ascii=False, indent=2).replace("</", "<\\/")
    corpo = "\n".join("    " + linha for linha in corpo.splitlines())
    return f'    <script type="application/ld+json">\n{corpo}\n    </script>\n'


def gerar(documento):
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    pt = json.loads(I18N.read_text(encoding="utf-8"))
    en = json.loads(I18N_EN.read_text(encoding="utf-8"))
    documento = _preencher_textos(documento, pt)
    documento = _bloco("meta", _meta(pt), documento)
    return _bloco("jsonld", _jsonld(config, {"pt-BR": pt, "en-US": en}), documento)


def main(argv):
    atual = PAGINA.read_text(encoding="utf-8")
    novo = gerar(atual)
    if "--verificar" in argv:
        if novo != atual:
            print(f"{PAGINA.relative_to(RAIZ)} desatualizada: rode python docs/gerar_pagina_precos.py")
            return 1
        return 0
    if novo != atual:
        PAGINA.write_text(novo, encoding="utf-8", newline="\n")
        print(f"atualizado: {PAGINA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
