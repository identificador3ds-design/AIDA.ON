"""AIDA Documents: triagem de um documento (PDF, DOCX, DOC ou TXT).

Mesmos tres estados do AIDA Core: REAL, IA/MANIPULADA e INCONCLUSIVO. Nao ha modelo
treinado: cada indicio tem um peso fixo e a suspeita combinada e
1 - prod(1 - peso), para que dois indicios fracos somem sem que um so decida.
Os pesos sao um ponto de partida e devem ser calibrados com `avaliar_lote`.

Uso:
    python -m aida_documents.analisar nota.pdf
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benford import N_RECOMENDADO, analisar_benford
from .estrutura import inspecionar_pdf
from .numeros import extrair_numeros, verificar_identificadores
from .office import inspecionar_doc, inspecionar_docx
from .texto_puro import MIN_INVISIVEIS, inspecionar_txt

LIMIAR_MANIPULADO = 0.60
LIMIAR_REAL = 0.25
MAD_NAO_CONFORME = 0.015
# As faixas de MAD de Nigrini supõem N grande: com 120 valores tirados da propria
# distribuicao de Benford o MAD ja passa de 0,02 por acaso. Por isso o desvio so conta
# quando o qui-quadrado tambem rejeita Benford.
P_VALOR_BENFORD = 0.01
DIAS_MODIFICACAO_ALERTA = 1.0
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp", ".tif", ".tiff"}
RESSALVA = "Indício técnico, não prova. O AIDA Documents é uma triagem em validação; confirme na fonte (SEFAZ, banco, emissor)."

PESOS = {
    # Manifesto C2PA que se declara IA (ex.: ChatGPT). Sozinho passa do limiar de 0,60.
    "credencial_c2pa_ia": 0.80,
    "dv_invalido": 0.60,
    # Em .docx/.txt/.doc o texto e digitado: DV errado pode ser erro de digitacao.
    "dv_invalido_digitado": 0.30,
    "alterado_apos_assinatura": 0.50,
    "revisoes_incrementais": 0.30,
    "ferramenta_edicao": 0.30,
    "ferramenta_escritorio": 0.10,
    "gerador_programatico": 0.15,
    "sem_camada_texto_total": 0.35,
    "sem_camada_texto_parcial": 0.20,
    "fonte_subconjunto_duplicado": 0.30,
    "modificado_depois": 0.15,
    "benford_nao_conforme": 0.25,
    "benford_nao_conforme_forte": 0.35,
    # .docx e .txt
    "texto_colado": 0.20,
    "metadados_inconsistentes": 0.15,
    "caracteres_invisiveis": 0.15,
}
MINUTOS_COLAGEM = 2
CARACTERES_COLAGEM = 1500
LIMITES_FORMATO = {
    "docx": ["um .docx é editável: a análise olha o histórico que o Word grava, não prova quem escreveu o texto"],
    "doc": ["do .doc (formato antigo) só os metadados são lidos; para analisar o texto, envie em .docx ou PDF"],
    "txt": ["um .txt não guarda programa, datas nem histórico: só o texto é analisado"],
}
_ESCRITORIO = ("processador de texto", "impressão de navegador", "impressora virtual", "organizador de páginas")
_PROGRAMACAO = "biblioteca de programação"


def _combinar(pesos):
    restante = 1.0
    for p in pesos:
        restante *= 1.0 - p
    return 1.0 - restante


def _confianca(suspeita):
    distancia = min(abs(suspeita - LIMIAR_MANIPULADO), abs(suspeita - LIMIAR_REAL))
    return "alta" if distancia >= 0.25 else "media" if distancia >= 0.10 else "baixa"


def _formato(dados: bytes, nome: str):
    """Pelo conteudo, nao pela extensao (um .pdf que e ZIP e tratado como .docx)."""
    if dados.lstrip()[:5].startswith(b"%PDF"):
        return "pdf"
    if dados[:4] == b"PK\x03\x04":
        return "docx"
    if dados[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "doc"
    if Path(nome).suffix.lower() == ".txt":
        return "txt"
    raise ValueError("formato não suportado: envie PDF, DOCX, DOC ou TXT")


def _inspecionar(formato, dados):
    if formato == "pdf":
        return inspecionar_pdf(dados)
    if formato == "docx":
        return inspecionar_docx(dados)
    if formato == "doc":
        return inspecionar_doc(dados)
    return inspecionar_txt(dados)


def analisar_bytes(dados: bytes, nome="documento.pdf"):
    if Path(nome).suffix.lower() in EXTENSOES_IMAGEM:
        return {
            "resultado": "INCONCLUSIVO",
            "inconclusivo": True,
            "suspeita": None,
            "motivos": ["documento enviado como imagem: sem estrutura de PDF para inspecionar"],
            "indicios": [],
            "limitacoes": ["analise a imagem no AIDA Image; OCR de documento ainda não implementado"],
            "ressalva": RESSALVA,
        }
    formato = _formato(dados, nome)
    est = _inspecionar(formato, dados)
    est.setdefault("formato", formato)
    texto = est.pop("texto")
    ids = verificar_identificadores(texto)
    benford = analisar_benford(extrair_numeros(texto, apenas_monetarios=True))

    indicios, limitacoes, alertas_seguranca = [], [], []

    def indicio(chave, descricao):
        indicios.append({"indicio": chave, "peso": PESOS[chave], "descricao": descricao})

    c2pa = est["c2pa"]
    if c2pa["presente"] and c2pa["declara_ia"]:
        quem = " / ".join(x for x in (c2pa["gerador"], c2pa["modelo"]) if x) or "gerador não identificado"
        indicio("credencial_c2pa_ia", f"credencial de conteúdo (C2PA) declara: {c2pa['origem_declarada']} ({quem})")
    for alerta in ids["alertas"]:
        if formato == "pdf":
            indicio("dv_invalido", alerta)
        else:
            indicio("dv_invalido_digitado", f"{alerta} (num arquivo digitado pode ser erro de digitação)")
    for ferramenta in est.get("ferramentas_edicao", []):
        if ferramenta.startswith(_PROGRAMACAO):
            indicio("gerador_programatico", f"montado por {ferramenta}: comum em documento feito por script ou IA")
        else:
            chave = "ferramenta_escritorio" if ferramenta.startswith(_ESCRITORIO) else "ferramenta_edicao"
            indicio(chave, f"gerado ou salvo por {ferramenta}")
    if est.get("caracteres_invisiveis", 0) >= MIN_INVISIVEIS:
        indicio("caracteres_invisiveis", f"{est['caracteres_invisiveis']} caracteres invisíveis no texto (marca d'água ou texto oculto)")

    if formato == "pdf":
        _indicios_pdf(est, indicio)
    elif formato == "docx":
        _indicios_docx(est, len(texto), len(texto.split()), indicio)
    if benford["suficiente"] and benford["mad"] > MAD_NAO_CONFORME and benford["p_valor"] < P_VALOR_BENFORD:
        chave = "benford_nao_conforme_forte" if benford["n"] >= N_RECOMENDADO else "benford_nao_conforme"
        indicio(chave, f"valores fogem da Lei de Benford (MAD {benford['mad']:.4f}, N={benford['n']})")
    elif not benford["suficiente"]:
        limitacoes.append(f"só {benford['n']} valores monetários: Benford não entra na decisão")

    if est.get("elementos_ativos"):
        alertas_seguranca.append("o arquivo contém " + ", ".join(est["elementos_ativos"]) + ": não abra fora de um visualizador seguro")
    if formato == "pdf" and est["assinaturas"]:
        limitacoes.append("a validade criptográfica da assinatura não é verificada (use o Verificador ITI/Adobe)")
    if c2pa["presente"]:
        limitacoes.append("a assinatura da credencial C2PA não é verificada (confira em contentcredentials.org/verify)")
    limitacoes += LIMITES_FORMATO.get(formato, [])
    if formato == "doc" and not est.get("metadados_lidos"):
        limitacoes.append("os metadados do .doc não foram lidos (pacote olefile ausente no servidor)")

    suspeita = _combinar(i["peso"] for i in indicios)
    # REAL exige algo que comprove a ORIGEM, nao so a ausencia de edicao: CNPJ e CPF com
    # DV certo saem de qualquer gerador (so o DV errado e indicio). Contam a assinatura
    # digital intacta e a chave de acesso valida, que pode ser conferida na SEFAZ. So no
    # PDF: um .docx ou .txt qualquer pessoa escreve, com a chave que quiser.
    if formato == "pdf":
        assinatura_intacta = bool(est["assinaturas"]) and not est["bytes_apos_assinatura"]
        chave_ok = ids["chaves_acesso"] > 0 and not any("chave" in a for a in ids["alertas"])
        origem_verificavel = assinatura_intacta or chave_ok
    else:
        chave_ok = origem_verificavel = False
    motivos = []
    if suspeita >= LIMIAR_MANIPULADO:
        resultado = "IA/MANIPULADA"
    elif suspeita < LIMIAR_REAL and origem_verificavel and not est["paginas_sem_texto"]:
        resultado = "REAL"
        if chave_ok:
            limitacoes.append("a chave de acesso tem formato válido; confirme na SEFAZ que a nota existe e bate valor e data")
    else:
        resultado = "INCONCLUSIVO"
        if suspeita > LIMIAR_REAL:
            motivos.append("indícios fracos: não bastam para afirmar manipulação")
        if formato != "pdf":
            motivos.append(f"arquivo .{formato} pode ser escrito ou alterado por qualquer pessoa: nada nele comprova a origem")
        elif not origem_verificavel:
            motivos.append(
                "nada comprova a origem: sem assinatura digital e sem chave de acesso de nota fiscal "
                "(CNPJ e CPF com dígito certo podem ser inventados)"
            )

    return {
        "resultado": resultado,
        "inconclusivo": resultado == "INCONCLUSIVO",
        "suspeita": round(suspeita, 4),
        "confianca": _confianca(suspeita),
        "formato": formato,
        "limiares": {"manipulado": LIMIAR_MANIPULADO, "real": LIMIAR_REAL},
        "motivos": motivos,
        "indicios": indicios,
        "limitacoes": limitacoes,
        "alertas_seguranca": alertas_seguranca,
        "estrutura": est,
        "identificadores": ids,
        "benford": benford,
        "caracteres_de_texto": len(texto),
        "ressalva": RESSALVA,
    }


def _indicios_pdf(est, indicio):
    if est["bytes_apos_assinatura"] > 0:
        indicio("alterado_apos_assinatura", f"{est['bytes_apos_assinatura']} bytes acrescentados depois da assinatura digital")
    # O manifesto C2PA entra no PDF como revisao incremental: essa nao e edicao.
    edicoes = est["revisoes"] - 1 - est["assinaturas"] - int(est["c2pa"]["presente"])
    if edicoes > 0:
        indicio("revisoes_incrementais", f"{est['revisoes']} revisões salvas no arquivo (edição após a criação)")
    if est["paginas_analisadas"] and est["paginas_sem_texto"] == est["paginas_analisadas"]:
        indicio("sem_camada_texto_total", "nenhuma página tem texto selecionável: é imagem (print, foto ou montagem)")
    elif est["paginas_sem_texto"]:
        indicio("sem_camada_texto_parcial", f"{est['paginas_sem_texto']} página(s) só com imagem")
    for fonte in est["fontes_subconjunto_duplicado"]:
        indicio("fonte_subconjunto_duplicado", f"fonte {fonte} embutida duas vezes (texto acrescentado por outro programa)")
    dias = est["dias_entre_criacao_e_modificacao"]
    if dias is not None and dias > DIAS_MODIFICACAO_ALERTA:
        indicio("modificado_depois", f"modificado {dias:g} dias depois de criado")


def _indicios_docx(est, caracteres, palavras, indicio):
    tempo = est["tempo_edicao_min"]
    # Ninguem digita 1.500 caracteres em 2 minutos: o texto chegou pronto (colado ou importado).
    if est["eh_word"] and tempo is not None and tempo <= MINUTOS_COLAGEM and caracteres >= CARACTERES_COLAGEM:
        indicio("texto_colado", f"{caracteres} caracteres com {tempo} min de edição registrados no Word "
                                f"({est['sessoes_edicao']} sessão(ões)): o texto chegou pronto, colado ou importado")
    # O Word atualiza a contagem de palavras a cada gravacao; zerada com texto, o arquivo nao foi salvo pelo Word.
    if est["palavras_registradas"] == 0 and palavras >= 50:
        indicio("metadados_inconsistentes", f"o arquivo diz ter 0 palavras, mas tem {palavras}: não foi salvo pelo programa que declara")


def analisar_documento(caminho):
    caminho = Path(caminho)
    return analisar_bytes(caminho.read_bytes(), caminho.name)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Triagem forense de um PDF.")
    parser.add_argument("arquivo")
    args = parser.parse_args(argv)
    print(json.dumps(analisar_documento(args.arquivo), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
