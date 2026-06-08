# Inventario LGPD inicial - AIDA.ON

Atualizado em 29/05/2026.

Este documento e um ponto de partida tecnico para adequacao do projeto. Ele nao substitui revisao juridica, mas registra onde o sistema trata dados pessoais e quais controles ja foram iniciados.

## Dados pessoais mapeados

| Area | Dados | Local atual | Observacao |
| --- | --- | --- | --- |
| Cadastro/login | Nome, e-mail, senha via Supabase Auth, dados do Google OAuth quando usado | Supabase Auth e tabela `usuarios` | Senhas nao devem ser manipuladas fora do provedor de autenticacao. |
| Perfil | Nome, e-mail, tipo de usuario e quantidade de analises | Supabase e `localStorage` para exibicao local | Evitar usar dados locais como fonte de autorizacao real. |
| Analise de imagem | Arquivo em base64, metadados do arquivo, resultado tecnico | Backend Flask no Render durante processamento | A imagem pode conter dado pessoal ou sensivel se houver pessoas identificaveis. |
| Historico | URL da imagem original, resultado, metodo, probabilidade, data e `user_id` | Supabase tabela `historico_analises` e bucket `evidencias` | Agora o salvamento depende de escolha explicita na tela de analise. |
| Preferencias locais | Tutorial visto, decisao de instalacao PWA, opcao de salvar historico | Navegador do usuario | Manter apenas preferencias necessarias para UX. |

## Controles implementados nesta etapa

- Aviso de Privacidade em `pages/index-privacidade.html`.
- Aceite informativo do Aviso de Privacidade antes de cadastro.
- Imagem selecionada migrada de `localStorage` para `sessionStorage`.
- Historico de analise passou a ser opcional e desligado por padrao.
- Limpeza do historico agora tenta remover tambem arquivos do bucket `evidencias`.
- Pagina de historico teve HTML duplicado corrigido e saidas de dados escapadas.
- Backend Flask recebeu limite de payload, validacao basica de base64 e CORS configuravel por ambiente.
- Senha administrativa hard-coded no JavaScript foi removida; o admin agora deve autenticar pelo Supabase.

## Riscos prioritarios ainda abertos

| Prioridade | Risco | Proxima acao recomendada |
| --- | --- | --- |
| Alta | Admin ainda e reconhecido por e-mail no front-end | Usar papel/claim no Supabase e validar autorizacao por RLS/backend. |
| Alta | Garantir RLS nas tabelas `usuarios` e `historico_analises` | Criar politicas para cada usuario acessar somente seus registros. |
| Alta | Bucket `evidencias` parece usar URL publica | Preferir bucket privado com URL assinada temporaria. |
| Media | Falta prazo formal de retencao | Definir prazo de expiracao do historico e rotina de limpeza. |
| Media | Falta canal formal do encarregado/controlador | Definir responsavel, e-mail oficial e procedimento de resposta a titulares. |
| Media | Backend aceita origem ampla se `ALLOWED_ORIGINS` nao for configurado | Definir dominios finais de producao no ambiente. |
| Baixa | Textos de privacidade ainda genericos | Validar bases legais e prestadores com responsavel juridico. |

## Fontes oficiais consultadas

- ANPD - Perguntas Frequentes sobre LGPD: https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/perguntas-frequentes-anpd
- ANPD - Direitos dos titulares: https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares
- ANPD - Guia de seguranca para agentes de tratamento de pequeno porte: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-orientativo-sobre-seguranca-da-informacao-para-agentes-de-tratamento-de-pequeno-porte
- ANPD - Guia de cookies e protecao de dados pessoais: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia_orientativo_cookies_e_protecao_de_dados_pessoais
