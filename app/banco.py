# -*- coding: utf-8 -*-
"""Login pelo Authentication do Supabase e gravacao no schema posto_fiscal.

O app usa a chave PUBLICA (anon) + a sessao de quem entrou; quem manda e o RLS do banco
(so e-mails em posto_fiscal.acesso leem e gravam). A chave de servico NAO e usada aqui.
Variaveis: SUPABASE_URL, SUPABASE_ANON_KEY (Secrets do Streamlit).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

SCHEMA = "posto_fiscal"
LOTE = 200


def _iso(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def linhas_titulo(titulos: list, carga_id: Optional[int] = None) -> tuple:
    """(linhas para upsert, quantos ficaram de fora por falta de numero de titulo ou repetidos).
    Repetido no mesmo lote derruba o upsert (padrao PADROES-GERAIS): fica a ultima ocorrencia."""
    por_ref, fora = {}, 0
    for t in titulos:
        ref = (t.titulo or "").strip()
        if not ref:
            fora += 1
            continue
        if ref in por_ref:
            fora += 1
        por_ref[ref] = {
            "titulo_ref": ref, "carga_id": carga_id, "linha": t.linha, "ref_origem": t.ref_origem,
            "recebido": _iso(t.recebido), "urgente": t.urg == "S", "empresa": t.empresa, "setor": t.setor,
            "tipo_doc": t.tipo_doc, "num_doc": t.num_doc, "fornecedor": t.fornecedor, "cpf_cnpj": t.cpf_cnpj,
            "parcela": t.parcela, "valor_bruto": t.valor_bruto, "retencoes": t.retencoes,
            "valor_liquido": t.valor_liquido, "emissao": _iso(t.emissao), "vencimento": _iso(t.vencimento),
            "lancamento": _iso(t.lancamento), "reprogramado": _iso(t.reprogramado), "pc_ct": t.pc_ct,
            "tipo_despesa": t.tipo_despesa, "ret_conferidas": t.ret_conferidas, "devolvida": t.devolvida,
            "obs": t.obs, "atualizado_em": datetime.utcnow().isoformat(),
        }
    return list(por_ref.values()), fora


def linha_sienge(titulo_ref: str, s, avisos: list) -> dict:
    return {
        "titulo_ref": titulo_ref, "consultado_em": datetime.utcnow().isoformat(), "http": s.http,
        "encontrado": s.encontrado, "tipo": s.tipo, "emissao": _iso(s.emissao), "cadastro": _iso(s.cadastro),
        "num_doc": s.num_doc, "cnpj_cpf": s.cnpj_cpf, "valor_total": s.valor_total,
        "tem_contrato": s.tem_contrato, "tem_medicao": s.tem_medicao, "tem_pedido": s.tem_pedido,
        "tem_chave": s.tem_chave, "status": s.status,
        "parcelas": [{"n": x.numero, "venc": _iso(x.vencimento), "valor": x.valor} for x in s.parcelas],
        "avisos": avisos,
    }


def entrar(url: str, chave_publica: str, email: str, senha: str):
    """Devolve (cliente, e-mail) ou levanta erro se o login falhar ou o e-mail nao estiver autorizado."""
    from supabase import create_client  # import tardio: so o app precisa
    cli = create_client(url, chave_publica)
    resp = cli.auth.sign_in_with_password({"email": email.strip(), "password": senha})
    email_ok = (resp.user.email if resp and resp.user else "") or ""
    r = cli.schema(SCHEMA).table("acesso").select("email").execute()
    if not r.data:
        cli.auth.sign_out()
        raise PermissionError("Este e-mail não está autorizado no Posto-Fiscal.")
    return cli, email_ok


def sair(cli) -> None:
    try:
        cli.auth.sign_out()
    except Exception:
        pass


def salvar_planilha(cli, p, arquivo_nome: str, sha256: str, ini, fim, usuario: str) -> dict:
    carga = cli.schema(SCHEMA).table("carga").insert({
        "enviado_por": usuario, "arquivo_nome": arquivo_nome, "arquivo_sha256": sha256,
        "linhas": len(p.titulos), "periodo_ini": _iso(ini), "periodo_fim": _iso(fim),
    }).execute()
    carga_id = carga.data[0]["id"]
    linhas, fora = linhas_titulo(p.titulos, carga_id)
    for i in range(0, len(linhas), LOTE):
        cli.schema(SCHEMA).table("titulo").upsert(linhas[i:i + LOTE], on_conflict="titulo_ref").execute()
    return {"carga_id": carga_id, "gravados": len(linhas), "fora": fora}


def salvar_sienge(cli, resultados: list) -> int:
    """resultados = [(titulo_ref, TituloSienge, avisos)]; o titulo precisa ja existir em posto_fiscal.titulo."""
    linhas = [linha_sienge(ref, s, av) for ref, s, av in resultados]
    for i in range(0, len(linhas), LOTE):
        cli.schema(SCHEMA).table("titulo_sienge").upsert(linhas[i:i + LOTE], on_conflict="titulo_ref").execute()
    return len(linhas)
