# -*- coding: utf-8 -*-
"""Testa a preparacao das linhas (sem rede, dados inventados)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date, datetime
from app.banco import linhas_titulo, linha_sienge
from app.planilha import Titulo
from app.sienge_leitura import TituloSienge, Parcela


def teste_linhas_titulo():
    ts = [Titulo(2, titulo="10", urg="S", recebido=datetime(2026, 10, 1, 9, 0), valor_bruto=5.0),
          Titulo(3, titulo="10", recebido=datetime(2026, 10, 2, 9, 0)),      # repetido: fica a ultima
          Titulo(4, titulo=""),                                              # sem numero: fica fora
          Titulo(5, titulo="11", emissao=date(2026, 10, 3))]
    linhas, fora = linhas_titulo(ts, 7)
    assert fora == 2 and [x["titulo_ref"] for x in linhas] == ["10", "11"]
    assert linhas[0]["linha"] == 3 and linhas[0]["recebido"].startswith("2026-10-02") and linhas[0]["urgente"] is False
    assert linhas[1]["emissao"] == "2026-10-03" and linhas[1]["carga_id"] == 7


def teste_linha_sienge():
    s = TituloSienge(id=1, http=200, encontrado=True, tipo="NFS", emissao=date(2026, 10, 1),
                     cadastro=datetime(2026, 10, 2, 10, 0), parcelas=[Parcela(1, date(2026, 11, 1), 9.5)])
    r = linha_sienge("1", s, ["TIPO_DIFERENTE"])
    assert r["parcelas"] == [{"n": 1, "venc": "2026-11-01", "valor": 9.5}] and r["avisos"] == ["TIPO_DIFERENTE"]
    assert r["cadastro"] == "2026-10-02T10:00:00"


if __name__ == "__main__":
    teste_linhas_titulo(); teste_linha_sienge(); print("testes ok")
