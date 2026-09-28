"""AIDA Video: geometria da trajetoria temporal (estilo ReStraV).

O Core olha cada frame como uma foto isolada. Este modulo olha o video como
sequencia: cada frame vira um ponto no espaco de representacao do DINOv2, e a
forma do caminho entre eles e a evidencia.

Base: Interno et al., "AI-Generated Video Detection via Perceptual
Straightening" (NeurIPS 2025, https://arxiv.org/abs/2507.00583). Videos
naturais tracam trajetorias mais "retas" no espaco do DINOv2 que videos
gerados; o artigo resume o caminho em 21 numeros (distancias entre frames
consecutivos e angulos de curvatura) e um classificador leve decide.

Diferenca deliberada em relacao ao artigo: a amostragem
------------------------------------------------------
O artigo pega 24 frames em 2 s por TEMPO. No nosso conjunto os videos IA sao
10/16/24 fps e os reais 30/60 fps; amostrar por tempo em fps diferentes gera
frames repetidos ou passos irregulares que dependem do fps — o classificador
aprenderia o fps, nao a IA. Aqui o passo e um numero INTEIRO de frames,
escolhido para chegar perto de `fps_alvo` (30 fps -> a cada 4, 24 -> 3, 16 -> 2,
10 -> 1). Nenhum frame se repete e o passo e regular. `treinar_trajetoria`
mede o que sobra do atalho (AUC do fps sozinho, e o desempenho so em 24/30 fps).
"""

from __future__ import annotations

from pathlib import Path
import threading

import numpy as np

N_FRAMES = 24
FPS_ALVO = 8.0
MAX_JANELAS = 3
MAX_SEGUNDOS = 30.0
LADO = 224
MODELO_DINO = "vit_small_patch14_dinov2.lvd142m"
ARQUIVO_MODELO = Path(__file__).resolve().parent / "modelos" / "trajetoria.joblib"

NOMES_CARACTERISTICAS = (
    [f"dist_{i}" for i in range(7)]
    + [f"curv_{i}" for i in range(6)]
    + ["dist_media", "dist_min", "dist_max", "dist_var"]
    + ["curv_media", "curv_min", "curv_max", "curv_var"]
)


def passo_de_frames(fps, fps_alvo=FPS_ALVO):
    return max(1, int(round((fps or 30.0) / fps_alvo)))


def _quadrado(rgb, lado=LADO):
    """Recorte central quadrado e reducao para lado x lado (como no artigo)."""
    import cv2

    h, w = rgb.shape[:2]
    m = min(h, w)
    y, x = (h - m) // 2, (w - m) // 2
    return cv2.resize(rgb[y:y + m, x:x + m], (lado, lado), interpolation=cv2.INTER_AREA)


