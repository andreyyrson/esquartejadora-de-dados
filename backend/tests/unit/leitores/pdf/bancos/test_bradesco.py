"""Layout do extrato do Bradesco em PDF.

O texto reproduz a saída do pdfplumber para o extrato do Bradesco,
conforme o parser validado contra extratos reais no conversor-pdf-para-ofx
(MIT, Jean Vieira): cada lançamento ocupa várias linhas (tipo, linha
com documento/valor/saldo, continuação). Todos os dados são fictícios.
"""

from datetime import date
from decimal import Decimal

import pytest

from conciliador.conferencia import StatusConferencia, conferir_saldo
from conciliador.leitores.erros import LeituraInvalida
from conciliador.leitores.pdf.bancos import bradesco
from conciliador.transacao import Origem

EXTRATO = """Bradesco Net Empresa
Extrato de: Agência: 0000 | Conta: 00000-0
Data Lançamento Dcto. Crédito (R$) Débito (R$) Saldo (R$)
SALDO ANTERIOR 1.000,00
03/08/2026 PIX RECEBIDO
REM: PESSOA EXEMPLO 03/08 1234567 500,00 1.500,00
TARIFA BANCARIA
MAX EMPRESARIAL 1234 -45,90 1.454,10
05/08/2026
PAGTO ELETRON COBRANCA 5678 -1.200,00 254,10
FORNECEDOR EXEMPLO
PIX ENVIADO
DES: PESSOA EXEMPLO 05/08 9999 -300,00 -45,90
Total 500,00 -1.545,90 -45,90
"""


def extrair(texto: str = EXTRATO):  # type: ignore[no-untyped-def]
    return bradesco.extrair(texto, arquivo="bradesco.pdf")


class TestReconhecimento:
    def test_reconhece_pelo_cabecalho_das_colunas(self) -> None:
        assert bradesco.reconhece(EXTRATO)

    def test_nome_do_banco_como_favorecido_nao_confunde(self) -> None:
        outro = "EXTRATO SICOOB\n01/08 TED BRADESCO SEGUROS 10,00D"
        assert not bradesco.reconhece(outro)


class TestLancamentos:
    def test_lancamentos_em_varias_linhas(self) -> None:
        assert [(t.data, t.descricao, t.valor) for t in extrair().transacoes] == [
            (
                date(2026, 8, 3),
                "PIX RECEBIDO - REM: PESSOA EXEMPLO 03/08",
                Decimal("500.00"),
            ),
            (date(2026, 8, 3), "TARIFA BANCARIA - MAX EMPRESARIAL", Decimal("-45.90")),
            (
                date(2026, 8, 5),
                "PAGTO ELETRON COBRANCA - FORNECEDOR EXEMPLO",
                Decimal("-1200.00"),
            ),
            (
                date(2026, 8, 5),
                "PIX ENVIADO - DES: PESSOA EXEMPLO 05/08",
                Decimal("-300.00"),
            ),
        ]

    def test_documento(self) -> None:
        assert [t.documento for t in extrair().transacoes] == [
            "1234567",
            "1234",
            "5678",
            "9999",
        ]

    def test_rastreio(self) -> None:
        extrato = extrair()
        assert extrato.banco == "0237"
        for posicao, t in enumerate(extrato.transacoes, start=1):
            assert (t.origem, t.arquivo, t.linha) == (
                Origem.BANCO,
                "bradesco.pdf",
                posicao,
            )

    def test_cabecalho_de_nova_pagina_nao_entra_na_descricao(self) -> None:
        texto = EXTRATO.replace(
            "PIX ENVIADO\n",
            "Data Lançamento Dcto. Crédito (R$) Débito (R$) Saldo (R$)\nPIX ENVIADO\n",
        )
        assert extrair(texto).transacoes[3].descricao.startswith("PIX ENVIADO")


class TestSaldos:
    def test_saldo_negativo_nao_perde_o_lancamento(self) -> None:
        # O último lançamento deixa a conta negativa (-45,90).
        assert extrair().transacoes[-1].valor == Decimal("-300.00")

    def test_saldo_inicial_e_final_e_conferencia(self) -> None:
        extrato = extrair()
        assert extrato.saldo_inicial == Decimal("1000.00")
        assert extrato.saldo_final == Decimal("-45.90")
        assert conferir_saldo(extrato).status is StatusConferencia.BATE
        assert extrato.avisos == ()

    def test_sem_saldo_anterior_usa_o_saldo_da_primeira_linha(self) -> None:
        texto = EXTRATO.replace("SALDO ANTERIOR 1.000,00\n", "")
        assert extrair(texto).saldo_inicial == Decimal("1000.00")

    def test_lancamento_perdido_e_apontado(self) -> None:
        # Sem a tarifa, a linha seguinte não fecha com o saldo anterior.
        texto = EXTRATO.replace(
            "TARIFA BANCARIA\nMAX EMPRESARIAL 1234 -45,90 1.454,10\n", ""
        )
        extrato = extrair(texto)
        assert conferir_saldo(extrato).status is StatusConferencia.NAO_BATE
        assert len(extrato.avisos) == 1
        assert "PAGTO ELETRON COBRANCA" in extrato.avisos[0]
        assert "diferença -45.90" in extrato.avisos[0]


class TestErros:
    def test_sem_lancamentos(self) -> None:
        with pytest.raises(LeituraInvalida, match=r"bradesco\.pdf"):
            extrair("Data Lançamento Dcto. Crédito (R$) Débito (R$) Saldo (R$)\n")

    def test_lancamento_sem_data(self) -> None:
        texto = EXTRATO.replace("03/08/2026 PIX RECEBIDO", "PIX RECEBIDO")
        with pytest.raises(LeituraInvalida, match="sem data"):
            extrair(texto)
