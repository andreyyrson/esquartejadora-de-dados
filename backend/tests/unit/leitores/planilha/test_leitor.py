"""Leitor genérico de planilhas configurado por perfil. Dados inventados."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from conciliador.conferencia import StatusConferencia, conferir_saldo
from conciliador.leitores.erros import LeituraInvalida
from conciliador.leitores.planilha import PerfilInvalido, carregar_perfil, ler_planilha
from conciliador.transacao import Origem
from tests.apoio.planilhas import gerar_xls, gerar_xlsx

PERFIL = carregar_perfil(
    """
nome = "exemplo"
banco = "999"
origem = "banco"
reconhecer = ["EXTRATO EXEMPLO"]

[colunas]
data = ["Data"]
descricao = ["Histórico", "Detalhe"]
valor = "Valor"
natureza = "D/C"
documento = "Documento"

[saldos]
inicial = ["SALDO ANTERIOR"]
final = ["SALDO FINAL"]

[fim]
marcadores = ["Total"]
"""
)

LINHAS: list[list[object]] = [
    ["EXTRATO EXEMPLO"],
    ["Agencia", "0001"],
    [],
    ["Data", "Histórico", "Detalhe", "Documento", " Valor ", "D/C"],
    ["31/01/2024", "SALDO ANTERIOR", "", "", "1.000,00", "C"],
    ["01/02/2024", "PIX RECEBIDO", "PESSOA EXEMPLO", "123", "500,00", "C"],
    [datetime(2024, 2, 2), "TARIFA", "", "", 45.9, "D"],
    [None, None, None, None, None, None],
    ["05/02/2024", "PAGAMENTO", "FORNECEDOR EXEMPLO", "456", "1.200,00", "D"],
    ["05/02/2024", "SALDO FINAL", "", "", "254,10", "C"],
    ["Total", "", "", "", "", ""],
    ["06/02/2024", "DEPOIS DO FIM", "", "", "9,99", "C"],
]


def ler(conteudo: bytes, perfil=PERFIL):  # type: ignore[no-untyped-def]
    return ler_planilha(conteudo, nome="extrato.xlsx", perfil=perfil)


class TestLeituraPorPerfil:
    def test_lancamentos(self) -> None:
        extrato = ler(gerar_xlsx(LINHAS))
        assert [(t.data, t.descricao, t.valor) for t in extrato.transacoes] == [
            (date(2024, 2, 1), "PIX RECEBIDO - PESSOA EXEMPLO", Decimal("500.00")),
            (date(2024, 2, 2), "TARIFA", Decimal("-45.90")),
            (date(2024, 2, 5), "PAGAMENTO - FORNECEDOR EXEMPLO", Decimal("-1200.00")),
        ]

    def test_documento_linha_origem_e_banco(self) -> None:
        extrato = ler(gerar_xlsx(LINHAS))
        assert [t.documento for t in extrato.transacoes] == ["123", None, "456"]
        assert [t.linha for t in extrato.transacoes] == [6, 7, 9]
        assert {t.origem for t in extrato.transacoes} == {Origem.BANCO}
        assert extrato.transacoes[0].arquivo == "extrato.xlsx"
        assert extrato.banco == "999"

    def test_saldos_e_conferencia(self) -> None:
        extrato = ler(gerar_xlsx(LINHAS))
        assert (extrato.saldo_inicial, extrato.saldo_final) == (
            Decimal("1000.00"),
            Decimal("254.10"),
        )
        assert conferir_saldo(extrato).status is StatusConferencia.BATE

    def test_xls_antigo_da_o_mesmo_resultado(self) -> None:
        novo, antigo = ler(gerar_xlsx(LINHAS)), ler(gerar_xls(LINHAS))
        assert [(t.data, t.valor, t.descricao) for t in antigo.transacoes] == [
            (t.data, t.valor, t.descricao) for t in novo.transacoes
        ]

    def test_so_a_primeira_aba(self) -> None:
        copia = [["Data", "Coluna1", "Valor"], ["01/02/2024", "X", 1]]
        extrato = ler(gerar_xlsx(LINHAS, abas_extras={"Extrato (2)": copia}))
        assert len(extrato.transacoes) == 3

    def test_sem_saldos_no_arquivo(self) -> None:
        linhas = [linha for linha in LINHAS if "SALDO" not in str(linha[1:2])]
        extrato = ler(gerar_xlsx(linhas))
        assert (extrato.saldo_inicial, extrato.saldo_final) == (None, None)


class TestVariacoesDePerfil:
    def test_colunas_de_credito_e_debito(self) -> None:
        perfil = carregar_perfil(
            """
