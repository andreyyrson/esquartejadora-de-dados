"""Extrato de conta corrente do Bradesco.

Cada lançamento ocupa várias linhas: o tipo (``PIX RECEBIDO``), a linha
com ``[complemento] DOCUMENTO VALOR SALDO`` e, às vezes, uma continuação
da descrição. Como o saldo vem em toda linha, cada lançamento é
conferido contra o anterior: se a leitura perder uma linha, o ponto
exato vira aviso.

Adaptado do conversor-pdf-para-ofx (MIT, Jean Vieira), validado lá
contra extratos reais; aqui também aceita saldo negativo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from conciliador.datas import DataInvalida, parse_data
from conciliador.extrato import Extrato
from conciliador.leitores.erros import LeituraInvalida
from conciliador.transacao import Origem, Transacao
from conciliador.valores import parse_valor

NOME = "bradesco"
_CODIGO_BANCO = "0237"

_VALOR = r"-?[0-9.]+,[0-9]{2}"
_LINHA_COM_VALOR = re.compile(rf"^(.*?)\s*(\S+)\s+({_VALOR})\s+({_VALOR})$")
_ULTIMO_VALOR = re.compile(rf"({_VALOR})\s*$")
_COM_DATA = re.compile(r"^([0-9]{2}/[0-9]{2}/[0-9]{4})\s*(.*)$")

_SALDO_ANTERIOR = "SALDO ANTERIOR"
# Linhas que não são lançamento e interrompem a descrição em montagem.
_IGNORADOS = ("TOTAL", "SALDOS INVEST", "SALDO INVEST", "OS DADOS ACIMA")
_CABECALHOS = ("DATA LANÇAMENTO", "EXTRATO DE:")
# Início de um novo lançamento: nunca é continuação do anterior.
_TIPOS = (
    "PIX RECEBIDO",
    "PIX ENVIADO",
    "PIX QR CODE",
    "PAGTO ELETRON",
    "TARIFA BANCARIA",
    "RENTAB.INVEST",
    "TED ",
    "DOC ",
    "DEB ",
    "CRED ",
    "REM:",
    "DES:",
)


@dataclass(frozen=True)
class _Registro:
    data: date
    descricao: str
    documento: str
    valor: Decimal
    saldo: Decimal


def reconhece(texto: str) -> bool:
    cabecalho = "Lançamento" in texto and "Dcto." in texto and "Débito" in texto
    return cabecalho or "Nome do usuário:" in texto


def extrair(texto: str, *, arquivo: str) -> Extrato:
    saldo_anterior, registros = _registros(texto, arquivo)
    if not registros:
        raise LeituraInvalida(f"{arquivo}: nenhum lançamento do Bradesco reconhecido")

    primeiro = registros[0]
    saldo_inicial = (
        saldo_anterior
        if saldo_anterior is not None
        else primeiro.saldo - primeiro.valor
    )
    avisos: list[str] = []
    corrente = saldo_inicial
    for registro in registros:
        esperado = corrente + registro.valor
        if esperado != registro.saldo:
            avisos.append(
                f"Bradesco: saldo não fecha em '{registro.descricao}' de "
                f"{registro.data:%d/%m/%Y}: {corrente} + {registro.valor} = "
                f"{esperado}, mas o extrato mostra {registro.saldo} (diferença "
                f"{registro.saldo - esperado}); algum lançamento pode ter "
                "ficado de fora."
            )
        corrente = registro.saldo

    transacoes = tuple(
        Transacao.criar(
            data=r.data,
            valor=r.valor,
            descricao=r.descricao,
            origem=Origem.BANCO,
            documento=r.documento,
            arquivo=arquivo,
            linha=posicao,
        )
        for posicao, r in enumerate(registros, start=1)
    )
    return Extrato(
        transacoes=transacoes,
        banco=_CODIGO_BANCO,
        saldo_inicial=saldo_inicial,
        saldo_final=registros[-1].saldo,
        avisos=tuple(avisos),
    )


def _registros(texto: str, arquivo: str) -> tuple[Decimal | None, list[_Registro]]:
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    saldo_anterior: Decimal | None = None
    registros: list[_Registro] = []
    data: date | None = None
    descricao: list[str] = []
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        i += 1
        chave = linha.upper()
        if chave.startswith(_SALDO_ANTERIOR):
            if (ultimo := _ULTIMO_VALOR.search(linha)) and saldo_anterior is None:
                saldo_anterior = parse_valor(ultimo.group(1))
            descricao = []
            continue
        if chave.startswith(_IGNORADOS + _CABECALHOS):
            descricao = []
            continue
        if com_data := _COM_DATA.match(linha):
            try:
                data = parse_data(com_data.group(1))
            except DataInvalida as exc:
                raise LeituraInvalida(f"{arquivo}: {exc}") from exc
            linha = com_data.group(2).strip()
            if not linha:
                continue
        lancamento = _LINHA_COM_VALOR.match(linha)
        if lancamento is None:
            descricao.append(linha)
            continue
        complemento, documento, valor, saldo = lancamento.groups()
        partes = [*descricao, complemento.strip()]
        descricao = []
        if i < len(linhas) and _continuacao(linhas[i]):
            partes.append(linhas[i])
            i += 1
        if data is None:
            raise LeituraInvalida(f"{arquivo}: lançamento sem data: {linha!r}")
        registros.append(
            _Registro(
                data=data,
                descricao=" - ".join(p for p in partes if p),
                documento=documento,
                valor=parse_valor(valor),
                saldo=parse_valor(saldo),
            )
        )
    return saldo_anterior, registros


def _continuacao(linha: str) -> bool:
    chave = linha.upper()
    return not (
        _COM_DATA.match(linha)
        or _LINHA_COM_VALOR.match(linha)
        or chave.startswith(_TIPOS + _IGNORADOS + _CABECALHOS + (_SALDO_ANTERIOR,))
    )
