"""Conversão de datas de extratos para ``date``.

Datas com barra são sempre dia/mês (padrão brasileiro): ``01/02/2024``
é 1º de fevereiro. Uma data ilegível gera ``DataInvalida`` em vez de ser
adivinhada, porque uma data errada casa lançamentos errados.
"""

from __future__ import annotations

import re
from datetime import date, datetime

_HORA = r"(?:[ T]([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?(?:\.[0-9]+)?)?"
# 01/02/2024, 1-2-24, 01.02.2024 10:30
_BR = re.compile(r"([0-9]{1,2})[/.-]([0-9]{1,2})[/.-]([0-9]{4}|[0-9]{2})" + _HORA)
# 2024-02-01, 2024-02-01T10:30:00
_ISO = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})" + _HORA)
# OFX: 20240201, 20240201103000.000[-3:BRT]
_OFX = re.compile(
    r"([0-9]{4})([0-9]{2})([0-9]{2})"
    r"(?:([0-9]{2})([0-9]{2})([0-9]{2})?(?:\.[0-9]+)?)?"
    r"(?:\[[^\]]*\])?"
)


class DataInvalida(ValueError):
    """O valor não pôde ser interpretado como data."""


def parse_data(valor: object) -> date:
    """Converte uma data de extrato em ``date``.

    Aceita ``date``, ``datetime`` (a hora é descartada) e texto nos
    formatos brasileiro (dia/mês), ISO e OFX.
    """
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        return _parse_texto(valor)
    raise DataInvalida(f"data inválida: {valor!r}")


def _parse_texto(texto: str) -> date:
    limpo = texto.strip()
    if match := _BR.fullmatch(limpo):
        dia, mes, ano, *hora = match.groups()
    elif match := _ISO.fullmatch(limpo) or _OFX.fullmatch(limpo):
        ano, mes, dia, *hora = match.groups()
    else:
        raise DataInvalida(f"data inválida: {texto!r}")

    if not _hora_valida(*hora):
        raise DataInvalida(f"data inválida: {texto!r}")
    try:
        return date(_ano_completo(ano), int(mes), int(dia))
    except ValueError as exc:
        raise DataInvalida(f"data inválida: {texto!r}") from exc


def _ano_completo(ano: str) -> int:
    """Ano com dois dígitos: 69-99 -> 1969-1999, 00-68 -> 2000-2068."""
    if len(ano) == 2:
        valor = int(ano)
        return 1900 + valor if valor >= 69 else 2000 + valor
    return int(ano)


def _hora_valida(hora: str | None, minuto: str | None, segundo: str | None) -> bool:
    return (
        (hora is None or int(hora) < 24)
        and (minuto is None or int(minuto) < 60)
        and (segundo is None or int(segundo) < 60)
    )
