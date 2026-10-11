"""AIDA Documents: triagem de PDFs (notas, recibos, comprovantes) adulterados ou gerados."""

from importlib import import_module

# Import preguicoso, como em aida_audio: evita carregar o modulo duas vezes com
# `python -m aida_documents.analisar`.
_ONDE = {
    "analisar_documento": "analisar",
    "analisar_bytes": "analisar",
    "analisar_benford": "benford",
    "caracteristicas_bytes": "caracteristicas",
    "inspecionar_pdf": "estrutura",
    "extrair_numeros": "numeros",
    "verificar_identificadores": "numeros",
}
__all__ = sorted(_ONDE)


def __getattr__(nome):
    if nome in _ONDE:
        return getattr(import_module(f".{_ONDE[nome]}", __name__), nome)
    raise AttributeError(f"module {__name__!r} has no attribute {nome!r}")
