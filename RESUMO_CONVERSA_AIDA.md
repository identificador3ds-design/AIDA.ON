# Resumo da Consultoria Técnica - AIDA API

Este documento contém o resumo de tudo o que configuramos, resolvemos e aprendemos sobre a arquitetura da sua API em produção.

## 1. Testando a API no Postman
- **Coleção Criada**: Foi gerado o arquivo `AIDA_API_Postman_Collection.json` com as rotas públicas (informações e contrato) e protegidas (análise de imagens) já configuradas.
- **Erro `EISDIR`**: Se ocorrer esse erro ao anexar a imagem no Postman, significa que você selecionou uma pasta ao invés do arquivo. Para resolver, remova o anexo na aba *Body* e selecione o arquivo de imagem diretamente.

## 2. Deploy no Hugging Face (Erro de Configuração)
Ao hospedar a **API Borda** no Hugging Face, ocorreu um "Configuration error". Para resolver isso, foram necessários dois passos:
1. **Adicionar o SDK no `README.md`**: Colocar o seguinte bloco no topo absoluto do arquivo:
   ```yaml
   ---
   title: Aida Borda Api
   emoji: 🚀
   colorFrom: blue
   colorTo: green
   sdk: docker
   pinned: false
   ---
   ```
2. **Criar o arquivo `Dockerfile`**: Foi necessário criar um `Dockerfile` na raiz do Space no Hugging Face para instalar as dependências e colocar os arquivos dentro de uma pasta `aida_api/` (resolvendo os erros de *relative import* do Python), expondo a porta `7860`.

## 3. Integração com o Cliente (Front-end B2B)
- Foi criado o arquivo `exemplo_cliente.html`. 
- Ele serve para demonstrar como o site de uma empresa terceira (seu cliente) faria a integração via JavaScript (`fetch()`) com a sua API hospedada no Hugging Face.
- Ele conta com interface moderna e processa o JSON da API devolvendo de forma legível a porcentagem, veredito (REAL/IA) e confiança.

## 4. Como funciona a "Venda" de Chaves (Rate Limit)
- A chave de API não é de uso único, mas funciona como um "crachá" para a empresa consumidora.
- **Janela Deslizante:** O sistema conta as requisições baseadas em tempo. Por padrão (`config.py`), o limite é de 60 análises a cada 1 hora. Se exceder, a API retorna erro `429 Too Many Requests`.
- **Modelo de Negócios:** Você vende *Planos Mensais de Volume*. O "Plano Básico" pode ter uma chave limitada a 100 análises/hora, enquanto o "Plano Pro" tem 10.000 análises/hora. 

## 5. Como gerar chaves reais (Conexão Supabase)
Para que a geração de chaves funcione com segurança, o sistema exige um banco de dados Supabase:
1. Copie o script SQL localizado em `aida_api/migracoes/migracao-api-keys.sql` e execute no painel do seu Supabase para criar as tabelas.
2. Pegue o `Project URL` e a `service_role secret` no Supabase.
3. No seu terminal (PowerShell), defina as variáveis e emita a chave para o seu cliente:
   ```powershell
   $env:SUPABASE_URL="https://sua-url.supabase.co"
   $env:SUPABASE_SERVICE_ROLE_KEY="sua_chave_secreta"
   
   python -m aida_api.gerenciar_chaves emitir "Nome do Cliente" --limite 100
   ```
O Supabase vai criptografar a chave. O terminal mostrará o Bearer Token que o seu cliente usará nas requisições. 

---
**Nota:** Para testes rápidos na nuvem do Hugging Face sem conectar o Supabase, basta ir na aba *Settings > Variables and secrets* do Space e criar a variável `AIDA_API_DEV_KEYS` com o valor `aida_teste`.
