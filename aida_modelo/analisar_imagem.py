import argparse
import json
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd

from config import (
    ARQUIVO_COLUNAS,
    ARQUIVO_IMPUTER,
    ARQUIVO_MELHOR_MODELO,
    ARQUIVO_SCALER,
    MODELOS_DIR,
    criar_estrutura,
)
from extratores import extrair_todas_metricas
from historico import gerar_id_analise, salvar_historico, salvar_relatorios
from utils_imagem import validar_arquivo_imagem


def _carregar_predicao():
    modelo_path = MODELOS_DIR / ARQUIVO_MELHOR_MODELO
    colunas_path = MODELOS_DIR / ARQUIVO_COLUNAS
    imputer_path = MODELOS_DIR / ARQUIVO_IMPUTER
    if not modelo_path.exists() or not colunas_path.exists() or not imputer_path.exists():
        raise FileNotFoundError("Modelo não encontrado. Execute python treinar_ml.py antes da análise.")
    pacote = joblib.load(modelo_path)
    colunas = json.loads(colunas_path.read_text(encoding="utf-8"))
    imputer = joblib.load(imputer_path)
    scaler = joblib.load(MODELOS_DIR / ARQUIVO_SCALER) if (MODELOS_DIR / ARQUIVO_SCALER).exists() else None
    return pacote, colunas, imputer, scaler


def _confianca(prob_ia):
    distancia = abs(prob_ia - 0.5)
    if distancia < 0.15:
        return "baixa"
    if distancia < 0.30:
        return "média"
    return "alta"


def _explicacao(resultado, confianca):
    if resultado == "IA/MANIPULADA":
        base = "A imagem apresentou padrões estatísticos parecidos com os exemplos IA/manipulados usados no treinamento."
    else:
        base = "A imagem apresentou padrões estatísticos parecidos com os exemplos reais usados no treinamento."
    return f"{base} A confiança da decisão foi {confianca}; o resultado não deve ser tratado como prova absoluta."


def analisar_imagem(
    caminho_imagem,
    historico_habilitado=True,
    imagem_mantida=True,
    id_analise=None,
):
    criar_estrutura()
    caminho = validar_arquivo_imagem(caminho_imagem)
    pacote, colunas, imputer, scaler = _carregar_predicao()
    metricas = extrair_todas_metricas(caminho)
    x = pd.DataFrame([{col: metricas.get(col, 0.0) for col in colunas}])
    x_imp = imputer.transform(x)
    entrada = scaler.transform(x_imp) if pacote.get("usa_scaler") and scaler is not None else x_imp
    modelo = pacote["modelo"]
    if hasattr(modelo, "n_jobs"):
        modelo.n_jobs = 1

    if hasattr(modelo, "predict_proba"):
        proba = modelo.predict_proba(entrada)[0]
        classes = list(modelo.classes_)
        prob_real = float(proba[classes.index(0)]) if 0 in classes else 0.0
        prob_ia = float(proba[classes.index(1)]) if 1 in classes else 0.0
    else:
        pred = int(modelo.predict(entrada)[0])
        prob_real = 1.0 if pred == 0 else 0.0
        prob_ia = 1.0 if pred == 1 else 0.0

    resultado = "IA/MANIPULADA" if prob_ia >= 0.5 else "REAL"
    confianca = _confianca(prob_ia)
    id_analise = id_analise or gerar_id_analise()
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resposta = {
        "id_analise": id_analise,
        "nome_imagem": caminho.name,
        "caminho_imagem": str(caminho),
        "data_hora": data_hora,
        "resultado": resultado,
        "probabilidade_real": prob_real,
        "probabilidade_ia": prob_ia,
        "confianca": confianca,
        "explicacao": _explicacao(resultado, confianca),
        "modelo_utilizado": pacote["nome"],
    }
    rel_json, rel_txt = salvar_relatorios(resposta, metricas)
    salvar_historico(
        {
            "id_analise": id_analise,
            "data_hora": data_hora,
            "nome_arquivo": caminho.name,
            "caminho_imagem": str(caminho) if imagem_mantida else "",
            "resultado": resultado,
            "probabilidade_real": f"{prob_real:.6f}",
            "probabilidade_ia": f"{prob_ia:.6f}",
            "confianca": confianca,
            "modelo_utilizado": pacote["nome"],
            "relatorio_json": str(rel_json),
            "relatorio_txt": str(rel_txt),
            "historico_habilitado": bool(historico_habilitado),
            "imagem_mantida_no_historico": bool(imagem_mantida),
        }
    )
    resposta["relatorio_json"] = str(rel_json)
    resposta["relatorio_txt"] = str(rel_txt)
    resposta["principais_metricas"] = metricas
    return resposta


def imprimir_resultado(resultado):
    print(f"ID da análise: {resultado['id_analise']}")
    print(f"Resultado: {resultado['resultado']}")
    print(f"Probabilidade REAL: {resultado['probabilidade_real']:.2%}")
    print(f"Probabilidade IA/manipulada: {resultado['probabilidade_ia']:.2%}")
    print(f"Confiança: {resultado['confianca']}")
    print(f"Explicação: {resultado['explicacao']}")
    print(f"Relatório JSON: {resultado['relatorio_json']}")
    print(f"Relatório TXT: {resultado['relatorio_txt']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analisa uma imagem individual com o modelo AIDA.ON.")
    parser.add_argument("imagem", nargs="?", help="Caminho da imagem.")
    args = parser.parse_args()
    caminho = args.imagem or input("Informe o caminho da imagem: ").strip('" ')
    imprimir_resultado(analisar_imagem(caminho))
