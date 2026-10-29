# -*- coding: utf-8 -*-
"""Posto-Fiscal | tela do Felipe (RASCUNHO v0.1, primeiro corte: so planilha + conferencia opcional com o Sienge).

Rodar: streamlit run app/streamlit_app.py
Entrada pelo Authentication do Supabase (e-mail e senha) e lista de e-mails em posto_fiscal.acesso.
Grava a planilha em posto_fiscal.titulo e o resultado da conferencia em posto_fiscal.titulo_sienge; nunca altera a planilha.
A conferencia com o Sienge so le (GET) e so liga se existirem os Secrets do Sienge.
Teste local sem banco: POSTO_MODO_LOCAL=1 (sem login e sem gravar). Em producao NAO definir essa variavel.
"""
from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import streamlit as st

import hashlib

from app.banco import entrar, sair, salvar_planilha, salvar_sienge
from app.indicadores import (META_NO_PRAZO, META_TEMPO_MEDIO, PRAZO_DIAS_UTEIS, calcular, d0, prazo,
                             status_prazo)
from app.planilha import ler_planilha
from app.sienge_leitura import SiengeSomenteLeitura, comparar

st.set_page_config(page_title="Posto-Fiscal", layout="wide")


def pct(x):
    return "-" if x is None else f"{x * 100:.1f}%".replace(".", ",")


def num(x, casas=1, suf=""):
    return "-" if x is None else f"{x:.{casas}f}".replace(".", ",") + suf


def moeda(x):
    return "R$ " + f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def segredo(nome: str) -> str:
    """Le primeiro da variavel de ambiente (o Streamlit Cloud tambem expoe os segredos assim);
    so consulta st.secrets se existir secrets.toml, porque sem o arquivo o Streamlit mostra uma caixa de erro."""
    v = os.environ.get(nome, "")
    if v:
        return v
    for caminho in (os.path.join(".streamlit", "secrets.toml"), os.path.expanduser("~/.streamlit/secrets.toml"),
                    "/mount/src"):   # /mount/src existe no Streamlit Community Cloud
        if os.path.exists(caminho):
            try:
                return st.secrets.get(nome, "") or ""
            except Exception:
                return ""
    return ""


MODO_LOCAL = os.environ.get("POSTO_MODO_LOCAL") == "1"
SB_URL, SB_CHAVE = segredo("SUPABASE_URL"), segredo("SUPABASE_ANON_KEY")

st.title("Posto-Fiscal")
if MODO_LOCAL:
    st.warning("Modo local: sem login e sem gravação no banco.")
