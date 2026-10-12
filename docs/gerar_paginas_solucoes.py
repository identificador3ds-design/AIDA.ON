"""Gera as páginas explicativas das soluções (pages/solucao-*.html).

Cada página tem duas camadas: "Em poucas palavras" (para quem não é da área) e
"Transparência técnica" (como funciona, dados, números medidos, limites e
privacidade). Os números vêm das avaliações registradas no repositório do
modelo (RESULTADO_RETREINO_2026-10.md, RESULTADO_AUDIO_V2.md) — atualizar aqui
quando o modelo mudar e rodar de novo:

    python docs/gerar_paginas_solucoes.py
"""

from __future__ import annotations

from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

SOLUCOES = {
    "image": {
        "nome": "Image", "tipo": "Foto", "cor": "image",
        "resumo": "Diz se uma foto tem indícios de ter sido gerada ou alterada por inteligência artificial.",
        "simples": [
            ("O que faz", "Você envia uma foto e a AIDA responde se ela parece uma fotografia real, uma foto real editada "
                          "ou uma imagem gerada por IA — e explica o porquê em linguagem simples."),
            ("Como usar", "Envie o arquivo original, do jeito que você recebeu ou tirou. Prints de tela e imagens "
                          "reenviadas várias vezes perdem informação."),
            ("O que a resposta significa", "REAL: nenhum indício de IA. REAL EDITADA: foto real que passou por um "
                                            "editor (ex.: Lightroom). IA: indícios de geração ou manipulação. Se a "
                                            "AIDA não tiver segurança, ela pede mais uma evidência (o original ou "
                                            "outra foto da mesma cena) antes de responder."),
            ("Quando desconfiar", "Nenhum detector acerta sempre. A resposta é um indício técnico, não uma prova: "
                                  "em casos importantes, confira também a fonte da imagem."),
        ],
        "etapas": [
            ("Três leituras independentes",
             "Cada imagem é lida por três módulos que olham coisas diferentes.",
             "CLIP ViT-B/32 (OpenAI) com cabeça treinada pela equipe sobre os embeddings; módulo forense com "
             "846 características (espectro de Fourier, ruído residual, blocos JPEG, estatística de cor) em "
             "gradient boosting; RIGID (estabilidade da representação sob pequenas perturbações)."),
            ("Fusão calibrada",
             "As três notas viram uma única probabilidade, calibrada para significar o que diz.",
             "Gradient boosting monotônico sobre as notas dos módulos e a qualidade do arquivo; calibração na "
             "validação."),
            ("Decisão com margem de segurança",
             "Perto do ponto de decisão, ou quando os módulos discordam muito, a AIDA não chuta.",
             "Limiar 0,686 (escolhido para no máximo 3% de fotos reais acusadas na validação); faixa de "
             "abstenção 0,606–0,766; corte de desacordo entre módulos 0,716."),
            ("Proveniência e edição",
             "A AIDA também lê o que o próprio arquivo declara.",
             "Leitura de credenciais C2PA (ex.: imagens do ChatGPT assinadas) e de metadados de editores "
             "(Lightroom, Photoshop...) para o estado REAL EDITADA."),
        ],
        "dados": "Cerca de 55 mil imagens derivadas (treino, validação e teste separados por origem, sem "
                 "repetir a mesma cena entre conjuntos): fotos reais públicas (MS COCO, OpenFake reais, Pexels), "
                 "fotos e vídeos da equipe, e imagens de mais de 100 geradores (GPT-Image, Midjourney, Flux, "
                 "Seedream, Ideogram, Nano Banana Pro, Z-Image...). Cada imagem também entra comprimida "
                 "(JPEG, WebP, WhatsApp, print de tela) para o modelo não depender do formato.",
        "numeros": [
            ("OpenFake (conjunto público independente, 405 imagens)", "IA detectada 70%; IA dita real 8,6%; "
                                                                       "foto real acusada 1,9%; inconclusivas: "
                                                                       "21% das IA, 8% das reais"),
            ("Vídeos reais de celular (14 vídeos de regressão)", "nenhum quadro acusado de IA"),
            ("Versão anterior (até 11/10/2026), mesmo teste OpenFake", "IA dita real 12,7%; foto real acusada 4,4%"),
        ],
        "limites": [
            "Geradores lançados depois do treino podem passar despercebidos até a próxima rodada de treino.",
            "Imagens muito pequenas, muito comprimidas ou que não são fotografias (desenhos, telas) têm leitura pior; "
            "fora do escopo, a AIDA avisa.",
            "Panorâmicas de celular e fotos com filtros pesados ainda geram respostas inconclusivas com mais frequência.",
        ],
        "privacidade": "A imagem é analisada no servidor e o resultado fica em cache por até 7 dias para reabrir a "
                       "análise no AIDA Forensics. No histórico, só quem enviou vê a própria imagem (armazenamento "
                       "privado, link temporário).",
    },
    "forensics": {
        "nome": "Forensics", "tipo": "Investigação", "cor": "forensics",
        "resumo": "Mostra o material que sustentou o resultado de uma análise de imagem.",
        "simples": [
            ("O que faz", "Abre uma análise já feita e mostra, passo a passo, o que cada módulo encontrou: mapas da "
                          "imagem, notas de cada método e o que o arquivo declara sobre a própria origem."),
            ("Para quem é", "Para quem precisa justificar uma conclusão — jornalistas, professores, peritos — ou "
                            "simplesmente quer entender por que a AIDA respondeu o que respondeu."),
            ("O que você vê", "Mapas visuais (onde a imagem varia, ruído, espectro, atenção do modelo), a nota de "
                              "cada módulo e a decisão final com os motivos."),
            ("Quando desconfiar", "Os mapas ajudam a interpretar, mas não são prova por si só: uma região destacada "
                                  "não é necessariamente a região manipulada."),
        ],
        "etapas": [
            ("Mapas de evidência", "Imagens auxiliares geradas durante a análise.",
             "Gradiente, bordas, ruído residual, espectro de Fourier (magnitude e fase) e atenção do CLIP por região."),
            ("Notas por módulo", "Cada módulo mostra a própria probabilidade.",
             "CLIP, forense e RIGID, com o desacordo entre eles e a qualidade estimada do arquivo."),
            ("Proveniência", "O que o arquivo diz sobre si mesmo.",
             "C2PA (credencial de conteúdo), software de edição nos metadados, atribuição provável do gerador."),
        ],
        "dados": "Usa a mesma análise do AIDA Image — não há modelo separado.",
        "numeros": [("Reabertura", "análises ficam disponíveis por até 7 dias no servidor")],
        "limites": [
            "Depois de 7 dias a análise expira e é preciso analisar a imagem de novo.",
            "Mapas de atenção mostram onde o modelo olhou, não onde está a manipulação.",
        ],
        "privacidade": "Só abre análises pelo identificador gerado na sua sessão; nada é público.",
    },
    "video": {
        "nome": "Video", "tipo": "Vídeo", "cor": "video",
        "resumo": "Diz se um vídeo tem indícios de ter sido gerado por IA, olhando imagem, movimento e áudio.",
        "simples": [
            ("O que faz", "Separa quadros do vídeo, analisa cada um como uma foto, observa como a cena se move e "
                          "escuta a trilha de áudio. Junta tudo numa resposta só."),
            ("Como usar", "Envie o vídeo original (até 300 MB). Gravações de tela e vídeos reenviados muitas vezes "
                          "perdem detalhe."),
            ("O que a resposta significa", "REAL, IA ou INCONCLUSIVO, com os motivos: em quantos quadros houve "
                                            "indício, se o movimento é natural e o que o áudio indicou."),
            ("Quando desconfiar", "Vídeos curtos, escuros ou muito comprimidos têm leitura pior. É um indício "
                                  "técnico, não uma prova."),
        ],
        "etapas": [
            ("Quadros", "Um quadro por segundo vai para o mesmo detector de fotos.",
             "Intervalo de 1 s, até 40 quadros (máximo 120); cada quadro passa pelo AIDA Image."),
            ("Movimento", "Vídeos gerados por IA costumam ter trajetórias de cena pouco naturais.",
             "Embeddings DINOv2 (ViT-S/14) ao longo do tempo; um classificador de trajetória entra na fusão."),
            ("Áudio", "A voz também é analisada, com o AIDA Audio.",
             "Imagem com indício de IA decide IA; imagem inconclusiva deixa o áudio decidir; imagem real com áudio "
             "fortemente sintético vira IA (voz clonada sobre imagem real); áudio fraco que discorda vira "
             "inconclusivo."),
        ],
        "dados": "Os mesmos dados do AIDA Image e do AIDA Audio, mais vídeos reais de celular da equipe e vídeos "
                 "gerados por Sora, Veo, Wan, LTX e outros para o classificador de trajetória.",
        "numeros": [
            ("Vídeos reais de celular (14 vídeos de regressão)", "nenhum acusado de IA; nenhum quadro acusado"),
            ("Quadros de vídeos reais (teste com 121 vídeos)", "0% dos quadros acusados de IA"),
        ],
        "limites": [
            "Só os primeiros quadros (até 40 por padrão) são analisados em vídeos longos.",
            "Vídeos de IA que copiam movimento real (ex.: animação a partir de foto real) são mais difíceis.",
        ],
        "privacidade": "O vídeo é apagado do servidor ao fim da análise; os quadros ficam só até o resultado ser "
                       "consultado.",
    },
    "audio": {
        "nome": "Audio", "tipo": "Áudio", "cor": "audio",
        "resumo": "Diz se uma voz tem indícios de ter sido gerada ou clonada por IA.",
        "simples": [
            ("O que faz", "Você envia uma mensagem de voz ou gravação e a AIDA mede o som da voz — sem transcrever "
                          "o que é dito — para encontrar marcas de síntese."),
            ("Como usar", "Envie o arquivo original (o áudio do WhatsApp baixado direto funciona). Evite regravar "
                          "pelo alto-falante. Até 30 MB; os 2 primeiros minutos são analisados."),
            ("O que a resposta significa", "REAL ou IA, com a chance estimada. Em golpes com voz clonada, confirme "
                                            "sempre por outro canal antes de agir."),
            ("Quando desconfiar", "Áudio de ligação telefônica e áudio muito curto (menos de 1 s) ou quase todo em "
                                  "silêncio são difíceis — a AIDA avisa quando não dá para concluir."),
        ],
        "etapas": [
            ("Padronização", "O áudio vira mono, 16 kHz.",
             "Decodificação pelo FFmpeg (PyAV); trilhas de vídeo também são aceitas."),
            ("Impressão da voz", "Um modelo de fala treinado em 128 línguas transforma trechos de 6 s numa "
                                 "representação do som.",
             "XLS-R-300m (wav2vec 2.0, Meta); média e desvio das camadas 5 a 12 (2.048 números) em até 4 trechos "
             "espalhados pelo áudio."),
            ("Decisão", "Um classificador dá a probabilidade de cada trecho; a resposta é a média.",
             "Regressão logística; limiar escolhido por validação cruzada para no máximo 3% de vozes reais acusadas."),
        ],
        "dados": "Vozes reais: Multilingual LibriSpeech (português), FLEURS (português do Brasil), áudio dos vídeos "
                 "de celular da equipe e gravações do YouTube. Vozes de IA: MLAAD (16 sintetizadores em português, "
                 "como XTTS, Bark e OpenAI TTS) e um conjunto público de vozes comerciais (Polly, Kokoro, Luvvoice, "
                 "ElevenLabs, Hume, Speechify).",
        "numeros": [
            ("Vozes comerciais NUNCA vistas no treino (ElevenLabs, Hume, Speechify)", "96,8% detectadas; 3,2% ditas reais"),
            ("Áudio real de celular (vídeos fora do treino)", "98,8% corretos; 1,2% acusados"),
            ("FLEURS português (falantes fora do treino)", "100% corretos"),
            ("Versão anterior (até 11/10/2026)", "56% das vozes comerciais detectadas; 41% do áudio de celular acusado"),
        ],
        "limites": [
            "Ainda não medido em áudio de vídeos gerados por IA (Sora, Veo) nem em ligações telefônicas (8 kHz).",
            "Clonagens de voz de sistemas muito novos podem escapar até o próximo treino.",
        ],
        "privacidade": "O áudio vai para uma pasta temporária do servidor e é apagado ao fim da análise; nada é "
                       "transcrito nem guardado.",
    },
    "documents": {
        "nome": "Documents", "tipo": "PDF", "cor": "documents",
        "resumo": "Aponta indícios de que um PDF (nota, recibo, comprovante) foi editado, montado ou inventado.",
        "simples": [
            ("O que faz", "Confere os números do documento, a estrutura do arquivo e os valores, e explica cada "
                          "indício encontrado."),
            ("Como usar", "Envie o PDF original, do jeito que você recebeu. Prints e PDFs refeitos perdem os rastros."),
            ("O que a resposta significa", "IA/MANIPULADA quando há indícios fortes; REAL só quando, além de não "
                                            "haver sinais de edição, há prova de origem (assinatura digital ou "
                                            "chave de nota fiscal); senão, inconclusivo."),
            ("Quando desconfiar", "Um documento inventado do zero pode não ter sinais de edição. Em valores "
                                  "importantes, confira no portal da nota, no banco ou com o emissor."),
        ],
        "etapas": [
            ("Números de cadastro", "CNPJ, CPF e chave de acesso têm dígitos de controle que sistemas nunca erram.",
             "Módulo 11 para CNPJ (inclusive alfanumérico), CPF e chave de 44 dígitos da NF-e/NFC-e; UF, mês e "
             "modelo da chave; CNPJ do emitente embutido na chave."),
            ("Estrutura do arquivo", "Um PDF guarda rastros de como foi feito.",
             "Revisões incrementais, bytes além do /ByteRange da assinatura, páginas só com imagem, produtor do "
             "PDF, fontes duplicadas, datas de criação e modificação."),
            ("Valores", "Listas grandes de valores reais seguem um padrão no primeiro dígito.",
             "Lei de Benford com MAD de Nigrini e qui-quadrado; só entra na decisão com pelo menos 50 valores."),
            ("Conclusão", "Cada indício tem um peso.",
             "Suspeita = 1 − ∏(1 − peso). A partir de 60%: IA/manipulada. Real só abaixo de 25% e com prova de origem."),
        ],
        "dados": "Regras explícitas — não é um modelo treinado. O aprendizado de máquina com PDFs reais e "
                 "adulterados está em andamento.",
        "numeros": [("Situação", "versão inicial, ainda sem calibração com um conjunto grande de documentos")],
        "limites": [
            "Não consulta a SEFAZ nem valida a assinatura digital.",
            "PDFs que são só uma foto do documento devem ir pela análise de imagem.",
        ],
        "privacidade": "O PDF é lido na memória do servidor e descartado ao fim da análise; o texto não é guardado.",
    },
}

