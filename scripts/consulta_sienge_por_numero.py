# -*- coding: utf-8 -*-
"""Posto-Fiscal | Consulta SOMENTE LEITURA: acha titulo(s) do Sienge pelo numero do documento e lista vizinhos.

Para entender casos como "titulo da planilha que o Sienge devolve 404" (ex.: pro-forma retificada e relancada).
REPOSITORIO PUBLICO: o log e publico. Imprime SO id, tipo, datas, status e contagem de parcelas.
Nunca imprime fornecedor, CNPJ, valores, observacoes ou usuario.

Variaveis: SIENGE_BASE_URL, SIENGE_USER, SIENGE_PASSWORD (Secrets);
NUMERO (numero do documento, ex. 245), TIPO (opcional, ex. PRO), DIAS (janela, padrao 60),
VIZINHOS (faixa de ids, ex. 38385-38395, opcional).
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

from diagnostico_sienge_titulos import Cliente, LIM, _env, dia


def linha(c: dict, parcelas=None) -> str:
    return (f"id={c.get('id')} | tipo={(c.get('documentIdentificationId') or '').strip()} | emissao={dia(c.get('issueDate'))}"
            f" | cadastro={str(c.get('registeredDate') or '')[:19]} | status={c.get('status')}"
            + (f" | parcelas={parcelas}" if parcelas is not None else ""))


def main() -> int:
    cli = Cliente(_env("SIENGE_BASE_URL"), _env("SIENGE_USER"), _env("SIENGE_PASSWORD"))
    numero = (os.environ.get("NUMERO") or "").strip()
    tipo = (os.environ.get("TIPO") or "").strip().upper()
    dias = int((os.environ.get("DIAS") or "60").strip() or "60")
    viz = (os.environ.get("VIZINHOS") or "").strip()
    hoje = date.today()
    print(f"Consulta somente leitura | {hoje} | numero={numero or '-'} tipo={tipo or '-'} janela={dias} dias")
    achados, status_n, total, offset = [], [], 0, 0
    while offset < LIM * 60:
        st, c = cli.get("/v1/bills", {"startDate": (hoje - timedelta(days=dias)).isoformat(),
                                      "endDate": hoje.isoformat(), "limit": LIM, "offset": offset})
        if st != 200:
            print(f"HTTP {st} no offset {offset}; parando.")
            break
        rs = c.get("results", c) if isinstance(c, dict) else c
        if not rs:
            break
        for b in rs:
            total += 1
            t = (b.get("documentIdentificationId") or "").strip().upper()
            if numero and str(b.get("documentNumber") or "").strip() == numero and (not tipo or t == tipo):
                achados.append(b)
            if str(b.get("status")) == "N":
                status_n.append(b)
        if len(rs) < LIM:
            break
        offset += LIM
    print(f"varridos {total} titulos")
    print(f"== titulos com documento {numero} (tipo {tipo or 'qualquer'}): {len(achados)} ==")
    for b in achados:
        st2, p = cli.get(f"/v1/bills/{b.get('id')}/installments")
        n = len((p.get("results") if isinstance(p, dict) else None) or [])
        print(linha(b, n))
    print(f"== titulos com status N na janela: {len(status_n)} ==")
    for b in status_n[:20]:
        print(linha(b))
    if "-" in viz:
        a, z = viz.split("-", 1)
        print(f"== vizinhos {a} a {z} ==")
        for i in range(int(a), int(z) + 1):
            st, c = cli.get(f"/v1/bills/{i}")
            print(linha(c) if st == 200 and isinstance(c, dict) else f"id={i} | HTTP {st}")
    print("\nConcluido. Nada foi gravado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
