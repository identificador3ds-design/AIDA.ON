# AIDA.ON

Plataforma web/PWA para análise de imagens com foco na identificação de indícios de geração por inteligência artificial. O projeto reúne uma interface web estática, autenticação e persistência com Supabase e um backend em Python para processar técnicas de detecção.

## Visão geral

O AIDA.ON permite:

- autenticação de usuários;
- seleção e envio de imagens para análise;
- execução de métodos técnicos de detecção;
- armazenamento de histórico de análises;
- acesso a perfil de usuário;
- gerenciamento administrativo de partes da experiência;
- instalação como PWA em dispositivos compatíveis.

## Métodos de análise identificados no projeto

- `Marca Visual`: procura assinatura visual do Gemini na imagem.
- `Metadados`: verifica metadados associados a ferramentas de IA.
- `FFT`: análise em frequência.
- `M4 / LSB`: análise do plano de bits menos significativos.
- `GRAD`: análise por gradiente.

## Stack do projeto

### Front-end

- HTML
- CSS
- JavaScript
- GSAP
- Supabase JS
- PWA com `manifest.webmanifest` e `service-worker.js`

### Back-end

- Python
- Flask
- Flask-CORS
- NumPy
- OpenCV
- Pillow
- Matplotlib

## Estrutura principal

```text
AIDA.ON/
|-- index.html
|-- manifest.webmanifest
|-- service-worker.js
|-- pages/
|   |-- index-login.html
|   |-- index-apresentacao.html
|   |-- index-seleciona.html
|   |-- index-analise.html
|   |-- index-historico.html
|   |-- index-perfil.html
|   |-- index-admin.html
|   |-- index-manutencao.html
|   `-- validador_tac_aida.html
|-- scripts/
|-- styles/
|-- assets/
`-- apps/
    `-- metodo/
        |-- app.py
        |-- fft.py
        |-- grad.py
        |-- m4.py
        |-- marca_dagua.py
        |-- metadados.py
        `-- requirements.txt
```

## Fluxo principal da aplicação

1. O usuário acessa a landing page em `index.html`.
2. Faz login ou cadastro.
3. Entra na apresentação da plataforma.
4. Seleciona uma imagem para análise.
5. Escolhe o método e executa a análise.
6. Visualiza o resultado e, quando autenticado, pode registrar histórico.

## Como executar o projeto localmente

### Front-end

Como o projeto é composto por páginas estáticas, basta servir a raiz do repositório com um servidor local.

Exemplo com Python:

```bash
python -m http.server 5500
```

Depois, abra:

```text
http://localhost:5500
```

### Back-end Python

Entre na pasta do backend:

```bash
cd apps/metodo
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Execute a aplicação:

```bash
python app.py
```

Por padrão, o servidor sobe na porta `5000`.

## Integrações já presentes no código

### Supabase

O front-end já contém integração direta com Supabase para:

- autenticação;
- leitura e edição de dados de usuário;
- histórico de análises;
- upload de evidências.

### API de análise

Na implementação atual, a tela de análise faz requisição para:

```text
https://aida-on.onrender.com/analisar
```

Se a intenção for usar o backend local, esse endpoint precisa ser ajustado no arquivo `scripts/script-analise.js`.

## Páginas principais

- `index.html`: entrada inicial do projeto.
- `pages/index-login.html`: login e cadastro.
- `pages/index-apresentacao.html`: apresentação institucional da plataforma.
- `pages/index-seleciona.html`: seleção da imagem.
- `pages/index-analise.html`: execução da análise e exibição do resultado.
- `pages/index-historico.html`: histórico das análises.
- `pages/index-perfil.html`: perfil do usuário.
- `pages/index-admin.html`: painel administrativo.
- `pages/index-manutencao.html`: controle de manutenção/acesso temporário.

## Observações importantes

- O projeto possui comportamento de PWA e cache offline parcial.
- Parte das credenciais e integrações está definida diretamente nos scripts do front-end.
- O arquivo `apps/metodo/app.py` aparenta conter trechos duplicados e pode merecer revisão.
- Algumas páginas ainda mostram sinais de inconsistência de caminhos e acentuação, o que também pode ser revisado em uma próxima etapa.

## Objetivo acadêmico

Pela estrutura e nomenclatura do repositório, este projeto parece ter sido desenvolvido como solução acadêmica voltada à validação de autenticidade visual e apoio à identificação de imagens potencialmente geradas por IA.

