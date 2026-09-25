"""Extrato mensal de conta corrente do Itaú.

Lançamentos ``DD/MM HISTÓRICO 1.234,56[-] [saldo]``: o ``-`` no fim do
valor marca débito e o ano vem do cabeçalho (``mar 2026``). Linhas sem
data continuam no dia anterior.

Adaptado do conversor-pdf-para-ofx (MIT, Jean Vieira), validado lá
contra extratos reais.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from decimal import Decimal

from conciliador.extrato import Extrato
from conciliador.leitores.erros import LeituraInvalida
from conciliador.transacao import Origem, Transacao, TransacaoInvalida
from conciliador.valores import parse_valor

NOME = "itau"
_CODIGO_BANCO = "0341"

_MESES = (
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
)
_MES_ANO = re.compile(rf"\b({'|'.join(_MESES)})\s+(20[0-9]{{2}})\b", re.IGNORECASE)
_VALOR = r"[0-9.]+,[0-9]{2}"
_LANCAMENTO = re.compile(rf"^(.+?)\s+({_VALOR})(-)?(?:\s+{_VALOR}-?)?$")
_COM_DATA = re.compile(r"^([0-9]{2})/([0-9]{2})\s+(.+)$")
# Tabelas-resumo do fim do extrato repetem lançamentos com data DD/MM/AA.
_DATA_DE_RESUMO = re.compile(r"^[0-9]{2}/[0-9]{2}/[0-9]{2}\b")
_LETRA = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")
_VALOR_NA_DESCRICAO = re.compile(r"[0-9],[0-9]{2}")

_SALDO_INICIAL = "SALDO ANTERIOR"
_APLICACAO_AUTOMATICA = "APLIC AUT MAIS"
_IGNORADOS = ("SALDO EM C/C", "SALDO FINAL", "TOTAL")


def reconhece(texto: str) -> bool:
    minusculo = texto.lower()
    return "extrato mensal" in minusculo and ("itaú" in minusculo or "B001A" in texto)


def extrair(texto: str, *, arquivo: str) -> Extrato:
    mes_ano = _MES_ANO.search(texto)
    if mes_ano is None:
        raise LeituraInvalida(f"{arquivo}: mês/ano do extrato não encontrado no Itaú")
    mes = _MESES.index(mes_ano.group(1).lower()) + 1
    ano = int(mes_ano.group(2))

    saldo_inicial: Decimal | None = None
    aplicacao_automatica = False
    transacoes: list[Transacao] = []
    dia: tuple[str, str] | None = None
    for linha in (linha.strip() for linha in texto.splitlines()):
        if not linha or _DATA_DE_RESUMO.match(linha):
            continue
        historico_e_valor = linha
        if com_data := _COM_DATA.match(linha):
            dia = (com_data.group(1), com_data.group(2))
            historico_e_valor = com_data.group(3)
        # Tabela de aplicações/resgates: DD/MM seguido só de números.
        if not _LETRA.search(historico_e_valor):
            continue
        lancamento = _LANCAMENTO.match(historico_e_valor)
        if lancamento is None:
            continue
        historico, valor, debito = lancamento.groups()
        # Resumos (ex.: do CDB) trazem vários valores dentro do "histórico".
        if _VALOR_NA_DESCRICAO.search(historico):
            continue
        quantia = parse_valor(f"{valor}-" if debito else valor)
        chave = historico.upper()
        if chave.startswith(_SALDO_INICIAL):
            saldo_inicial = quantia if saldo_inicial is None else saldo_inicial
            continue
        if chave.startswith(_APLICACAO_AUTOMATICA):
            aplicacao_automatica = True
            continue
        if chave.startswith(_IGNORADOS) or dia is None:
            continue
        try:
            transacoes.append(
                Transacao.criar(
                    data=f"{dia[0]}/{dia[1]}/{ano}",
                    valor=quantia,
                    descricao=historico,
                    origem=Origem.BANCO,
                    arquivo=arquivo,
                    linha=len(transacoes) + 1,
                )
            )
        except TransacaoInvalida as exc:
            raise LeituraInvalida(f"{arquivo}: {exc}") from exc

    if not transacoes and saldo_inicial is None:
        raise LeituraInvalida(f"{arquivo}: nenhum lançamento do Itaú reconhecido")
    avisos = (
        (
            'Itaú: lançamentos "Aplic Aut Mais" (aplicação automática) ficaram '
            "de fora; confira se precisar deles.",
        )
        if aplicacao_automatica
        else ()
    )
    return Extrato(
        transacoes=tuple(transacoes),
        banco=_CODIGO_BANCO,
        saldo_inicial=saldo_inicial,
        inicio=date(ano, mes, 1),
        fim=date(ano, mes, calendar.monthrange(ano, mes)[1]),
        avisos=avisos,
    )
