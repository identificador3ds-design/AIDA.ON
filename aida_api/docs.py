"""Referencia legivel de /v1, gerada do proprio contrato.

Documentacao escrita a mao descola do codigo — e descola em silencio, porque
nada quebra quando ela mente. Aqui a pagina e uma renderizacao de
`contrato.CONTRATO`, o mesmo objeto que `GET /v1/contract` serve e que as rotas
usam. Campo novo aparece na pagina sem ninguem lembrar de edita-la.
"""

from __future__ import annotations

from html import escape

from .contrato import CONTRATO

_ESTILO = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 48px 24px 96px;
  background: #0b2420; color: #e8f2ee;
  font: 16px/1.65 ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif;
}
main { max-width: 860px; margin: 0 auto; }
h1 { font-size: 2.4rem; margin: 0 0 4px; letter-spacing: -0.02em; }
h2 { font-size: 1.35rem; margin: 48px 0 12px; color: #fff; }
h3 { font-size: 1rem; margin: 24px 0 6px; font-family: ui-monospace, monospace; color: #a7f3d0; }
p, li { color: #c3d8d1; }
.tag {
  display: inline-block; padding: 4px 12px; border-radius: 999px;
  background: rgba(224,138,30,.14); color: #f0b45e; font-size: .72rem;
  letter-spacing: .14em; text-transform: uppercase; font-weight: 700;
}
.aviso {
  border: 1px solid rgba(240,180,94,.35); border-radius: 12px;
  background: rgba(240,180,94,.07); padding: 16px 20px; margin: 24px 0;
}
table { width: 100%; border-collapse: collapse; margin: 8px 0 24px; }
td { border-top: 1px solid rgba(255,255,255,.09); padding: 10px 8px; vertical-align: top; }
td.campo { font-family: ui-monospace, monospace; color: #a7f3d0; white-space: nowrap; width: 34%; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
pre {
  background: #071a17; border: 1px solid rgba(255,255,255,.08); border-radius: 12px;
  padding: 18px; overflow-x: auto; font-size: .86rem; color: #d7e9e2;
}
footer { margin-top: 64px; color: #7ea79b; font-size: .85rem; }
"""

_EXEMPLO_REQ = """curl -X POST https://<host>/v1/analyze/image \\
  -H "Authorization: Bearer <sua-chave>" \\
  -F "image=@foto.jpg" \\
  -F "evidence=true"
"""

_EXEMPLO_RESP = """{
  "api_version": "v1",
  "analysis_id": "<id>",
  "result": "INCONCLUSIVO",
  "inconclusive": true,
  "out_of_domain": false,
  "confidence": "baixa",
  "ai_probability": 0.51,
  "real_probability": 0.49,
  "reasons": ["..."],
  "module_scores": { "...": 0.0 },
  "quality": { "...": 0.0 },
  "limitations": ["..."],
  "evidence": { "maps": { "...": "/v1/evidence/<id>/<mapa>" } },
  "disclaimer": "indicio, nao prova",
  "model_version": "AIDA-2.0"
}
"""


def _tabela(dicionario):
    linhas = "".join(
        f"<tr><td class='campo'>{escape(str(chave))}</td><td>{escape(str(valor))}</td></tr>"
        for chave, valor in dicionario.items()
    )
    return f"<table>{linhas}</table>"


def _endpoints():
    partes = []
    for rota, detalhe in CONTRATO["endpoints"].items():
        partes.append(f"<h3>{escape(rota)}</h3>")
        if isinstance(detalhe, dict):
            partes.append(f"<p>{escape(str(detalhe.get('summary', '')))}</p>")
            campos = detalhe.get("fields")
            if campos:
                partes.append(_tabela(campos))
        else:
            partes.append(f"<p>{escape(str(detalhe))}</p>")
    return "".join(partes)


def pagina_html():
    avisos = "".join(f"<li>{escape(a)}</li>" for a in CONTRATO["integration_warnings"])
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AIDA API — referencia {escape(CONTRATO['version'])}</title>
<style>{_ESTILO}</style>
</head>
<body>
<main>
  <span class="tag">{escape(CONTRATO['status'])}</span>
  <h1>{escape(CONTRATO['api'])} <span style="color:#b7a8f0">{escape(CONTRATO['version'])}</span></h1>
  <p>{escape(CONTRATO['notice'])}</p>

  <div class="aviso">
    <strong>Antes de integrar</strong>
    <ul>{avisos}</ul>
  </div>

  <h2>Autenticacao</h2>
  {_tabela(CONTRATO['auth'])}

  <h2>Endpoints</h2>
  {_endpoints()}

  <h2>Exemplo</h2>
  <pre>{escape(_EXEMPLO_REQ)}</pre>
  <pre>{escape(_EXEMPLO_RESP)}</pre>

  <h2>Objeto de analise</h2>
  {_tabela(CONTRATO['analysis_object'])}

  <h2>Erros</h2>
  {_tabela(CONTRATO['errors'])}

  <h2>Versionamento</h2>
  <p>{escape(CONTRATO['versioning'])}</p>

  <footer>
    Pagina gerada a partir de <code>GET /v1/contract</code> — a mesma estrutura
    que as rotas usam. Se um campo mudar no codigo, muda aqui junto.
  </footer>
</main>
</body>
</html>"""
