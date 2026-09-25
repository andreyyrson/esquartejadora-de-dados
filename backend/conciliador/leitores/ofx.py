"""Leitor de OFX (versões 1 e 2), usando o ofxparse.

Antes de entregar o arquivo ao ofxparse, o texto é normalizado para
contornar dois problemas comuns nos arquivos de bancos brasileiros:

- codificação: o cabeçalho costuma declarar USASCII/1252 mesmo quando o
  arquivo está em UTF-8, e o OFX 2 (XML) em UTF-8 não é reconhecido.
  Aqui o arquivo é decodificado primeiro como UTF-8 e, se falhar, como
  cp1252, e reescrito com cabeçalho UTF-8;
- fuso horário: o ofxparse converte ``20240201230000[-3:BRT]`` para
  UTC, jogando o lançamento para o dia seguinte. O fuso é removido para
  manter a data local do banco.
"""

from __future__ import annotations

import io
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import ofxparse

from conciliador.datas import parse_data
from conciliador.extrato import Extrato
from conciliador.leitores.erros import LeituraInvalida
from conciliador.transacao import Origem, Transacao, TransacaoInvalida

_CABECALHO_UTF8 = (
    "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\n"
    "ENCODING:UTF-8\nCHARSET:NONE\nCOMPRESSION:NONE\n"
    "OLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
)
_INICIO_OFX = re.compile(r"<OFX>", re.IGNORECASE)
_FUSO_EM_DATA = re.compile(
    r"(<DT[A-Z]+>\s*[0-9]{8,14}(?:\.[0-9]+)?)\s*\[[^\]<]*\]", re.IGNORECASE
)


def ler_ofx(caminho: str | Path) -> list[Extrato]:
    """Lê um arquivo OFX e devolve um ``Extrato`` por conta."""
    caminho = Path(caminho)
    try:
        conteudo = caminho.read_bytes()
    except OSError as exc:
        raise LeituraInvalida(f"{caminho.name}: não foi possível ler ({exc})") from exc
    return ler_ofx_bytes(conteudo, nome=caminho.name)


def ler_ofx_bytes(conteudo: bytes, *, nome: str) -> list[Extrato]:
    """Lê o conteúdo de um OFX (por exemplo, de um upload)."""
    texto = _normalizar(conteudo, nome)
    try:
        ofx = ofxparse.OfxParser.parse(io.BytesIO(texto.encode("utf-8")))
    except Exception as exc:
        raise LeituraInvalida(f"{nome}: OFX inválido ({exc})") from exc
    if not ofx.accounts:
        raise LeituraInvalida(f"{nome}: nenhuma conta encontrada no OFX")
    try:
        return [_extrato(conta, nome) for conta in ofx.accounts]
    except TransacaoInvalida as exc:
        raise LeituraInvalida(f"{nome}: {exc}") from exc


def _normalizar(conteudo: bytes, nome: str) -> str:
    try:
        texto = conteudo.decode("utf-8")
    except UnicodeDecodeError:
        texto = conteudo.decode("cp1252", errors="replace")
    inicio = _INICIO_OFX.search(texto)
    if inicio is None:
        raise LeituraInvalida(f"{nome}: não é um arquivo OFX")
    corpo = _FUSO_EM_DATA.sub(r"\1", texto[inicio.start() :])
    return _CABECALHO_UTF8 + corpo


def _extrato(conta: Any, nome: str) -> Extrato:
    extrato = conta.statement
    numero = conta.account_id or None
    transacoes = tuple(
        Transacao.criar(
            data=t.date,
            valor=t.amount,
            descricao=t.memo or t.payee,
            origem=Origem.BANCO,
            documento=t.checknum,
            conta=numero,
            arquivo=nome,
            linha=posicao,
        )
        for posicao, t in enumerate(extrato.transactions, start=1)
    )
    return Extrato(
        transacoes=transacoes,
        banco=conta.routing_number or None,
        conta=numero,
        saldo_final=_decimal_opcional(getattr(extrato, "balance", None)),
        data_saldo=_data_opcional(getattr(extrato, "balance_date", None)),
        inicio=_data_opcional(getattr(extrato, "start_date", None)),
        fim=_data_opcional(getattr(extrato, "end_date", None)),
    )


def _data_opcional(valor: object) -> date | None:
    # Campo ausente no OFX: o ofxparse deixa None ou texto vazio.
    if valor is None or valor == "":
        return None
    return parse_data(valor)


def _decimal_opcional(valor: object) -> Decimal | None:
    return valor if isinstance(valor, Decimal) else None
