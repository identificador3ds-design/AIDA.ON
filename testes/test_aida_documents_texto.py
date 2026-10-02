"""Testes da análise de texto do AIDA Documents: extração, limpeza, medidas, decisão,
calibração e rotas. O modelo de linguagem é falso (sem torch): a surpresa de cada
palavra é baixa se ela está numa lista de palavras comuns e alta se não está."""

from __future__ import annotations

import io
import random
import re
import zipfile

import pytest

from aida_documents.texto import calibrar as cal_mod
from aida_documents.texto.detector import analisar_texto_bytes, parametros, segmentar
from aida_documents.texto.estilo import burstiness, detectar_idioma, dividir_frases, mattr, medir_estilo
from aida_documents.texto.extracao import FormatoNaoSuportado, extrair
from aida_documents.texto.limpeza import limpar

COMUNS = set(
    "a o e de que em um uma para com não os as do da no na por mais como é são se ao dos das ser tem sua seu "
    "além disso importante papel fundamental sociedade tecnologia forma processo desenvolvimento pessoas "
    "nesse sentido vale destacar permite diversos aspectos contexto atual também".split()
)
RARAS = (
    "quintal goiabeira ferrugem bisavó trinco moringa capim estribo alpendre candeeiro paiol cumeeira tramela "
    "sabiá brejo cacimba roçado gamela taquara urucum jirau mourão porteira picumã borralho"
).split()


class ModeloFalso:
    nome = "falso"

    def pontuar(self, texto):
        return [(m.start(), m.end(), 1.5 if m.group().lower() in COMUNS else 6.0) for m in re.finditer(r"\w+", texto)]


def texto_ia(n_frases=40):
    frase = "Além disso, a tecnologia tem um papel fundamental no desenvolvimento da sociedade e das pessoas."
    outra = "Nesse sentido, vale destacar que o processo permite diversos aspectos no contexto atual."
    return " ".join(frase if i % 2 else outra for i in range(n_frases))


def texto_humano(n_frases=40, semente=3):
    rng = random.Random(semente)
    frases = []
    for i in range(n_frases):
        n = rng.choice([3, 5, 9, 16, 24])
        palavras = [rng.choice(RARAS) for _ in range(n)]
        # Palavras funcionais para o idioma ser reconhecido.
        frases.append(("O " if i % 2 else "A ") + " de ".join(palavras[:2]) + " " + " ".join(palavras[2:]) + " não é que" + rng.choice(".!?"))
    return " ".join(f[0].upper() + f[1:] for f in frases)


CALIBRADO = {"pt": {
    "calibrado": True, "modelo": "falso", "features": ["log_ppl", "burst_frases"],
    "centro": {"log_ppl": 3.5, "burst_frases": 0.4}, "escala": {"log_ppl": 1.0, "burst_frases": 0.2},
    "pesos": {"log_ppl": -3.0, "burst_frases": -1.0}, "vies": 0.0,
    "limiares": {"segmento": 0.7, "ia": 0.8, "humano": 0.2},
}}


def docx(paragrafos, tabela=False, cabecalho="CABECALHO SECRETO"):
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    corpo = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragrafos)
    if tabela:
        corpo += "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>celula de tabela</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f"<w:document {w}><w:body>{corpo}</w:body></w:document>")
        z.writestr("word/header1.xml", f"<w:hdr {w}><w:p><w:r><w:t>{cabecalho}</w:t></w:r></w:p></w:hdr>")
    return buf.getvalue()


# ---------------------------------------------------------------- extração


def test_extrai_txt_e_docx_sem_cabecalho_nem_tabela():
    assert extrair("Olá, mundo.".encode("utf-8"), "a.txt")["paginas"] == ["Olá, mundo."]
    assert extrair("ação".encode("latin-1"), "a.txt")["paginas"] == ["ação"]
    r = extrair(docx(["Primeiro parágrafo.", "Segundo parágrafo."], tabela=True), "a.docx")
    assert r["paginas"] == ["Primeiro parágrafo.\n\nSegundo parágrafo."]
    assert "CABECALHO" not in r["paginas"][0] and "celula" not in r["paginas"][0]
    assert any("tabela" in a for a in r["avisos"])


