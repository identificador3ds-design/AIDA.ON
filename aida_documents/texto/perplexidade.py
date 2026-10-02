"""Perplexidade: o quanto um modelo de linguagem "adivinha" cada palavra do texto.

Para cada token, o modelo da a probabilidade que atribuia a ele dado o que veio
antes. A surpresa do token e -ln(p); a media das surpresas e o log da perplexidade.
Texto gerado por LLM tende a escolher sempre continuacoes provaveis, entao a
surpresa media e baixa e varia pouco de frase para frase.

O modelo de referencia e um GPT-2 pequeno por idioma (124 M de parametros, roda em
CPU). Ele nao precisa ser o modelo que gerou o texto: o que se mede e o quanto o
texto e previsivel para UM modelo de linguagem. Trocar o modelo muda a escala dos
numeros, por isso a calibracao guarda o nome do modelo com que foi feita.

    AIDA_TEXTO_MODELO_PT   (padrao: pierreguillou/gpt2-small-portuguese)
    AIDA_TEXTO_MODELO_EN   (padrao: gpt2)
    AIDA_TEXTO_THREADS     (padrao: o do torch)

Aceitam um nome do Hugging Face Hub ou uma pasta local com o modelo ja baixado.
torch e transformers sao opcionais: sem eles `obter_modelo` devolve o motivo e o
detector responde INCONCLUSIVO em vez de inventar um numero.
"""

from __future__ import annotations

import os
import threading

MODELOS_PADRAO = {"pt": "pierreguillou/gpt2-small-portuguese", "en": "gpt2"}
MAX_TOKENS = 512
# Tokens repetidos no comeco de cada janela, so para dar contexto (nao sao recontados).
SOBREPOSICAO = 64

_cache = {}
_trava = threading.Lock()


def nome_do_modelo(idioma):
    return os.environ.get(f"AIDA_TEXTO_MODELO_{idioma.upper()}") or MODELOS_PADRAO.get(idioma)


class ModeloLinguagem:
    def __init__(self, nome):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        threads = os.environ.get("AIDA_TEXTO_THREADS")
        if threads:
            torch.set_num_threads(int(threads))
        self.nome = nome
        self._torch = torch
        self._tok = AutoTokenizer.from_pretrained(nome, use_fast=True)
        self._modelo = AutoModelForCausalLM.from_pretrained(nome)
        self._modelo.eval()
        self._inicio = self._tok.bos_token_id if self._tok.bos_token_id is not None else self._tok.eos_token_id
        # Um forward por vez: as tarefas do servidor dividem o mesmo modelo.
        self._uso = threading.Lock()

    def pontuar(self, texto):
        """Lista de (inicio, fim, surpresa em nats), um item por token de `texto`."""
        torch = self._torch
        codificado = self._tok(texto, return_offsets_mapping=True, add_special_tokens=False)
        ids, posicoes = codificado["input_ids"], codificado["offset_mapping"]
        pontos = []
        passo = MAX_TOKENS - SOBREPOSICAO
        for inicio in range(0, len(ids), passo):
            contexto = max(0, inicio - SOBREPOSICAO)
            janela = ids[contexto : inicio + passo]
            entrada = torch.tensor([[self._inicio] + janela])
            with self._uso, torch.inference_mode():
                logits = self._modelo(entrada).logits[0, :-1]
            surpresas = torch.nn.functional.cross_entropy(logits, entrada[0, 1:], reduction="none").tolist()
            for k in range(inicio - contexto, len(janela)):
                a, b = posicoes[contexto + k]
                pontos.append((a, b, surpresas[k]))
        return pontos


def obter_modelo(idioma):
    """(modelo, None) ou (None, motivo). O modelo fica em cache no processo."""
    nome = nome_do_modelo(idioma)
    if not nome:
        return None, f"não há modelo de linguagem configurado para o idioma '{idioma}'"
    with _trava:
        if nome not in _cache:
            try:
                _cache[nome] = (ModeloLinguagem(nome), None)
            except ImportError:
                _cache[nome] = (None, "torch e transformers não estão instalados neste servidor")
            except Exception as exc:  # sem rede, nome errado, memoria
                _cache[nome] = (None, f"não foi possível carregar o modelo {nome}: {type(exc).__name__}")
        return _cache[nome]


def surpresa_por_frase(pontos, frases):
    """Media das surpresas dos tokens de cada frase. `frases`: lista de (inicio, fim)."""
    medias = []
    for a, b in frases:
        valores = [s for ini, _, s in pontos if a <= ini < b]
        medias.append(sum(valores) / len(valores) if valores else None)
    return medias
