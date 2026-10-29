# Posto-Fiscal

Medição do Posto Fiscal da EnerMais (notas fiscais e contas a pagar). O Felipe sobe a planilha-base e o app completa as informações pelo Sienge (somente leitura) e calcula os indicadores. Streamlit + Supabase (schema `posto_fiscal`).

**Status:** planejamento. Hoje só existe o diagnóstico de leitura do Sienge (`scripts/diagnostico_sienge_titulos.py`, acionado à mão em Actions > "Diagnostico Sienge").

**Repositório público.** Nunca commitar chaves, senhas, planilhas reais nem dados de fornecedores. O log do GitHub Actions também é público: os scripts imprimem só contagens, códigos de tipo, datas e "preenchido sim/não". As credenciais ficam em Settings > Secrets and variables > Actions (`SIENGE_BASE_URL`, `SIENGE_USER`, `SIENGE_PASSWORD`).