def test_extrai_pdf_por_pagina():
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for texto in ("Texto da primeira pagina do documento.", "Texto da segunda pagina do documento."):
        c.drawString(40, 800, texto)
        c.showPage()
    c.save()
    r = extrair(buf.getvalue(), "a.pdf")
    assert len(r["paginas"]) == 2 and "segunda" in r["paginas"][1]


@pytest.mark.parametrize("nome,dados", [("a.doc", b"x"), ("a.xlsx", b"x"), ("a.pdf", b"nao e pdf"), ("a.docx", b"nao e zip")])
def test_formato_nao_suportado(nome, dados):
    with pytest.raises(FormatoNaoSuportado):
        extrair(dados, nome)


# ---------------------------------------------------------------- limpeza


def pagina(n, corpo):
    return "\n".join(["Universidade Exemplo - Relatório 2026", *corpo, f"Página {n} de 5"])


def test_limpeza_tira_cabecalho_rodape_e_numero_de_pagina():
    def corpo(tema):
        return [
            f"Este é um parágrafo sobre {tema} que ocupa mais de uma linha no arquivo e foi que-",
            f"brado pelo PDF bem no meio de uma palavra, como costuma acontecer com {tema}.",
        ]

    temas = ["história", "geografia", "química", "biologia", "música"]
    r = limpar([pagina(n, corpo(t)) for n, t in enumerate(temas, 1)])
    texto = " ".join(p["texto"] for p in r["paragrafos"])
    assert "Universidade Exemplo" not in texto and "Página" not in texto
    assert "quebrado pelo PDF" in texto
    assert r["removidos"]["cabecalho_rodape"] == 5 and r["removidos"]["numero_pagina"] == 5
    assert [p["pagina"] for p in r["paragrafos"]] == [1, 2, 3, 4, 5]


def test_limpeza_tira_titulos_sumario_e_referencias():
    linhas = [
        "1 INTRODUÇÃO",
        "",
        "Sumário ........................ 3",
        "",
        "Este parágrafo tem palavras suficientes para contar como prosa e termina com ponto final, como deve ser.",
        "",
        "Outro parágrafo de prosa, igualmente comprido, para que as referências fiquem na segunda metade do texto.",
        "",
        "REFERÊNCIAS",
        "",
        "SILVA, J. Um título de livro bastante longo para parecer prosa de verdade. São Paulo: Editora, 2019.",
    ]
    r = limpar(["\n".join(linhas)])
    assert len(r["paragrafos"]) == 2
    assert r["removidos"]["referencias"] == 2 and r["removidos"]["nao_prosa"] == 2
    assert all("SILVA" not in p["texto"] for p in r["paragrafos"])


def test_paragrafo_continua_na_pagina_seguinte():
    a = "Este parágrafo começa numa página e a frase fica aberta no fim dela, sem ponto, porque o texto"
    b = "continua na página seguinte até finalmente terminar aqui, com ponto final e tudo."
    r = limpar([a, b])
    assert len(r["paragrafos"]) == 1 and "o texto continua" in r["paragrafos"][0]["texto"]


# ---------------------------------------------------------------- estilo


def test_frases_respeitam_abreviaturas():
    texto = "O Dr. Silva chegou às 10h. Ele citou o art. 5 da lei. Tudo certo?"
    assert [texto[a:b] for a, b in dividir_frases(texto)] == [
        "O Dr. Silva chegou às 10h.", "Ele citou o art. 5 da lei.", "Tudo certo?",
    ]


def test_idioma():
    assert detectar_idioma("O relatório mostra que os resultados não são os que a equipe esperava para o ano. " * 3) == "pt"
    assert detectar_idioma("The report shows that the results are not what the team had expected for this year. " * 3) == "en"
    assert detectar_idioma("Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore " * 3) is None
    assert detectar_idioma("curto") is None


