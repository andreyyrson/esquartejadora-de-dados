"""Extrato de conta corrente do Sicoob, em dois layouts.

- curto: ``DD/MM HISTÓRICO 1.234,56C``, com o ano tirado da linha
  ``PERÍODO: DD/MM/AAAA - DD/MM/AAAA``;
- detalhado: ``DD/MM/AAAA [documento] HISTÓRICO 1.234,56C``.

Adaptado do conversor-pdf-para-ofx (MIT, Jean Vieira), onde os dois
layouts foram validados contra extratos reais com o saldo batendo.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from conciliador.datas import parse_data
from conciliador.extrato import Extrato
from conciliador.leitores.erros import LeituraInvalida
from conciliador.transacao import Origem, Transacao, TransacaoInvalida
from conciliador.valores import parse_valor

NOME = "sicoob"
_CODIGO_BANCO = "0756"

_VALOR = r"[0-9.]+,[0-9]{2}"
_PERIODO = re.compile(
    r"PER[ÍI]ODO:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})\s*-\s*([0-9]{2}/[0-9]{2}/[0-9]{4})"
)
_LINHA_CURTA = re.compile(rf"^([0-9]{{2}})/([0-9]{{2}})\s+(.+?)\s+({_VALOR})([CD])$")
_LINHA_DETALHADA = re.compile(
    rf"^([0-9]{{2}}/[0-9]{{2}}/[0-9]{{4}})\s+(.+?)\s+({_VALOR})([CD])$"
)
# Fragmentos que o pdfplumber produz quando o valor passa de 1.000,00.
_SEM_CD = re.compile(rf"^[0-9]{{2}}/[0-9]{{2}}\s+.+?\s+{_VALOR}$")
_DATA_E_HISTORICO = re.compile(r"^[0-9]{2}/[0-9]{2}\s+\S.*$")
_VALOR_SOZINHO = re.compile(rf"^{_VALOR}$")

_SALDO_INICIAL = ("SALDO ANTERIOR",)
_SALDO_FINAL = ("SALDO DO DIA",)
_SALDO_IGNORADO = ("SALDO BLOQ.ANTERIOR", "SALDO BLOQUEADO ANTERIOR")


def reconhece(texto: str) -> bool:
    return "SICOOB" in texto and "SISTEMA DE COOPERATIVAS" in texto


def extrair(texto: str, *, arquivo: str) -> Extrato:
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    periodo = _PERIODO.search(texto)
    inicio: date | None = None
    fim: date | None = None
    if periodo:
        inicio, fim = parse_data(periodo.group(1)), parse_data(periodo.group(2))
        registros = _registros_curtos(_reconstruir(linhas), inicio, fim)
    else:
        registros = _registros_detalhados(linhas)
    if not registros:
        raise LeituraInvalida(f"{arquivo}: nenhum lançamento do Sicoob reconhecido")

    saldo_inicial: Decimal | None = None
    saldo_final: Decimal | None = None
    transacoes: list[Transacao] = []
    for data, historico, valor in registros:
        chave = historico.upper()
        if chave.startswith(_SALDO_IGNORADO):
            continue
        if chave.startswith(_SALDO_INICIAL):
            saldo_inicial = valor if saldo_inicial is None else saldo_inicial
            continue
        if chave.startswith(_SALDO_FINAL):
            saldo_final = valor
            continue
        try:
            transacoes.append(
                Transacao.criar(
                    data=data,
                    valor=valor,
                    descricao=historico,
                    origem=Origem.BANCO,
                    arquivo=arquivo,
                    linha=len(transacoes) + 1,
                )
            )
        except TransacaoInvalida as exc:
            raise LeituraInvalida(f"{arquivo}: {exc}") from exc

    return Extrato(
        transacoes=tuple(transacoes),
        banco=_CODIGO_BANCO,
        saldo_inicial=saldo_inicial,
        saldo_final=saldo_final,
        inicio=inicio,
        fim=fim,
    )


# Cada registro: (data em texto, histórico, valor com sinal). A data só é
# convertida para lançamentos: linhas de saldo podem ter data fora do período.
_Registro = tuple[str, str, Decimal]


def _registros_curtos(linhas: list[str], inicio: date, fim: date) -> list[_Registro]:
    registros: list[_Registro] = []
    for linha in linhas:
        if match := _LINHA_CURTA.match(linha):
            dia, mes, historico, valor, cd = match.groups()
            ano = inicio.year if int(mes) >= inicio.month else fim.year
            registros.append(
                (f"{dia}/{mes}/{ano}", historico.strip(), parse_valor(f"{valor} {cd}"))
            )
    return registros


def _registros_detalhados(linhas: list[str]) -> list[_Registro]:
    registros: list[_Registro] = []
    for linha in linhas:
        if match := _LINHA_DETALHADA.match(linha):
            data, historico, valor, cd = match.groups()
            registros.append((data, historico.strip(), parse_valor(f"{valor} {cd}")))
    return registros


def _reconstruir(linhas: list[str]) -> list[str]:
    """Junta os fragmentos que o pdfplumber cria em valores >= 1.000,00.

    a) ``"05/08 PIX EMIT 4.554,00"`` / ``"D"``
    b) ``"1.200,00"`` / ``"03/08 PIX RECEB"`` / ``"C"``
    """
    saida: list[str] = []
    i = 0
    while i < len(linhas):
        atual = linhas[i]
        seguinte = linhas[i + 1] if i + 1 < len(linhas) else ""
        depois = linhas[i + 2] if i + 2 < len(linhas) else ""
        if (
            _VALOR_SOZINHO.match(atual)
            and _DATA_E_HISTORICO.match(seguinte)
            and not _SEM_CD.match(seguinte)
            and depois in ("C", "D")
        ):
            saida.append(f"{seguinte} {atual}{depois}")
            i += 3
        elif _SEM_CD.match(atual) and seguinte in ("C", "D"):
            saida.append(atual + seguinte)
            i += 2
        else:
            saida.append(atual)
            i += 1
    return saida
