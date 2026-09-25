"""Extrato de uma conta: as transações e os dados que vieram com elas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from conciliador.transacao import Transacao


@dataclass(frozen=True, slots=True)
class Extrato:
    transacoes: tuple[Transacao, ...]
    banco: str | None = None
    conta: str | None = None
    saldo_inicial: Decimal | None = None
    saldo_final: Decimal | None = None
    data_saldo: date | None = None
    inicio: date | None = None
    fim: date | None = None