nome = "cd"
origem = "banco"
[colunas]
data = ["Data"]
descricao = ["Lançamento"]
credito = "Crédito (R$)"
debito = "Débito (R$)"
"""
        )
        linhas: list[list[object]] = [
            ["Data", "Lançamento", "Crédito (R$)", "Débito (R$)"],
            ["01/02/2024", "PIX RECEBIDO", "500,00", ""],
            ["02/02/2024", "TARIFA", "", "-45,90"],
            ["03/02/2024", "PIX ENVIADO", None, "10,00"],
        ]
        extrato = ler(gerar_xlsx(linhas), perfil)
        assert [t.valor for t in extrato.transacoes] == [
            Decimal("500.00"),
            Decimal("-45.90"),
            Decimal("-10.00"),
        ]

    def test_sistema_com_sinal_invertido_e_data_alternativa(self) -> None:
        perfil = carregar_perfil(
            """
nome = "sistema"
origem = "sistema"
inverter_sinal = true
[colunas]
data = ["Dt. Compensação", "Dt. Pagto"]
descricao = ["Parceiro", "Histórico"]
valor = "Valor Pago"
documento = "Lanc."
"""
        )
        linhas: list[list[object]] = [
            [
                "Dt. Pagto",
                "Dt. Compensação",
                "Lanc.",
                "Parceiro",
                "Valor Pago",
                "Histórico",
            ],
            [
                datetime(2024, 2, 5),
                datetime(2024, 2, 6),
                1001,
                "FORNECEDOR A",
                250.0,
                "NF 1",
            ],
            [datetime(2024, 2, 7), None, 1002, "FORNECEDOR B", -30.5, "ESTORNO"],
        ]
        extrato = ler(gerar_xls(linhas), perfil)
        assert [
            (t.data, t.valor, t.documento, t.origem) for t in extrato.transacoes
        ] == [
            (date(2024, 2, 6), Decimal("-250.00"), "1001", Origem.SISTEMA),
            (date(2024, 2, 7), Decimal("30.50"), "1002", Origem.SISTEMA),
        ]
        assert extrato.transacoes[0].descricao == "FORNECEDOR A - NF 1"

    def test_data_sem_ano_usa_o_periodo_e_linhas_ignoradas(self) -> None:
        perfil = carregar_perfil(
            """
