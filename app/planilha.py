# -*- coding: utf-8 -*-
"""Leitura da planilha-base do Felipe (aba Base, v5). So le; nunca grava na planilha.

As colunas de prazo da planilha sao formulas; aqui elas sao RECALCULADAS a partir das colunas digitadas
(Recebido, URG, Lancamento...), para nao depender do valor guardado pelo Excel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import openpyxl

from .dias_uteis import so_data

# cabecalho exato da aba Base (linha 1) -> nome interno
CABECALHOS = {
    "Ref. origem": "ref_origem",
    "Recebido (e-mail)": "recebido",
    "URG": "urg",
    "Empresa": "empresa",
    "Setor": "setor",
    "Fornecedor / credor": "fornecedor",
    "CPF/CNPJ": "cpf_cnpj",
    "Tipo doc.": "tipo_doc",
    "Nº documento": "num_doc",
    "Título": "titulo",
    "Parcela": "parcela",
    "Valor bruto": "valor_bruto",
    "Retenções": "retencoes",
    "Valor líquido": "valor_liquido",
    "Emissão": "emissao",
    "Vencimento": "vencimento",
    "Lançamento (cadastro)": "lancamento",
    "Reprogramado para": "reprogramado",
    "PC / CT": "pc_ct",
    "Tipo de despesa": "tipo_despesa",
    "Retenções conferidas": "ret_conferidas",
    "Devolvida / relançada": "devolvida",
    "Obs.": "obs",
}


@dataclass
class Titulo:
    linha: int
    ref_origem: str = ""
    recebido: Optional[datetime] = None
    urg: str = ""
    empresa: str = ""
    setor: str = ""
    fornecedor: str = ""
    cpf_cnpj: str = ""
    tipo_doc: str = ""
    num_doc: str = ""
    titulo: str = ""
    parcela: str = ""
    valor_bruto: Optional[float] = None
    retencoes: Optional[float] = None
    valor_liquido: Optional[float] = None
    emissao: Optional[date] = None
    vencimento: Optional[date] = None
    lancamento: Optional[datetime] = None
    reprogramado: Optional[date] = None
    pc_ct: str = ""
    tipo_despesa: str = ""
    ret_conferidas: str = ""
    devolvida: str = ""
    obs: str = ""


@dataclass
class Planilha:
    titulos: list = field(default_factory=list)
    feriados: list = field(default_factory=list)
    excecoes_sem_vinculo: list = field(default_factory=list)
    avisos: list = field(default_factory=list)


def _txt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _dt(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    return None


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _lista_nomeada(wb, nome: str) -> list:
    try:
        destino = list(wb.defined_names[nome].destinations)
    except KeyError:
        return []
    saida = []
    for aba, ref in destino:
        for linha in wb[aba][ref.replace("$", "")]:
            for c in (linha if isinstance(linha, tuple) else (linha,)):
                if c.value not in (None, ""):
                    saida.append(c.value)
    return saida


def ler_planilha(origem) -> Planilha:
    """`origem` = caminho do .xlsx ou arquivo aberto (upload do Streamlit)."""
    wb = openpyxl.load_workbook(origem, data_only=True)
    p = Planilha()
    if "Base" not in wb.sheetnames:
        p.avisos.append("Aba Base nao encontrada")
        return p
    ws = wb["Base"]
    cab = {}
    for i, c in enumerate(ws[1], start=1):
        nome = CABECALHOS.get(str(c.value).strip()) if c.value is not None else None
        if nome:
            cab[nome] = i
    faltando = sorted(set(CABECALHOS.values()) - set(cab))
    if faltando:
        p.avisos.append("Colunas nao encontradas no cabecalho: " + ", ".join(faltando))
    p.feriados = [so_data(x) for x in _lista_nomeada(wb, "Feriados") if isinstance(x, (date, datetime))]
    p.excecoes_sem_vinculo = [str(x).strip().upper() for x in _lista_nomeada(wb, "Excecoes")]
    for r in range(2, ws.max_row + 1):
        def v(nome):
            i = cab.get(nome)
            return ws.cell(r, i).value if i else None
        if _dt(v("recebido")) is None and not _txt(v("titulo")):
            continue  # linha vazia (a planilha vem com 1000 linhas pre-formatadas)
        t = Titulo(
            linha=r, ref_origem=_txt(v("ref_origem")), recebido=_dt(v("recebido")),
            urg=_txt(v("urg")).upper(), empresa=_txt(v("empresa")), setor=_txt(v("setor")).upper(),
            fornecedor=_txt(v("fornecedor")), cpf_cnpj=_txt(v("cpf_cnpj")), tipo_doc=_txt(v("tipo_doc")).upper(),
            num_doc=_txt(v("num_doc")), titulo=_txt(v("titulo")), parcela=_txt(v("parcela")),
            valor_bruto=_num(v("valor_bruto")), retencoes=_num(v("retencoes")), valor_liquido=_num(v("valor_liquido")),
            emissao=(_dt(v("emissao")) or None) and so_data(_dt(v("emissao"))),
            vencimento=(_dt(v("vencimento")) or None) and so_data(_dt(v("vencimento"))),
            lancamento=_dt(v("lancamento")),
            reprogramado=(_dt(v("reprogramado")) or None) and so_data(_dt(v("reprogramado"))),
            pc_ct=_txt(v("pc_ct")), tipo_despesa=_txt(v("tipo_despesa")).upper(),
            ret_conferidas=_txt(v("ret_conferidas")).upper(), devolvida=_txt(v("devolvida")).upper(), obs=_txt(v("obs")),
        )
        p.titulos.append(t)
    return p
