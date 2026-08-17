# Rotas do AIDA

Mapa das URLs públicas do site (`vercel.json`) e dos endpoints da API de
análise. A regra que orienta tudo aqui: **URL antiga não quebra**. Elas já
foram compartilhadas, gravadas em relatórios e indexadas; renomeá-las por causa
da nova nomenclatura da plataforma seria custo sem ganho.

## Site

### Soluções (rotas novas)

| Rota         | Arquivo                       | Observação                                        |
| ------------ | ----------------------------- | ------------------------------------------------- |
| `/solucoes`  | `pages/index-solucoes.html`   | Os quatro cards das soluções                      |
| `/image`     | `pages/index-seleciona.html`  | Entrada do AIDA Image (seleção da imagem)         |
| `/forensics` | `pages/index-forensics.html`  | Investigação de uma análise existente             |
| `/video`     | `pages/index-video.html`      | Página do produto — em desenvolvimento            |
| `/api`       | `pages/index-api.html`        | Página do produto — em desenvolvimento            |

Os cards das soluções **não** ficam na página de apresentação. A Home apresenta
o projeto e leva a `/solucoes` por um botão na seção "Experimente o AIDA agora";
o ecossistema é o passo seguinte de quem já se interessou, não um bloco a mais
para rolar. Isso também mantém a Home com o comprimento e o ritmo de rolagem
para os quais as animações dela foram ajustadas.

`/image` aponta para a **seleção**, não para `index-analise.html`: a tela de
análise depende de uma imagem já escolhida e, aberta direto, mostraria um
estado vazio.

### Compatibilidade (rotas anteriores, todas mantidas)

`/admin`, `/analise`, `/apresentacao`, `/apoiadores`, `/historico`, `/login`,
`/manutencao`, `/perfil`, `/privacidade`, `/selecionar`, `/validador`.

Duas correções entraram junto:

* `/analise` aparecia **duas vezes** na lista de rewrites, apontando para
  arquivos diferentes (`index-analise.html` e `index-apresentacao.html`). A
  segunda regra nunca era alcançada — a primeira vence. A tela de apresentação
  ficou sem rota curta até agora; ela passou a ser `/apresentacao`;
* `/selecionar` e `/image` levam ao mesmo arquivo, de propósito: o nome antigo
  continua válido e o novo entra sem substituí-lo.

### Redirecionamentos

| De             | Para                                    | Motivo                                    |
| -------------- | --------------------------------------- | ----------------------------------------- |
| `/forense`     | `/forensics`                            | Variante em português                     |
| `/imagem`      | `/image`                                | Variante em português                     |
| `/api/v1/*`    | `/api`                                  | Ver observação abaixo                     |

Sobre `/api/v1/*`: a AIDA API **não existe** como serviço. Quem tentar chamar
`https://<site>/api/v1/analyze/image` a partir do exemplo conceitual da página
cairia num 404 do site, sem explicação. O redirect leva à página que declara o
estado da solução. Quando a API real for publicada, esta regra sai — e o
caminho passa a ser servido de verdade.

## API de análise

Servida pelo backend (`aida-space/site_api/app.py`), em outra origem. O
front-end tenta as bases em ordem: Space publicado, depois `127.0.0.1:7860`.

| Método   | Endpoint                    | Papel                                                        |
| -------- | --------------------------- | ------------------------------------------------------------ |
| `GET`    | `/`                         | Estado do serviço e lista de módulos carregados              |
| `GET`    | `/saude`                    | Diagnóstico: módulos, política, proveniência, cache          |
| `GET`    | `/contrato`                 | Contrato de `POST /analisar`, servido pelo próprio código    |
| `POST`   | `/analisar`                 | Executa a análise de uma imagem                              |
| `GET`    | `/forense/<id>`             | Dossiê do AIDA Forensics, a partir do resultado em cache     |
| `DELETE` | `/forense/<id>`             | Remove a análise do cache                                    |
| `GET`    | `/evidencia/<id>/<mapa>`    | PNG de um mapa de explicabilidade                            |
| `GET`    | `/analise/<id>`             | Registro da análise no histórico local do servidor           |

`GET /forense/<id>` **não recalcula nada**. Quando o cache não tem a análise
— expirou, foi invalidada ou nasceu em outra versão do modelo — a resposta é
404 pedindo uma nova análise. Reexecutar o pipeline ali poderia devolver
números diferentes dos que o usuário viu no AIDA Image, e uma investigação que
contradiz o resultado que a originou é pior do que investigação nenhuma.
