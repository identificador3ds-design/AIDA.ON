# Relatório de Melhorias — Site AIDA.ON

**Projeto:** AIDA — AI Detector & Analyzer
**URL analisada:** https://aida-on.vercel.app
**Data da análise:** 19/08/2026
**Escopo:** 16 páginas em produção, `vercel.json`, folhas de estilo, scripts e comportamento real no navegador (rotas, cabeçalhos HTTP, console e rede).

---

## Sumário executivo

O site tem uma boa base (PWA configurado, HTTPS, backend de análise no ar, conteúdo honesto e arquitetura de navegação clara), mas apresenta **2 problemas críticos** que precisam ser resolvidos antes da entrega/apresentação, além de pontos importantes de segurança, SEO, consistência de design e acabamento de conteúdo.

**Prioridade recomendada:**
1. Remover credenciais de admin do código público + proteger o painel no backend
2. Corrigir as rotas quebradas do `vercel.json`
3. Adicionar cabeçalhos de segurança e travar versões das bibliotecas
4. Revisão ortográfica e remoção de textos de rascunho/placeholders
5. Unificar o design system e a tipografia
6. Adicionar meta description e Open Graph

---

## 🔴 CRÍTICO — resolver primeiro

### 1. Senha de administrador exposta no código público
- **Onde:** `scripts/script-login.js` (linhas 7–8).
- **Problema:** o e-mail e a senha do admin estão escritos em texto puro e são baixados por qualquer visitante:
  - `ADMIN_EMAIL = "admin@gmail.com"`
  - `ADMIN_PASSWORD = "admin3ds"`
- **Confirmado ao vivo** em `https://aida-on.vercel.app/scripts/script-login.js`.
- **Agravante:** o acesso ao painel admin é validado apenas no navegador (`scripts/script-administrador.js`, ~linha 225, checa `localStorage.usuarioTipo === "admin"`). É possível virar admin digitando no console: `localStorage.setItem("usuarioTipo","admin")`.
- **O que mudar:**
  - Remover a senha do front-end (nunca deve existir senha no JS público).
  - Trocar a senha atual (ela já está comprometida).
  - Mover a autenticação/autorização de admin para o Supabase (papéis + Row Level Security), de forma que o back-end é quem decide o acesso.

### 2. Todas as URLs "limpas" retornam 404
- **Onde:** `vercel.json` (`cleanUrls: true` + bloco `rewrites`).
- **Problema:** com `cleanUrls: true`, os arquivos passam a ser servidos **sem** `.html`, mas os `rewrites` apontam para destinos **com** `.html` (ex.: `/pages/index-solucoes.html`). Como o destino não resolve, as rotas amigáveis caem em 404.
- **Comprovado (teste de status HTTP):**
  - `/solucoes`, `/login`, `/analise`, `/forensics`, `/video`, `/api`, `/perfil`, `/admin`, `/historico`, `/privacidade`, `/apoiadores`, `/validador`, `/manutencao` → **404**
  - `/pages/index-solucoes` (link interno relativo) → 200
- **Impacto:** o site só funciona pela navegação interna com caminhos relativos (`./index-*.html`). Qualquer link "bonito" divulgado (ex.: `/login`) abre uma página de erro.
- **O que mudar:** nos `rewrites`, remover a extensão `.html` dos destinos (usar `/pages/index-solucoes`), **ou** desativar `cleanUrls`. Padronizar a decisão em todo o arquivo.

---

## 🟠 IMPORTANTE — segurança e robustez