else:
    if not (SB_URL and SB_CHAVE):
        st.error("Configuração ausente: defina SUPABASE_URL e SUPABASE_ANON_KEY nos Secrets.")
        st.stop()
    if "sb" not in st.session_state:
        st.subheader("Entrar")
        with st.form("login"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            ok = st.form_submit_button("Entrar")
        if ok:
            try:
                st.session_state["sb"], st.session_state["usuario"] = entrar(SB_URL, SB_CHAVE, email, senha)
                st.rerun()
            except PermissionError as e:
                st.error(str(e))
            except Exception:
                st.error("E-mail ou senha inválidos.")
        st.stop()
    st.sidebar.write(f"Logado: {st.session_state['usuario']}")
    if st.sidebar.button("Sair"):
        sair(st.session_state.pop("sb"))
        st.session_state.pop("usuario", None)
        st.rerun()
st.caption(f"Contas a pagar · prazo de lançamento: {PRAZO_DIAS_UTEIS} dias úteis · primeiro corte (só planilha)")

arquivo = st.file_uploader("Planilha-base (aba Base)", type=["xlsx"])
if not arquivo:
    st.info("Envie a planilha do dia para ver os indicadores.")
    st.stop()

p = ler_planilha(arquivo)
for aviso in p.avisos:
    st.warning(aviso)
if not p.titulos:
    st.error("Nenhuma linha com data de recebimento ou título na aba Base.")
    st.stop()

bases = [d for d in (d0(t, p.feriados) for t in p.titulos) if d]
c1, c2, c3 = st.columns([1, 1, 2])
ini = c1.date_input("De (data de recebimento considerada)", min(bases))
fim = c2.date_input("Até", max(bases))
tipos_disp = sorted({t.tipo_doc for t in p.titulos if t.tipo_doc})
tipos = c3.multiselect("Tipo de documento (vazio = todos)", tipos_disp)

r = calcular(p, ini, fim, hoje=date.today(), tipos=tipos or None)

if not MODO_LOCAL:
    if st.button("Gravar esta planilha no banco"):
        try:
            arquivo.seek(0)
            sha = hashlib.sha256(arquivo.read()).hexdigest()
            res = salvar_planilha(st.session_state["sb"], p, getattr(arquivo, "name", ""), sha, ini, fim,
                                  st.session_state["usuario"])
            st.success(f"Gravado: {res['gravados']} títulos (envio nº {res['carga_id']}); {res['fora']} ficaram de fora por falta de número ou repetição.")
        except Exception:
            st.error("Não consegui gravar. Confira o login e se o schema posto_fiscal está exposto na API do Supabase.")

st.subheader("Fluxo e prazo")
a, b, c, d = st.columns(4)
a.metric("Recebidos", r["recebidos_n"], moeda(r["recebidos_valor"]))
b.metric("Lançados", r["lancados_n"], pct(r["pct_lancados"]))
c.metric(f"No prazo ({PRAZO_DIAS_UTEIS} dias úteis)", pct(r["pct_no_prazo"]), f"meta ≥ {int(META_NO_PRAZO * 100)}%")
d.metric("Tempo médio até lançar", num(r["tempo_medio_dias_uteis"], 2, " dia útil"),
         f"{num(r['tempo_medio_horas'], 1, ' h')} corridas · meta ≤ {int(META_TEMPO_MEDIO)} dia")
e, f, g, h = st.columns(4)
e.metric("Lançados fora do prazo", r["fora_prazo_n"])
f.metric("Pendentes fora do prazo", r["pendentes_fora_prazo_n"])
g.metric("Pendentes ainda no prazo", r["pendentes_no_prazo_n"])
h.metric("Possíveis duplicidades", r["possiveis_duplicidades"])

st.subheader("Qualidade e vínculo")
i, j, k = st.columns(3)
i.metric("Devolvidas/relançadas", pct(r["pct_devolvidas"]), "meta < 2%")
j.metric("Retenções conferidas", pct(r["pct_retencoes"]), "meta 100%")
k.metric("Sem pedido/contrato (critério da planilha)", f'{r["sem_vinculo_n"]} de {r["sem_vinculo_base_n"]}', "meta 0")
st.caption("Atenção: este indicador usa o campo PC/CT digitado. O pedido de compra do Sienge vem vazio nos títulos normais, então a etapa 2 não pode contar com ele.")

col_t, col_s = st.columns(2)
col_t.write("Por tipo de documento")
col_t.dataframe(pd.Series(r["por_tipo"], name="títulos").sort_values(ascending=False))
col_s.write("Por setor")
col_s.dataframe(pd.Series(r["por_setor"], name="títulos").sort_values(ascending=False))

st.subheader("Pendentes de lançamento")
hoje = date.today()
linhas = []
for t in p.titulos:
    base = d0(t, p.feriados)
    if base is None or not (ini <= base <= fim) or (tipos and t.tipo_doc not in tipos):
        continue
    s = status_prazo(t, p.feriados, hoje)
    if s.startswith("Pendente"):
        linhas.append({"Título": t.titulo, "Tipo": t.tipo_doc, "Setor": t.setor, "Recebido": t.recebido,
                       "Prazo": prazo(t, p.feriados), "Situação": s})
st.dataframe(pd.DataFrame(linhas), use_container_width=True)

st.subheader("Conferência com o Sienge (somente leitura)")
base_url, usuario, senha = segredo("SIENGE_BASE_URL"), segredo("SIENGE_USER"), segredo("SIENGE_PASSWORD")
if not (base_url and usuario and senha):
    st.caption("Desligada: faltam os Secrets SIENGE_BASE_URL, SIENGE_USER e SIENGE_PASSWORD.")
else:
    limite = st.number_input("Quantos títulos conferir agora (do primeiro ao último da lista)", 1, 300, 20)
    if st.button("Conferir com o Sienge"):
        cli = SiengeSomenteLeitura(base_url, usuario, senha)
        resultado, guardar = [], []
        alvo = [t for t in p.titulos if t.titulo.isdigit()][: int(limite)]
        barra = st.progress(0.0)
        for n, t in enumerate(alvo, start=1):
            s = cli.consultar_titulo(int(t.titulo))
            av = comparar(t, s)
            guardar.append((t.titulo, s, av))
            resultado.append({"Título": t.titulo, "Avisos": ", ".join(av) or "sem diferença"})
            barra.progress(n / len(alvo))
        st.session_state["conferencia"] = (guardar, resultado)
    if "conferencia" in st.session_state:
        guardar, resultado = st.session_state["conferencia"]
        st.dataframe(pd.DataFrame(resultado), use_container_width=True)
        if not MODO_LOCAL and st.button("Gravar esta conferência no banco"):
            try:
                n = salvar_sienge(st.session_state["sb"], guardar)
                st.success(f"Gravadas {n} conferências. (Grave a planilha antes, para os títulos existirem no banco.)")
            except Exception:
                st.error("Não consegui gravar a conferência. Grave a planilha primeiro e confira a exposição do schema.")
