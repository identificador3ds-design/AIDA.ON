"""Testes da AIDA API (/v1).

Nenhum teste toca a rede: o AIDA Core e substituido por um duble. O que se
verifica aqui e o comportamento da BORDA — contrato, autenticacao, cota, cache,
validacao e traducao de erro —, nunca a qualidade da deteccao, que e do Core.

Rodar a partir da raiz do repositorio:

    python -m pytest testes -q
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from aida_api import app as modulo_app  # noqa: E402
from aida_api import cache as cache_mod  # noqa: E402
from aida_api import chaves_api, config, core, limites  # noqa: E402
from aida_api.contrato import mapear_analise  # noqa: E402

CHAVE = "aida_chave_de_teste"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 128

RESPOSTA_CORE = {
    "id_analise": "abc123",
    "resultado": "INCONCLUSIVO",
    "inconclusivo": True,
    "fora_de_dominio": False,
    "confianca": "baixa",
    "probabilidade_ia": 0.31,
    "probabilidade_ia_exibicao": 0.52,
    "probabilidade_real_exibicao": 0.48,
    "probabilidade_ia_conteudo": 0.29,
    "limiar": 0.28,
    "limiar_exibicao": 0.5,
    "banda_inconclusiva": [0.24, 0.33],
    "motivos": ["desacordo entre modulos"],
    "scores_modulos": {"clip": 0.4, "forense": 0.6},
    "qualidade": {"qualidade_score": 0.8},
    "limitacoes": ["imagem recomprimida"],
    "evidencias": {"urls": {"mapa_calor": "/evidencia/abc123/mapa_calor"}, "patches_suspeitos": []},
    "proveniencia": {"status": "NO_PROVENANCE_FOUND"},
    "ressalva": "Indicio tecnico, nao prova.",
    "titulo": "Resultado indeterminado",
    "explicacao": "texto pronto",
    "versao_modelo": "AIDA-2.0",
    "duracao_s": 3.2,
}


@pytest.fixture
def cliente(monkeypatch):
    """App com Core dublado, chave de desenvolvimento e estado limpo."""
    monkeypatch.setattr(config, "CHAVES_DEV", [CHAVE])
    monkeypatch.setattr(config, "SUPABASE_URL", "")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "")
    chaves_api.limpar_cache()

    modulo_app.analises.limpar()
    modulo_app.limitador = limites.LimitadorEmMemoria(limite_padrao=100, janela_s=60)

    chamadas = []

    def core_falso(conteudo, nome, evidencias=True, timeout=None):
        chamadas.append({"bytes": len(conteudo), "nome": nome, "evidencias": evidencias})
        return dict(RESPOSTA_CORE), 3.2

    monkeypatch.setattr(core, "analisar", core_falso)
    monkeypatch.setattr(modulo_app.core, "analisar", core_falso)

    cliente = modulo_app.app.test_client()
    cliente.chamadas_ao_core = chamadas
    return cliente


def enviar(cliente, conteudo=PNG, nome="foto.png", chave=CHAVE, **campos):
    dados = {"image": (io.BytesIO(conteudo), nome), **campos}
    cabecalhos = {"Authorization": f"Bearer {chave}"} if chave else {}
    return cliente.post(
        "/v1/analyze/image", data=dados, headers=cabecalhos, content_type="multipart/form-data"
    )


# --------------------------------------------------------------------------- #
# Contrato
# --------------------------------------------------------------------------- #
def test_os_tres_estados_sobrevivem_a_traducao():
    for estado in ("REAL", "IA/MANIPULADA", "INCONCLUSIVO"):
        corpo = mapear_analise({**RESPOSTA_CORE, "resultado": estado})
        assert corpo["result"] == estado


def test_resultado_desconhecido_vira_inconclusivo_e_nao_um_dos_lados():
    # Se o Core mudar de vocabulario, a borda se abstem. Escolher REAL ou
    # IA seria a borda decidindo — exatamente o que ela nao faz.
    corpo = mapear_analise({**RESPOSTA_CORE, "resultado": "SEI_LA"})
    assert corpo["result"] == "INCONCLUSIVO"


def test_ressalva_sempre_presente_mesmo_se_o_core_omitir():
    bruto = {k: v for k, v in RESPOSTA_CORE.items() if k != "ressalva"}
    corpo = mapear_analise(bruto)
    assert corpo["disclaimer"]


def test_probabilidade_exibida_e_a_de_exibicao_nao_a_calibrada():
    corpo = mapear_analise(RESPOSTA_CORE)
    assert corpo["ai_probability"] == 0.52
    assert corpo["calibration"]["ai_probability_calibrated"] == 0.31


def test_urls_de_evidencia_apontam_para_a_borda():
    corpo = mapear_analise(RESPOSTA_CORE, prefixo_evidencia="/v1/evidence")
    assert corpo["evidence"]["maps"]["mapa_calor"] == "/v1/evidence/abc123/mapa_calor"


def test_contrato_e_docs_sao_publicos(cliente):
    assert cliente.get("/v1/contract").status_code == 200
    resposta = cliente.get("/v1/docs")
    assert resposta.status_code == 200
    assert b"AIDA API" in resposta.data


def test_docs_refletem_o_contrato(cliente):
    """A pagina e gerada do contrato: um campo dele aparece nela."""
    corpo = cliente.get("/v1/docs").data.decode("utf-8")
    assert "out_of_domain" in corpo


# --------------------------------------------------------------------------- #
# Autenticacao
# --------------------------------------------------------------------------- #
def test_sem_cabecalho_401(cliente):
    resposta = enviar(cliente, chave=None)
    assert resposta.status_code == 401
    assert resposta.get_json()["error"]["code"] == "missing_credentials"


def test_chave_invalida_401(cliente):
    resposta = enviar(cliente, chave="aida_nao_existe")
    assert resposta.status_code == 401
    assert resposta.get_json()["error"]["code"] == "invalid_key"


def test_sem_autenticacao_configurada_responde_503_e_nao_libera(cliente, monkeypatch):
    # Servidor mal configurado nao pode virar porta aberta; e tambem nao pode
    # dizer "chave invalida", que manda o integrador procurar defeito no lugar errado.
    monkeypatch.setattr(config, "CHAVES_DEV", [])
    resposta = enviar(cliente)
    assert resposta.status_code == 503
    assert resposta.get_json()["error"]["code"] == "auth_unavailable"


# --------------------------------------------------------------------------- #
# Analise
# --------------------------------------------------------------------------- #
def test_analise_devolve_o_contrato_completo(cliente):
    resposta = enviar(cliente)
    assert resposta.status_code == 200
    corpo = resposta.get_json()
    for campo in (
        "analysis_id", "result", "confidence", "ai_probability", "module_scores",
        "quality", "limitations", "evidence", "disclaimer", "api_version",
    ):
        assert campo in corpo
    assert corpo["result"] == "INCONCLUSIVO"
    assert corpo["timing"]["total_seconds"] is not None


def test_nome_do_arquivo_nao_vaza_para_o_core(cliente):
    enviar(cliente, nome="cpf-do-joao.png")
    assert "cpf" not in cliente.chamadas_ao_core[0]["nome"]


def test_evidence_false_chega_ao_core(cliente):
    enviar(cliente, evidence="false")
    assert cliente.chamadas_ao_core[0]["evidencias"] is False


def test_evidence_invalido_400(cliente):
    resposta = enviar(cliente, evidence="talvez")
    assert resposta.status_code == 400
    assert resposta.get_json()["error"]["code"] == "invalid_field"


def test_sem_arquivo_400(cliente):
    resposta = cliente.post(
        "/v1/analyze/image",
        data={},
        headers={"Authorization": f"Bearer {CHAVE}"},
        content_type="multipart/form-data",
    )
    assert resposta.status_code == 400
    assert resposta.get_json()["error"]["code"] == "missing_image"


def test_extensao_recusada_na_borda_sem_gastar_o_core(cliente):
    resposta = enviar(cliente, nome="documento.pdf")
    assert resposta.status_code == 400
    assert resposta.get_json()["error"]["code"] == "unsupported_format"
    assert cliente.chamadas_ao_core == []


def test_arquivo_que_nao_e_imagem_recusado_na_borda(cliente):
    resposta = enviar(cliente, conteudo=b"isto nao e uma imagem, e so texto")
    assert resposta.status_code == 400
    assert resposta.get_json()["error"]["code"] == "invalid_image"
    assert cliente.chamadas_ao_core == []


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #
def test_mesmo_conteudo_com_outro_nome_reaproveita_a_analise(cliente):
    primeira = enviar(cliente, nome="a.png")
    segunda = enviar(cliente, nome="b.png")
    assert primeira.headers["X-AIDA-Cache"] == "miss"
    assert segunda.headers["X-AIDA-Cache"] == "hit"
    assert len(cliente.chamadas_ao_core) == 1
    assert segunda.get_json()["analysis_id"] == primeira.get_json()["analysis_id"]


def test_cache_separa_com_e_sem_evidencias(cliente):
    enviar(cliente, evidence="true")
    enviar(cliente, evidence="false")
    # Uma resposta sem mapas nao serve para quem pediu mapas: sao entradas distintas.
    assert len(cliente.chamadas_ao_core) == 2


def test_recuperar_analise_pelo_id(cliente):
    id_analise = enviar(cliente).get_json()["analysis_id"]
    resposta = cliente.get(
        f"/v1/analysis/{id_analise}", headers={"Authorization": f"Bearer {CHAVE}"}
    )
    assert resposta.status_code == 200
    assert resposta.get_json()["analysis_id"] == id_analise


def test_analise_fora_do_cache_404_em_vez_de_recalcular(cliente):
    resposta = cliente.get(
        "/v1/analysis/nao-existe", headers={"Authorization": f"Bearer {CHAVE}"}
    )
    assert resposta.status_code == 404
    assert cliente.chamadas_ao_core == []


# --------------------------------------------------------------------------- #
# Cota
# --------------------------------------------------------------------------- #
def test_cota_esgotada_responde_429_com_retry_after(cliente, monkeypatch):
    # A cota da chave manda: o limite do registro tem precedencia sobre o
    # padrao do limitador — e o que permite dar mais folga a um integrador
    # sem afrouxar o teto de todos.
    monkeypatch.setattr(config, "LIMITE_PADRAO", 2)
    monkeypatch.setattr(
        modulo_app, "limitador", limites.LimitadorEmMemoria(limite_padrao=2, janela_s=60)
    )
    assert enviar(cliente, conteudo=PNG + b"1").status_code == 200
    assert enviar(cliente, conteudo=PNG + b"2").status_code == 200
    terceira = enviar(cliente, conteudo=PNG + b"3")
    assert terceira.status_code == 429
    assert terceira.get_json()["error"]["code"] == "rate_limited"
    assert int(terceira.headers["Retry-After"]) > 0


def test_resposta_bem_sucedida_informa_a_cota(cliente, monkeypatch):
    monkeypatch.setattr(config, "LIMITE_PADRAO", 5)
    monkeypatch.setattr(
        modulo_app, "limitador", limites.LimitadorEmMemoria(limite_padrao=5, janela_s=60)
    )
    resposta = enviar(cliente)
    assert resposta.headers["X-RateLimit-Limit"] == "5"
    assert resposta.headers["X-RateLimit-Remaining"] == "4"


def test_janela_deslizante_libera_conforme_o_tempo_passa():
    limitador = limites.LimitadorEmMemoria(limite_padrao=1, janela_s=0.2)
    assert limitador.consumir("k").permitido
    assert not limitador.consumir("k").permitido
    import time as _t

    _t.sleep(0.25)
    assert limitador.consumir("k").permitido


def test_cota_e_por_chave():
    limitador = limites.LimitadorEmMemoria(limite_padrao=1, janela_s=60)
    assert limitador.consumir("chave-a").permitido
    assert limitador.consumir("chave-b").permitido


# --------------------------------------------------------------------------- #
# Falhas do Core
# --------------------------------------------------------------------------- #
def test_core_fora_do_ar_vira_503_e_nao_500(cliente, monkeypatch):
    def indisponivel(*_a, **_k):
        raise core.CoreIndisponivel("timeout")

    monkeypatch.setattr(modulo_app.core, "analisar", indisponivel)
    resposta = enviar(cliente)
    assert resposta.status_code == 503
    assert resposta.get_json()["error"]["code"] == "core_unavailable"
    assert resposta.headers["Retry-After"]


def test_400_do_core_continua_400_para_quem_chamou(cliente, monkeypatch):
    def recusa(*_a, **_k):
        raise core.CoreErro(400, {"erro": "imagem invalida"})

    monkeypatch.setattr(modulo_app.core, "analisar", recusa)
    resposta = enviar(cliente)
    # Erro da requisicao nao pode virar 500: isso manda o integrador depurar o
    # servidor quando o problema esta no que ele enviou.
    assert resposta.status_code == 400
    assert resposta.get_json()["error"]["code"] == "invalid_image"


def test_erro_do_core_nao_expoe_detalhe_interno(cliente, monkeypatch):
    def explode(*_a, **_k):
        raise core.CoreErro(500, {"traceback": "linha 42 de app.py", "erro": "boom"})

    monkeypatch.setattr(modulo_app.core, "analisar", explode)
    corpo = enviar(cliente).get_data(as_text=True)
    assert "traceback" not in corpo and "linha 42" not in corpo


def test_fila_cheia_responde_503_sem_iniciar_a_analise(cliente, monkeypatch):
    class FilaSemVaga:
        def __enter__(self):
            raise cache_mod.FilaCheia("sem vaga")

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(modulo_app, "fila", FilaSemVaga())
    resposta = enviar(cliente)
    assert resposta.status_code == 503
    assert resposta.get_json()["error"]["code"] == "busy"


# --------------------------------------------------------------------------- #
# Monitoramento
# --------------------------------------------------------------------------- #
def test_health_acusa_core_inalcancavel(cliente, monkeypatch):
    monkeypatch.setattr(
        modulo_app.core, "saude", lambda *_a, **_k: {"reachable": False, "status": "unreachable"}
    )
    resposta = cliente.get("/v1/health")
    assert resposta.status_code == 503
    assert resposta.get_json()["status"] == "degraded"


def test_health_acusa_modulo_do_core_que_deixou_de_carregar(cliente, monkeypatch):
    monkeypatch.setattr(
        modulo_app.core,
        "saude",
        lambda *_a, **_k: {"reachable": True, "status": "ok", "modules": ["clip", "rigid"]},
    )
    corpo = cliente.get("/v1/health").get_json()
    assert corpo["status"] == "degraded"
    assert corpo["core"]["missing_modules"] == ["forense"]


def test_health_ok_quando_o_core_esta_completo(cliente, monkeypatch):
    monkeypatch.setattr(
        modulo_app.core,
        "saude",
        lambda *_a, **_k: {"reachable": True, "status": "ok", "modules": ["forense", "clip", "rigid"]},
    )
    resposta = cliente.get("/v1/health")
    assert resposta.status_code == 200
    assert resposta.get_json()["status"] == "ok"


# --------------------------------------------------------------------------- #
# Chaves
# --------------------------------------------------------------------------- #
def test_chave_e_guardada_como_hash_nao_em_texto():
    valor = "aida_exemplo"
    assert chaves_api.hash_chave(valor) != valor
    assert len(chaves_api.hash_chave(valor)) == 64


def test_prefixo_nao_permite_reconstruir_a_chave():
    chave = "aida_" + "x" * 43
    assert chaves_api.prefixo_de(chave) in chave
    assert len(chaves_api.prefixo_de(chave)) < len(chave)


def test_emitir_sem_supabase_falha_de_forma_clara(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "")
    with pytest.raises(chaves_api.AutenticacaoIndisponivel):
        chaves_api.gerar_chave("teste")
