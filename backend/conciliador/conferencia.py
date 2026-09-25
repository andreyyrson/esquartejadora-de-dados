"""Conferência de saldo: saldo inicial + lançamentos = saldo final.

É o que torna a leitura de PDF confiável: se a extração perder ou
duplicar uma linha, o saldo não bate e o problema aparece em vez de
seguir em silêncio para a conciliação.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from conciliador.extrato import Extrato


class StatusConferencia(Enum):
    BATE = "bate"
    NAO_BATE = "nao_bate"
    SEM_SALDO = "sem_saldo"  # o extrato não informa saldo inicial ou final


@dataclass(frozen=True, slots=True)
class Conferencia:
    status: StatusConferencia
    total_creditos: Decimal
    total_debitos: Decimal
    saldo_calculado: Decimal | None
    # saldo final - saldo calculado: a soma dos lançamentos que faltaram.
    diferenca: Decimal | None


def conferir_saldo(extrato: Extrato) -> Conferencia:
    valores = [t.valor for t in extrato.transacoes]
    creditos = sum((v for v in valores if v > 0), Decimal("0"))
    debitos = sum((v for v in valores if v < 0), Decimal("0"))

    if extrato.saldo_inicial is None or extrato.saldo_final is None:
        return Conferencia(StatusConferencia.SEM_SALDO, creditos, debitos, None, None)

    calculado = extrato.saldo_inicial + creditos + debitos
    diferenca = extrato.saldo_final - calculado
    status = StatusConferencia.BATE if diferenca == 0 else StatusConferencia.NAO_BATE
    return Conferencia(status, creditos, debitos, calculado, diferenca)
