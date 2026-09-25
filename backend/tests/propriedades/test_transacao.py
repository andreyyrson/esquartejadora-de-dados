from datetime import date
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from conciliador.transacao import Natureza, Origem, Transacao

valores = st.decimals(
    min_value=Decimal("-999999999.99"),
    max_value=Decimal("999999999.99"),
    places=2,
)
datas = st.dates(min_value=date(1969, 1, 1), max_value=date(2068, 12, 31))


@given(datas, valores, st.text())
def test_criar_preserva_data_e_valor(data: date, valor: Decimal, desc: str) -> None:
    t = Transacao.criar(
        data=data.strftime("%d/%m/%Y"),
        valor=f"{valor:.2f}",
        descricao=desc,
        origem=Origem.BANCO,
    )
    assert t.data == data
    assert t.valor == valor


@given(valores)
def test_natureza_segue_o_sinal(valor: Decimal) -> None:
    t = Transacao.criar(
        data="01/02/2024", valor=valor, descricao="X", origem=Origem.SISTEMA
    )
    esperado = Natureza.DEBITO if valor < 0 else Natureza.CREDITO
    assert t.natureza is esperado


@given(st.text())
def test_descricao_normalizada_nao_tem_espacos_duplos(desc: str) -> None:
    t = Transacao.criar(
        data="01/02/2024", valor="1,00", descricao=desc, origem=Origem.BANCO
    )
    assert t.descricao == t.descricao.strip()
    assert "  " not in t.descricao
