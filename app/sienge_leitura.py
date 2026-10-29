# -*- coding: utf-8 -*-
"""Consulta SOMENTE LEITURA ao Sienge, titulo por titulo (caminho A, decidido em 29/10).

Trava de seguranca: so existe GET e so para 3 caminhos (titulo, parcelas, credor). Qualquer outro caminho
levanta erro antes de sair da maquina. Este modulo nunca imprime nada; quem chama decide o que mostrar
(em repositorio publico, log so com contagens).
Variaveis: SIENGE_BASE_URL, SIENGE_USER, SIENGE_PASSWORD (Secrets; o Claude nunca ve os valores).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

CAMINHOS_PERMITIDOS = (
    re.compile(r"^/v1/bills/\d+$"),
    re.compile(r"^/v1/bills/\d+/installments$"),
    re.compile(r"^/v1/creditors/\d+$"),
)


class CaminhoNaoPermitido(Exception):
    pass


def _preenchido(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, (int, float)):
        return v != 0
    return bool(v)


def _data(v) -> Optional[date]:
    return datetime.fromisoformat(str(v)[:10]).date() if v else None


def _data_hora(v) -> Optional[datetime]:
    if not v:
        return None
    s = str(v).replace("T", " ")[:19]
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


@dataclass
class Parcela:
    numero: Optional[int]
    vencimento: Optional[date]
    valor: Optional[float]


@dataclass
class TituloSienge:
    id: int
    http: int
    encontrado: bool = False
    tipo: str = ""
    emissao: Optional[date] = None
    cadastro: Optional[datetime] = None
    num_doc: str = ""
    credor_id: Optional[int] = None
    cnpj_cpf: str = ""
    valor_total: Optional[float] = None
    tem_contrato: bool = False
    tem_medicao: bool = False
    tem_pedido: bool = False
    tem_chave: bool = False
    status: str = ""
    parcelas: list = field(default_factory=list)


class SiengeSomenteLeitura:
    def __init__(self, base_url: str, usuario: str, senha: str, pausa: float = 0.15, tentativas: int = 3):
        self.base = base_url.rstrip("/")
        self.pausa = pausa
        self.tentativas = tentativas
        self.s = requests.Session()
        self.s.auth = HTTPBasicAuth(usuario, senha)
        self._credores: dict = {}

    def _get(self, caminho: str):
        if not any(rx.match(caminho) for rx in CAMINHOS_PERMITIDOS):
            raise CaminhoNaoPermitido("Caminho fora da lista de leitura permitida")
        for tentativa in range(self.tentativas):
            time.sleep(self.pausa)
            try:
                r = self.s.get(self.base + caminho, timeout=60)
            except requests.RequestException:
                r = None
            if r is not None and r.status_code not in (429, 500, 502, 503, 504):
                try:
                    return r.status_code, r.json()
                except ValueError:
                    return r.status_code, None
            time.sleep(2 ** tentativa)
        return 0, None

    def _cnpj_cpf(self, credor_id) -> str:
        if credor_id is None:
            return ""
        if credor_id not in self._credores:
            st, c = self._get(f"/v1/creditors/{int(credor_id)}")
            doc = ""
            if st == 200 and isinstance(c, dict):
                doc = str(c.get("cnpj") or c.get("cpf") or "").strip()
            self._credores[credor_id] = doc
        return self._credores[credor_id]

    def consultar_titulo(self, titulo_id: int) -> TituloSienge:
        """Le titulo, parcelas e CNPJ/CPF do credor. 404 = nao encontrado (nao e erro: o app mostra o aviso)."""
        st, c = self._get(f"/v1/bills/{int(titulo_id)}")
        if st != 200 or not isinstance(c, dict):
            return TituloSienge(id=int(titulo_id), http=st)
        t = TituloSienge(
            id=int(titulo_id), http=st, encontrado=True,
            tipo=(c.get("documentIdentificationId") or "").strip(),
            emissao=_data(c.get("issueDate")), cadastro=_data_hora(c.get("registeredDate")),
            num_doc=str(c.get("documentNumber") or "").strip(), credor_id=c.get("creditorId"),
            valor_total=c.get("totalInvoiceAmount"),
            tem_contrato=_preenchido(c.get("contractNumber")), tem_medicao=_preenchido(c.get("measurementNumber")),
            tem_pedido=_preenchido(c.get("purchaseOrderId")), tem_chave=_preenchido(c.get("accessKeyNumber")),
            status=str(c.get("status") or ""),
        )
        st2, p = self._get(f"/v1/bills/{int(titulo_id)}/installments")
        for x in ((p.get("results") if isinstance(p, dict) else None) or []):
            t.parcelas.append(Parcela(x.get("installmentNumber"), _data(x.get("dueDate")), x.get("amount")))
        t.cnpj_cpf = self._cnpj_cpf(t.credor_id)
        return t


def comparar(planilha_titulo, s: TituloSienge) -> list:
    """Codigos de aviso entre a linha da planilha e o titulo do Sienge (so codigos, nunca valores)."""
    if not s.encontrado:
        return ["NAO_ENCONTRADO_NO_SIENGE"]
    avisos = []
    if planilha_titulo.tipo_doc and s.tipo and planilha_titulo.tipo_doc != s.tipo.upper():
        avisos.append("TIPO_DIFERENTE")
    if planilha_titulo.emissao and s.emissao and planilha_titulo.emissao != s.emissao:
        avisos.append("EMISSAO_DIFERENTE")
    venc = s.parcelas[0].vencimento if len(s.parcelas) == 1 else None
    if planilha_titulo.vencimento and venc and planilha_titulo.vencimento != venc:
        avisos.append("VENCIMENTO_DIFERENTE")
    if planilha_titulo.num_doc and s.num_doc and planilha_titulo.num_doc != s.num_doc:
        avisos.append("NUM_DOC_DIFERENTE")
    if not planilha_titulo.num_doc and s.num_doc:
        avisos.append("NUM_DOC_SO_NO_SIENGE")
    if planilha_titulo.lancamento and s.cadastro:
        minutos = abs((planilha_titulo.lancamento - s.cadastro).total_seconds()) / 60
        if minutos > 60:
            avisos.append("LANCAMENTO_DIFERE_MAIS_DE_1H")
    return avisos
