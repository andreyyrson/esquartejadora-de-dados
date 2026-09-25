"""Layout do extrato do Gerenciador Caixa em PDF.

O texto reproduz a saída do pdfplumber para o extrato do Gerenciador
Caixa, conforme o parser validado contra extratos reais no
conversor-pdf-para-ofx (MIT, Jean Vieira): cada lançamento em três
linhas (histórico, data, documento/detalhe/valor/saldo/C-D). Todos os
dados são fictícios.
"""

from datetime import date
from decimal import Decimal

import pytest

from conciliador.leitores.erros import LeituraInvalida
from conciliador.leitores.pdf.bancos import caixa
from conciliador.transacao import Origem

EXTRATO = """Gerenciador CAIXA
Extrato no período de 01/08/2026 a 31/08/2026
Histórico Data Documento Valor Saldo
SALDO ANTERIOR
31/07/2026
000000 SALDO R$ 1.000,00 R$ 1.000,00 C
PIX RECEBIDO
03/08/2026
031234 PESSOA EXEMPLO R$ 500,00 R$ 1.500,00 C
TARIFA PACOTE
03/08/2026
031235 CESTA SERVICOS R$ 45,90 R$ 1.454,10 D
SALDO DO DIA
03/08/2026
000000 SALDO R$ 1.454,10 R$ 1.454,10 C
PAGAMENTO BOLETO
05/08/2026
051236 FORNECEDOR EXEMPLO R$ 1.200,00 R$ 254,10 D
"""


def extrair(texto: str = EXTRATO):  # type: ignore[no-untyped-def]
    return caixa.extrair(texto, arquivo="caixa.pdf")


class TestReconhecimento:
    def test_reconhece_o_gerenciador_caixa(self) -> None:
        assert caixa.reconhece(EXTRATO)

    def test_reconhece_pelo_titulo_do_periodo(self) -> None:
        assert caixa.reconhece("Extrato no período de 01/08/2026 a 31/08/2026")

    def test_nome_caixa_como_favorecido_nao_confunde(self) -> None:
        assert not caixa.reconhece("SICOOB\n01/08 TED CAIXA ECONOMICA 10,00D")


class TestLancamentos:
    def test_historico_detalhe_valor_e_sinal(self) -> None:
        assert [(t.data, t.descricao, t.valor) for t in extrair().transacoes] == [
            (date(2026, 8, 3), "PIX RECEBIDO - PESSOA EXEMPLO", Decimal("500.00")),
            (date(2026, 8, 3), "TARIFA PACOTE - CESTA SERVICOS", Decimal("-45.90")),
            (
                date(2026, 8, 5),
                "PAGAMENTO BOLETO - FORNECEDOR EXEMPLO",
                Decimal("-1200.00"),
            ),
        ]

    def test_documento(self) -> None:
        assert [t.documento for t in extrair().transacoes] == [
            "031234",
            "031235",
            "051236",
        ]

    def test_periodo_e_rastreio(self) -> None:
        extrato = extrair()
        assert (extrato.inicio, extrato.fim) == (date(2026, 8, 1), date(2026, 8, 31))
        assert extrato.banco == "0104"
        for posicao, t in enumerate(extrato.transacoes, start=1):
            assert (t.origem, t.arquivo, t.linha) == (
                Origem.BANCO,
                "caixa.pdf",
                posicao,
            )

    def test_linhas_de_saldo_nao_sao_lancamentos(self) -> None:
        descricoes = [t.descricao for t in extrair().transacoes]
        assert not [d for d in descricoes if d.startswith("SALDO")]

    def test_saldos_nao_sao_adivinhados(self) -> None:
        # O significado do C/D nas linhas de saldo não foi validado.
        extrato = extrair()
        assert (extrato.saldo_inicial, extrato.saldo_final) == (None, None)

    def test_sem_periodo_no_cabecalho(self) -> None:
        texto = EXTRATO.replace("Extrato no período de 01/08/2026 a 31/08/2026\n", "")
        extrato = extrair(texto)
        assert (extrato.inicio, extrato.fim) == (None, None)
        assert len(extrato.transacoes) == 3


class TestErros:
    def test_sem_lancamentos(self) -> None:
        with pytest.raises(LeituraInvalida, match=r"caixa\.pdf"):
            extrair("Gerenciador CAIXA\nnenhum lançamento\n")

    def test_data_impossivel(self) -> None:
        texto = EXTRATO.replace("05/08/2026", "31/02/2026")
        with pytest.raises(LeituraInvalida, match=r"caixa\.pdf"):
            extrair(texto)