### 3. Cabeçalhos de segurança ausentes
- **Situação atual:** só existe `Strict-Transport-Security`.
- **Faltam:**
  - `Content-Security-Policy` (limita de onde scripts/estilos podem vir)
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY` (hoje o site pode ser embutido em iframe — risco de clickjacking)
  - `Referrer-Policy`
  - `Permissions-Policy`
- **O que mudar:** adicionar um bloco `headers` no `vercel.json` aplicando esses cabeçalhos a todas as rotas.

### 4. Bibliotecas externas sem trava de versão nem verificação (SPOF)
- **Onde:** páginas que carregam GSAP, Font Awesome e Supabase por CDN.
- **Problemas:**
  - Nenhum `<script>`/`<link>` externo usa `integrity` (SRI). Se o CDN for comprometido ou alterado, o código roda mesmo assim.
  - **Conflito de versão do GSAP:** carregado `gsap@3.14.1` (core + SplitText) junto com `3.12.5` (ScrollTrigger) na mesma página. Pode causar bugs de animação.
- **O que mudar:** padronizar uma única versão do GSAP, adicionar `integrity` + `crossorigin` nos recursos externos e, de preferência, hospedar as bibliotecas localmente.

---

## 🟠 IMPORTANTE — SEO e compartilhamento

### 5. Metadados de SEO/redes sociais praticamente inexistentes
- **12 de 16 páginas** não têm `<meta name="description">`. Páginas sem descrição: apoiadores, admin, análise, apresentação, histórico, login, manutenção, perfil, privacidade, seleciona, entre outras.
- **Zero tags Open Graph (`og:`) e Twitter Card** em todo o site. Ao compartilhar o link (WhatsApp, LinkedIn, etc.), não aparece título, imagem nem descrição — só a URL crua.
- **O que mudar:**
  - Adicionar `<meta name="description">` único em cada página.
  - Adicionar `og:title`, `og:description`, `og:image`, `og:url` e `twitter:card` pelo menos na apresentação e nas soluções.

---

## 🟡 CONSISTÊNCIA — design e UI/UX

### 6. Design fragmentado (sem sistema único aplicado)
- Existe `styles/aida-design-system.css`, mas ele é usado em **apenas 4 das 16 páginas** (soluções, forensics, video, api).
- As demais páginas (apresentação, análise, login, perfil, admin, histórico…) definem cada uma o seu próprio `:root` com variáveis próprias.
- **Efeito:** divergência de cores, espaçamentos e estilos de botão entre telas.
- **O que mudar:** consolidar tokens (cores, tipografia, espaçamento, raios, sombras) no design system e importá-lo em **todas** as páginas.

### 7. Tipografia inconsistente
- O site carrega **duas famílias diferentes**: `Afacad` (página de apresentação) e `Montserrat` (demais páginas).
- **O que mudar:** escolher uma família principal e aplicá-la em todo o site.

### 8. Acessibilidade
- **Pontos bons:** todas as 74 imagens têm atributo `alt`; `lang="pt-BR"` correto; botão de menu com atributos `aria`.
- **A melhorar:**
  - Apenas 1 página possui *skip link* (link "pular para o conteúdo").
  - Vários `<input>` (login, admin, análise) dependem só de `placeholder`, sem `<label>` associado.
  - Validar contraste de cores e estados de foco visíveis (teclado).
- **O que mudar:** adicionar `<label>` a todos os campos, incluir skip link, e rodar uma auditoria (Lighthouse ou axe).

### 9. Redirecionamento duplo na página inicial
- **Onde:** `index.html`.
- **Problema:** usa `<meta http-equiv="refresh">` **e** `window.location.replace()` apontando para a mesma URL — redundante.
- **O que mudar:** manter apenas um mecanismo (idealmente um redirect configurado no Vercel).

---

## 🟢 ACABAMENTO — conteúdo (impacto direto na banca do TCC)

### 10. Erros de acentuação e digitação no texto visível
Exemplos encontrados nas páginas: "identificaçãoo" (o dobrado), "experiencia", "relatorios", "análise estatistica", "Faca o upload", "ha indicios", "inteligencia", "Historico", "Manutencao".
- **O que mudar:** revisão ortográfica completa de todos os textos exibidos.

### 11. Textos de rascunho e placeholders vazados para produção
- Rodapé com **"Empresa 2"** (apoiador fictício).
- E-mail **`contato@aida.com`** (domínio que não corresponde ao projeto).
- Frase **"inspirado exclusivamente na referência enviada"** na seção de funcionamento — linguagem interna de rascunho que ficou pública.
- **O que mudar:** substituir por conteúdo real ou remover.

### 12. Detalhe técnico do favicon
- O favicon `AIDABranco.ico` é declarado como `type="image/png"`, quando é `.ico`.
- **O que mudar:** ajustar o `type` ou usar um arquivo `.png` de verdade. (Impacto baixo.)

---

## O que já está bom (manter)
- PWA configurado: `manifest.webmanifest`, `service-worker.js` e ícones Apple.
- Backend de análise (Hugging Face Space) respondendo normalmente (HTTP 200).
- HTTPS com HSTS ativo.
- `alt` presente em 100% das imagens.
- Texto honesto e responsável na página de Soluções ("o resultado é um indício técnico, nunca uma prova").
- Arquitetura de conteúdo clara: apresentação → soluções → ferramenta → forensics.

---

## Checklist de execução

- [x] Remover `ADMIN_PASSWORD`/`ADMIN_EMAIL` do front e trocar a senha
- [x] Proteger o painel admin no Supabase (RLS + papéis)
- [x] Corrigir destinos dos `rewrites` no `vercel.json` (sem `.html`) ou desligar `cleanUrls`
- [x] Adicionar cabeçalhos de segurança (CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy)
- [x] Padronizar versão do GSAP e adicionar SRI nos recursos externos
- [x] Adicionar `<meta name="description">` em todas as páginas
- [x] Adicionar Open Graph / Twitter Card
- [x] Importar o design system em todas as páginas e unificar tokens
- [x] Escolher uma única família tipográfica
- [x] Adicionar `<label>` aos campos e skip link; auditar acessibilidade
- [x] Simplificar o redirecionamento da `index.html`
- [x] Revisão ortográfica geral
- [x] Remover placeholders ("Empresa 2", e-mail fictício, "referência enviada")

---

## Estado da execução — 19/08/2026

Todos os itens do checklist foram aplicados no código. Duas ressalvas:

- **Troca da senha do admin e RLS** dependem de acesso ao painel do Supabase.
  O código já não contém senha e o painel só abre para quem tem o papel `admin`
  assinado no JWT. Falta rodar `docs/supabase-admin-setup.sql` e redefinir a
  senha da conta `admin@gmail.com` — a antiga esteve pública e está comprometida.
- O e-mail `contato@aida.com` foi **mantido** (é caixa real, hospedada na Umbler).
  A variante `contato@aida.com.br` da página de privacidade foi padronizada.

### Defeitos encontrados durante a execução (fora do relatório original)

1. **`updateFavicon()` derrubava scripts inteiros.** Doze scripts liam
   `document.getElementById("favicon")`, mas só seis páginas declaravam o `id`.
   Nas outras, o `TypeError` interrompia todo o arquivo — inclusive a checagem de
   acesso do painel administrativo. Corrigido nos dois lados: guarda nos scripts
   e `id="favicon"` em todas as páginas.
2. **A home carregava pela metade.** `updateActiveNav()` passava o href
   `./index-solucoes.html` para `querySelector`, que lança `SyntaxError`. O erro
   matava tudo que vinha depois no boot: carrossel da equipe, animações GSAP e
   ScrollTrigger nunca rodavam. Depois da correção: 25 elementos de carrossel e
   4 ScrollTriggers ativos, contra 0 e 0 antes.
3. **Dois contrastes abaixo de AA.** O selo "Novidade" (2,54:1) e o próprio skip
   link (1,56:1, vencido em especificidade por `body.aida-shell a`). Agora em
   4,75:1 e 7,76:1.

### Ainda em aberto

- `_teste-scanner.html` na raiz é uma página de diagnóstico interna servida
  publicamente. Não foi removida por estar fora do escopo do relatório.
- Três famílias tipográficas estavam em uso, não duas: Afacad, Montserrat
  (login) e Space Grotesk (admin). Todas foram unificadas em Afacad.