def amostrar_janelas(caminho, n_frames=N_FRAMES, fps_alvo=FPS_ALVO, max_janelas=MAX_JANELAS,
                     max_segundos=MAX_SEGUNDOS):
    """Ate `max_janelas` janelas de `n_frames` frames consecutivos na grade de passo inteiro.

    Devolve (janelas, info): janelas e uma lista de arrays (n, LADO, LADO, 3) RGB uint8.
    Videos curtos rendem uma janela menor (minimo 8 frames); abaixo disso, nenhuma.
    """
    import av

    from .extrair_frames import aplicar_rotacao

    amostras = []
    with av.open(str(caminho)) as container:
        trilha = container.streams.video[0]
        trilha.thread_type = "AUTO"
        fps = float(trilha.average_rate or trilha.guessed_rate or 30.0)
        passo = passo_de_frames(fps, fps_alvo)
        limite = int(max_segundos * fps)
        for indice, quadro in enumerate(container.decode(trilha)):
            if indice >= limite:
                break
            if indice % passo:
                continue
            # Reduz ja na conversao de cor (swscale): converter 4K inteiro custa segundos.
            escala = 320 / max(1, min(quadro.width, quadro.height))
            largura = max(LADO, int(quadro.width * escala) // 2 * 2)
            altura = max(LADO, int(quadro.height * escala) // 2 * 2)
            rgb = quadro.to_ndarray(format="rgb24", width=largura, height=altura)
            amostras.append(_quadrado(aplicar_rotacao(rgb, quadro.rotation)))

    info = {"fps": round(fps, 3), "passo_frames": passo, "fps_efetivo": round(fps / passo, 3),
            "amostras": len(amostras)}
    if len(amostras) < 8:
        return [], info
    if len(amostras) < n_frames:
        return [np.stack(amostras)], info
    n_janelas = min(max_janelas, len(amostras) // n_frames)
    if n_janelas == 1:  # janela unica no meio: o inicio costuma ter fade/logo
        inicios = [(len(amostras) - n_frames) // 2]
    else:
        inicios = np.linspace(0, len(amostras) - n_frames, n_janelas).round().astype(int)
    return [np.stack(amostras[i:i + n_frames]) for i in inicios], info


class CodificadorDino:
    """DINOv2 ViT-S/14 congelado; um frame vira o vetor [CLS + patches] achatado."""

    def __init__(self, nome=MODELO_DINO, threads=None):
        import timm
        import torch

        if threads:
            torch.set_num_threads(threads)
        self._torch = torch
        self.modelo = timm.create_model(nome, pretrained=True, img_size=LADO).eval()
        cfg = self.modelo.pretrained_cfg
        self._media = torch.tensor(cfg["mean"]).view(1, 3, 1, 1)
        self._desvio = torch.tensor(cfg["std"]).view(1, 3, 1, 1)

    def codificar(self, frames_rgb):
        torch = self._torch
        x = torch.from_numpy(np.ascontiguousarray(frames_rgb)).permute(0, 3, 1, 2).float() / 255.0
        x = (x - self._media) / self._desvio
        with torch.inference_mode():
            tokens = self.modelo.forward_features(x)
        return tokens.flatten(1).numpy().astype(np.float64)


def caracteristicas_trajetoria(z):
    """21 numeros da trajetoria z (n_frames, dim): distancias e curvaturas (graus)."""
    z = np.asarray(z, dtype=np.float64)
    if len(z) < 3:
        raise ValueError("A trajetória precisa de pelo menos 3 frames.")
    delta = np.diff(z, axis=0)
    dist = np.linalg.norm(delta, axis=1)
    normas = np.maximum(dist, 1e-12)
    cos = np.sum(delta[:-1] * delta[1:], axis=1) / (normas[:-1] * normas[1:])
    curv = np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))

    def primeiros(v, k):
        return list(v[:k]) + [float(v.mean())] * max(0, k - len(v))

    def estat(v):
        return [float(v.mean()), float(v.min()), float(v.max()), float(v.var())]

    return np.array(primeiros(dist, 7) + primeiros(curv, 6) + estat(dist) + estat(curv))


def caracteristicas_video(caminho, codificador, **kw):
    """Uma linha de 21 caracteristicas por janela do video, mais o info da amostragem."""
    janelas, info = amostrar_janelas(caminho, **kw)
    linhas = [caracteristicas_trajetoria(codificador.codificar(j)) for j in janelas]
    return (np.stack(linhas) if linhas else np.empty((0, len(NOMES_CARACTERISTICAS)))), info


_CODIFICADOR = None
_TRAVA_CODIFICADOR = threading.Lock()


def _codificador():
    """O DINOv2 leva segundos para carregar: carrega uma vez por processo."""
    global _CODIFICADOR
    with _TRAVA_CODIFICADOR:
        if _CODIFICADOR is None:
            _CODIFICADOR = CodificadorDino()
        return _CODIFICADOR


def analisar_trajetoria(caminho_video, prob_core=None, caminho_modelo=None, codificador=None):
    """Probabilidade de IA pelo movimento entre frames (e, se houver, pela mediana do Core).

    Usa UMA janela de 24 frames, como no treino (`treinar_trajetoria --janelas 1`).
    Nunca levanta excecao: sem modelo, sem torch/timm ou com video curto devolve
    `disponivel: False` e o motivo, e o video segue so com os frames."""
    caminho_modelo = Path(caminho_modelo or ARQUIVO_MODELO)
    if not caminho_modelo.is_file():
        return {"disponivel": False, "motivos": ["modelo de trajetória não treinado"]}
    try:
        import joblib

        pacote = joblib.load(caminho_modelo)
        linhas, info = caracteristicas_video(caminho_video, codificador or _codificador(), max_janelas=1)
    except ImportError as exc:
        return {"disponivel": False, "motivos": [f"análise de movimento indisponível neste servidor ({exc.name} não instalado)"]}
    except Exception as exc:
        return {"disponivel": False, "motivos": [f"falha na análise de movimento: {type(exc).__name__}: {exc}"]}
    if not len(linhas):
        return {"disponivel": False, "info": info,
                "motivos": ["vídeo curto demais para a análise de movimento (mínimo de 8 frames amostrados)"]}

    usa_core = prob_core is not None and "modelo_fusao" in pacote
    if usa_core:
        X = np.hstack([linhas, np.full((len(linhas), 1), float(prob_core))])
        prob = float(pacote["modelo_fusao"].predict_proba(X)[:, 1].mean())
    else:
        prob = float(pacote["modelo"].predict_proba(linhas)[:, 1].mean())
    limiar = float(pacote.get("limiar", 0.5))
    return {
        "disponivel": True,
        "resultado": "IA/MANIPULADA" if prob >= limiar else "REAL",
        "probabilidade_ia": round(prob, 4),
        "limiar": limiar,
        "usa_core": usa_core,
        "janelas": int(len(linhas)),
        "info": info,
        "motivos": [],
    }
