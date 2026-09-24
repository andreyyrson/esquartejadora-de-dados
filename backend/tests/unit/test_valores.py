from decimal import Decimal

import pytest

from conciliador.valores import ValorInvalido, parse_valor

NBSP = "\u00a0"  # espaço não separável, comum em PDF/Excel


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("1.500,00", Decimal("1500.00")),  # milhar brasileiro
        ("1.234.567,89", Decimal("1234567.89")),
        ("-12,90", Decimal("-12.90")),
        ("+12,90", Decimal("12.90")),
        ("0,01", Decimal("0.01")),
        ("150", Decimal("150")),
        ("R$ 1.234,56", Decimal("1234.56")),  # com símbolo
        ("R$" + NBSP + "1.234,56", Decimal("1234.56")),  # espaço não separável
        ("-R$ 10,00", Decimal("-10.00")),
        ("R$ -10,00", Decimal("-10.00")),
        ("(50,00)", Decimal("-50.00")),  # negativo contábil
        ("50,00 D", Decimal("-50.00")),  # sufixo D/C dos extratos
        ("50,00 C", Decimal("50.00")),
        ("50,00D", Decimal("-50.00")),
        ("50,00-", Decimal("-50.00")),  # sinal no final
        ("  1.500,00  ", Decimal("1500.00")),
        ("1500.00", Decimal("1500.00")),  # ponto decimal (formato OFX)
        ("1.50", Decimal("1.50")),
        ("-1500.5", Decimal("-1500.5")),
        ("1,234.56", Decimal("1234.56")),  # formato americano completo
    ],
)
def test_converte_formatos_brasileiros(texto: str, esperado: Decimal) -> None:
    assert parse_valor(texto) == esperado


def test_ponto_sozinho_em_grupo_de_milhar_e_milhar_brasileiro() -> None:
    # "1.500" é ambíguo; por padrão vale a convenção brasileira.
    assert parse_valor("1.500") == Decimal("1500")
    assert parse_valor("12.345.678") == Decimal("12345678")


def test_preserva_casas_decimais() -> None:
    assert str(parse_valor("10,50")) == "10.50"


@pytest.mark.parametrize("valor", [Decimal("10.50"), 10, -3])
def test_aceita_numeros_ja_convertidos(valor: Decimal | int) -> None:
    assert parse_valor(valor) == Decimal(valor)


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "   ",
        "abc",
        "R$",
        "12,34,56",  # duas vírgulas
        "1.23,45",  # grupo de milhar malformado
        "1,234,5",
        "--10,00",
        "(-10,00)",
        "-10,00 D",  # dois indicadores de sinal
        "-R$ -10,00",
        "+R$ -10,00",
        "10,00 X",
        "1e5",
        "NaN",
        "Infinity",
    ],
)
def test_texto_invalido_gera_erro_em_vez_de_zero(texto: str) -> None:
    with pytest.raises(ValorInvalido):
        parse_valor(texto)


@pytest.mark.parametrize("valor", [None, 1.5, True, [], Decimal("NaN")])
def test_tipo_invalido_gera_erro(valor: object) -> None:
    with pytest.raises(ValorInvalido):
        parse_valor(valor)


def test_mensagem_de_erro_mostra_o_valor_recebido() -> None:
    with pytest.raises(ValorInvalido, match="12,34,56"):
        parse_valor("12,34,56")
