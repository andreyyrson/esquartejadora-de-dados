"""Modelo único de transação, comum a todos os leitores de extrato.

Todo leitor (OFX, PDF, planilha do sistema) devolve ``Transacao``; o
motor de conciliação só conhece este modelo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from conciliador.datas import parse_data
from conciliador.valores import parse_valor


class Origem(Enum):
    """De qual lado da conciliação a transação veio."""

    BANCO = "banco"
    SISTEMA = "sistema"


class Natureza(Enum):
    CREDITO = "C"
    DEBITO = "D"


class TransacaoInvalida(ValueError):
    """Um campo da transação é inválido."""


@dataclass(frozen=True, slots=True)
class Transacao:
    data: date
    valor: Decimal
    descricao: str
    origem: Origem
    documento: str | None = None
    conta: str | None = None
    arquivo: str | None = None
    linha: int | None = None

    def __post_init__(self) -> None:
        if type(self.data) is not date:
            self._falhar("data", f"esperado date, recebido {self.data!r}")
        if not isinstance(self.valor, Decimal) or not self.valor.is_finite():
            self._falhar("valor", f"esperado Decimal finito, recebido {self.valor!r}")
        if not isinstance(self.origem, Origem):
            self._falhar("origem", f"esperado Origem, recebido {self.origem!r}")
        if self.linha is not None and (type(self.linha) is not int or self.linha < 1):
            self._falhar("linha", f"esperado inteiro >= 1, recebido {self.linha!r}")

    @classmethod
    def criar(
        cls,
        *,
        data: object,
        valor: object,
        descricao: str | None,
        origem: Origem,
        documento: str | None = None,
        conta: str | None = None,
        arquivo: str | None = None,
        linha: int | None = None,
    ) -> Transacao:
        """Cria a transação a partir dos valores crus lidos do extrato."""
        local = _local(arquivo, linha)
        try:
            data_convertida = parse_data(data)
        except ValueError as exc:
            raise TransacaoInvalida(f"campo 'data' inválido{local}: {exc}") from exc
        try:
            valor_convertido = parse_valor(valor)
        except ValueError as exc:
            raise TransacaoInvalida(f"campo 'valor' inválido{local}: {exc}") from exc
        return cls(
            data=data_convertida,
            valor=valor_convertido,
            descricao=" ".join((descricao or "").split()),
            origem=origem,
            documento=(documento or "").strip() or None,
            conta=conta,
            arquivo=arquivo,
            linha=linha,
        )

    @property
    def natureza(self) -> Natureza:
        return Natureza.DEBITO if self.valor < 0 else Natureza.CREDITO

    def _falhar(self, campo: str, motivo: str) -> None:
        local = _local(self.arquivo, self.linha)
        raise TransacaoInvalida(f"campo '{campo}' inválido{local}: {motivo}")


def _local(arquivo: str | None, linha: int | None) -> str:
    """Trecho da mensagem de erro que diz onde o problema está."""
    partes = []
    if arquivo:
        partes.append(arquivo)
    if linha is not None:
        partes.append(f"linha {linha}")
    return f" ({', '.join(partes)})" if partes else ""
