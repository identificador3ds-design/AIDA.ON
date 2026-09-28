"""AIDA Audio: leitura, caracteristicas, treino e analise de audio sintetico."""

from importlib import import_module

# Import preguicoso: importar os submodulos aqui faria `python -m aida_audio.analisar`
# carregar o modulo duas vezes (RuntimeWarning do runpy).
_ONDE = {
    "AudioAusente": "carregar",
    "carregar_audio": "carregar",
    "salvar_wav": "carregar",
    "extrair_caracteristicas": "caracteristicas",
    "analisar_amostras": "analisar",
    "analisar_audio": "analisar",
}
__all__ = sorted(_ONDE)


def __getattr__(nome):
    if nome in _ONDE:
        return getattr(import_module(f".{_ONDE[nome]}", __name__), nome)
    raise AttributeError(f"module {__name__!r} has no attribute {nome!r}")