MODELO = """<!DOCTYPE html>
<html lang="pt-BR">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#10403b">
    <meta name="description" content="{resumo}">
    <link rel="manifest" href="../manifest.webmanifest">
    <link rel="apple-touch-icon" href="../assets/images/pwa-icon-180.png">
    <link id="favicon" rel="icon" type="image/x-icon" href="../assets/images/AIDABranco.ico">
    <title>AIDA {nome} — como funciona</title>
    <link rel="canonical" href="https://aida-on.com.br/solucoes/{chave}">
    <meta property="og:type" content="article">
    <meta property="og:site_name" content="AIDA.ON">
    <meta property="og:title" content="AIDA {nome} — como funciona">
    <meta property="og:description" content="{resumo}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Afacad:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="../styles/style-shared-theme.css">
    <link rel="stylesheet" href="../styles/aida-design-system.css">
    <link rel="stylesheet" href="../styles/style-solucao.css?v=20261011-v1">
</head>

<!-- Gerado por docs/gerar_paginas_solucoes.py: edite lá, não aqui. -->
<body class="aida-shell solucao-page solucao--{cor}">
    <a class="aida-skip-link" href="#conteudo">Pular para o conteúdo</a>
    <header class="page-header">
        <a href="./index-apresentacao.html" aria-label="Página inicial do AIDA">
            <img src="../assets/images/LogoBranca.png" alt="Logo AIDA.ON" class="brand-logo">
        </a>
        <nav class="aida-row" aria-label="Navegação da plataforma">
            <a href="./index-solucoes.html" class="top-link">Todas as soluções</a>
            <a href="./index-enviar.html" class="top-link">Analisar arquivo</a>
        </nav>
    </header>

    <main id="conteudo" class="page-frame sol-pagina">
        <section class="sol-pagina__topo">
            <span class="aida-eyebrow">{tipo}</span>
            <h1 class="aida-title-2">AIDA <span>{nome}</span></h1>
            <p class="sol-pagina__resumo">{resumo}</p>
        </section>

        <section class="sol-pagina__bloco" aria-labelledby="tituloSimples">
            <h2 class="sol-pagina__titulo" id="tituloSimples">Em poucas palavras</h2>
            <div class="sol-pagina__grade">
{simples}
            </div>
        </section>

        <section class="sol-pagina__bloco sol-pagina__tecnico" aria-labelledby="tituloTecnico">
            <h2 class="sol-pagina__titulo" id="tituloTecnico">Transparência técnica</h2>
            <p class="sol-pagina__nota">Para quem quer saber exatamente o que acontece com o arquivo — e o quanto
                confiar no resultado.</p>

            <h3 class="sol-pagina__sub">Como funciona, passo a passo</h3>
            <ol class="sol-pagina__etapas">
{etapas}
            </ol>

            <h3 class="sol-pagina__sub">Com que dados foi feito</h3>
            <p class="sol-pagina__texto">{dados}</p>

            <h3 class="sol-pagina__sub">Números medidos</h3>
            <dl class="sol-pagina__numeros">
{numeros}
            </dl>
            <p class="sol-pagina__nota">Medidos em dados que não foram usados no treino. Relatórios completos no
                repositório do projeto.</p>

            <h3 class="sol-pagina__sub">Limites conhecidos</h3>
            <ul class="sol-pagina__lista">
{limites}
            </ul>

            <h3 class="sol-pagina__sub">Privacidade</h3>
            <p class="sol-pagina__texto">{privacidade} Veja o <a href="./index-privacidade.html">Aviso de Privacidade</a>.</p>
        </section>

        <p class="sol-pagina__rodape">
            <a href="./index-solucoes.html" class="aida-btn aida-btn--ghost aida-btn--sm">&larr; Todas as soluções</a>
        </p>
    </main>

    <script src="../scripts/script-cookie-consent.js"></script>
</body>

</html>
"""


def gerar(chave, s):
    e = escape
    simples = "\n".join(
        f'                <article class="sol-pagina__cartao glass-card"><h3>{e(t)}</h3><p>{e(x)}</p></article>'
        for t, x in s["simples"])
    etapas = "\n".join(
        f'                <li><strong>{e(t)}</strong><p>{e(x)}</p><small>{e(d)}</small></li>'
        for t, x, d in s["etapas"])
    numeros = "\n".join(
        f'                <div><dt>{e(t)}</dt><dd>{e(v)}</dd></div>' for t, v in s["numeros"])
    limites = "\n".join(f"                <li>{e(x)}</li>" for x in s["limites"])
    return MODELO.format(chave=chave, nome=e(s["nome"]), tipo=e(s["tipo"]), cor=s["cor"], resumo=e(s["resumo"]),
                         simples=simples, etapas=etapas, numeros=numeros, limites=limites,
                         dados=e(s["dados"]), privacidade=e(s["privacidade"]))


def main():
    for chave, s in SOLUCOES.items():
        destino = RAIZ / "pages" / f"solucao-{chave}.html"
        destino.write_text(gerar(chave, s), encoding="utf-8")
        print("gerado", destino.name)


if __name__ == "__main__":
    main()
