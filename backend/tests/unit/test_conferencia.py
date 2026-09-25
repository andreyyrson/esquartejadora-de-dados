from datetime import date
from decimal import Decimal

from conciliador.conferencia import StatusConferencia, conferir_saldo
from conciliador.extrato import Extrato
from conciliador.transacao import Origem, Transacao


def extrato(
    *valores: str, inicial: str | None = "100,00", final: str | None = "150,00"
) -> Extrato:
    transacoes = tuple(
        Transacao.criar(
            data=date(2024, 2, 1), valor=v, descricao="X", origem=Origem.BANCO
        )
        for v in valores
    )
    return Extrato(
        transacoes=transacoes,
        saldo_inicial=None if inicial is None else Decimal(inicial.replace(",", ".")),
        saldo_final=None if final is None else Decimal(final.replace(",", ".")),
    )


def test_saldo_bate() -> None:
    resultado = conferir_saldo(extrato("80,00", "-30,00"))
    assert resultado.status is StatusConferencia.BATE
    assert resultado.diferenca == Decimal("0")
    assert resultado.total_creditos == Decimal("80.00")
    assert resultado.total_debitos == Decimal("-30.00")


def test_saldo_nao_bate_informa_a_diferenca() -> None:
    # Faltou um débito de 12,90 (ex.: linha que o leitor não reconheceu).
    # diferenca = saldo final - saldo calculado = soma do que faltou.
    resultado = conferir_saldo(extrato("80,00", "-17,10", final="150,00"))
    assert resultado.status is StatusConferencia.NAO_BATE
    assert resultado.diferenca == Decimal("-12.90")
    assert resultado.saldo_calculado == Decimal("162.90")


def test_sem_saldo_inicial_nao_da_para_conferir() -> None:
    resultado = conferir_saldo(extrato("50,00", inicial=None))
    assert resultado.status is StatusConferencia.SEM_SALDO
    assert resultado.diferenca is None


def test_sem_saldo_final_nao_da_para_conferir() -> None:
    resultado = conferir_saldo(extrato("50,00", final=None))
    assert resultado.status is StatusConferencia.SEM_SALDO


def test_extrato_sem_lancamentos() -> None:
    resultado = conferir_saldo(extrato(inicial="100,00", final="100,00"))
    assert resultado.status is StatusConferencia.BATE


def test_saldos_negativos() -> None:
    resultado = conferir_saldo(extrato("-50,00", inicial="-10,00", final="-60,00"))
    assert resultado.status is StatusConferencia.BATE
