from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATASET_DIR = BASE_DIR / "dataset"
DATASET_REAIS_DIR = DATASET_DIR / "reais"
DATASET_IA_DIR = DATASET_DIR / "ia"

METRICAS_DIR = BASE_DIR / "metricas"
CSV_METRICAS = METRICAS_DIR / "metricas_aida.csv"

MODELOS_DIR = BASE_DIR / "modelos"
SAIDAS_DIR = BASE_DIR / "saidas"
GRAFICOS_DIR = SAIDAS_DIR / "graficos"
RELATORIOS_DIR = SAIDAS_DIR / "relatorios"
HISTORICO_DIR = SAIDAS_DIR / "historico"
HISTORICO_CSV = HISTORICO_DIR / "historico_analises.csv"

SITE_API_DIR = BASE_DIR / "site_api"
UPLOADS_DIR = SITE_API_DIR / "uploads"

EXTENSOES_ACEITAS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".avif"}
TAMANHO_MAX_MB = 15
TAMANHO_MAX_BYTES = TAMANHO_MAX_MB * 1024 * 1024

RANDOM_STATE = 42
TEST_SIZE = 0.30
MIN_IMAGENS_POR_CLASSE = 2

PARAMETROS_EXTRATORES = {
    "imagem_tamanho_max_processamento": 1024,
    "fft_blocos": 5,
    "lsb_blocos": 5,
    "benford_digitos": list(range(1, 10)),
    "limiar_bordas_percentil": 90,
    "janela_desvio_local": 9,
}

ARQUIVO_MODELO_LOGISTICO = "modelo_regressao_logistica.pkl"
ARQUIVO_MODELO_RANDOM_FOREST = "modelo_random_forest.pkl"
ARQUIVO_MELHOR_MODELO = "melhor_modelo.pkl"
ARQUIVO_SCALER = "scaler.pkl"
ARQUIVO_IMPUTER = "imputer.pkl"
ARQUIVO_COLUNAS = "colunas_treinamento.json"
ARQUIVO_DESEMPENHO = "desempenho_modelos.json"


def criar_estrutura():
    pastas = [
        DATASET_REAIS_DIR,
        DATASET_IA_DIR,
        METRICAS_DIR,
        MODELOS_DIR,
        GRAFICOS_DIR,
        RELATORIOS_DIR,
        HISTORICO_DIR,
        UPLOADS_DIR,
        SITE_API_DIR / "templates",
    ]

    for pasta in pastas:
        pasta.mkdir(parents=True, exist_ok=True)

    return pastas