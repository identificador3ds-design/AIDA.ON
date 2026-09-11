"""Camada 02: orquestracao — cache por conteudo e fila de execucao.

Cache por CONTEUDO, nao por nome de arquivo: a mesma foto reenviada com outro
nome e a mesma analise, e a analise e cara. A chave inclui a flag `evidence`,
porque uma resposta sem mapas nao serve para quem pediu mapas.

Cache e fila vivem no processo. Com mais de uma instancia, cada uma tem os seus
— o que custa reprocessamento, nunca resposta errada. Trocar por Redis e
substituir esta classe; nenhuma rota precisa saber.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict

from . import config


def chave_conteudo(conteudo, evidencias):
    """sha256 do arquivo + a flag que muda a forma da resposta."""
    digest = hashlib.sha256(conteudo).hexdigest()
    return f"{digest}:{'com_evidencias' if evidencias else 'sem_evidencias'}"


class CacheAnalises:
    def __init__(self, ttl_s=None, max_itens=None):
        self._ttl = ttl_s if ttl_s is not None else config.CACHE_TTL_S
        self._max = max_itens if max_itens is not None else config.CACHE_MAX_ITENS
        self._itens = OrderedDict()   # chave_conteudo -> (expira_em, id, bruto)
        self._por_id = {}             # analysis_id -> chave_conteudo
        self._lock = threading.Lock()
        self.acertos = 0
        self.faltas = 0

    def _expirar(self, agora):
        vencidas = [c for c, (expira, _, _) in self._itens.items() if expira <= agora]
        for chave in vencidas:
            self._remover(chave)

    def _remover(self, chave):
        item = self._itens.pop(chave, None)
        if item:
            self._por_id.pop(item[1], None)

    def obter(self, chave):
        agora = time.time()
        with self._lock:
            self._expirar(agora)
            item = self._itens.get(chave)
            if not item:
                self.faltas += 1
                return None
            self._itens.move_to_end(chave)
            self.acertos += 1
            return item[1], item[2]

    def obter_por_id(self, id_analise):
        with self._lock:
            chave = self._por_id.get(id_analise)
            if not chave:
                return None
            item = self._itens.get(chave)
            if not item or item[0] <= time.time():
                return None
            return item[2]

    def guardar(self, chave, id_analise, bruto):
        if self._ttl <= 0 or self._max <= 0:
            return
        with self._lock:
            self._remover(chave)
            self._itens[chave] = (time.time() + self._ttl, id_analise, bruto)
            self._por_id[id_analise] = chave
            while len(self._itens) > self._max:
                self._itens.popitem(last=False)
            self._reindexar()

    def _reindexar(self):
        self._por_id = {valor[1]: chave for chave, valor in self._itens.items()}

    def estado(self):
        with self._lock:
            return {
                "items": len(self._itens),
                "max_items": self._max,
                "ttl_seconds": self._ttl,
                "hits": self.acertos,
                "misses": self.faltas,
            }

    def limpar(self):
        with self._lock:
            self._itens.clear()
            self._por_id.clear()
            self.acertos = 0
            self.faltas = 0


class FilaCheia(RuntimeError):
    """Nao havia vaga para executar a analise dentro do tempo de espera."""


class Fila:
    """Limita quantas analises correm ao mesmo tempo.

    A analise e pesada: sem teto, N requisicoes simultaneas viram N processos
    disputando CPU e todas estouram o timeout juntas. Com teto, quem chega
    depois espera um pouco e, se nao houver vaga, leva 503 com Retry-After —
    resposta honesta e barata, em vez de um timeout caro.
    """

    def __init__(self, maximo=None, espera_s=None):
        self._maximo = max(1, maximo if maximo is not None else config.CONCORRENCIA_MAX)
        self._espera = espera_s if espera_s is not None else config.ESPERA_FILA_S
        self._semaforo = threading.BoundedSemaphore(self._maximo)
        self._lock = threading.Lock()
        self._em_execucao = 0
        self._recusadas = 0

    def __enter__(self):
        if not self._semaforo.acquire(timeout=self._espera):
            with self._lock:
                self._recusadas += 1
            raise FilaCheia(
                f"Nenhuma vaga livre apos {self._espera:.0f}s de espera."
            )
        with self._lock:
            self._em_execucao += 1
        return self

    def __exit__(self, *_):
        with self._lock:
            self._em_execucao -= 1
        self._semaforo.release()
        return False

    def estado(self):
        with self._lock:
            return {
                "running": self._em_execucao,
                "max_concurrency": self._maximo,
                "queue_wait_seconds": self._espera,
                "rejected": self._recusadas,
            }