nome = "ano"
origem = "banco"
periodo = 'Período de (\\d{2}/\\d{2}/\\d{4}) a (\\d{2}/\\d{2}/\\d{4})'
[colunas]
data = ["Data"]
descricao = ["Lançamento"]
valor = "Valor"
[ignorar]
coluna = "Tipo"
valores = ["Saldo"]
"""
        )
        linhas: list[list[object]] = [
            ["Período de 01/12/2023 a 31/01/2024"],
            ["Data", "Tipo", "Lançamento", "Valor"],
            ["05/01", "Débito", "TARIFA", -2.5],
            ["31/12", "Saldo", "SALDO CONTA", 100],
            ["28/12", "Crédito", "PIX RECEBIDO", 10],
        ]
        extrato = ler(gerar_xlsx(linhas), perfil)
        assert [(t.data, t.valor) for t in extrato.transacoes] == [
            (date(2024, 1, 5), Decimal("-2.50")),
            (date(2023, 12, 28), Decimal("10.00")),
        ]
        assert (extrato.inicio, extrato.fim) == (date(2023, 12, 1), date(2024, 1, 31))


class TestReconhecimento:
    def test_reconhece_pelos_textos_do_cabecalho(self) -> None:
        assert PERFIL.reconhece(gerar_xlsx(LINHAS))

    def test_nao_reconhece_outra_planilha(self) -> None:
        assert not PERFIL.reconhece(gerar_xlsx([["OUTRO BANCO"], ["Data", "Valor"]]))

    def test_nao_reconhece_o_que_nao_e_planilha(self) -> None:
        assert not PERFIL.reconhece(b"isto nao e planilha")


class TestErros:
    def test_cabecalho_nao_encontrado(self) -> None:
        with pytest.raises(LeituraInvalida, match=r"cabeçalho.*Documento"):
            ler(gerar_xlsx([["Data", "Histórico", "Detalhe", "Valor", "D/C"]]))

    def test_valor_ilegivel_aponta_a_linha(self) -> None:
        linhas = [list(linha) for linha in LINHAS]
        linhas[5][4] = "abc"
        with pytest.raises(LeituraInvalida, match=r"extrato\.xlsx, linha 6"):
            ler(gerar_xlsx(linhas))

    def test_natureza_invalida(self) -> None:
        linhas = [list(linha) for linha in LINHAS]
        linhas[5][5] = "X"
        with pytest.raises(LeituraInvalida, match="linha 6"):
            ler(gerar_xlsx(linhas))

    def test_nao_e_planilha(self) -> None:
        with pytest.raises(LeituraInvalida, match=r"ruim\.xlsx"):
            ler_planilha(b"isto nao e planilha", nome="ruim.xlsx", perfil=PERFIL)

    def test_planilha_vazia(self) -> None:
        with pytest.raises(LeituraInvalida, match="cabeçalho"):
            ler(gerar_xlsx([]))


CABECA = "nome = 'x'\norigem = 'banco'\n"
COLUNAS_OK = "[colunas]\ndata = ['D']\ndescricao = ['H']\nvalor = 'V'"


class TestPerfilInvalido:
    @pytest.mark.parametrize(
        "texto",
        [
            CABECA,  # sem colunas
            CABECA + "[colunas]\ndescricao = ['H']\nvalor = 'V'",  # sem data
            CABECA + "[colunas]\ndata = ['D']\ndescricao = ['H']",  # sem valor
            CABECA.replace("banco", "outra") + COLUNAS_OK,  # origem inválida
            "isto não é toml = = =",
        ],
    )
    def test_perfil_invalido(self, texto: str) -> None:
        with pytest.raises(PerfilInvalido):
            carregar_perfil(texto)


PERFIL_COM_SALDO = carregar_perfil(
    """
nome = "saldo"
origem = "banco"
[colunas]
data = ["Data"]
descricao = ["Lançamento"]
credito = "Crédito"
debito = "Débito"
saldo = "Saldo"
[saldos]
inicial = ["SALDO ANTERIOR"]
[fim]
marcadores = ["Total"]
"""
)
COM_SALDO: list[list[object]] = [
    ["Data", "Lançamento", "Crédito", "Débito", "Saldo"],
    ["31/01/2024", "SALDO ANTERIOR", "", "", "1.000,00"],
    ["01/02/2024", "PIX RECEBIDO", "500,00", "", "1.500,00"],
    ["02/02/2024", "TARIFA", "", "-45,90", "1.454,10"],
    ["03/02/2024", "PIX ENVIADO", "", "-1.500,00", "-45,90"],
    ["Total", "", "500,00", "-1.545,90", "-45,90"],
]


class TestColunaDeSaldo:
    def test_saldo_anterior_vem_da_coluna_de_saldo(self) -> None:
        extrato = ler(gerar_xlsx(COM_SALDO), PERFIL_COM_SALDO)
        assert extrato.saldo_inicial == Decimal("1000.00")
        assert len(extrato.transacoes) == 3

    def test_saldo_final_e_o_da_ultima_linha(self) -> None:
        extrato = ler(gerar_xlsx(COM_SALDO), PERFIL_COM_SALDO)
        assert extrato.saldo_final == Decimal("-45.90")
        assert conferir_saldo(extrato).status is StatusConferencia.BATE
        assert extrato.avisos == ()

    def test_sem_saldo_anterior_usa_a_primeira_linha(self) -> None:
        extrato = ler(gerar_xlsx([COM_SALDO[0], *COM_SALDO[2:]]), PERFIL_COM_SALDO)
        assert extrato.saldo_inicial == Decimal("1000.00")

    def test_linha_perdida_vira_aviso_com_a_linha_e_a_diferenca(self) -> None:
        sem_tarifa = [linha for linha in COM_SALDO if linha[1] != "TARIFA"]
        extrato = ler(gerar_xlsx(sem_tarifa), PERFIL_COM_SALDO)
        assert conferir_saldo(extrato).status is StatusConferencia.NAO_BATE
        [aviso] = extrato.avisos
        assert "linha 4" in aviso
        assert "diferença -45.90" in aviso
