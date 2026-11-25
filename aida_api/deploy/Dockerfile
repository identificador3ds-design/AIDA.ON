# AIDA API (/v1) — imagem para o Space AIDAON/aida-borda-api (SDK: docker).
#
# Publicado pelo workflow .github/workflows/publicar-api.yml, que monta a raiz
# do Space assim: Dockerfile + README.md (deste diretorio) + pacote aida_api/.
# Nao edite os arquivos direto no Space: o proximo deploy sobrescreve.

FROM python:3.12-slim

# O Spaces roda o container como usuario 1000.
RUN useradd -m -u 1000 aida
USER aida
ENV HOME=/home/aida \
    PATH=/home/aida/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /home/aida/app

COPY --chown=aida aida_api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=aida aida_api ./aida_api

EXPOSE 7860
ENV PORT=7860

# 1 worker: cache de analises, fila e cota vivem na memoria do processo. Com
# 2 workers, GET /v1/analysis/{id} erra metade das vezes e a cota dobra.
# threads=8 atende chamadas concorrentes; a fila (AIDA_API_CONCORRENCIA)
# continua limitando quantas vao ao Core de uma vez.
# timeout=200: maior que AIDA_CORE_TIMEOUT_S (180), senao o gunicorn mata a
# requisicao antes do Core responder num cold start.
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "1", "--threads", "8", \
     "--timeout", "200", "--access-logfile", "-", "aida_api.app:app"]
