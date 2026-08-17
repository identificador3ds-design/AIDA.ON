"""Rotas do site e integridade das referências das páginas.

O AIDA.ON é estático: não há build para acusar um caminho errado. Um `href`
com typo só aparece como 404 em produção, e um destino de rewrite apontando
para um arquivo que não existe só aparece depois do deploy. Estes testes fazem
essa checagem antes.

Rodar a partir da raiz do repositório do site:

    python -m pytest testes -q
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PAGINAS = sorted((RAIZ / "pages").glob("*.html"))


@pytest.fixture(scope="module")
def vercel():
    return json.loads((RAIZ / "vercel.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# vercel.json
# --------------------------------------------------------------------------- #


def test_apenas_chaves_que_o_vercel_aceita(vercel):
    """Chave desconhecida em rewrite/redirect faz o deploy falhar na validação."""
    permitidas_rewrite = {"source", "destination", "has", "missing"}
    permitidas_redirect = permitidas_rewrite | {"permanent", "statusCode"}

    for regra in vercel["rewrites"]:
        assert set(regra) <= permitidas_rewrite, f"chave inesperada em {regra}"
    for regra in vercel.get("redirects", []):
        assert set(regra) <= permitidas_redirect, f"chave inesperada em {regra}"


def test_sem_rotas_duplicadas(vercel):
    """Duas regras para a mesma origem: a segunda nunca é alcançada.

    Foi exatamente o que acontecia com `/analise`, que aparecia duas vezes
    apontando para arquivos diferentes.
    """
    origens = [r["source"] for r in vercel["rewrites"]]
    duplicadas = {o for o in origens if origens.count(o) > 1}

    assert not duplicadas, f"origens duplicadas: {duplicadas}"


def test_destinos_existem_no_disco(vercel):
    for regra in vercel["rewrites"]:
        destino = regra["destination"].lstrip("/")
        assert (RAIZ / destino).is_file(), f"destino inexistente: {destino}"


def test_rotas_das_solucoes_existem(vercel):
    origens = {r["source"] for r in vercel["rewrites"]}

    assert {"/image", "/forensics", "/video", "/api"} <= origens


def test_urls_antigas_preservadas(vercel):
    """Elas já foram compartilhadas e indexadas; quebrá-las é custo sem ganho."""
    antigas = {
        "/admin", "/analise", "/apoiadores", "/historico", "/login",
        "/manutencao", "/perfil", "/privacidade", "/selecionar", "/validador",
    }
    origens = {r["source"] for r in vercel["rewrites"]}

    assert antigas <= origens, f"rotas perdidas: {antigas - origens}"


def test_image_aponta_para_a_selecao(vercel):
    """`index-analise.html` sem imagem escolhida abriria em estado vazio."""
    destino = next(r["destination"] for r in vercel["rewrites"] if r["source"] == "/image")

    assert destino.endswith("index-seleciona.html")


# --------------------------------------------------------------------------- #
# Referências das páginas
# --------------------------------------------------------------------------- #


PADRAO_RECURSO = re.compile(
    r'(?:href|src)\s*=\s*"(?P<caminho>\.\.?/[^"#?]+)(?:[#?][^"]*)?"'
)


@pytest.mark.parametrize("pagina", PAGINAS, ids=lambda p: p.name)
def test_recursos_locais_existem(pagina):
    """Todo `../styles/...`, `./index-...` e `../scripts/...` precisa existir."""
    html = pagina.read_text(encoding="utf-8", errors="ignore")
    faltando = []

    for achado in PADRAO_RECURSO.finditer(html):
        alvo = (pagina.parent / achado.group("caminho")).resolve()
        if not alvo.exists():
            faltando.append(achado.group("caminho"))

    assert not faltando, f"{pagina.name} referencia arquivos inexistentes: {faltando}"


@pytest.mark.parametrize(
    "pagina,esperado",
    [
        ("index-solucoes.html", ["aida-design-system.css", "aida-solucoes.css",
                                 "aida-solucoes.js"]),
        ("index-forensics.html", ["aida-design-system.css", "style-forensics.css",
                                  "script-forensics.js"]),
        ("index-video.html", ["aida-design-system.css", "aida-produto.css"]),
        ("index-api.html", ["aida-design-system.css", "aida-produto.css"]),
    ],
)
def test_paginas_carregam_o_design_system(pagina, esperado):
    html = (RAIZ / "pages" / pagina).read_text(encoding="utf-8")

    for recurso in esperado:
        assert recurso in html, f"{pagina} não carrega {recurso}"


# --------------------------------------------------------------------------- #
# Seção de soluções
# --------------------------------------------------------------------------- #


def test_pagina_de_solucoes_declara_os_quatro_cards():
    html = (RAIZ / "pages" / "index-solucoes.html").read_text(encoding="utf-8")

    for produto in ("image", "forensics", "video", "api"):
        assert f'data-sol="{produto}"' in html, f"card ausente: {produto}"


def test_estados_dos_produtos_refletem_a_realidade():
    """O selo é declaração de estado, não enfeite.

    Video e API não têm implementação; anunciá-los como disponíveis levaria o
    visitante a tentar usar o que não existe.
    """
    html = (RAIZ / "pages" / "index-solucoes.html").read_text(encoding="utf-8")
    cards = html.split('data-sol="')

    estados = {}
    for trecho in cards[1:]:
        produto = trecho.split('"')[0]
        marca = re.search(r"aida-status aida-status--(\w+)", trecho)
        estados[produto] = marca.group(1) if marca else None

    assert estados["image"] == "disponivel"
    assert estados["forensics"] == "beta"
    assert estados["video"] == "desenvolvimento"
    assert estados["api"] == "desenvolvimento"


def test_cards_em_desenvolvimento_nao_oferecem_envio():
    """O card do Video não pode dar a impressão de que já aceita upload."""
    html = (RAIZ / "pages" / "index-solucoes.html").read_text(encoding="utf-8")
    bloco_video = html.split('data-sol="video"')[1].split("</article>")[0]

    for termo in ("Enviar vídeo", "Enviar video", "Analisar vídeo", "Analisar video"):
        assert termo not in bloco_video


def test_cards_nao_exibem_porcentagem_de_resultado():
    """Um "98% IA" decorativo seria lido como demonstração real do detector."""
    html = (RAIZ / "pages" / "index-solucoes.html").read_text(encoding="utf-8")
    secao = html.split('data-solucoes')[1].split("</section>")[0]

    assert not re.search(r"\d{1,3}\s?%", secao), "há porcentagem na seção de soluções"


def test_paginas_de_produto_marcam_em_desenvolvimento():
    for nome in ("index-video.html", "index-api.html"):
        html = (RAIZ / "pages" / nome).read_text(encoding="utf-8")
        assert "aida-status--desenvolvimento" in html
        assert "Em desenvolvimento" in html


def test_pagina_da_api_nao_expoe_credencial():
    """O exemplo é conceitual: nenhum token, chave ou host real."""
    html = (RAIZ / "pages" / "index-api.html").read_text(encoding="utf-8")

    assert "sua-chave" in html, "o exemplo deveria usar um marcador explícito"
    assert not re.search(r"Bearer\s+[A-Za-z0-9_\-]{20,}", html)
    assert not re.search(r"eyJ[A-Za-z0-9_\-]{20,}", html), "parece um JWT real"


def test_roadmaps_nao_prometem_datas():
    """Roadmap com prazo inventado envelhece em uma semana e passa a mentir."""
    meses = r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"

    for nome in ("index-video.html", "index-api.html"):
        html = (RAIZ / "pages" / nome).read_text(encoding="utf-8")
        roadmap = html.split('id="roadmap"')[1]

        assert not re.search(meses, roadmap, re.IGNORECASE)
        assert not re.search(r"\b20[2-9]\d\b", roadmap)
        assert not re.search(r"\bQ[1-4]\b", roadmap)


# --------------------------------------------------------------------------- #
# Integração Image → Forensics e Histórico → Forensics
#
# São verificações estruturais sobre o JavaScript: o site não tem build nem
# runner de testes de front-end, e estas três propriedades são justamente as
# que quebram em silêncio numa refatoração — o botão some, o campo deixa de ser
# gravado, ou o histórico passa a oferecer um link que nunca abre.
# --------------------------------------------------------------------------- #


def test_resultado_do_image_oferece_a_passagem_para_o_forensics():
    html = (RAIZ / "pages" / "index-analise.html").read_text(encoding="utf-8")
    js = (RAIZ / "scripts" / "script-analise.js").read_text(encoding="utf-8")

    assert 'id="blocoForense"' in html
    assert "Ver análise forense" in html
    assert "index-forensics.html" in html
    assert "prepararPassagemForense" in js


def test_passagem_forense_exige_identificador():
    """Sem `id_analise` o botão fica escondido: um link que sempre falha é pior."""
    js = (RAIZ / "scripts" / "script-analise.js").read_text(encoding="utf-8")
    trecho = js.split("function prepararPassagemForense")[1].split("\nfunction ")[0]

    assert "if (!idAnalise)" in trecho
    assert "bloco.hidden = true" in trecho


def test_image_nao_embute_a_interface_do_forensics():
    """A tela de resultado é a da resposta rápida; a investigação é outra página."""
    html = (RAIZ / "pages" / "index-analise.html").read_text(encoding="utf-8")

    for marca in ("fo-grade", "fo-bloco", "fo-mapas"):
        assert marca not in html, f"a tela do Image embutiu {marca}"


def test_historico_persiste_o_identificador_da_analise():
    js = (RAIZ / "scripts" / "script-analise.js").read_text(encoding="utf-8")

    assert "analysis_id" in js and "api_base" in js
    assert (RAIZ / "docs" / "migracao-forensics.sql").is_file()


def test_historico_so_oferece_forensics_quando_pode_abrir():
    js = (RAIZ / "scripts" / "script-historico.js").read_text(encoding="utf-8")
    trecho = js.split("function linkForense")[1].split("\n    }")[0]

    assert "if (!idAnalise) return" in trecho
    assert "index-forensics.html" in trecho


def test_exclusao_do_historico_derruba_o_cache_forense():
    """Apagar a linha e deixar o dossiê acessível por link direto seria vazamento."""
    js = (RAIZ / "scripts" / "script-historico.js").read_text(encoding="utf-8")

    assert "removerCacheForense" in js
    assert 'method: "DELETE"' in js


def test_forensics_nao_recalcula_analise():
    """A página consome o dossiê pronto; ela não chama /analisar."""
    js = (RAIZ / "scripts" / "script-forensics.js").read_text(encoding="utf-8")

    assert "/forense/" in js
    assert "/analisar" not in js


def test_cards_respeitam_movimento_reduzido():
    css = (RAIZ / "styles" / "aida-solucoes.css").read_text(encoding="utf-8")
    js = (RAIZ / "scripts" / "aida-solucoes.js").read_text(encoding="utf-8")

    assert "prefers-reduced-motion" in css
    assert "prefers-reduced-motion" in js
    # Sem GSAP ou com movimento reduzido, o CSS assume o estado de repouso.
    assert "is-static" in css and "is-static" in js


def test_animacoes_dos_cards_pausam_fora_da_viewport():
    js = (RAIZ / "scripts" / "aida-solucoes.js").read_text(encoding="utf-8")

    assert "IntersectionObserver" in js
    assert "visibilitychange" in js


# --------------------------------------------------------------------------- #
# A Home leva às soluções, mas não hospeda os cards
# --------------------------------------------------------------------------- #


def test_home_nao_hospeda_os_cards():
    """Os cards vivem em `index-solucoes.html`, não na página de apresentação."""
    html = (RAIZ / "pages" / "index-apresentacao.html").read_text(encoding="utf-8")

    assert "data-solucoes" not in html
    assert "data-sol=" not in html
    assert "aida-solucoes.js" not in html


def test_home_tem_botao_para_as_solucoes():
    html = (RAIZ / "pages" / "index-apresentacao.html").read_text(encoding="utf-8")
    bloco = html.split('class="btn-group-ferr"')[1].split("</div>")[0]

    assert "index-solucoes.html" in bloco, "o botão não está na seção da ferramenta"


def test_site_nao_tem_mais_parallax():
    """O parallax foi removido do site inteiro.

    Ele media o elemento com `getBoundingClientRect()` depois de já ter escrito
    um `transform` nele: cada rolagem realimentava a anterior e o deslocamento
    crescia sozinho. De quebra, reescrevia por cima do que o GSAP escrevia nos
    mesmos elementos, o que apagava os logos de tecnologia.
    """
    js = (RAIZ / "scripts" / "script-apresentacao.js").read_text(encoding="utf-8")
    # Os comentários que explicam a remoção citam os nomes de propósito; a
    # verificação olha só o código executável.
    codigo = "\n".join(
        linha for linha in js.splitlines() if not linha.lstrip().startswith("//")
    )

    assert "function setupParallax" not in codigo
    assert "setupParallax()" not in codigo
    assert "parallax-item" not in codigo

    for pagina in PAGINAS:
        html = pagina.read_text(encoding="utf-8", errors="ignore")
        assert "data-parallax-speed" not in html, f"{pagina.name} ainda tem parallax"
        assert "parallax-item" not in html, f"{pagina.name} ainda tem parallax"


def test_efeito_de_rolagem_da_equipe_preservado():
    """O que o parallax não fazia, e por isso não saiu junto."""
    js = (RAIZ / "scripts" / "script-apresentacao.js").read_text(encoding="utf-8")

    assert "setupTeamRotation()" in js
    assert "teamTrigger = ScrollTrigger.create(" in js


def test_logos_de_tecnologia_ficam_sob_o_css():
    """Regressão dos nove logos de tecnologia.

    `setupIconLoop` destaca ícones pela classe `.active`, que depende de
    `opacity` e `transform`. Estilo inline vence classe: qualquer tween do GSAP
    sobre `.icon-wrapper` rouba as duas propriedades — o destaque do laço some
    e, se o tween não chegar ao fim, os logos ficam presos em `opacity: 0`.

    A entrada da seção é animada no contêiner `.icons-grid`, que não tem classe
    de estado. Os filhos ficam inteiramente sob o CSS.
    """
    css = (RAIZ / "styles" / "style-apresentacao.css").read_text(encoding="utf-8")
    js = (RAIZ / "scripts" / "script-apresentacao.js").read_text(encoding="utf-8")

    # A premissa: o destaque do laço depende dessas duas propriedades.
    regra_ativa = css.split(".icon-wrapper.active {")[1].split("}")[0]
    assert "opacity" in regra_ativa and "transform" in regra_ativa

    # E o laço existe.
    assert "function setupIconLoop" in js
    assert 'classList.add("active")' in js

    # O GSAP não pode ter `.icon-wrapper` como alvo. O seletor em si continua
    # legítimo: é assim que `setupIconLoop` encontra os ícones.
    codigo = "\n".join(
        linha for linha in js.splitlines() if not linha.lstrip().startswith("//")
    )
    proibidos = (
        'animateGroup(".icon-wrapper"',
        'gsap.utils.toArray(".icon-wrapper")',
        'gsap.from(".icon-wrapper"',
        'gsap.to(".icon-wrapper"',
        'gsap.set(".icon-wrapper"',
        'gsap.fromTo(".icon-wrapper"',
    )
    for alvo in proibidos:
        assert alvo not in codigo, f"{alvo} rouba opacity/transform do laço de destaque"

    # A seção continua entrando com animação, pelo contêiner.
    assert 'animateGroup(".icons-grid"' in codigo


# --------------------------------------------------------------------------- #
# Microdemonstrações dos cards
#
# Os palcos deixaram de ser ilustrações abstratas e passaram a mostrar mídia
# real: uma fotografia do acervo sendo varrida, as saídas forenses de verdade
# do pipeline sobre essa MESMA fotografia, e frames numa linha do tempo.
# --------------------------------------------------------------------------- #


DEMOS = RAIZ / "assets" / "demos"


def test_assets_de_demonstracao_existem():
    esperados = [
        DEMOS / "image" / "demo.webp",
        DEMOS / "forensics" / "demo_fft.webp",
        DEMOS / "forensics" / "demo_gradient.webp",
        DEMOS / "forensics" / "demo_noise.webp",
    ] + [DEMOS / "video" / f"frame_{i:02d}.webp" for i in range(1, 7)]

    faltando = [p.name for p in esperados if not p.is_file()]
    assert not faltando, f"assets ausentes: {faltando} (rode gerar_assets_demo.py)"


def test_assets_tem_procedencia_registrada():
    """Sem isto, em um mês ninguém sabe de onde os arquivos vieram."""
    procedencia = DEMOS / "PROCEDENCIA.md"
    assert procedencia.is_file()

    texto = procedencia.read_text(encoding="utf-8")
    # O ponto mais fácil de esquecer: os frames NÃO são de um vídeo.
    assert "não são frames de um vídeo" in texto.lower()
    assert "mapa_gradiente" in texto and "mapa_ruido" in texto


def test_demonstracoes_nao_pesam_demais():
    """Microdemonstração não pode transformar a página numa página pesada."""
    total = sum(p.stat().st_size for p in DEMOS.rglob("*.webp"))
    assert total < 600 * 1024, f"assets somam {total / 1024:.0f} kB"


def test_image_e_forensics_usam_a_mesma_fotografia():
    """A continuidade narrativa é o ponto: Image analisa, Forensics investiga."""
    html = (RAIZ / "pages" / "index-solucoes.html").read_text(encoding="utf-8")

    bloco_image = html.split('data-sol="image"')[1].split("</article>")[0]
    bloco_forensics = html.split('data-sol="forensics"')[1].split("</article>")[0]

    assert "demos/image/demo.webp" in bloco_image
    assert "demos/image/demo.webp" in bloco_forensics


def test_forensics_compara_contra_os_tres_metodos_reais():
    html = (RAIZ / "pages" / "index-solucoes.html").read_text(encoding="utf-8")
    bloco = html.split('data-sol="forensics"')[1].split("</article>")[0]

    for arquivo in ("demo_fft.webp", "demo_gradient.webp", "demo_noise.webp"):
        assert arquivo in bloco, f"falta a camada {arquivo}"
    for metodo in ("FFT", "Gradiente", "Ruído"):
        assert f'data-metodo="{metodo}"' in bloco


def test_video_usa_frames_reais():
    html = (RAIZ / "pages" / "index-solucoes.html").read_text(encoding="utf-8")
    bloco = html.split('data-sol="video"')[1].split("</article>")[0]

    for i in range(1, 7):
        assert f"frame_{i:02d}.webp" in bloco


def test_midias_dos_cards_sao_lazy_e_tem_dimensao():
    """`loading=lazy` para não pesar na primeira pintura; `width`/`height` para
    o navegador reservar o espaço e a página não saltar ao carregar."""
    html = (RAIZ / "pages" / "index-solucoes.html").read_text(encoding="utf-8")

    for tag in re.findall(r"<img[^>]*demos/[^>]*>", html):
        assert 'loading="lazy"' in tag, f"sem lazy: {tag[:70]}"
        assert "width=" in tag and "height=" in tag, f"sem dimensão: {tag[:70]}"


def test_card_da_api_nao_inventa_valores():
    """Os campos da resposta existem; os valores aparecem elididos."""
    html = (RAIZ / "pages" / "index-solucoes.html").read_text(encoding="utf-8")
    bloco = html.split('data-sol="api"')[1].split("</article>")[0]

    assert '"ai_probability"' in bloco and '"confidence"' in bloco
    # Nenhum número decimal fazendo as vezes de resultado.
    assert not re.search(r"\d+\.\d+", bloco), "há valor numérico no corpo da resposta"
    assert bloco.count("…") >= 3, "os valores deveriam estar elididos"


def test_nada_de_processamento_forense_no_navegador():
    """FFT e afins são pré-gerados. O navegador só exibe os arquivos."""
    js = (RAIZ / "scripts" / "aida-solucoes.js").read_text(encoding="utf-8")

    for proibido in ("getImageData", "createImageBitmap", "OffscreenCanvas", "getContext("):
        assert proibido not in js, f"{proibido} indica processamento de imagem no cliente"


def test_hover_de_cada_card_reforca_a_propria_funcao():
    """O comportamento comum fica na casca; a animação interna é específica.

    Um `entrar()` idêntico nos quatro cards significaria que o hover não diz
    nada sobre qual produto está sob o cursor.
    """
    js = (RAIZ / "scripts" / "aida-solucoes.js").read_text(encoding="utf-8")

    blocos = {
        "image": js.split("function montarImage")[1].split("function montarForensics")[0],
        "forensics": js.split("function montarForensics")[1].split("function montarVideo")[0],
        "video": js.split("function montarVideo")[1].split("function montarApi")[0],
        "api": js.split("function montarApi")[1].split("var CONSTRUTORES")[0],
    }

    # Cada palco reage no seu próprio vocabulário.
    assert "fx-img__band" in blocos["image"] and "fx-img__canto" in blocos["image"]
    assert "--split" in blocos["forensics"]
    assert "fx-vid__playhead" in blocos["video"] and "fx-vid__frame" in blocos["video"]
    assert "fx-api__pulse" in blocos["api"] and "fx-api__endpoint" in blocos["api"]

    # Os três palcos com resposta ao cursor a declaram; a API não precisa.
    for nome in ("image", "forensics", "video"):
        assert "mover:" in blocos[nome], f"{nome} não responde ao cursor"


def test_cards_continuam_pausando_fora_da_viewport():
    js = (RAIZ / "scripts" / "aida-solucoes.js").read_text(encoding="utf-8")

    assert "IntersectionObserver" in js
    assert "visibilitychange" in js
    assert "prefers-reduced-motion" in js
    assert "is-static" in js
