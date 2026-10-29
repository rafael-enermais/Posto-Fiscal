# Posto-Fiscal

Medição do Posto Fiscal da EnerMais (notas fiscais e contas a pagar). O Felipe sobe a planilha-base, o app calcula os indicadores (prazo de 2 dias úteis) e confere cada título no Sienge (somente leitura). Streamlit + Supabase (schema `posto_fiscal`, projeto `radar-comercial`).

**Status:** v0.1 em montagem. Pronto: leitura da planilha, indicadores, login pelo Authentication do Supabase, gravação no schema `posto_fiscal`, conferência com o Sienge. Falta: aba Pendências, checklists, relatório semanal.

**Repositório público.** Nunca commitar chaves, senhas, planilhas reais nem dados de fornecedores (`.gitignore` já barra `.xlsx`, `.csv`, `.json`). O log do GitHub Actions também é público: os scripts imprimem só contagens, ids, tipos, datas e "preenchido sim/não".

## Pastas
- `app/` — código do app (`streamlit_app.py` é a tela; `requirements.txt` desta pasta é o que o Streamlit Cloud instala).
- `sql/` — schema do banco (`001_schema_posto_fiscal.sql`, já executado em 29/10/2026).
- `scripts/` e `.github/workflows/` — diagnósticos somente leitura do Sienge, acionados à mão em Actions.
- `tests/` — testes com dados inventados: `python tests/test_indicadores.py` (idem `test_sienge_leitura.py`, `test_banco.py`).

## Segredos (Settings do Streamlit Cloud > Secrets, ou GitHub > Settings > Secrets and variables > Actions)
- App: `SUPABASE_URL`, `SUPABASE_ANON_KEY` (chave pública `anon`; a chave `service_role` nunca entra no app).
- Conferência com o Sienge (opcional no app; usados nos workflows): `SIENGE_BASE_URL`, `SIENGE_USER`, `SIENGE_PASSWORD` (só leitura).

## Entrada
Login com e-mail e senha criados no Authentication do Supabase. Só entra quem também estiver em `posto_fiscal.acesso` (regra no banco, não no app).

## Rodar no computador
`pip install -r app/requirements.txt` e `POSTO_MODO_LOCAL=1 streamlit run app/streamlit_app.py` (modo local: sem login e sem gravar; em produção essa variável NÃO existe).
