"""Perfis embutidos de bancos, com planilhas inventadas no layout de cada um."""

from datetime import date
from decimal import Decimal

from conciliador.conferencia import StatusConferencia, conferir_saldo
from conciliador.leitores.planilha import ler_planilha
from conciliador.leitores.planilha.perfis import identificar_perfil, perfil_embutido
from tests.apoio.planilhas import gerar_xlsx

BB: list[list[object]] = [
    ["Extrato Conta Corrente"],
    ["Agencia", "00000", "Conta corrente", "000000000000"],
    [
        "Data",
        "observacao",
        "Data balancete",
        "Agencia Origem",
        "Lote",
        "Numero Documento",
        "Cod. Historico",
        "Historico",
        "Valor R$ ",
        "Inf.",
        "Detalhamento Hist.",
    ],
    [
        "31/01/2024",
        " ",
        "31/01/2024",
        "0000",
        "00000",
        "0",
        "000",
        "Saldo Anterior           ",
        "1.000,00 ",
        "C",
        "   ",
    ],
    [
        "01/02/2024",
        " ",
        "01/02/2024",
        "0000",
        "11111",
        "00012345",
        "821",
        "Pix - Recebido           ",
        "500,00 ",
        "C",
        "01/02 10:00 EMPRESA EXEMPLO",
    ],
    [
        "02/02/2024",
        " ",
        "02/02/2024",
        "0000",
        "22222",
        "00067890",
        "435",
        "Tarifa Mensal Exemplo    ",
        "45,90 ",
        "D",
        "Cobrança exemplo   ",
    ],
    [
        "29/02/2024",
        " ",
        "29/02/2024",
        "0000",
        "00000",
        "0",
        "999",
        "S A L D O                ",
        "1.454,10 ",
        "C",
        "   ",
    ],
]


def test_bb_le_e_confere_o_saldo() -> None:
    extrato = ler_planilha(gerar_xlsx(BB), nome="bb.xlsx", perfil=perfil_embutido("bb"))
    assert [(t.data, t.descricao, t.valor) for t in extrato.transacoes] == [
        (
            date(2024, 2, 1),
            "Pix - Recebido - 01/02 10:00 EMPRESA EXEMPLO",
            Decimal("500.00"),
        ),
        (
            date(2024, 2, 2),
            "Tarifa Mensal Exemplo - Cobrança exemplo",
            Decimal("-45.90"),
        ),
    ]
    assert [t.documento for t in extrato.transacoes] == ["00012345", "00067890"]
    assert extrato.banco == "001"
    assert conferir_saldo(extrato).status is StatusConferencia.BATE


def test_identifica_o_perfil_do_bb() -> None:
    assert identificar_perfil(gerar_xlsx(BB)).nome == "bb"


def test_planilha_desconhecida() -> None:
    assert identificar_perfil(gerar_xlsx([["OUTRO BANCO"]])) is None
