---
title: AIDA API v1
emoji: 🔑
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# AIDA API (`/v1`)

Camada pública, versionada, sobre o AIDA Core (`AIDAON/aida-api`). Não contém
lógica de detecção: autentica a chave, valida o arquivo, aplica a cota e delega
ao Core.

- Documentação: `GET /v1/docs`
- Contrato: `GET /v1/contract`
- Saúde: `GET /v1/health`

O código-fonte vive em `aida_api/` no repositório do site e é publicado aqui por
GitHub Actions. Alterações feitas direto neste Space são sobrescritas no próximo
deploy.
