# -*- coding: utf-8 -*-
"""Indicadores do Felipe no primeiro corte (so planilha), com o mesmo criterio da aba Indicadores v5.

Prazo = 2 dias uteis (decisao do Rafael, 28/10). Periodo = pelo D0 (data de recebimento considerada).
Cada funcao devolve numeros e contagens; nada aqui imprime nome, CNPJ ou valor de fornecedor.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time
from typing import Optional

from .dias_uteis import eh_util, networkdays, so_data, workday
from .planilha import Planilha, Titulo

PRAZO_DIAS_UTEIS = 2
META_NO_PRAZO = 0.95        # E33 (>= 95%)
META_TEMPO_MEDIO = 1.0      # I47 (<= 1 dia, planilha mede em dias uteis)
SETORES_COM_VINCULO = ("FROTAS", "RH", "OUTRAS DESPESAS")


def d0(t: Titulo, feriados) -> Optional[date]:
    """Data de recebimento considerada: urgente = mesmo dia; depois das 16h ou em dia nao util = proximo dia util."""
    if t.recebido is None:
        return None
    dia = so_data(t.recebido)
    if t.urg == "S":
        return dia
    fer = {so_data(f) for f in feriados}
    if t.recebido.time() > time(16, 0, 0) or not eh_util(dia, fer):
        return workday(dia, 1, fer)
    return dia


def prazo(t: Titulo, feriados) -> Optional[date]:
    base = d0(t, feriados)
    return workday(base, PRAZO_DIAS_UTEIS, feriados) if base else None


def dias_uteis_ate_lancar(t: Titulo, feriados) -> Optional[int]:
    base = d0(t, feriados)
    if base is None or t.lancamento is None:
        return None
    return networkdays(base, so_data(t.lancamento), feriados) - 1


def horas_ate_lancar(t: Titulo) -> Optional[float]:
    """I47 como o Rafael definiu: recebido (e-mail) ate a hora do lancamento, em horas corridas."""
    if t.recebido is None or t.lancamento is None:
        return None
    return (t.lancamento - t.recebido).total_seconds() / 3600.0


def status_prazo(t: Titulo, feriados, hoje: date) -> str:
    base = prazo(t, feriados)
    if base is None:
        return ""
    if t.lancamento is None:
        return "Pendente - fora do prazo" if hoje > base else "Pendente - no prazo"
    return "No prazo" if so_data(t.lancamento) <= base else "Fora do prazo"


def sem_vinculo(t: Titulo, excecoes) -> str:
    """'S' quando o setor exige pedido/contrato, o tipo de despesa nao e excecao e PC/CT esta vazio."""
    if t.setor not in SETORES_COM_VINCULO or t.tipo_despesa in set(excecoes):
        return "N"
    return "S" if not t.pc_ct else "N"


def duplicados(titulos: list) -> set:
    """Linhas com mesmo fornecedor + numero do documento + valor bruto + parcela (aviso 'Verificar')."""
    chaves = defaultdict(list)
    for t in titulos:
        if t.fornecedor and t.num_doc:
            chaves[(t.fornecedor, t.num_doc, t.valor_bruto, t.parcela)].append(t.linha)
    return {ln for lns in chaves.values() if len(lns) > 1 for ln in lns}


def calcular(p: Planilha, ini: date, fim: date, hoje: Optional[date] = None, tipos: Optional[list] = None) -> dict:
    hoje = hoje or date.today()
    fer = p.feriados
    dup = duplicados(p.titulos)
    sel = []
    for t in p.titulos:
        base = d0(t, fer)
        if base is None or not (ini <= base <= fim):
            continue
        if tipos and t.tipo_doc not in tipos:
            continue
        sel.append(t)
    lancados = [t for t in sel if t.lancamento is not None]
    st = Counter(status_prazo(t, fer, hoje) for t in sel)
    du = [x for x in (dias_uteis_ate_lancar(t, fer) for t in sel) if x is not None]
    hs = [x for x in (horas_ate_lancar(t) for t in sel) if x is not None]
    n_prazo, n_fora, n_pf = st["No prazo"], st["Fora do prazo"], st["Pendente - fora do prazo"]
    den = n_prazo + n_fora + n_pf
    ret_s = sum(1 for t in sel if t.ret_conferidas == "S")
    ret_n = sum(1 for t in sel if t.ret_conferidas == "N")
    devolvidas = sum(1 for t in sel if t.devolvida == "S")
    apos_venc = sum(1 for t in lancados if t.vencimento and so_data(t.lancamento) > t.vencimento)
    base_sv = [t for t in sel if t.setor in SETORES_COM_VINCULO and t.tipo_despesa not in set(p.excecoes_sem_vinculo)]
    sv = [t for t in base_sv if not t.pc_ct]
    return {
        "periodo": (ini, fim),
        "recebidos_n": len(sel),
        "recebidos_valor": sum(t.valor_bruto or 0 for t in sel),
        "lancados_n": len(lancados),
        "lancados_valor": sum(t.valor_bruto or 0 for t in lancados),
        "pct_lancados": (len(lancados) / len(sel)) if sel else None,
        "tempo_medio_dias_uteis": (sum(du) / len(du)) if du else None,      # I47 no criterio da planilha
        "tempo_medio_horas": (sum(hs) / len(hs)) if hs else None,           # I47 pela definicao do Rafael (29/10)
        "no_prazo_n": n_prazo, "fora_prazo_n": n_fora,
        "pendentes_fora_prazo_n": n_pf, "pendentes_no_prazo_n": st["Pendente - no prazo"],
        "pct_no_prazo": (n_prazo / den) if den else None,                   # E33 (meta >= 95%)
        "lancados_apos_vencimento": apos_venc,
        "possiveis_duplicidades": sum(1 for t in sel if t.linha in dup),
        "devolvidas_n": devolvidas,
        "pct_devolvidas": (devolvidas / len(sel)) if sel else None,         # I49 (meta < 2%)
        "retencoes_conferidas_n": ret_s, "retencoes_sem_conferencia_n": ret_n,
        "pct_retencoes": (ret_s / (ret_s + ret_n)) if (ret_s + ret_n) else None,   # E35 (meta 100%)
        "sem_vinculo_base_n": len(base_sv), "sem_vinculo_n": len(sv),       # I48 no criterio da planilha
        "por_tipo": dict(Counter(t.tipo_doc or "(vazio)" for t in sel)),
        "por_setor": dict(Counter(t.setor or "(vazio)" for t in sel)),
    }