def test_burstiness_mattr_e_marcadores():
    assert burstiness([10, 10, 10]) == 0 and burstiness([2, 10, 30]) > 0.7 and burstiness([1, 2]) is None
    assert mattr(["a"] * 100) == pytest.approx(1 / 50)
    assert mattr([str(i) for i in range(100)]) == 1.0
    ia, humano = medir_estilo(texto_ia(), "pt"), medir_estilo(texto_humano(), "pt")
    assert ia["burst_frases"] < 0.1 < humano["burst_frases"]
    assert ia["marcadores_por_mil"] > 20 and humano["marcadores_por_mil"] == 0
    assert "além disso" in ia["marcadores"]


# ---------------------------------------------------------------- detector


def test_segmentos_nao_cortam_frase_e_cobrem_o_texto():
    paragrafos = [{"texto": texto_humano(30), "pagina": 1}, {"texto": "Frase curta final.", "pagina": 2}]
    segs = segmentar(paragrafos)
    assert len(segs) > 1 and all(s["texto"][-1] in ".!?" for s in segs)
    assert sum(s["palavras"] for s in segs) == sum(len(re.findall(r"[^\W\d_]+", p["texto"])) for p in paragrafos)
    assert segs[-1]["texto"].endswith("Frase curta final.")


def test_texto_curto_e_idioma_desconhecido_sao_inconclusivos():
    r = analisar_texto_bytes("Só uma frase curta aqui.".encode(), "a.txt", modelo=ModeloFalso())
    assert r["resultado"] == "INCONCLUSIVO" and "palavras" in r["motivos"][0] and r["probabilidade_ia"] is None
    r = analisar_texto_bytes(("Lorem ipsum dolor sit amet consectetur adipiscing elit. " * 40).encode(), "a.txt", modelo=ModeloFalso())
    assert r["resultado"] == "INCONCLUSIVO" and "idioma" in r["motivos"][0]


def test_sem_calibracao_mostra_indicador_mas_nao_decide():
    r = analisar_texto_bytes(texto_ia().encode(), "a.txt", modelo=ModeloFalso(), calibracao={})
    assert r["resultado"] == "INCONCLUSIVO" and r["calibrado"] is False
    assert r["probabilidade_ia"] > 0.9 and r["segmentos"] and "calibrado" in r["motivos"][0]


def test_calibracao_de_outro_modelo_nao_vale():
    assert parametros("pt", CALIBRADO, "falso")["calibrado"] is True
    assert parametros("pt", CALIBRADO, "gpt2")["calibrado"] is False
    assert parametros("en", CALIBRADO, "falso")["calibrado"] is False


def test_decisao_calibrada_ia_humano_e_parcial():
    ia = analisar_texto_bytes(texto_ia().encode(), "a.txt", modelo=ModeloFalso(), calibracao=CALIBRADO)
    assert ia["resultado"] == "IA" and ia["fracao_suspeita"] == 1.0
    assert all(s["nivel"] == "alto" and s["texto"] for s in ia["segmentos"])
    assert ia["medidas"]["perplexidade"] < 10

    humano = analisar_texto_bytes(texto_humano(60).encode(), "a.txt", modelo=ModeloFalso(), calibracao=CALIBRADO)
    assert humano["resultado"] == "HUMANO" and humano["fracao_suspeita"] == 0.0

    misto = (texto_humano(120) + "\n\n" + texto_ia(14)).encode()
    r = analisar_texto_bytes(misto, "a.txt", modelo=ModeloFalso(), calibracao=CALIBRADO)
    assert r["resultado"] == "INCONCLUSIVO" and 0.1 < r["fracao_suspeita"] < 0.5
    assert "parcial" in r["motivos"][0]
    assert [s["nivel"] for s in r["segmentos"]][-1] == "alto" and r["segmentos"][0]["nivel"] == "baixo"


