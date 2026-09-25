import dataclasses
from datetime import date, datetime
from decimal import Decimal

import pytest

from conciliador.transacao import Natureza, Origem, Transacao, TransacaoInvalida


def uma_transacao(**campos: object) -> Transacao:
    """Constrói uma transação válida, sobrescrevendo só o que o teste precisa."""
    padrao: dict[str, object] = {
        "data": "01/02/2024",
        "valor": "-1.500,00",
        "descricao": "PAGTO ALUGUEL",
        "origem": Origem.BANCO,
    }
    padrao.update(campos)
    return Transacao.criar(**padrao)  # type: ignore[arg-type]


class TestCriarAPartirDoExtrato:
    def test_converte_data_e_valor_de_texto(self) -> None:
        t = uma_transacao(data="01/02/2024", valor="-1.500,00")
        assert t.data == date(2024, 2, 1)
        assert t.valor == Decimal("-1500.00")

    def test_aceita_valores_ja_convertidos(self) -> None:
        t = uma_transacao(data=datetime(2024, 2, 1, 9, 0), valor=Decimal("10.50"))
        assert t.data == date(2024, 2, 1)
        assert t.valor == Decimal("10.50")

    def test_guarda_campos_de_rastreio(self) -> None:
        t = uma_transacao(
            origem=Origem.SISTEMA,
            documento="NF 123",
            conta="0341-12345",
            arquivo="sistema.xlsx",
            linha=7,
        )
        assert t.origem is Origem.SISTEMA
        assert t.documento == "NF 123"
        assert t.conta == "0341-12345"
        assert t.arquivo == "sistema.xlsx"
        assert t.linha == 7

    def test_campos_opcionais_comecam_vazios(self) -> None:
        t = uma_transacao()
        assert (t.documento, t.conta, t.arquivo, t.linha) == (None, None, None, None)


class TestNormalizacao:
    def test_descricao_sem_espacos_sobrando(self) -> None:
        t = uma_transacao(descricao="  PAGTO   ALUGUEL \n SAO PAULO  ")
        assert t.descricao == "PAGTO ALUGUEL SAO PAULO"

    def test_descricao_ausente_vira_texto_vazio(self) -> None:
        assert uma_transacao(descricao=None).descricao == ""

    @pytest.mark.parametrize("documento", ["", "   ", None])
    def test_documento_vazio_vira_none(self, documento: str | None) -> None:
        assert uma_transacao(documento=documento).documento is None

    def test_documento_sem_espacos_nas_pontas(self) -> None:
        assert uma_transacao(documento="  123  ").documento == "123"


class TestNatureza:
    def test_valor_positivo_e_credito(self) -> None:
        assert uma_transacao(valor="10,00").natureza is Natureza.CREDITO

    def test_valor_negativo_e_debito(self) -> None:
        assert uma_transacao(valor="-10,00").natureza is Natureza.DEBITO

    def test_valor_zero_e_credito(self) -> None:
        # Linhas informativas de valor zero não são débito.
        assert uma_transacao(valor="0,00").natureza is Natureza.CREDITO


class TestImutabilidade:
    def test_nao_pode_ser_alterada(self) -> None:
        t = uma_transacao()
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.valor = Decimal("0")  # type: ignore[misc]

    def test_transacoes_iguais_sao_iguais_e_tem_mesmo_hash(self) -> None:
        a, b = uma_transacao(), uma_transacao()
        assert a == b
        assert hash(a) == hash(b)


class TestErros:
    def test_valor_invalido_informa_campo_arquivo_e_linha(self) -> None:
        with pytest.raises(TransacaoInvalida) as erro:
            uma_transacao(valor="abc", arquivo="itau.ofx", linha=12)
        mensagem = str(erro.value)
        assert "valor" in mensagem
        assert "abc" in mensagem
        assert "itau.ofx" in mensagem
        assert "12" in mensagem

    def test_data_invalida_informa_campo(self) -> None:
        with pytest.raises(TransacaoInvalida, match="data"):
            uma_transacao(data="31/02/2024")

    def test_erro_original_fica_encadeado(self) -> None:
        with pytest.raises(TransacaoInvalida) as erro:
            uma_transacao(valor="abc")
        assert isinstance(erro.value.__cause__, ValueError)

    @pytest.mark.parametrize(
        "campos",
        [
            {"valor": 1.5},  # float perde precisão
            {"valor": Decimal("NaN")},
            {"data": "2024-02-01"},  # construtor direto exige date
            {"data": datetime(2024, 2, 1)},
            {"origem": "banco"},
            {"linha": 0},  # linhas começam em 1
        ],
    )
    def test_construtor_direto_valida_tipos(self, campos: dict[str, object]) -> None:
        dados: dict[str, object] = {
            "data": date(2024, 2, 1),
            "valor": Decimal("10.00"),
            "descricao": "X",
            "origem": Origem.BANCO,
        }
        dados.update(campos)
        with pytest.raises(TransacaoInvalida):
            Transacao(**dados)  # type: ignore[arg-type]
