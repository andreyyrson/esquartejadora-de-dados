"""Layouts do Sicoob.

Os textos abaixo reproduzem a saída do pdfplumber para os dois layouts
do Sicoob, conforme documentado e validado contra extratos reais pelo
conversor-pdf-para-ofx (MIT, Jean Vieira), incluindo as quebras de
linha que o pdfplumber produz em valores acima de 1.000,00.
"""

from datetime import date
from decimal import Decimal

import pytest

from conciliador.conferencia import StatusConferencia, conferir_saldo
from conciliador.leitores.erros import LeituraInvalida
from conciliador.leitores.pdf.bancos import sicoob
from conciliador.transacao import Origem

CABECALHO = "SICOOB - SISTEMA DE COOPERATIVAS DE CRÉDITO DO BRASIL"

CURTO = f"""{CABECALHO}
EXTRATO CONTA CORRENTE
PERÍODO: 01/12/2023 - 31/01/2024
DATA HISTÓRICO VALOR
30/11 SALDO ANTERIOR 1.000,00C
15/12 PIX RECEB.OUTRA IF 150,00C
20/12 TARIFA PACOTE 12,90D
20/12 SALDO DO DIA 1.137,10C
05/01 PIX EMIT.OUTRA IF 4.554,00
D
1.200,00
08/01 PIX RECEB.OUTRA IF
C
09/01 DEP.CHEQUE BLOQ.1D 6.254,00*
09/01 SALDO BLOQ.ANTERIOR 6.254,00*
12/01 LIBER.DEPOSITO BLOQ 6.254,00C
12/01 SALDO DO DIA 4.037,10C
"""

DETALHADO = f"""{CABECALHO}
15/02/2024 EXTRATO CONTA CORRENTE 10:30:00
DATA DOCUMENTO HISTÓRICO VALOR
31/01/2024 SALDO ANTERIOR 20.456,14C
31/01/2024 SALDO BLOQUEADO ANTERIOR 0,00C
01/02/2024 Pix PIX RECEBIDO 500,00C
REM.: FULANO DE TAL
Recebimento Pix
01/02/2024 123456 PAGAMENTO BOLETO 1.250,40D
01/02/2024 SALDO DO DIA 19.705,74C
02/02/2024 RDC AUTOMATICO 700,00D
02/02/2024 SALDO DO DIA 19.005,74C
"""


def extrair(texto: str):  # type: ignore[no-untyped-def]
    return sicoob.extrair(texto, arquivo="sicoob.pdf")


class TestReconhecimento:
    def test_reconhece_sicoob(self) -> None:
        assert sicoob.reconhece(CURTO)
        assert sicoob.reconhece(DETALHADO)

    def test_nome_sicoob_como_favorecido_nao_confunde(self) -> None:
        # Extrato de outro banco com pagamento a um favorecido "SICOOB".
        outro = "EXTRATO SICREDI\n01/02/2024 TED PARA SICOOB CREDIPEL 10,00D"
        assert not sicoob.reconhece(outro)


