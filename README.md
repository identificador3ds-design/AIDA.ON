# AIDA.ON

### Análise de imagens, Inteligência Artificial e autenticidade digital

O **AIDA** é uma plataforma web desenvolvida para analisar imagens e identificar indícios de que um conteúdo visual possa ter sido **gerado ou manipulado por Inteligência Artificial**.

O projeto nasceu como Trabalho de Conclusão de Curso do Técnico em Desenvolvimento de Sistemas da **ETEC Deputado Salim Sedeh**, evoluindo para uma aplicação funcional que combina análise computacional, Machine Learning, experiência do usuário e investigação de características presentes em imagens digitais.

🌐 **Aplicação:** https://aida-on.vercel.app

---

## 📌 Sobre o projeto

Com a evolução das ferramentas de geração de imagens por Inteligência Artificial, tornou-se cada vez mais difícil distinguir fotografias reais de conteúdos sintéticos ou manipulados.

O AIDA foi desenvolvido a partir desse problema.

A proposta é reunir diferentes formas de análise em uma única plataforma, processar os resultados encontrados e apresentar ao usuário uma estimativa compreensível sobre a imagem analisada.

Em vez de depender exclusivamente de um único indicador, o projeto utiliza diferentes métodos para investigar padrões, estruturas, artefatos e informações presentes no arquivo.

---

## 🎯 Objetivo

O principal objetivo do AIDA é contribuir para a análise de **autenticidade digital**, tornando técnicas de investigação de imagens mais acessíveis através de uma aplicação web.

A plataforma busca:

- identificar indícios compatíveis com imagens geradas ou manipuladas por IA;
- analisar características estruturais e estatísticas das imagens;
- investigar metadados e informações de proveniência;
- combinar diferentes métodos de análise;
- apresentar os resultados de maneira visual e compreensível;
- permitir a evolução contínua dos modelos por meio de novos dados e testes.

---

## ⚙️ Como funciona

O fluxo principal da aplicação ocorre da seguinte maneira:

1. O usuário acessa a plataforma.
2. Uma imagem é selecionada para análise.
3. O arquivo é validado e encaminhado para o backend.
4. A imagem passa pelo pré-processamento.
5. Diferentes métodos analisam suas características.
6. Os resultados são combinados.
7. O sistema apresenta uma estimativa de:

   - probabilidade de imagem real;
   - probabilidade de imagem gerada ou manipulada por IA;
   - nível de confiança da análise.

Quando habilitado pelo usuário, o resultado também pode ser armazenado no histórico da conta.

---

## 🔬 Métodos de análise

O AIDA utiliza diferentes abordagens para investigar características presentes nas imagens.

Entre os métodos desenvolvidos e estudados no projeto estão técnicas relacionadas a:

- análise de frequência utilizando FFT;
- investigação de padrões através de LSB;
- análise de gradientes;
- análise estatística e estrutural;
- Machine Learning;
- leitura de metadados;
- investigação de informações de proveniência digital.

A combinação dos métodos permite analisar diferentes características da mesma imagem, evitando depender exclusivamente de um único indicador.

> Os métodos continuam sendo aprimorados conforme novos testes, imagens e resultados são incorporados ao projeto.

---

## 🧠 Dataset e treinamento

Uma das principais etapas do desenvolvimento do AIDA é a construção e expansão do conjunto de dados utilizado nos experimentos.

Atualmente, o projeto trabalha com um dataset de aproximadamente **10.000 imagens**, contendo diferentes exemplos utilizados para treinamento e validação.

O conjunto inclui:

- fotografias reais;
- imagens geradas por Inteligência Artificial;
- imagens manipuladas;
- diferentes cenários e contextos visuais.

O dataset é utilizado em rodadas de treinamento, testes e comparação dos métodos desenvolvidos pela equipe.

O objetivo dos experimentos é melhorar progressivamente a capacidade do sistema de diferenciar imagens reais de conteúdos artificiais sem comprometer o desempenho entre as diferentes categorias.

---

# 💻 Tecnologias

## Front-end

- HTML5
- CSS3
- JavaScript
- GSAP

## UI/UX

- Figma

## Processamento e Machine Learning

- Python
- NumPy
- Pandas
- OpenCV
- Pillow
- Scikit-learn
- Joblib

## Backend

- Flask
- Flask-CORS

## Banco de dados

- Supabase

## Deploy

- Vercel
- Render

## Versionamento

- Git
- GitHub

---

## ✨ Principais funcionalidades

Entre os recursos desenvolvidos na plataforma estão:

- autenticação de usuários;
- login e cadastro;
- envio de imagens;
- validação dos arquivos;
- processamento pelo backend;
- apresentação das probabilidades obtidas;
- histórico de análises;
- perfil do usuário;
- interface responsiva;
- suporte a diferentes formatos de imagem;
- animações e interações na interface.

---

# 👥 Equipe

O AIDA é desenvolvido por uma equipe de **cinco integrantes**, com responsabilidades distribuídas entre diferentes áreas do projeto.

