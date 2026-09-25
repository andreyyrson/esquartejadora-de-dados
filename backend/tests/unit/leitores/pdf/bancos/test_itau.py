"""Layout do extrato mensal do Itaú em PDF.

O texto reproduz a saída do pdfplumber para o extrato mensal do Itaú,
conforme o parser validado contra extratos reais no conversor-pdf-para-ofx
(MIT, Jean Vieira). Todos os nomes e valores são fictícios.
"""

from datetime import date
from decimal import Decimal

import pytest

from conciliador.leitores.erros import LeituraInvalida
from conciliador.leitores.pdf.bancos import itau
from conciliador.transacao import Origem

EXTRATO = """Itaú Unibanco
extrato mensal
agência 0000 conta 00000-0
período de visualização: mar 2026
data lançamentos valor (R$) saldo (R$)
28/02 SALDO ANTERIOR 1.000,00
02/03 PIX RECEBIDO PESSOA EXEMPLO 02/03 500,00
02/03 TAR PACOTE SERVICOS 45,90-
02/03 SISPAG FORNECEDOR EXEMPLO 1.200,00- 254,10
03/03 APLIC AUT MAIS 254,10-
03/03 RSHOP-PADARIA EXEMPLO 10,00-
RSHOP-MERCADO EXEMPLO 20,00- 224,10
03/03 0,00 1.000,00 2,00
principal 5.784,11 15.901,17 0,00 16.980,46
compras a débito
03/03/26 RSHOP-PADARIA EXEMPLO 10,00
TOTAL 10,00
"""


def extrair(texto: str = EXTRATO):  # type: ignore[no-untyped-def]
    return itau.extrair(texto, arquivo="itau.pdf")


class TestReconhecimento:
    def test_reconhece_extrato_mensal_do_itau(self) -> None:
        assert itau.reconhece(EXTRATO)

    def test_nao_confunde_com_outro_banco_que_cita_itau(self) -> None:
        assert not itau.reconhece("SICOOB\n01/02 TED PARA ITAÚ 10,00D")


class TestLancamentos:
    def test_lancamentos_com_sinal_e_ano_do_cabecalho(self) -> None:
        assert [(t.data, t.descricao, t.valor) for t in extrair().transacoes] == [
            (date(2026, 3, 2), "PIX RECEBIDO PESSOA EXEMPLO 02/03", Decimal("500.00")),
            (date(2026, 3, 2), "TAR PACOTE SERVICOS", Decimal("-45.90")),
            (date(2026, 3, 2), "SISPAG FORNECEDOR EXEMPLO", Decimal("-1200.00")),
            (date(2026, 3, 3), "RSHOP-PADARIA EXEMPLO", Decimal("-10.00")),
            (date(2026, 3, 3), "RSHOP-MERCADO EXEMPLO", Decimal("-20.00")),
        ]

    def test_linha_sem_data_herda_o_dia_anterior(self) -> None:
        mercado = extrair().transacoes[4]
        assert mercado.data == date(2026, 3, 3)

    def test_rastreio(self) -> None:
        extrato = extrair()
        assert extrato.banco == "0341"
        assert extrato.inicio == date(2026, 3, 1)
        assert extrato.fim == date(2026, 3, 31)
        for posicao, t in enumerate(extrato.transacoes, start=1):
            assert (t.origem, t.arquivo, t.linha) == (Origem.BANCO, "itau.pdf", posicao)


class TestLinhasIgnoradas:
    def test_saldo_anterior_vira_saldo_inicial(self) -> None:
        extrato = extrair()
        assert extrato.saldo_inicial == Decimal("1000.00")
        assert "SALDO ANTERIOR" not in [t.descricao for t in extrato.transacoes]

    def test_saldo_anterior_negativo(self) -> None:
        texto = EXTRATO.replace("SALDO ANTERIOR 1.000,00", "SALDO ANTERIOR 1.000,00-")
        assert extrair(texto).saldo_inicial == Decimal("-1000.00")

    def test_aplicacao_automatica_fica_de_fora_com_aviso(self) -> None:
        extrato = extrair()
        assert not [t for t in extrato.transacoes if "APLIC AUT" in t.descricao]
        assert any("Aplic Aut Mais" in aviso for aviso in extrato.avisos)

    def test_sem_aplicacao_automatica_nao_ha_aviso(self) -> None:
        texto = EXTRATO.replace("03/03 APLIC AUT MAIS 254,10-\n", "")
        assert extrair(texto).avisos == ()

    def test_tabelas_de_resumo_nao_duplicam_lancamentos(self) -> None:
        # "03/03/26 ..." (resumo de compras), linha só de números
        # (aplicações) e "principal ..." (resumo do CDB) são ignoradas.
        descricoes = [t.descricao for t in extrair().transacoes]
        assert descricoes.count("RSHOP-PADARIA EXEMPLO") == 1
        assert not [d for d in descricoes if d.startswith(("principal", "TOTAL"))]

    def test_lancamento_antes_de_qualquer_data_e_ignorado(self) -> None:
        texto = EXTRATO.replace(
            "data lançamentos", "LANCAMENTO SEM DATA 99,00\ndata lançamentos"
        )
        assert "LANCAMENTO SEM DATA" not in [
            t.descricao for t in extrair(texto).transacoes
        ]

    def test_saldo_final_nao_e_adivinhado(self) -> None:
        # O layout do saldo final não foi validado: melhor não inventar.
        assert extrair().saldo_final is None


class TestErros:
    def test_sem_mes_e_ano_no_cabecalho(self) -> None:
        texto = EXTRATO.replace("período de visualização: mar 2026\n", "")
        with pytest.raises(LeituraInvalida, match="mês/ano"):
            extrair(texto)

    def test_sem_lancamentos(self) -> None:
        with pytest.raises(LeituraInvalida, match=r"itau\.pdf"):
            extrair("Itaú Unibanco\nextrato mensal\nmar 2026\n")

    def test_data_impossivel(self) -> None:
        texto = EXTRATO.replace("03/03 RSHOP-PADARIA", "31/02 RSHOP-PADARIA")
        with pytest.raises(LeituraInvalida, match=r"itau\.pdf"):
            extrair(texto)
