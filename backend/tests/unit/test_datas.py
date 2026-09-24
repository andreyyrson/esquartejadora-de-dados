from datetime import date, datetime

import pytest
from conciliador.datas import DataInvalida, parse_data


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("01/02/2024", date(2024, 2, 1)),  # sempre dia/mês (padrão brasileiro)
        ("1/2/2024", date(2024, 2, 1)),
        ("31/12/2023", date(2023, 12, 31)),
        ("01/02/24", date(2024, 2, 1)),  # ano com dois dígitos
        ("01-02-2024", date(2024, 2, 1)),
        ("01.02.2024", date(2024, 2, 1)),
        ("2024-02-01", date(2024, 2, 1)),  # ISO
        ("2024-02-01T10:30:00", date(2024, 2, 1)),
        ("2024-02-01 10:30:00", date(2024, 2, 1)),
        ("01/02/2024 10:30", date(2024, 2, 1)),  # hora é descartada
        ("01/02/2024 10:30:59", date(2024, 2, 1)),
        ("20240201", date(2024, 2, 1)),  # OFX
        ("20240201103000", date(2024, 2, 1)),
        ("20240201103000[-3:BRT]", date(2024, 2, 1)),
        ("20240201103000.000[-3:BRT]", date(2024, 2, 1)),
        ("  01/02/2024  ", date(2024, 2, 1)),
        ("29/02/2024", date(2024, 2, 29)),  # ano bissexto
    ],
)
def test_converte_formatos_de_extrato(texto: str, esperado: date) -> None:
    assert parse_data(texto) == esperado


def test_aceita_date_sem_alterar() -> None:
    assert parse_data(date(2024, 2, 1)) == date(2024, 2, 1)


def test_datetime_vira_date() -> None:
    # openpyxl devolve datetime para células de data do Excel.
    resultado = parse_data(datetime(2024, 2, 1, 15, 45))
    assert resultado == date(2024, 2, 1)
    assert type(resultado) is date


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "   ",
        "abc",
        "31/02/2024",  # dia inexistente
        "29/02/2023",  # não é bissexto
        "01/13/2024",  # mês 13: não aceita formato americano
        "2024-13-01",
        "01/02",  # sem ano
        "01/02/2024/05",
        "1/2/202",
        "2024201",
        "20241301",
        "01/02/2024 25:00",  # hora inválida
        "01/02/2024 abc",
    ],
)
def test_texto_invalido_gera_erro(texto: str) -> None:
    with pytest.raises(DataInvalida):
        parse_data(texto)


@pytest.mark.parametrize("valor", [None, 20240201, 1.5, True, []])
def test_tipo_invalido_gera_erro(valor: object) -> None:
    with pytest.raises(DataInvalida):
        parse_data(valor)


def test_mensagem_de_erro_mostra_o_valor_recebido() -> None:
    with pytest.raises(DataInvalida, match="31/02/2024"):
        parse_data("31/02/2024")
