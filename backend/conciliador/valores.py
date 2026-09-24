"""Conversão de valores monetários de extratos para Decimal.

Dinheiro nunca é float: ``0.1 + 0.2 != 0.3`` e a conciliação precisa
bater centavo a centavo. Um valor ilegível gera ``ValorInvalido`` em vez
de virar zero, porque um zero silencioso corrompe todas as somas.
"""

from __future__ import annotations

import re
from decimal import Decimal

# "1.500" / "12.345.678": ponto sozinho em grupos de milhar. Ambíguo com o
# ponto decimal americano; por padrão vale a convenção brasileira.
_SO_MILHAR_BR = re.compile(r"[0-9]{1,3}(?:\.[0-9]{3})+")
# "1.234,56" / "1234,56"
_DECIMAL_BR = re.compile(r"[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]+|[0-9]+,[0-9]+")
# "1,234.56" / "1500.00" / "150"
_DECIMAL_PONTO = re.compile(r"[0-9]{1,3}(?:,[0-9]{3})*\.[0-9]+|[0-9]+(?:\.[0-9]+)?")

_NBSP = chr(0xA0)  # espaço não separável, comum em PDF/Excel
_SUFIXO_DC = re.compile(r"(.*?)\s*([DC])")
_PARENTESES = re.compile(r"\((.*)\)")


class ValorInvalido(ValueError):
    """O valor não pôde ser interpretado como quantia monetária."""


def parse_valor(valor: object) -> Decimal:
    """Converte um valor de extrato em ``Decimal``.

    Aceita ``Decimal``, ``int`` e texto nos formatos brasileiro
    (``1.500,00``) e com ponto decimal (``1500.00``, como no OFX), com
    símbolo ``R$`` e sinal negativo como ``-``, ``(...)``, ``-`` no
    final ou sufixo ``D`` (débito). ``float`` é recusado, porque já
    chega com a precisão perdida.
    """
    if isinstance(valor, bool):
        raise ValorInvalido(f"valor monetário inválido: {valor!r}")
    if isinstance(valor, Decimal):
        if not valor.is_finite():
            raise ValorInvalido(f"valor monetário inválido: {valor!r}")
        return valor
    if isinstance(valor, int):
        return Decimal(valor)
    if isinstance(valor, str):
        return _parse_texto(valor)
    raise ValorInvalido(f"valor monetário inválido: {valor!r}")


def _parse_texto(texto: str) -> Decimal:
    resto = texto.replace(_NBSP, " ").strip()
    negativo = False
    indicadores = 0

    if match := _SUFIXO_DC.fullmatch(resto):
        resto, marca = match.group(1), match.group(2)
        negativo = marca == "D"
        indicadores += 1
    if match := _PARENTESES.fullmatch(resto):
        resto = match.group(1).strip()
        negativo = True
        indicadores += 1
    if resto.endswith("-"):
        resto = resto[:-1].strip()
        negativo = True
        indicadores += 1
    sinais = []
    resto, sinal = _tirar_sinal_inicial(resto)
    sinais.append(sinal)
    if resto.startswith("R$"):
        resto, sinal = _tirar_sinal_inicial(resto[2:].strip())
        sinais.append(sinal)
    for sinal in filter(None, sinais):
        negativo = negativo or sinal == "-"
        indicadores += 1

    if indicadores > 1:
        raise ValorInvalido(f"valor monetário inválido: {texto!r}")

    numero = _normalizar_numero(resto)
    if numero is None:
        raise ValorInvalido(f"valor monetário inválido: {texto!r}")
    quantia = Decimal(numero)
    return -quantia if negativo else quantia


def _tirar_sinal_inicial(texto: str) -> tuple[str, str]:
    """Separa um ``+``/``-`` inicial do resto do texto."""
    if texto[:1] in ("-", "+"):
        return texto[1:].strip(), texto[0]
    return texto, ""


def _normalizar_numero(texto: str) -> str | None:
    """Devolve o número com ponto decimal e sem milhar, ou None."""
    if _SO_MILHAR_BR.fullmatch(texto):
        return texto.replace(".", "")
    if _DECIMAL_BR.fullmatch(texto):
        return texto.replace(".", "").replace(",", ".")
    if _DECIMAL_PONTO.fullmatch(texto):
        return texto.replace(",", "")
    return None
