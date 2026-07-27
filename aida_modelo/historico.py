import csv
import json
from datetime import datetime
from pathlib import Path

from config import HISTORICO_CSV, RELATORIOS_DIR, criar_estrutura


CAMPOS_HISTORICO = [
    "id_analise",
    "data_hora",
    "nome_arquivo",
    "caminho_imagem",
    "resultado",
    "probabilidade_real",
    "probabilidade_ia",
    "confianca",
    "modelo_utilizado",
    "relatorio_json",
    "relatorio_txt",
    "historico_habilitado",
    "imagem_mantida_no_historico",
]


def gerar_id_analise():
    criar_estrutura()
    ano = datetime.now().year
    maior = 0
    if HISTORICO_CSV.exists():
        with open(HISTORICO_CSV, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                ident = row.get("id_analise", "")
                prefixo = f"AIDA-{ano}-"
                if ident.startswith(prefixo):
                    try:
                        maior = max(maior, int(ident.replace(prefixo, "")))
                    except ValueError:
                        pass
    return f"AIDA-{ano}-{maior + 1:04d}"


def salvar_historico(registro):
    criar_estrutura()
    existe = HISTORICO_CSV.exists()
    with open(HISTORICO_CSV, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_HISTORICO)
        if not existe:
            writer.writeheader()
        writer.writerow({campo: registro.get(campo, "") for campo in CAMPOS_HISTORICO})


def buscar_analise_por_id(id_analise):
    if not HISTORICO_CSV.exists():
        return None
    with open(HISTORICO_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("id_analise") == id_analise:
                return row
    return None


def salvar_relatorios(resultado, metricas):
    criar_estrutura()
    id_analise = resultado["id_analise"]
    json_path = RELATORIOS_DIR / f"{id_analise}.json"
    txt_path = RELATORIOS_DIR / f"{id_analise}.txt"

    conteudo_json = dict(resultado)
    conteudo_json["principais_metricas_extraidas"] = metricas
    conteudo_json["observacao"] = (
        "Resultado estatístico baseado no modelo treinado. Não é uma prova absoluta."
    )
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(conteudo_json, f, ensure_ascii=False, indent=2)

    linhas = [
        f"ID da análise: {id_analise}",
        f"Imagem: {resultado['nome_imagem']}",
        f"Caminho: {resultado['caminho_imagem']}",
        f"Data e hora: {resultado['data_hora']}",
        f"Resultado final: {resultado['resultado']}",
        f"Probabilidade REAL: {resultado['probabilidade_real']:.2%}",
        f"Probabilidade IA/manipulada: {resultado['probabilidade_ia']:.2%}",
        f"Confiança: {resultado['confianca']}",
        f"Explicação: {resultado['explicacao']}",
        f"Modelo utilizado: {resultado['modelo_utilizado']}",
        "",
        "Principais métricas extraídas:",
    ]
    for chave, valor in list(metricas.items())[:80]:
        linhas.append(f"- {chave}: {valor}")
    linhas.extend(
        [
            "",
            "Observação: este resultado é uma previsão estatística baseada no modelo treinado,",
            "não uma prova absoluta sobre a origem da imagem.",
        ]
    )
    txt_path.write_text("\n".join(linhas), encoding="utf-8")
    return json_path, txt_path
