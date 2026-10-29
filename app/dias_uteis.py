# -*- coding: utf-8 -*-
"""Dias uteis no mesmo criterio do Excel (WORKDAY e NETWORKDAYS), com a lista de feriados da aba Parametros."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable


def so_data(x) -> date:
    return x.date() if isinstance(x, datetime) else x


def eh_util(d: date, feriados: set) -> bool:
    return d.weekday() < 5 and d not in feriados


def workday(inicio, n: int, feriados: Iterable = ()) -> date:
    """Igual ao WORKDAY do Excel: anda n dias uteis a partir de `inicio` (n pode ser negativo)."""
    fer = {so_data(f) for f in feriados}
    d = so_data(inicio)
    passo = 1 if n >= 0 else -1
    falta = abs(n)
    while falta > 0:
        d += timedelta(days=passo)
        if eh_util(d, fer):
            falta -= 1
    return d


def networkdays(a, b, feriados: Iterable = ()) -> int:
    """Igual ao NETWORKDAYS do Excel: conta dias uteis de a ate b, inclusive; negativo se a > b."""
    fer = {so_data(f) for f in feriados}
    a, b = so_data(a), so_data(b)
    if a > b:
        return -networkdays(b, a, fer)
    total, d = 0, a
    while d <= b:
        total += 1 if eh_util(d, fer) else 0
        d += timedelta(days=1)
    return total
