# -*- coding: utf-8 -*-
"""Testa a trava de leitura e a comparacao, sem rede e com dados inventados."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date, datetime
from app.sienge_leitura import SiengeSomenteLeitura, CaminhoNaoPermitido, CAMINHOS_PERMITIDOS, TituloSienge, Parcela, comparar
from app.planilha import Titulo


class Falso(SiengeSomenteLeitura):
    """Sienge de mentira: responde sem rede, mas passa pela mesma trava de caminhos."""

    def __init__(self):
        super().__init__("https://exemplo.invalido/api", "u", "s", pausa=0)

    def _get(self, caminho):
        if not any(rx.match(caminho) for rx in CAMINHOS_PERMITIDOS):
            raise CaminhoNaoPermitido("x")
        if caminho == "/v1/bills/1":
            return 200, {"id": 1, "documentIdentificationId": "NFS ", "issueDate": "2026-10-20", "registeredDate": "2026-10-22 10:00:00",
                         "documentNumber": "99", "creditorId": 7, "purchaseOrderId": 0, "contractNumber": "C1"}
        if caminho == "/v1/bills/1/installments":
            return 200, {"results": [{"installmentNumber": 1, "dueDate": "2026-11-10", "amount": 10.0}]}
        if caminho == "/v1/creditors/7":
            return 200, {"cnpj": "00000000000000"}
        return 404, None


def teste_trava():
    c = SiengeSomenteLeitura("https://exemplo.invalido/api", "u", "s", pausa=0)
    for ruim in ("/v1/bills", "/v1/bills/1/payments", "/v1/bills/abc", "/v1/bills/1?x=1", "/v1/bills/1/../2"):
        try:
            c._get(ruim)
            raise AssertionError("deveria bloquear " + ruim)
        except CaminhoNaoPermitido:
            pass


def teste_consulta_e_comparacao():
    f = Falso()
    t = f.consultar_titulo(1)
    assert t.encontrado and t.tipo == "NFS" and t.tem_contrato and not t.tem_pedido and len(t.parcelas) == 1 and t.cnpj_cpf
    assert not f.consultar_titulo(2).encontrado
    pl = Titulo(2, tipo_doc="NFS", emissao=date(2026, 10, 20), vencimento=date(2026, 11, 11), num_doc="", lancamento=datetime(2026, 10, 22, 10, 5))
    assert comparar(pl, t) == ["VENCIMENTO_DIFERENTE", "NUM_DOC_SO_NO_SIENGE"]
    assert comparar(pl, f.consultar_titulo(2)) == ["NAO_ENCONTRADO_NO_SIENGE"]


if __name__ == "__main__":
    teste_trava(); teste_consulta_e_comparacao(); print("testes ok")
