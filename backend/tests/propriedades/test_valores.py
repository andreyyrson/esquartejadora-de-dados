from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from conciliador.valores import ValorInvalido, parse_valor

valores_monetarios = st.decimals(
    min_value=Decimal("-999999999.99"),
    max_value=Decimal("999999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


def formatar_br(valor: Decimal) -> str:
    """Formata como um extrato brasileiro: 1.234,56 / -1.234,56."""
    inteiro, centavos = f"{abs(valor):,.2f}".split(".")
    texto = inteiro.replace(",", ".") + "," + centavos
    return f"-{texto}" if valor < 0 else texto


@given(valores_monetarios)
def test_ida_e_volta_no_formato_brasileiro(valor: Decimal) -> None:
    assert parse_valor(formatar_br(valor)) == valor


@given(valores_monetarios)
def test_ida_e_volta_com_simbolo_e_sufixo_dc(valor: Decimal) -> None:
    sufixo = "D" if valor < 0 else "C"
    texto = f"R$ {formatar_br(abs(valor))} {sufixo}"
    assert parse_valor(texto) == valor


@given(valores_monetarios)
def test_ida_e_volta_no_formato_ofx(valor: Decimal) -> None:
    assert parse_valor(f"{valor:.2f}") == valor


@given(st.text())
def test_nunca_quebra_com_excecao_inesperada(texto: str) -> None:
    # Qualquer texto vira Decimal ou ValorInvalido, nunca outro erro.
    try:
        resultado = parse_valor(texto)
    except ValorInvalido:
        return
    assert resultado.is_finite()
