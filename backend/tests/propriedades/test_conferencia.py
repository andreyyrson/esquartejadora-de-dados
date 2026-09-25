from datetime import date
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from conciliador.conferencia import StatusConferencia, conferir_saldo
from conciliador.extrato import Extrato
from conciliador.transacao import Origem, Transacao

valores = st.decimals(
    min_value=Decimal("-99999.99"), max_value=Decimal("99999.99"), places=2
)


def montar(lista: list[Decimal], inicial: Decimal, final: Decimal) -> Extrato:
    return Extrato(
        transacoes=tuple(
            Transacao(
                data=date(2024, 2, 1), valor=v, descricao="X", origem=Origem.BANCO
            )
            for v in lista
        ),
        saldo_inicial=inicial,
        saldo_final=final,
    )


@given(st.lists(valores, max_size=50), valores)
def test_saldo_final_correto_sempre_bate(
    lista: list[Decimal], inicial: Decimal
) -> None:
    final = inicial + sum(lista, Decimal("0"))
    assert (
        conferir_saldo(montar(lista, inicial, final)).status is StatusConferencia.BATE
    )


@given(st.lists(valores, min_size=1, max_size=50), valores)
def test_faltar_um_lancamento_sempre_e_detectado(
    lista: list[Decimal], inicial: Decimal
) -> None:
    final = inicial + sum(lista, Decimal("0"))
    faltando = lista[1:]
    resultado = conferir_saldo(montar(faltando, inicial, final))
    if lista[0] == 0:
        assert resultado.status is StatusConferencia.BATE
    else:
        assert resultado.status is StatusConferencia.NAO_BATE
        assert resultado.diferenca == lista[0]
