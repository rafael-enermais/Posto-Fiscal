# -*- coding: utf-8 -*-
"""Posto-Fiscal | Diagnostico SOMENTE LEITURA do Sienge (v0.1, 29/10/2026).

Nao grava nada no Sienge nem em banco. Responde:
  A) Os numeros de "Titulo" da planilha do Felipe sao ids de titulo do Sienge?  (GET /v1/bills/{id})
  B) Que tipo de documento (FVOL, NFS...) e quais campos vem preenchidos nesses titulos?
  C) Em set-out/2026, quantos titulos de cada tipo existem e o que startDate/endDate filtram?

REPOSITORIO PUBLICO: o log tambem e publico. Este script imprime SO contagens, codigos de tipo,
datas e "preenchido sim/nao". NUNCA imprime nome, CNPJ, valores, usuario, observacoes ou chaves.

Variaveis de ambiente: SIENGE_BASE_URL, SIENGE_USER, SIENGE_PASSWORD (Secrets do repositorio),
IDS (titulos separados por virgula), DIAS (janela da varredura em dias; padrao 60).
"""
from __future__ import annotations

import collections
import os
import sys
import time
from datetime import date, timedelta

import requests
from requests.auth import HTTPBasicAuth

LIM = 200
CAMPOS = ("documentNumber", "accessKeyNumber", "purchaseOrderId", "contractNumber",
          "measurementNumber", "notes")


def _env(nome: str) -> str:
    v = (os.environ.get(nome) or "").strip()
    if not v:
        print(f"ERRO: variavel {nome} nao configurada.", file=sys.stderr)
        sys.exit(1)
    return v