| Integrante | Principal área de atuação |
|---|---|
| **Pedro Henrique** | UX/UI e Desenvolvimento Front-end |
| **Iago** | Integração Python ↔ JavaScript e Backend |
| **Arthur** | Python e Métodos de Detecção |
| **Alexandre** | Documentação |
| **Eduardo** | Pesquisa e aquisição de dados |

Além das responsabilidades principais, a equipe também colabora em atividades de planejamento, testes, preparação do dataset e evolução do projeto.

---

# 👨‍💻 Minha contribuição

## Pedro Henrique Silvestre Candido
### UX/UI Designer e Desenvolvedor Front-end

Minha principal atuação no AIDA está concentrada na construção da **experiência visual e da interface da plataforma**.

### UI/UX

- criação do design da plataforma no Figma;
- definição e evolução da identidade visual;
- planejamento das interfaces;
- organização da experiência de navegação;
- prototipação de telas;
- planejamento de novos componentes e funcionalidades.

### Desenvolvimento Front-end

Implementação das interfaces utilizando:

- HTML;
- CSS;
- JavaScript;
- GSAP.

Entre as áreas em que atuei estão:

- página de apresentação;
- área de login;
- perfil do usuário;
- fluxo de seleção e envio de imagens;
- área de apoiadores;
- componentes da interface;
- responsividade;
- animações e interações.

### Dataset e Machine Learning

Também participo de atividades experimentais relacionadas ao sistema de detecção, incluindo:

- coleta de imagens;
- expansão e organização do dataset;
- execução assistida de treinamentos;
- realização de testes;
- análise dos resultados obtidos.

Essa participação ocorre em colaboração com os integrantes responsáveis pelo desenvolvimento dos métodos e pela integração com o backend.

---

# 🏆 Reconhecimento

## 1º Lugar — Projeto de Inovação e Tecnologia

Em agosto de 2026, o AIDA conquistou o **1º lugar no Prêmio de Projeto de Inovação e Tecnologia da EXPOTEC 2026**.

A premiação reconheceu a proposta, o desenvolvimento e a inovação apresentada pela equipe.

O projeto também foi apresentado à empresa de tecnologia **Dev&Co**, proporcionando contato com um ambiente profissional e a apresentação da solução para uma empresa do setor.

---

# 🚀 Roadmap

O AIDA continua em desenvolvimento.

Além da análise de imagens, novas vertentes estão sendo planejadas para ampliar a proposta do projeto.

## AIDA Video

Planejamento de uma solução voltada à análise de vídeos e identificação de possíveis sinais de conteúdo gerado ou manipulado por Inteligência Artificial.

## AIDA Audio

Estudo e planejamento de métodos para análise de conteúdos de áudio potencialmente sintéticos ou manipulados.

## AIDA Documents

Planejamento de recursos voltados à investigação e análise de documentos digitais.

## AIDA API

Planejamento de uma API que permita integrar os recursos do AIDA a sites, sistemas e aplicações externas.

> As vertentes acima fazem parte do roadmap do projeto e possuem diferentes estágios de planejamento e desenvolvimento.

---

# 🏗️ Arquitetura simplificada

```text
Usuário
   │
   ▼
Interface Web
HTML • CSS • JavaScript • GSAP
   │
   ▼
Backend
Python • Flask
   │
   ▼
Pré-processamento
   │
   ▼
Métodos de análise
   │
   ├── Frequência
   ├── Gradientes
   ├── Estrutura da imagem
   ├── Metadados
   └── Machine Learning
   │
   ▼
Combinação dos resultados
   │
   ▼
Probabilidade apresentada ao usuário
```

---

# ⚠️ Limitações

O AIDA deve ser entendido como uma ferramenta de **apoio à análise**, e não como um mecanismo capaz de certificar de maneira absoluta a origem de uma imagem.

A detecção de conteúdos gerados por Inteligência Artificial apresenta desafios como:

- evolução constante dos modelos generativos;
- compressão;
- redimensionamento;
- edição da imagem;
- aplicação de filtros;
- alteração ou remoção de metadados;
- diferenças entre diferentes geradores de IA.

Por esse motivo, os resultados apresentados pelo sistema possuem caráter probabilístico e devem ser interpretados juntamente com outras evidências disponíveis.

---

# 📈 Status do projeto

🚧 **Em desenvolvimento ativo**

O AIDA continua recebendo:

- expansão do dataset;
- novas rodadas de treinamento;
- testes;
- análise dos resultados;
- melhorias de precisão;
- melhorias de UI/UX;
- novos métodos;
- novas vertentes de análise.

---

# 🌐 Demonstração

**Acesse a aplicação:**

https://aida-on.vercel.app

---

# 🎓 Contexto acadêmico

Projeto desenvolvido como Trabalho de Conclusão de Curso do:

**Técnico em Desenvolvimento de Sistemas integrado ao Ensino Médio**

**ETEC Deputado Salim Sedeh**

Leme, São Paulo  
2026

---

# 📄 Uso do projeto

O AIDA é um projeto acadêmico e tecnológico em desenvolvimento.

O código, modelos, datasets e demais recursos utilizados pelo projeto podem possuir condições específicas de utilização definidas pela equipe responsável.

Para utilização de componentes do projeto fora de seu contexto original, recomenda-se consultar previamente a equipe responsável.