def test_sem_modelo_de_linguagem_e_inconclusivo(monkeypatch):
    monkeypatch.setattr("aida_documents.texto.detector.obter_modelo", lambda idioma: (None, "torch não instalado"))
    r = analisar_texto_bytes(texto_ia().encode(), "a.txt", calibracao=CALIBRADO)
    assert r["resultado"] == "INCONCLUSIVO" and "modelo de linguagem" in r["motivos"][0]
    assert r["medidas"]["burst_frases"] is not None and r["segmentos"] == []


def test_progresso_e_limite_de_palavras(monkeypatch):
    monkeypatch.setattr("aida_documents.texto.detector.MAX_PALAVRAS_DOCUMENTO", 300)
    passos = []
    r = analisar_texto_bytes(texto_ia(80).encode(), "a.txt", modelo=ModeloFalso(), calibracao=CALIBRADO,
                             progresso=lambda f, t: passos.append((f, t)))
    assert passos[-1][0] == passos[-1][1] == len(r["segmentos"])
    assert any("documento longo" in m for m in r["limitacoes"])


# ---------------------------------------------------------------- calibração


def docs_sinteticos(n=40, semente=0):
    rng = random.Random(semente)
    docs = []
    for i in range(n):
        for rotulo, centro in ((0, 4.2), (1, 2.8)):
            segs = [{"palavras": 120, "medidas": {
                "log_ppl": rng.gauss(centro, 0.4), "burst_ppl": rng.gauss(1.0 - 0.3 * rotulo, 0.2),
                "burst_frases": rng.gauss(0.6 - 0.2 * rotulo, 0.15), "marcadores_por_mil": None if i % 7 == 0 else rng.gauss(4 + 6 * rotulo, 3),
            }} for _ in range(5)]
            docs.append({"arquivo": f"{'ia' if rotulo else 'humano'}/{i}.txt", "rotulo": rotulo, "segmentos": segs})
    return docs


def test_divisao_e_por_documento_e_estratificada():
    partes = cal_mod.dividir(docs_sinteticos())
    nomes = [{d["arquivo"] for d in p} for p in partes.values()]
    assert not (nomes[0] & nomes[1] or nomes[0] & nomes[2] or nomes[1] & nomes[2])
    assert [len(p) for p in partes.values()] == [48, 16, 16]
    assert all(sum(d["rotulo"] for d in p) * 2 == len(p) for p in partes.values())


def test_limiares_respeitam_o_teto_de_falso_positivo():
    assert cal_mod.limiar_fpr([0.1, 0.2, 0.3, 0.9], [0.1, 0.2, 0.3, 0.9, 0.95], alvo=0.0) == 0.95
    assert cal_mod.limiar_fpr([0.1, 0.2, 0.3, 0.9], [0.1, 0.2, 0.3, 0.9, 0.95], alvo=0.25) == 0.9
    assert cal_mod.limiar_fnr([0.4, 0.8, 0.9], [0.1, 0.4, 0.8, 0.9], alvo=0.0) == 0.1
    assert cal_mod.auc([(1, 0.9), (1, 0.6), (0, 0.6), (0, 0.1)]) == pytest.approx(0.875)


def test_calibrar_aprende_o_sinal_e_gera_parametros_validos():
    cal = cal_mod.calibrar(docs_sinteticos(), "falso", fpr_alvo=0.01)
    assert cal["calibrado"] and cal["modelo"] == "falso"
    assert cal["pesos"]["log_ppl"] < 0  # perplexidade baixa aponta para IA
    assert 0 <= cal["limiares"]["humano"] <= cal["limiares"]["ia"] <= 1
    assert cal["metricas_validacao"]["falso_positivo"] <= 0.01
    assert cal["metricas_teste"]["auc"] > 0.95 and cal["metricas_teste"]["documentos"] == 16
    # Os parametros gravados sao os que o detector le.
    assert parametros("pt", {"pt": cal}, "falso") is cal


