import contextlib
from datetime import date

from conciliador.datas import DataInvalida, parse_data
from hypothesis import given
from hypothesis import strategies as st

# Ano com dois dígitos: 69-99 -> 1969-1999 e 00-68 -> 2000-2068.
datas = st.dates(min_value=date(1969, 1, 1), max_value=date(2068, 12, 31))


@given(datas)
def test_ida_e_volta_no_formato_brasileiro(data: date) -> None:
    assert parse_data(data.strftime("%d/%m/%Y")) == data


@given(datas)
def test_ida_e_volta_com_ano_de_dois_digitos(data: date) -> None:
    assert parse_data(data.strftime("%d/%m/%y")) == data


@given(datas)
def test_ida_e_volta_nos_formatos_iso_e_ofx(data: date) -> None:
    assert parse_data(data.isoformat()) == data
    assert parse_data(data.strftime("%Y%m%d")) == data


@given(st.text())
def test_nunca_quebra_com_excecao_inesperada(texto: str) -> None:
    with contextlib.suppress(DataInvalida):
        parse_data(texto)
