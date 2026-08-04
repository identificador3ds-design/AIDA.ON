import subprocess
import sys

from config import criar_estrutura
from gerar_csv import gerar_csv, gerar_graficos_comparativos
from historico import buscar_analise_por_id
from treinar_ml import treinar_modelos
from analisar_imagem import analisar_imagem, imprimir_resultado


def exibir_analise(registro):
    if not registro:
        print("Análise não encontrada.")
        return
    print(f"ID: {registro.get('id_analise')}")
    print(f"Data e hora: {registro.get('data_hora')}")
    print(f"Imagem: {registro.get('nome_arquivo')}")
    print(f"Resultado: {registro.get('resultado')}")
    print(f"Probabilidade REAL: {registro.get('probabilidade_real')}")
    print(f"Probabilidade IA/manipulada: {registro.get('probabilidade_ia')}")
    print(f"Confiança: {registro.get('confianca')}")
    print(f"Relatório JSON: {registro.get('relatorio_json')}")
    print(f"Relatório TXT: {registro.get('relatorio_txt')}")
    print(f"Imagem mantida: {registro.get('imagem_mantida_no_historico')}")


def main():
    while True:
        print("\nAIDA.ON - Menu")
        print("1. Criar/verificar estrutura de pastas")
        print("2. Gerar CSV de métricas")
        print("3. Treinar modelos de machine learning")
        print("4. Analisar uma imagem individual")
        print("5. Gerar gráficos comparativos")
        print("6. Iniciar API Flask")
        print("7. Buscar relatório pelo ID da análise")
        print("8. Sair")
        opcao = input("Escolha uma opção: ").strip()

        try:
            if opcao == "1":
                criar_estrutura()
                print("Estrutura verificada/criada.")
            elif opcao == "2":
                gerar_csv()
            elif opcao == "3":
                treinar_modelos()
            elif opcao == "4":
                caminho = input("Caminho da imagem: ").strip('" ')
                imprimir_resultado(analisar_imagem(caminho))
            elif opcao == "5":
                gerar_graficos_comparativos()
                print("Gráficos comparativos gerados.")
            elif opcao == "6":
                subprocess.run([sys.executable, "site_api/app.py"], check=False)
            elif opcao == "7":
                id_analise = input("ID da análise: ").strip()
                exibir_analise(buscar_analise_por_id(id_analise))
            elif opcao == "8":
                break
            else:
                print("Opção inválida.")
        except Exception as exc:
            print(f"Erro: {exc}")


if __name__ == "__main__":
    main()
