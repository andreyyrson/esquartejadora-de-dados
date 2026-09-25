"""Extrato do Gerenciador Caixa (Caixa Econômica Federal).

Cada lançamento vem em três linhas: histórico, data e
``DOCUMENTO DETALHE R$ VALOR R$ SALDO C|D``, onde C/D é a natureza do
lançamento. Os saldos não são usados: o significado do C/D nas linhas
de saldo não foi validado.

Adaptado do conversor-pdf-para-ofx (MIT, Jean Vieira), validado lá
contra extratos reais.
"""

from __future__ import annotations

import re

from conciliador.datas import DataInvalida, parse_data
from conciliador.extrato import Extrato
from conciliador.leitores.erros import LeituraInvalida
from conciliador.transacao import Origem, Transacao, TransacaoInvalida
from conciliador.valores import parse_valor

NOME = "caixa"
_CODIGO_BANCO = "0104"

_VALOR = r"[0-9.]+,[0-9]{2}"
_LANCAMENTO = re.compile(
    r"(?P<historico>[^\n]+)\n"
    r"(?P<data>[0-9]{2}/[0-9]{2}/[0-9]{4})\n"
    rf"(?P<documento>\S+)\s+(?P<detalhe>.+?)\s+R\$\s*(?P<valor>{_VALOR})"
    rf"\s+R\$\s*{_VALOR}\s+(?P<natureza>[CD])"
)
_PERIODO = re.compile(
    r"Extrato no período de\s+([0-9]{2}/[0-9]{2}/[0-9]{4})\s+a\s+"
    r"([0-9]{2}/[0-9]{2}/[0-9]{4})"
)


def reconhece(texto: str) -> bool:
    maiusculo = texto.upper()
    gerenciador = "GERENCIADOR" in maiusculo and "CAIXA" in maiusculo
    return gerenciador or "Extrato no período de" in texto


def extrair(texto: str, *, arquivo: str) -> Extrato:
    transacoes: list[Transacao] = []
    for lancamento in _LANCAMENTO.finditer(texto):
        historico = lancamento.group("historico").strip()
        chave = historico.upper()
        if chave.startswith("SALDO ANTERIOR") or (
            chave.startswith("SALDO") and "DIA" in chave
        ):
            continue
        valor = lancamento.group("valor")
        try:
            transacoes.append(
                Transacao.criar(
                    data=lancamento.group("data"),
                    valor=parse_valor(f"{valor} {lancamento.group('natureza')}"),
                    descricao=f"{historico} - {lancamento.group('detalhe').strip()}",
                    origem=Origem.BANCO,
                    documento=lancamento.group("documento"),
                    arquivo=arquivo,
                    linha=len(transacoes) + 1,
                )
            )
        except TransacaoInvalida as exc:
            raise LeituraInvalida(f"{arquivo}: {exc}") from exc
    if not transacoes:
        raise LeituraInvalida(f"{arquivo}: nenhum lançamento da Caixa reconhecido")

    inicio = fim = None
    if periodo := _PERIODO.search(texto):
        try:
            inicio, fim = parse_data(periodo.group(1)), parse_data(periodo.group(2))
        except DataInvalida as exc:
            raise LeituraInvalida(f"{arquivo}: {exc}") from exc
    return Extrato(
        transacoes=tuple(transacoes), banco=_CODIGO_BANCO, inicio=inicio, fim=fim
    )
