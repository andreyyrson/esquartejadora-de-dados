"""Perfis embutidos de bancos, com planilhas inventadas no layout de cada um."""

from datetime import date
from decimal import Decimal

from conciliador.conferencia import StatusConferencia, conferir_saldo
from conciliador.leitores.planilha import ler_planilha
from conciliador.leitores.planilha.perfis import identificar_perfil, perfil_embutido
from conciliador.transacao import Origem
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


BRADESCO: list[list[object]] = [
    ["Bradesco Net Empresa"],
    ["Extrato Mensal / Por Período"],
    ["Data", "Lançamento", "Dcto.", "Crédito (R$)", "Débito (R$)", "Saldo (R$)"],
    ["", "SALDO ANTERIOR", "", "", "", "1.000,00"],
    ["01/02/2024", "PIX RECEBIDO EXEMPLO", "1111", "500,00", "", "1.500,00"],
    ["", "REM: EMPRESA FICTICIA", "", "", "", ""],
    ["02/02/2024", "TARIFA EXEMPLO", "2222", "", "-45,90", "1.454,10"],
    ["Total", "", "", "500,00", "-45,90", "1.454,10"],
    ["Últimos Lançamentos"],
    ["03/02/2024", "LANCAMENTO FUTURO", "3333", "", "-99,00", ""],
]


def test_bradesco_le_ate_o_total_e_confere_o_saldo() -> None:
    extrato = ler_planilha(
        gerar_xlsx(BRADESCO), nome="bradesco.xlsx", perfil=perfil_embutido("bradesco")
    )
    assert [(t.data, t.descricao, t.valor) for t in extrato.transacoes] == [
        (date(2024, 2, 1), "PIX RECEBIDO EXEMPLO", Decimal("500.00")),
        (date(2024, 2, 2), "TARIFA EXEMPLO", Decimal("-45.90")),
    ]
    assert [t.documento for t in extrato.transacoes] == ["1111", "2222"]
    assert extrato.banco == "237"
    assert extrato.saldo_inicial == Decimal("1000.00")
    assert extrato.saldo_final == Decimal("1454.10")
    assert conferir_saldo(extrato).status is StatusConferencia.BATE
    assert extrato.avisos == ()


SAFRA: list[list[object]] = [
    ["Banco Safra S/A "],
    ["Conta Corrente - Extrato de Movimentação"],
    ["Período de 01/01/2024 a 29/02/2024"],
    [
        "Data",
        "Situação",
        "Tipo do Lançamento",
        "Lançamento",
        "Complemento",
        "Nº Documento",
        "Valor",
        "Saldo",
    ],
    ["", "Realizado", "Saldo", "SALDO TOTAL", "", "", None, 1454.1],
    ["02/02", "Realizado", "Débito", "TARIFA EXEMPLO", "", 2222.0, -45.9, None],
    [
        "01/02",
        "Realizado",
        "Crédito",
        "PIX RECEBIDO",
        "EMPRESA FICTICIA",
        1111.0,
        500.0,
        None,
    ],
    ["31/12", "Realizado", "Crédito", "TED RECEBIDA", "", 3333.0, 10.0, None],
    ["", "Realizado", "Saldo", "SALDO ANTERIOR", "", "", None, 954.1],
]


def test_safra_usa_o_ano_do_periodo_e_ignora_linhas_de_saldo() -> None:
    extrato = ler_planilha(
        gerar_xlsx(SAFRA), nome="safra.xlsx", perfil=perfil_embutido("safra")
    )
    assert [(t.data, t.descricao, t.valor) for t in extrato.transacoes] == [
        (date(2024, 2, 2), "TARIFA EXEMPLO", Decimal("-45.90")),
        (date(2024, 2, 1), "PIX RECEBIDO - EMPRESA FICTICIA", Decimal("500.00")),
        (date(2023, 12, 31), "TED RECEBIDA", Decimal("10.00")),
    ]
    assert [t.documento for t in extrato.transacoes] == ["2222", "1111", "3333"]
    assert extrato.banco == "422"
    assert extrato.inicio == date(2024, 1, 1)


SISTEMA_CONTAS_PAGAS: list[list[object]] = [
    [
        "Cód. Filial",
        "Dt. Pagto",
        "Lanc.",
        "Parceiro",
        "Valor Pago",
        "Histórico",
        "Dt. Compensação",
    ],
    [
        "1",
        "01/02/2024",
        101.0,
        "FORNECEDOR EXEMPLO",
        45.9,
        "COMPRA EXEMPLO",
        "02/02/2024",
    ],
    ["1", "03/02/2024", 102.0, "OUTRO FORNECEDOR", 100.0, "", ""],
]


def test_sistema_contas_pagas_inverte_o_sinal_e_prefere_a_compensacao() -> None:
    perfil = perfil_embutido("sistema_contas_pagas")
    extrato = ler_planilha(
        gerar_xlsx(SISTEMA_CONTAS_PAGAS), nome="s.xlsx", perfil=perfil
    )
    assert [(t.data, t.descricao, t.valor, t.origem) for t in extrato.transacoes] == [
        (
            date(2024, 2, 2),
            "FORNECEDOR EXEMPLO - COMPRA EXEMPLO",
            Decimal("-45.90"),
            Origem.SISTEMA,
        ),
        (date(2024, 2, 3), "OUTRO FORNECEDOR", Decimal("-100.00"), Origem.SISTEMA),
    ]
    assert [t.documento for t in extrato.transacoes] == ["101", "102"]


def test_identifica_cada_perfil() -> None:
    assert identificar_perfil(gerar_xlsx(BRADESCO)).nome == "bradesco"
    assert identificar_perfil(gerar_xlsx(SAFRA)).nome == "safra"
    assert (
        identificar_perfil(gerar_xlsx(SISTEMA_CONTAS_PAGAS)).nome
        == "sistema_contas_pagas"
    )
