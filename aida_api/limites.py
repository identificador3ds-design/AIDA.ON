"""Limites de uso: cota por chave, em janela deslizante.

A analise e cara — segundos de CPU por imagem. Sem cota, uma unica chave em
rajada consome a capacidade de todas as outras, e o efeito para quem esta do
lado de fora e indistinguivel de queda do servico.

A janela e deslizante, nao fixa: com janela fixa, quem chama no fim de uma e no
comeco da seguinte passa duas cotas em poucos segundos, exatamente a rajada que
o limite existia para conter.

O contador vive no processo. Com varias instancias atras de um balanceador, o
teto efetivo e multiplicado pelo numero delas; para cota global e preciso um
contador compartilhado (Redis/Postgres) no lugar desta classe — a interface
`consumir` continua a mesma.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from . import config


class Veredito:
    """Resultado de uma tentativa de consumo de cota."""

    def __init__(self, permitido, restante, limite, janela_s, esperar_s=0):
        self.permitido = permitido
        self.restante = restante
        self.limite = limite
        self.janela_s = janela_s
        self.esperar_s = esperar_s

    def cabecalhos(self):
        """Cabecalhos padrao de cota, presentes tambem no caso permitido."""
        cabecalhos = {
            "X-RateLimit-Limit": str(self.limite),
            "X-RateLimit-Remaining": str(max(0, self.restante)),
            "X-RateLimit-Window": str(self.janela_s),
        }
        if not self.permitido:
            cabecalhos["Retry-After"] = str(max(1, int(self.esperar_s) + 1))
        return cabecalhos


class LimitadorEmMemoria:
    def __init__(self, limite_padrao=None, janela_s=None):
        self._limite_padrao = limite_padrao if limite_padrao is not None else config.LIMITE_PADRAO
        self._janela = janela_s if janela_s is not None else config.JANELA_LIMITE_S
        self._marcas = {}
        self._lock = threading.Lock()

    def _limpar(self, fila, agora):
        while fila and fila[0] <= agora - self._janela:
            fila.popleft()

    def consumir(self, identificador, limite=None):
        limite = int(limite or self._limite_padrao)
        if limite <= 0:
            # Limite zero e uma decisao explicita: chave suspensa sem revogar.
            return Veredito(False, 0, limite, self._janela, self._janela)

        agora = time.time()
        with self._lock:
            fila = self._marcas.setdefault(identificador, deque())
            self._limpar(fila, agora)
            if len(fila) >= limite:
                esperar = self._janela - (agora - fila[0])
                return Veredito(False, 0, limite, self._janela, max(0, esperar))
            fila.append(agora)
            return Veredito(True, limite - len(fila), limite, self._janela)

    def estado(self, identificador=None):
        agora = time.time()
        with self._lock:
            if identificador is not None:
                fila = self._marcas.get(identificador, deque())
                self._limpar(fila, agora)
                return {"used": len(fila), "limit": self._limite_padrao, "window_seconds": self._janela}
            for fila in self._marcas.values():
                self._limpar(fila, agora)
            return {
                "tracked_keys": len([f for f in self._marcas.values() if f]),
                "default_limit": self._limite_padrao,
                "window_seconds": self._janela,
                "scope": "processo (nao compartilhado entre instancias)",
            }

    def limpar(self):
        with self._lock:
            self._marcas.clear()