def preenchido(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return True


def sn(v) -> str:
    return "S" if preenchido(v) else "N"


def dia(v):
    return str(v)[:10] if v else None


class Cliente:
    def __init__(self, base: str, usuario: str, senha: str):
        self.base = base.rstrip("/")
        self.s = requests.Session()
        self.s.auth = HTTPBasicAuth(usuario, senha)

    def get(self, caminho: str, params=None):
        """(status_http, corpo_json_ou_None). Nunca imprime o corpo."""
        time.sleep(0.15)
        try:
            r = self.s.get(self.base + caminho, params=params, timeout=60)
        except requests.RequestException:
            return 0, None
        try:
            corpo = r.json()
        except ValueError:
            corpo = None
        return r.status_code, corpo


def parte_a(cli: Cliente, ids: list) -> None:
    print("== A) Titulos da planilha lidos pelo numero (GET /v1/bills/{id}) ==")
    http = collections.Counter()
    tipos = collections.Counter()
    id_confere = 0
    por_tipo_campo = collections.defaultdict(collections.Counter)
    cred_cache, cred_http, cred_cnpj = {}, collections.Counter(), 0
    parc_http, com_venc = collections.Counter(), 0
    for i in ids:
        st, c = cli.get(f"/v1/bills/{i}")
        http[st] += 1
        if st != 200 or not isinstance(c, dict):
            print(f"{i} | HTTP {st}")
            continue
        tipo = (c.get("documentIdentificationId") or "").strip() or "(vazio)"
        tipos[tipo] += 1
        if str(c.get("id")) == str(i):
            id_confere += 1
        for campo in CAMPOS:
            por_tipo_campo[tipo][campo] += 1 if preenchido(c.get(campo)) else 0
        por_tipo_campo[tipo]["_n"] += 1
        # parcelas
        st2, p = cli.get(f"/v1/bills/{i}/installments")
        parc_http[st2] += 1
        res = (p.get("results") if isinstance(p, dict) else None) or []
        venc = sorted(dia(x.get("dueDate")) for x in res if isinstance(x, dict) and x.get("dueDate"))
        com_venc += 1 if venc else 0
        # credor (so "tem CNPJ/CPF?")
        cid = c.get("creditorId")
        if cid is not None and cid not in cred_cache:
            st3, cc = cli.get(f"/v1/creditors/{cid}")
            cred_http[st3] += 1
            cred_cache[cid] = isinstance(cc, dict) and (preenchido(cc.get("cnpj")) or preenchido(cc.get("cpf")))
            cred_cnpj += 1 if cred_cache[cid] else 0
        print(f"{i} | tipo={tipo} | emissao={dia(c.get('issueDate'))} | cadastro={str(c.get('registeredDate') or '')[:19]}"
              f" | ndoc={sn(c.get('documentNumber'))} pc={sn(c.get('purchaseOrderId'))} ct={sn(c.get('contractNumber'))}"
              f" med={sn(c.get('measurementNumber'))} chave={sn(c.get('accessKeyNumber'))}"
              f" | parcelas={len(res)} venc1={venc[0] if venc else None} | credor_cnpj_cpf={sn(cred_cache.get(cid))}")
    print("-- resumo A --")
    print("HTTP dos titulos:", dict(http), "| id devolvido = numero pedido:", id_confere, "de", len(ids))
    print("tipos:", dict(tipos))
    for t, cont in por_tipo_campo.items():
        n = cont["_n"]
        print(f"  {t} (n={n}): " + ", ".join(f"{k}={cont[k]}" for k in CAMPOS))
    print("HTTP das parcelas:", dict(parc_http), "| titulos com vencimento:", com_venc)
    print("HTTP dos credores:", dict(cred_http), "| credores distintos:", len(cred_cache), "| com CNPJ/CPF:", cred_cnpj)


def parte_b(cli: Cliente, ini: date, fim: date, ids: list) -> None:
    print(f"\n== B) Varredura GET /v1/bills de {ini} a {fim} (startDate/endDate) ==")
    total = 0
    tipos = collections.Counter()
    emissao_mes, cadastro_mes = collections.Counter(), collections.Counter()
    emissao_dentro = cadastro_dentro = 0
    visto = set()
    preench = collections.defaultdict(collections.Counter)
    status = collections.Counter()
    truncado = True
    offset = 0
    while offset < LIM * 60:
        st, c = cli.get("/v1/bills", {"startDate": ini.isoformat(), "endDate": fim.isoformat(),
                                      "limit": LIM, "offset": offset})
        if st != 200:
            print(f"HTTP {st} no offset {offset}; parando.")
            break
        rs = c.get("results", c) if isinstance(c, dict) else c
        if not rs:
            truncado = False
            break
        for b in rs:
            total += 1
            visto.add(str(b.get("id")))
            t = (b.get("documentIdentificationId") or "").strip() or "(vazio)"
            tipos[t] += 1
            status[str(b.get("status"))] += 1
            e, r = dia(b.get("issueDate")), dia(b.get("registeredDate"))
            if e:
                emissao_mes[e[:7]] += 1
                emissao_dentro += 1 if ini.isoformat() <= e <= fim.isoformat() else 0
            if r:
                cadastro_mes[r[:7]] += 1
                cadastro_dentro += 1 if ini.isoformat() <= r <= fim.isoformat() else 0
            preench[t]["_n"] += 1
            for campo in CAMPOS:
                preench[t][campo] += 1 if preenchido(b.get(campo)) else 0
        if len(rs) < LIM:
            truncado = False
            break
        offset += LIM
    print("total de titulos na varredura:", total, "| varredura truncada no teto:", truncado)
    print("por tipo:", dict(tipos.most_common()))
    print("status (S/N):", dict(status))
    print("por mes de EMISSAO:", dict(sorted(emissao_mes.items())))
    print("por mes de CADASTRO:", dict(sorted(cadastro_mes.items())))
    print(f"emissao dentro da janela: {emissao_dentro} | cadastro dentro da janela: {cadastro_dentro} (de {total})")
    ids_set = {str(i) for i in ids}
    print("titulos da planilha encontrados na varredura:", len(ids_set & visto), "de", len(ids_set))
    print("FVOL na varredura:", tipos.get("FVOL", 0))
    print("preenchimento por tipo (so os 8 maiores):")
    for t, _ in tipos.most_common(8):
        cont = preench[t]
        print(f"  {t} (n={cont['_n']}): " + ", ".join(f"{k}={cont[k]}" for k in CAMPOS))


def main() -> int:
    cli = Cliente(_env("SIENGE_BASE_URL"), _env("SIENGE_USER"), _env("SIENGE_PASSWORD"))
    ids = [x.strip() for x in (os.environ.get("IDS") or "").split(",") if x.strip().isdigit()]
    dias = int((os.environ.get("DIAS") or "60").strip() or "60")
    hoje = date.today()
    print(f"Diagnostico somente leitura | {hoje} | {len(ids)} titulo(s) | janela {dias} dias")
    if ids:
        parte_a(cli, ids)
    parte_b(cli, hoje - timedelta(days=dias), hoje, ids)
    print("\nConcluido. Nada foi gravado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
