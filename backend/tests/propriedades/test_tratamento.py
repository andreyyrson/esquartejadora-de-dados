from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from conciliador.transacao import Origem, Transacao
from conciliador.tratamento import tratar, tratar_todos

descricoes = st.sampled_from(
    [
        "CHEQUE COMPENSADO",
        "DEVOLUCAO CHQ SEM FUNDOS",
        "ESTORNO LANCAMENTO",
        "PIX ENVIADO X",
        "TARIFA PACOTE",
    ]
)


@st.composite
def lancamentos(draw: st.DrawFn) -> list[Transacao]:
    itens = draw(
        st.lists(
            st.tuples(
                descricoes,
                st.sampled_from(["-50.00", "50.00", "0.00"]),
                st.integers(0, 6),
            ),
            max_size=20,
        )
    )
    return [
        Transacao(
            data=date(2024, 2, 1) + timedelta(days=d),
            valor=Decimal(v),
            descricao=desc,
            origem=Origem.BANCO,
        )
        for desc, v, d in itens
    ]


@given(lancamentos())
def test_anulados_vem_em_pares_que_somam_zero(transacoes: list[Transacao]) -> None:
    tratados = tratar_todos(transacoes)
    for t in tratados:
        if t.anula is not None:
            par = next(x for x in tratados if x.transacao is t.anula)
            assert par.anula is t.transacao
            assert t.transacao.valor + par.transacao.valor == 0
            assert abs((t.transacao.data - par.transacao.data).days) <= 3


@given(lancamentos())
def test_tratar_todos_preserva_quantidade_e_ordem(transacoes: list[Transacao]) -> None:
    assert [t.transacao for t in tratar_todos(transacoes)] == transacoes


@given(st.text())
def test_descricao_limpa_nunca_quebra_e_fica_em_maiusculas(texto: str) -> None:
    limpa = tratar(
        Transacao(
            data=date(2024, 2, 1),
            valor=Decimal("1"),
            descricao=texto,
            origem=Origem.BANCO,
        )
    ).descricao_limpa
    assert limpa == limpa.upper().strip()
    assert "  " not in limpa
