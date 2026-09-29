"""AIDA Documents: triagem de um PDF (nota fiscal, recibo, comprovante, boleto).

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
    "dv_invalido": 0.60,
    "alterado_apos_assinatura": 0.50,
    "revisoes_incrementais": 0.30,
    "ferramenta_edicao": 0.30,
    "ferramenta_escritorio": 0.10,
    "sem_camada_texto_total": 0.35,
    "sem_camada_texto_parcial": 0.20,
    "fonte_subconjunto_duplicado": 0.30,
    "modificado_depois": 0.15,
    "benford_nao_conforme": 0.25,
    "benford_nao_conforme_forte": 0.35,
}
_ESCRITORIO = ("processador de texto", "impressão de navegador", "impressora virtual")


def _combinar(pesos):
    restante = 1.0
    for p in pesos:
        restante *= 1.0 - p
    return 1.0 - restante


def _confianca(suspeita):
    distancia = min(abs(suspeita - LIMIAR_MANIPULADO), abs(suspeita - LIMIAR_REAL))
    return "alta" if distancia >= 0.25 else "media" if distancia >= 0.10 else "baixa"


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
    if not dados.lstrip()[:5].startswith(b"%PDF"):
        raise ValueError("o arquivo não é um PDF")

    est = inspecionar_pdf(dados)
    texto = est.pop("texto")
    ids = verificar_identificadores(texto)
    benford = analisar_benford(extrair_numeros(texto, apenas_monetarios=True))

    indicios, limitacoes, alertas_seguranca = [], [], []

    def indicio(chave, descricao):
        indicios.append({"indicio": chave, "peso": PESOS[chave], "descricao": descricao})

    for alerta in ids["alertas"]:
        indicio("dv_invalido", alerta)
    if est["bytes_apos_assinatura"] > 0:
        indicio("alterado_apos_assinatura", f"{est['bytes_apos_assinatura']} bytes acrescentados depois da assinatura digital")
    edicoes = est["revisoes"] - 1 - est["assinaturas"]
    if edicoes > 0:
        indicio("revisoes_incrementais", f"{est['revisoes']} revisões salvas no arquivo (edição após a criação)")
    for ferramenta in est["ferramentas_edicao"]:
        chave = "ferramenta_escritorio" if ferramenta.startswith(_ESCRITORIO) else "ferramenta_edicao"
        indicio(chave, f"gerado ou salvo por {ferramenta}")
    if est["paginas_analisadas"] and est["paginas_sem_texto"] == est["paginas_analisadas"]:
        indicio("sem_camada_texto_total", "nenhuma página tem texto selecionável: é imagem (print, foto ou montagem)")
    elif est["paginas_sem_texto"]:
        indicio("sem_camada_texto_parcial", f"{est['paginas_sem_texto']} página(s) só com imagem")
    for fonte in est["fontes_subconjunto_duplicado"]:
        indicio("fonte_subconjunto_duplicado", f"fonte {fonte} embutida duas vezes (texto acrescentado por outro programa)")
    dias = est["dias_entre_criacao_e_modificacao"]
    if dias is not None and dias > DIAS_MODIFICACAO_ALERTA:
        indicio("modificado_depois", f"modificado {dias:g} dias depois de criado")
    if benford["suficiente"] and benford["mad"] > MAD_NAO_CONFORME and benford["p_valor"] < P_VALOR_BENFORD:
        chave = "benford_nao_conforme_forte" if benford["n"] >= N_RECOMENDADO else "benford_nao_conforme"
        indicio(chave, f"valores fogem da Lei de Benford (MAD {benford['mad']:.4f}, N={benford['n']})")
    elif not benford["suficiente"]:
        limitacoes.append(f"só {benford['n']} valores monetários: Benford não entra na decisão")

    if est["elementos_ativos"]:
        alertas_seguranca.append("PDF contém " + ", ".join(est["elementos_ativos"]) + ": não abra fora de um visualizador seguro")
    if est["assinaturas"]:
        limitacoes.append("a validade criptográfica da assinatura não é verificada (use o Verificador ITI/Adobe)")

    suspeita = _combinar(i["peso"] for i in indicios)
    # REAL exige evidencia positiva: texto nativo + algo verificavel (DV, Benford ou assinatura intacta).
    verificavel = (ids["cnpjs"] + ids["cpfs"] + ids["chaves_acesso"]) > 0 or benford["suficiente"] or (
        est["assinaturas"] and not est["bytes_apos_assinatura"]
    )
    motivos = []
    if suspeita >= LIMIAR_MANIPULADO:
        resultado = "IA/MANIPULADA"
    elif suspeita < LIMIAR_REAL and verificavel and not est["paginas_sem_texto"]:
        resultado = "REAL"
    else:
        resultado = "INCONCLUSIVO"
        if not verificavel:
            motivos.append("nada verificável no documento (sem CNPJ/CPF/chave, poucos valores, sem assinatura)")
        elif suspeita > LIMIAR_REAL:
            motivos.append("indícios fracos: não bastam para afirmar manipulação")

    return {
        "resultado": resultado,
        "inconclusivo": resultado == "INCONCLUSIVO",
        "suspeita": round(suspeita, 4),
        "confianca": _confianca(suspeita),
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
