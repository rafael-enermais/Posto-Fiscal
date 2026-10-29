-- Posto-Fiscal | schema posto_fiscal | v1 de 29/10/2026 (OK do Rafael para criar o schema em 29/10)
-- Idempotente: so cria o que nao existe; nunca altera nem apaga nada de outros schemas.
-- Regras (ENERDATA/metricas.md seção 4): banco unico, 1 schema por app, so tabelas NOVAS no proprio schema,
-- nada de alterar ou apagar o que existe em outros schemas. As tres tabelas de metrica seguem o padrao comum.
-- Seguranca: login pelo Authentication do Supabase; RLS libera so os e-mails da tabela posto_fiscal.acesso.

create schema if not exists posto_fiscal;

-- 1) Cada envio da planilha pelo Felipe
create table if not exists posto_fiscal.carga (
  id            bigserial primary key,
  enviado_em    timestamptz not null default now(),
  enviado_por   text,
  arquivo_nome  text,
  arquivo_sha256 text,
  linhas        integer,
  periodo_ini   date,
  periodo_fim   date
);

-- 2) Linhas da aba Base (so os campos digitados; os de prazo sao recalculados pelo app)
create table if not exists posto_fiscal.titulo (
  titulo_ref     text primary key,              -- coluna "Titulo" da planilha = id do titulo no Sienge
  carga_id       bigint references posto_fiscal.carga(id),
  linha          integer,
  ref_origem     text,
  recebido       timestamp,                      -- data e hora do e-mail (so a planilha sabe)
  urgente        boolean not null default false,
  empresa        text,
  setor          text,
  tipo_doc       text,
  num_doc        text,
  fornecedor     text,
  cpf_cnpj       text,
  parcela        text,
  valor_bruto    numeric(15,2),
  retencoes      numeric(15,2),
  valor_liquido  numeric(15,2),
  emissao        date,
  vencimento     date,
  lancamento     timestamp,
  reprogramado   date,
  pc_ct          text,
  tipo_despesa   text,
  ret_conferidas text,                           -- S, N ou NA
  devolvida      text,                           -- S ou N
  obs            text,
  atualizado_em  timestamptz not null default now()
);
create index if not exists titulo_recebido_idx on posto_fiscal.titulo (recebido);

-- 3) O que o Sienge respondeu para cada titulo (consulta por numero, somente leitura)
create table if not exists posto_fiscal.titulo_sienge (
  titulo_ref    text primary key references posto_fiscal.titulo(titulo_ref),
  consultado_em timestamptz not null default now(),
  http          integer,
  encontrado    boolean not null,                -- false = 404 (excluido, cancelado ou relancado: a confirmar)
  tipo          text,
  emissao       date,
  cadastro      timestamp,                       -- registeredDate = hora do lancamento (I47)
  num_doc       text,
  cnpj_cpf      text,
  valor_total   numeric(15,2),
  tem_contrato  boolean,
  tem_medicao   boolean,
  tem_pedido    boolean,
  tem_chave     boolean,
  status        text,
  parcelas      jsonb,
  avisos        text[]                           -- codigos de comparacao com a planilha
);

-- 4) Padrao de metricas (ENERDATA/metricas.md seção 4)
create table if not exists posto_fiscal.metrica_registro (
  id               bigserial primary key,
  item_id          text not null,                -- I45..I49, E33..E38
  periodo          text not null,                -- AAAA-MM
  pessoa           text not null default 'Felipe',
  empresa          text,
  obra             text,
  un               text,
  app_origem       text not null default 'Posto-Fiscal',
  meta             text,
  previsto         numeric,
  realizado        numeric,
  numerador        numeric,
  denominador      numeric,
  pct_atingimento  numeric,
  status           text,                         -- No alvo | Atencao | Fora da meta | Sem lancamento
  origem           text,                         -- medido | checklist | manual
  detalhe          text,
  atualizado_em    timestamptz not null default now(),
  atualizado_por   text,
  unique nulls not distinct (item_id, periodo, empresa, obra, un)
);
create table if not exists posto_fiscal.metrica_ocorrencia (
  id            bigserial primary key,
  item_id       text not null,
  data_prevista date,
  data_feita    date,
  no_prazo      boolean,
  observacao    text
);
create table if not exists posto_fiscal.metrica_registro_hist (
  id             bigserial primary key,
  registro_id    bigint references posto_fiscal.metrica_registro(id),
  quem           text,
  quando         timestamptz not null default now(),
  valor_anterior text,
  motivo         text
);

-- 5) Quem pode entrar: login pelo Authentication do Supabase + lista de e-mails autorizados
create table if not exists posto_fiscal.acesso (
  email  text primary key,
  nome   text,
  papel  text not null default 'usuario',         -- usuario | admin (so informativo por enquanto)
  ativo  boolean not null default true
);

create or replace function posto_fiscal.tem_acesso() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from posto_fiscal.acesso a
    where a.ativo and lower(a.email) = lower(coalesce(auth.jwt() ->> 'email', ''))
  );
$$;

-- 6) RLS ligado em tudo; so quem esta na lista (e logado) le e grava
alter table posto_fiscal.acesso                enable row level security;
alter table posto_fiscal.carga                 enable row level security;
alter table posto_fiscal.titulo                enable row level security;
alter table posto_fiscal.titulo_sienge         enable row level security;
alter table posto_fiscal.metrica_registro      enable row level security;
alter table posto_fiscal.metrica_ocorrencia    enable row level security;
alter table posto_fiscal.metrica_registro_hist enable row level security;

drop policy if exists acesso_proprio on posto_fiscal.acesso;
create policy acesso_proprio on posto_fiscal.acesso for select to authenticated
  using (lower(email) = lower(coalesce(auth.jwt() ->> 'email', '')));

do $$
declare t text;
begin
  foreach t in array array['carga','titulo','titulo_sienge','metrica_registro','metrica_ocorrencia','metrica_registro_hist']
  loop
    execute format('drop policy if exists %I on posto_fiscal.%I', t || '_lista', t);
    execute format('create policy %I on posto_fiscal.%I for all to authenticated using (posto_fiscal.tem_acesso()) with check (posto_fiscal.tem_acesso())', t || '_lista', t);
  end loop;
end $$;

-- 7) Permissoes: anonimo nao ve nada; logado le/grava mas NAO apaga; chave de servico para rotinas futuras
revoke all on schema posto_fiscal from anon;
revoke all on all tables in schema posto_fiscal from anon;
grant usage on schema posto_fiscal to authenticated, service_role;
grant select on posto_fiscal.acesso to authenticated;
grant select, insert, update on posto_fiscal.carga, posto_fiscal.titulo, posto_fiscal.titulo_sienge,
      posto_fiscal.metrica_registro, posto_fiscal.metrica_ocorrencia, posto_fiscal.metrica_registro_hist to authenticated;
grant usage, select on all sequences in schema posto_fiscal to authenticated;
grant execute on function posto_fiscal.tem_acesso() to authenticated;
grant all on all tables in schema posto_fiscal to service_role;
grant usage, select on all sequences in schema posto_fiscal to service_role;

-- 8) Incluir quem pode entrar (o usuario precisa existir antes no Authentication do Supabase).
--    O e-mail NAO fica neste arquivo (repositorio publico); rodar a linha abaixo a parte, com o e-mail certo:
--    insert into posto_fiscal.acesso (email, nome, papel) values ('<e-mail>', '<nome>', 'admin') on conflict (email) do nothing;

-- Ainda NAO desenhado: aba Pendencias (estoque, I46/E37), checklist E34/E35/E38 e a visao somente leitura
-- no schema `diretoria`. Entram na proxima versao.
