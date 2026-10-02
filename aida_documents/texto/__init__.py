"""AIDA Documents · texto: indícios de texto gerado por IA em PDF, DOCX e TXT."""

from importlib import import_module

_ONDE = {
    "analisar_texto": "detector",
    "analisar_texto_bytes": "detector",
    "extrair": "extracao",
    "limpar": "limpeza",
}
__all__ = sorted(_ONDE)


def __getattr__(nome):
    if nome in _ONDE:
        return getattr(import_module(f".{_ONDE[nome]}", __name__), nome)
    raise AttributeError(f"module {__name__!r} has no attribute {nome!r}")