class TestLayoutCurto:
    def test_credito_positivo_e_debito_negativo(self) -> None:
        extrato = extrair(CURTO)
        pix, tarifa = extrato.transacoes[:2]
        assert (pix.descricao, pix.valor) == ("PIX RECEB.OUTRA IF", Decimal("150.00"))
        assert (tarifa.descricao, tarifa.valor) == ("TARIFA PACOTE", Decimal("-12.90"))

    def test_ano_vem_do_periodo_na_virada_do_ano(self) -> None:
        extrato = extrair(CURTO)
        assert extrato.transacoes[0].data == date(2023, 12, 15)
        assert extrato.transacoes[2].data == date(2024, 1, 5)

    def test_cd_quebrado_na_linha_seguinte(self) -> None:
        # pdfplumber: "05/08 PIX EMIT.OUTRA IF 4.554,00" / "D"
        t = extrair(CURTO).transacoes[2]
        assert (t.descricao, t.valor) == ("PIX EMIT.OUTRA IF", Decimal("-4554.00"))

    def test_valor_deslocado_para_antes_da_linha(self) -> None:
        # pdfplumber: "1.200,00" / "08/01 PIX RECEB.OUTRA IF" / "C"
        t = extrair(CURTO).transacoes[3]
        assert (t.data, t.descricao, t.valor) == (
            date(2024, 1, 8),
            "PIX RECEB.OUTRA IF",
            Decimal("1200.00"),
        )

    def test_deposito_bloqueado_com_asterisco_nao_e_credito(self) -> None:
        # Só a liberação conta; contar os dois duplicaria o dinheiro.
        descricoes = [t.descricao for t in extrair(CURTO).transacoes]
        assert "DEP.CHEQUE BLOQ.1D" not in descricoes
        assert descricoes.count("LIBER.DEPOSITO BLOQ") == 1

    def test_linhas_de_saldo_nao_sao_lancamentos(self) -> None:
        descricoes = [t.descricao for t in extrair(CURTO).transacoes]
        assert not [d for d in descricoes if d.startswith("SALDO")]
        assert len(descricoes) == 5

    def test_saldos_e_conferencia(self) -> None:
        extrato = extrair(CURTO)
        assert extrato.saldo_inicial == Decimal("1000.00")
        assert extrato.saldo_final == Decimal("4037.10")
        assert extrato.inicio == date(2023, 12, 1)
        assert extrato.fim == date(2024, 1, 31)
        assert conferir_saldo(extrato).status is StatusConferencia.BATE

    def test_rastreio(self) -> None:
        extrato = extrair(CURTO)
        assert extrato.banco == "0756"
        for posicao, t in enumerate(extrato.transacoes, start=1):
            assert t.origem is Origem.BANCO
            assert t.arquivo == "sicoob.pdf"
            assert t.linha == posicao


class TestLayoutDetalhado:
    def test_lancamentos_com_ano_completo(self) -> None:
        extrato = extrair(DETALHADO)
        assert [(t.data, t.descricao, t.valor) for t in extrato.transacoes] == [
            (date(2024, 2, 1), "Pix PIX RECEBIDO", Decimal("500.00")),
            (date(2024, 2, 1), "123456 PAGAMENTO BOLETO", Decimal("-1250.40")),
            (date(2024, 2, 2), "RDC AUTOMATICO", Decimal("-700.00")),
        ]

    def test_saldos_e_conferencia(self) -> None:
        extrato = extrair(DETALHADO)
        assert extrato.saldo_inicial == Decimal("20456.14")
        assert extrato.saldo_final == Decimal("19005.74")
        assert conferir_saldo(extrato).status is StatusConferencia.BATE


class TestSaldos:
    def test_saldo_devedor_e_negativo(self) -> None:
        texto = (
            f"{CABECALHO}\nPERÍODO: 01/02/2024 - 29/02/2024\n"
            "31/01 SALDO ANTERIOR 50,00D\n"
            "01/02 TARIFA 10,00D\n"
            "01/02 SALDO DO DIA 60,00D\n"
        )
        extrato = extrair(texto)
        assert extrato.saldo_inicial == Decimal("-50.00")
        assert extrato.saldo_final == Decimal("-60.00")
        assert conferir_saldo(extrato).status is StatusConferencia.BATE

    def test_sem_linhas_de_saldo(self) -> None:
        texto = f"{CABECALHO}\nPERÍODO: 01/02/2024 - 29/02/2024\n01/02 TARIFA 10,00D\n"
        extrato = extrair(texto)
        assert extrato.saldo_inicial is None
        assert extrato.saldo_final is None


class TestErros:
    def test_sem_nenhum_lancamento_reconhecido(self) -> None:
        with pytest.raises(LeituraInvalida, match=r"sicoob\.pdf"):
            extrair(f"{CABECALHO}\nPÁGINA SEM LANÇAMENTOS\n")

    def test_data_impossivel(self) -> None:
        texto = f"{CABECALHO}\nPERÍODO: 01/02/2024 - 29/02/2024\n31/02 TARIFA 10,00D\n"
        with pytest.raises(LeituraInvalida, match=r"sicoob\.pdf"):
            extrair(texto)