def test_coletar_le_pastas_e_usa_cache(tmp_path):
    for sub, gerador in (("humano", texto_humano), ("ia", texto_ia)):
        (tmp_path / sub).mkdir()
        (tmp_path / sub / "a.txt").write_text(gerador(), encoding="utf-8")
    (tmp_path / "humano" / "curto.txt").write_text("Curto demais.", encoding="utf-8")
    cache = tmp_path / "medidas.json"
    docs = cal_mod.coletar(tmp_path, "pt", ModeloFalso(), cache, aviso=lambda _: None)
    assert sorted(d["arquivo"] for d in docs) == ["humano/a.txt", "ia/a.txt"]

    class Proibido(ModeloFalso):
        def pontuar(self, texto):
            raise AssertionError("deveria ter vindo do cache")

    assert cal_mod.coletar(tmp_path, "pt", Proibido(), cache, aviso=lambda _: None) == docs


# ---------------------------------------------------------------- servidor


@pytest.fixture
def cliente():
    flask = pytest.importorskip("flask")
    from aida_documents.servidor import registrar

    app = flask.Flask(__name__)
    app.config.update(TEXTO_MODELO=ModeloFalso(), TEXTO_CALIBRACAO=CALIBRADO, TEXTO_SINCRONO=True)
    registrar(app)
    return app.test_client()


def test_rota_saude(cliente):
    saude = cliente.get("/documento/texto/saude").get_json()
    assert saude["modelo_de_linguagem"] is True and ".docx" in saude["extensoes"]
    assert saude["idiomas"]["pt"]["calibrado"] is True and saude["idiomas"]["en"]["calibrado"] is False
    assert cliente.get("/documento/saude").status_code == 200


def test_rota_analisar_por_tarefa(cliente):
    resposta = cliente.post("/documento/texto/analisar", data={"documento": (io.BytesIO(texto_ia().encode()), "redacao.txt")})
    assert resposta.status_code == 202
    tarefa = cliente.get(f"/documento/texto/tarefa/{resposta.get_json()['tarefa']}").get_json()
    assert tarefa["estado"] == "concluida" and tarefa["relatorio"]["resultado"] == "IA"
    assert tarefa["relatorio"]["documento"] == "redacao.txt"
    assert tarefa["progresso"]["feitos"] == tarefa["progresso"]["total"] > 0


def test_rota_erros(cliente):
    assert cliente.post("/documento/texto/analisar").status_code == 400
    assert cliente.post("/documento/texto/analisar", data={"documento": (io.BytesIO(b"x"), "a.exe")}).status_code == 400
    assert cliente.get("/documento/texto/tarefa/naoexiste").status_code == 404
    r = cliente.post("/documento/texto/analisar", data={"documento": (io.BytesIO(b"nao e pdf"), "a.pdf")})
    tarefa = cliente.get(f"/documento/texto/tarefa/{r.get_json()['tarefa']}").get_json()
    assert tarefa["estado"] == "erro" and "PDF" in tarefa["erro"]


def test_titulo_depois_de_linha_cheia_e_pagina_do_trecho():
    cheia = "Esta linha tem o comprimento típico de uma linha de parágrafo num PDF e termina com ponto."
    aberta = "Já esta outra linha fica aberta no fim da página, sem ponto, porque a frase dela só"
    paginas = ["\n".join([cheia] * 4 + [aberta]), "\n".join(["termina na página seguinte, depois de atravessar a quebra, e o parágrafo segue adiante."] + [cheia] * 6 + ["2 MÉTODO", cheia])]
    r = limpar(paginas)
    assert [p["pagina"] for p in r["paragrafos"]] == [1, 2] and r["removidos"]["nao_prosa"] == 1
    assert "frase dela só termina" in r["paragrafos"][0]["texto"]
    # O 1º parágrafo atravessa a página: o trecho que começa no meio dele já está na página 2.
    assert [s["pagina"] for s in segmentar(r["paragrafos"])] == [1, 2]
