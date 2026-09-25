"""Tratamento dos lançamentos antes da conciliação (RF11, RF12, RF13).

Todos os nomes, documentos e valores são fictícios; só a estrutura das
descrições imita a de cada banco. CPF/CNPJ de exemplo são números
sequenciais com dígito verificador calculado.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from conciliador.transacao import Origem, Transacao
from conciliador.tratamento import (
    Contraparte,
    TipoLancamento,
    tratar,
    tratar_todos,
)

CPF = "123.456.789-09"  # dados-sensiveis: exemplo
CPF_DIGITOS = "12345678909"  # dados-sensiveis: exemplo
CNPJ = "11.222.333/0001-81"  # dados-sensiveis: exemplo
CNPJ_DIGITOS = "11222333000181"  # dados-sensiveis: exemplo


def lanc(
    descricao: str,
    valor: str = "-10.00",
    dia: int = 1,
    origem: Origem = Origem.BANCO,
) -> Transacao:
    return Transacao(
        data=date(2024, 2, 1) + timedelta(days=dia - 1),
        valor=Decimal(valor),
        descricao=descricao,
        origem=origem,
    )


class TestLimpezaEContraparte:
    """RF11: descrição limpa e contraparte extraída."""

    @pytest.mark.parametrize(
        ("descricao", "limpa", "nome", "documento"),
        [
            # Itaú
            (
                f"PIX ENVIADO PESSOA EXEMPLO {CPF}",
                "PESSOA EXEMPLO",
                "PESSOA EXEMPLO",
                CPF_DIGITOS,
            ),
            (
                f"PAGAMENTOS FORNECEDOR EXEMPLO LTDA {CNPJ}",
                "FORNECEDOR EXEMPLO LTDA",
                "FORNECEDOR EXEMPLO LTDA",
                CNPJ_DIGITOS,
            ),
            # Inter
            (
                'Pix enviado: "Cp :12345678-Pessoa Exemplo"',
                "PESSOA EXEMPLO",
                "PESSOA EXEMPLO",
                None,
            ),
            (
                'Pagamento efetuado: "FORNECEDOR EXEMPLO LTDA"',
                "FORNECEDOR EXEMPLO LTDA",
                "FORNECEDOR EXEMPLO LTDA",
                None,
            ),
            # Bradesco
            (
                "PIX RECEBIDO REM: PESSOA EXEMPLO 03/08",
                "PESSOA EXEMPLO",
                "PESSOA EXEMPLO",
                None,
            ),
            (
                "PIX ENVIADO - DES: PESSOA EXEMPLO 05/08",
                "PESSOA EXEMPLO",
                "PESSOA EXEMPLO",
                None,
            ),
            # Banco do Brasil
            (
                f"Pix - Recebido - 05/08 04:15 {CNPJ_DIGITOS} EMPRESA EXEMPLO",
                "EMPRESA EXEMPLO",
                "EMPRESA EXEMPLO",
                CNPJ_DIGITOS,
            ),
            (
                f"TED-Crédito em Conta - 341 1677 {CNPJ_DIGITOS} EMPRESA EXEMPLO",
                "EMPRESA EXEMPLO",
                "EMPRESA EXEMPLO",
                CNPJ_DIGITOS,
            ),
            # Safra (CPF sem o hífen)
            (
                "PIX RECEBIDO SAFRAPAY - Pessoa Exemplo 123.456.789 09",
                "PESSOA EXEMPLO",
                "PESSOA EXEMPLO",
                CPF_DIGITOS,
            ),  # dados-sensiveis: exemplo
            # Cora
            (
                "Transf Pix enviada - Pessoa Exemplo",
                "PESSOA EXEMPLO",
                "PESSOA EXEMPLO",
                None,
            ),
            (
                "Pgto QR Code Pix - EMPRESA EXEMPLO LTDA",
                "EMPRESA EXEMPLO LTDA",
                "EMPRESA EXEMPLO LTDA",
                None,
            ),
        ],
    )
    def test_formatos_dos_bancos(
        self, descricao: str, limpa: str, nome: str, documento: str | None
    ) -> None:
        tratado = tratar(lanc(descricao))
        assert tratado.descricao_limpa == limpa
        assert tratado.contraparte == Contraparte(nome=nome, documento=documento)

    def test_tira_acentos_e_espacos_sobrando(self) -> None:
        tratado = tratar(lanc("Transf Pix enviada -   Conceição   Exemplo  "))
        assert tratado.descricao_limpa == "CONCEICAO EXEMPLO"

    @pytest.mark.parametrize(
        "numero",
        [
            "123.456.789-00",  # CPF com dígito errado
            "111.111.111-11",  # todos os dígitos iguais
            "11.222.333/0001-00",  # CNPJ com dígito errado
            "00000000000000",
        ],
    )
    def test_numero_que_nao_e_documento_valido_nao_vira_documento(
        self, numero: str
    ) -> None:
        tratado = tratar(lanc(f"PIX ENVIADO PESSOA EXEMPLO {numero}"))
        assert tratado.contraparte.documento is None

    def test_descricao_sem_contraparte(self) -> None:
        tratado = tratar(lanc("TARIFA MENSAL EXEMPLO"))
        assert tratado.descricao_limpa == "TARIFA MENSAL EXEMPLO"
        assert tratado.contraparte == Contraparte(nome=None, documento=None)

    def test_descricao_vazia(self) -> None:
        tratado = tratar(lanc(""))
        assert tratado.descricao_limpa == ""
        assert tratado.contraparte == Contraparte(nome=None, documento=None)

    def test_mantem_a_transacao_original(self) -> None:
        original = lanc("PIX ENVIADO PESSOA EXEMPLO")
        assert tratar(original).transacao is original


class TestTipo:
    """RF12: tipo do lançamento, com prioridade entre as regras."""

    @pytest.mark.parametrize(
        ("descricao", "tipo"),
        [
            ("PIX ENVIADO PESSOA EXEMPLO", TipoLancamento.PIX),
            ("Pgto QR Code Pix - EMPRESA", TipoLancamento.PIX),
            ("TED-Pagamento Exemplo - 001 0001", TipoLancamento.TED),
            ("DOC ELETRONICO", TipoLancamento.DOC),
            ("Boleto pago - EMPRESA", TipoLancamento.BOLETO),
            ("PAGTO ELETRON COBRANCA", TipoLancamento.BOLETO),
            ('Pagamento efetuado: "EMPRESA EXEMPLO"', TipoLancamento.BOLETO),  # Inter
            ("LIQUIDACAO COBRANCA EXEMPLO", TipoLancamento.BOLETO),
            ("RECEBIMENTO REDE CARTAO EXEMPLO", TipoLancamento.CARTAO),
            ("RSHOP-PADARIA EXEMPLO", TipoLancamento.CARTAO),
            ("TARIFA TRANSFERENCIA PIX EXEMPLO", TipoLancamento.TARIFA),
            ("TARIFA PIX COBRANCA EXEMPLO", TipoLancamento.TARIFA),
            ("TAR PIX EXEMPLO", TipoLancamento.TARIFA),
            ("Tarifa Mensal Exemplo", TipoLancamento.TARIFA),
            ("PAGTO DARF EXEMPLO", TipoLancamento.IMPOSTO),
            ("Impostos - GUIA ESTADUAL EXEMPLO", TipoLancamento.IMPOSTO),
            ("CHEQUE COMPENSADO", TipoLancamento.CHEQUE),
            ("DEP DINHEIRO EXEMPLO 123", TipoLancamento.DEPOSITO),
            ("SAQUE ATM", TipoLancamento.SAQUE),
            ("APLIC AUT MAIS", TipoLancamento.APLICACAO),
            ("RESGATE POUPANCA EXEMPLO", TipoLancamento.APLICACAO),
            ("RDC AUTOMATICO", TipoLancamento.APLICACAO),
            ("TRANSFERENCIA ENTRE CONTAS", TipoLancamento.TRANSFERENCIA),
            ("DEVOLUCAO CHQ SEM FUNDOS", TipoLancamento.ESTORNO),
            ("ESTORNO LANCAMENTO REF.123", TipoLancamento.ESTORNO),
            ("EST SEGURO EXEMPLO", TipoLancamento.ESTORNO),
            ("PARCELA EXEMPLO 123", TipoLancamento.OUTROS),
            ("", TipoLancamento.OUTROS),
        ],
    )
    def test_classificacao(self, descricao: str, tipo: TipoLancamento) -> None:
        assert tratar(lanc(descricao)).tipo is tipo

    def test_palavra_dentro_de_outra_nao_conta(self) -> None:
        # "PIX" dentro de "PIXELS" e "TED" dentro de "TEDESCO" não classificam.
        assert tratar(lanc("PIXELS EXEMPLO LTDA")).tipo is TipoLancamento.OUTROS
        assert tratar(lanc("PAGAMENTO TEDESCO")).tipo is TipoLancamento.OUTROS


class TestNaoConciliar:
    """RF13: o que não precisa ir para a conciliação."""

    def test_por_padrao_tudo_e_conciliado(self) -> None:
        tratados = tratar_todos([lanc("PIX ENVIADO X"), lanc("TARIFA PACOTE")])
        assert all(t.conciliar for t in tratados)
        assert all(t.motivo is None for t in tratados)

    def test_estorno_e_o_lancamento_estornado_se_anulam(self) -> None:
        tratados = tratar_todos(
            [
                lanc("CHEQUE COMPENSADO", "-500.00", dia=1),
                lanc("PIX ENVIADO OUTRO", "-30.00", dia=1),
                lanc("DEVOLUCAO CHQ SEM FUNDOS", "500.00", dia=1),
            ]
        )
        compensado, pix, devolucao = tratados
        assert not compensado.conciliar and not devolucao.conciliar
        assert compensado.anula is devolucao.transacao
        assert devolucao.anula is compensado.transacao
        assert "anula" in (compensado.motivo or "")
        assert pix.conciliar

    def test_estorno_ate_tres_dias_depois(self) -> None:
        tratados = tratar_todos(
            [
                lanc("SEGURO VIDA", "-80.00", dia=1),
                lanc("EST SEGURO VIDA", "80.00", dia=4),
            ]
        )
        assert not any(t.conciliar for t in tratados)

    def test_estorno_distante_nao_anula(self) -> None:
        tratados = tratar_todos(
            [
                lanc("SEGURO VIDA", "-80.00", dia=1),
                lanc("EST SEGURO VIDA", "80.00", dia=5),
            ]
        )
        assert all(t.conciliar for t in tratados)

    def test_valor_oposto_sem_estorno_nao_anula(self) -> None:
        # Pagamento e recebimento de mesmo valor são dois lançamentos reais.
        tratados = tratar_todos(
            [lanc("PIX ENVIADO A", "-100.00"), lanc("PIX RECEBIDO B", "100.00")]
        )
        assert all(t.conciliar for t in tratados)

    def test_cada_lancamento_anula_no_maximo_um(self) -> None:
        tratados = tratar_todos(
            [
                lanc("CHEQUE COMPENSADO", "-500.00", dia=1),
                lanc("CHEQUE COMPENSADO", "-500.00", dia=2),
                lanc("DEVOLUCAO CHQ SEM FUNDOS", "500.00", dia=2),
            ]
        )
        assert [t.conciliar for t in tratados] == [True, False, False]

    def test_anulacao_so_na_mesma_origem(self) -> None:
        tratados = tratar_todos(
            [
                lanc("CHEQUE COMPENSADO", "-500.00"),
                lanc("ESTORNO LANCAMENTO", "500.00", origem=Origem.SISTEMA),
            ]
        )
        assert all(t.conciliar for t in tratados)

    def test_valor_zero(self) -> None:
        [tratado] = tratar_todos([lanc("SALDO INFORMATIVO", "0.00")])
        assert not tratado.conciliar
        assert tratado.motivo == "valor zero"

    def test_tipos_ignorados_sao_configuraveis(self) -> None:
        tarifa, pix = tratar_todos(
            [lanc("TARIFA PACOTE"), lanc("PIX ENVIADO X")],
            ignorar_tipos={TipoLancamento.TARIFA},
        )
        assert not tarifa.conciliar
        assert tarifa.motivo == "tipo tarifa ignorado"
        assert pix.conciliar

    def test_mantem_a_ordem(self) -> None:
        originais = [lanc(f"PIX ENVIADO {i}", f"-{i}.00") for i in range(1, 6)]
        assert [t.transacao for t in tratar_todos(originais)] == originais
