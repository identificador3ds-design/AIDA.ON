-- ---------------------------------------------------------------------------
-- AIDA — reabertura de uma análise do histórico no AIDA Forensics
-- ---------------------------------------------------------------------------
--
-- Duas colunas, deliberadamente curtas.
--
-- O que o Forensics precisa para reconstruir a investigação (mapas de
-- evidência, scores por módulo, metadados, proveniência, qualidade) já está no
-- cache do servidor de análise, indexado por `analysis_id`. Copiar esse
-- conteúdo para o Supabase multiplicaria o armazenamento por análise —
-- dezenas de kB de JSON e vários PNGs por linha — sem nenhum ganho: a mesma
-- informação passaria a existir em dois lugares, com risco de divergirem.
--
-- Por isso persistimos só o ponteiro:
--
--   analysis_id  identificador devolvido por POST /analisar
--   api_base     origem que atendeu a análise. A mesma conta pode ter análises
--                feitas no backend local e no publicado, e o identificador só
--                vale na base que o gerou.
--
-- Consequência aceita: o cache do servidor expira (sete dias, por padrão, via
-- AIDA_CACHE_TTL_H). Análises antigas deixam de abrir, e a tela do Forensics
-- trata esse caso pedindo uma nova análise. Persistir o dossiê inteiro para
-- evitar a expiração é uma decisão de armazenamento que ainda não se
-- justifica — e deve ser tomada com medição, não por precaução.
--
-- Execute no SQL Editor do Supabase. É idempotente.
-- ---------------------------------------------------------------------------

alter table public.historico_analises
  add column if not exists analysis_id text,
  add column if not exists api_base    text;

comment on column public.historico_analises.analysis_id is
  'ID da análise no servidor do AIDA. Abre GET /forense/<id> enquanto o cache existir.';

comment on column public.historico_analises.api_base is
  'Origem HTTP que executou a análise. O analysis_id só é válido nesta base.';

-- Busca por análise costuma vir filtrada por usuário e ordenada por data; o
-- índice parcial cobre a consulta da tela do histórico sem inchar a tabela com
-- linhas antigas que nunca tiveram identificador.
create index if not exists historico_analises_analysis_id_idx
  on public.historico_analises (user_id, analysis_id)
  where analysis_id is not null;
