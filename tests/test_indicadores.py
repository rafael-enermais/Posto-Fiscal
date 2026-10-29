# -*- coding: utf-8 -*-
"""Testes com dados INVENTADOS (nenhum dado real). Rodar: python tests/test_indicadores.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date, datetime
from app.dias_uteis import workday, networkdays
from app.planilha import Titulo, Planilha
from app.indicadores import d0, prazo, dias_uteis_ate_lancar, calcular, status_prazo

FER = [date(2026, 10, 12)]  # segunda-feira (feriado)


def teste_dias_uteis():
    assert workday(date(2026, 10, 9), 1, FER) == date(2026, 10, 13)   # sexta -> terca (pula sab, dom e feriado)
    assert workday(date(2026, 10, 9), 2, FER) == date(2026, 10, 14)
    assert networkdays(date(2026, 10, 9), date(2026, 10, 13), FER) == 2
    assert networkdays(date(2026, 10, 13), date(2026, 10, 9), FER) == -2


def teste_d0_e_prazo():
    a = Titulo(1, recebido=datetime(2026, 10, 14, 10, 0))                  # quarta, manha
    b = Titulo(2, recebido=datetime(2026, 10, 14, 16, 30))                 # depois das 16h -> proximo dia util
    c = Titulo(3, recebido=datetime(2026, 10, 14, 16, 30), urg="S")        # urgente -> mesmo dia
    d = Titulo(4, recebido=datetime(2026, 10, 17, 9, 0))                   # sabado -> segunda 19
    assert d0(a, FER) == date(2026, 10, 14) and prazo(a, FER) == date(2026, 10, 16)
    assert d0(b, FER) == date(2026, 10, 15)
    assert d0(c, FER) == date(2026, 10, 14)
    assert d0(d, FER) == date(2026, 10, 19)


def teste_indicadores():
    ts = [
        Titulo(2, recebido=datetime(2026, 10, 14, 10, 0), lancamento=datetime(2026, 10, 14, 15, 0), tipo_doc="NFS", setor="RH", fornecedor="A", num_doc="1", valor_bruto=100.0),
        Titulo(3, recebido=datetime(2026, 10, 14, 10, 0), lancamento=datetime(2026, 10, 20, 9, 0), tipo_doc="NFS", setor="RH", fornecedor="B", num_doc="2", valor_bruto=50.0, pc_ct="CT1"),
        Titulo(4, recebido=datetime(2026, 10, 14, 10, 0), tipo_doc="FVOL", setor="FROTAS", fornecedor="C", num_doc="3", valor_bruto=10.0),
        Titulo(5, recebido=datetime(2026, 10, 14, 10, 0), tipo_doc="FVOL", setor="FROTAS", fornecedor="C", num_doc="3", valor_bruto=10.0),
    ]
    p = Planilha(titulos=ts, feriados=FER, excecoes_sem_vinculo=[])
    r = calcular(p, date(2026, 10, 1), date(2026, 10, 31), hoje=date(2026, 10, 22))
    assert r["recebidos_n"] == 4 and r["lancados_n"] == 2
    assert r["no_prazo_n"] == 1 and r["fora_prazo_n"] == 1 and r["pendentes_fora_prazo_n"] == 2
    assert abs(r["pct_no_prazo"] - 0.25) < 1e-9
    assert r["possiveis_duplicidades"] == 2
    assert r["sem_vinculo_n"] == 3 and r["sem_vinculo_base_n"] == 4
    assert abs(r["tempo_medio_horas"] - (5 + 143) / 2) < 1e-6   # 5 h e 5 dias e 23 h = 143 h
    f = calcular(p, date(2026, 10, 1), date(2026, 10, 31), hoje=date(2026, 10, 22), tipos=["FVOL"])
    assert f["recebidos_n"] == 2 and f["por_tipo"] == {"FVOL": 2}


if __name__ == "__main__":
    teste_dias_uteis(); teste_d0_e_prazo(); teste_indicadores()
    print("testes ok")
