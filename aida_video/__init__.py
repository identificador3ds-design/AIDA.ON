"""AIDA Video: extracao de frames, analise por frame no AIDA Core, agregacao temporal e audio."""

from importlib import import_module

# Import preguicoso: ver aida_audio/__init__.py.
_ONDE = {
    "agregar": "agregacao",
    "combinar": "agregacao",
    "AnalisadorCore": "analisadores",
    "AnalisadorFixo": "analisadores",
    "CoreIndisponivel": "analisadores",
    "CoreRecusou": "analisadores",
    "analisar_video": "analisar_video",
    "extrair_frames": "extrair_frames",
    "validar_video": "extrair_frames",
}
__all__ = sorted(_ONDE)


def __getattr__(nome):
    if nome in _ONDE:
        return getattr(import_module(f".{_ONDE[nome]}", __name__), nome)
    raise AttributeError(f"module {__name__!r} has no attribute {nome!r}")
