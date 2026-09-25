"""Relatório do sistema (xlsx). Todos os dados são fictícios."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from conciliador.leitores.erros import LeituraInvalida
from conciliador.leitores.sistema import (
    MapaColunas,
    agrupar_por_conta,
    ler_relatorio,
    ler_relatorio_bytes,
)
from conciliador.transacao import Origem
from tests.apoio.xlsx import COLUNAS, gerar_xlsx, linha


def ler(*linhas: list[object]):  # type: ignore[no-untyped-def]
    return ler_relatorio_bytes(gerar_xlsx(list(linhas)), nome="relatorio.xlsx")


class TestLeitura:
    def test_le_data_valor_descricao_documento_e_conta(self) -> None:
        [t] = ler(linha(datetime(2024, 2, 1, 11, 13), -123.4, "FORNECEDOR A", 1001))
        assert t.data == date(2024, 2, 1)
        assert t.valor == Decimal("-123.40")
        assert t.descricao == "FORNECEDOR A"
        assert t.documento == "1001"
        assert t.conta == "BANCO A"
        assert t.origem is Origem.SISTEMA

    def test_valor_float_do_excel_vira_centavos_exatos(self) -> None:
        # 0.1 + 0.2 em float é 0.30000000000000004
        [t] = ler(linha(valor=0.1 + 0.2, crdeb="C"))
        assert t.valor == Decimal("0.30")

    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [(3000, "3000.00"), (-1250.4, "-1250.40"), ("1.500,00", "1500.00")],
    )
    def test_valor_inteiro_float_ou_texto(self, valor: object, esperado: str) -> None:
        crdeb = "D" if esperado.startswith("-") else "C"
        [t] = ler(linha(valor=valor, crdeb=crdeb))  # type: ignore[arg-type]
        assert t.valor == Decimal(esperado)

    def test_textos_sem_espacos_sobrando(self) -> None:
        [t] = ler(linha(descr="  PESSOA EXEMPLO   ", conta="BANCO B   "))
        assert t.descricao == "PESSOA EXEMPLO"
        assert t.conta == "BANCO B"

    def test_documento_em_texto(self) -> None:
        [t] = ler(linha(docum=" NF-123 "))
        assert t.documento == "NF-123"

    def test_sem_documento(self) -> None:
        [t] = ler(linha(docum=None))
        assert t.documento is None

    def test_linha_e_a_linha_da_planilha(self) -> None:
        transacoes = ler(linha(), linha(), linha())
        assert [t.linha for t in transacoes] == [2, 3, 4]
        assert transacoes[0].arquivo == "relatorio.xlsx"

    def test_ignora_linhas_totalmente_vazias(self) -> None:
        transacoes = ler(linha(), [None] * len(COLUNAS), linha())
        assert [t.linha for t in transacoes] == [2, 4]

    def test_le_de_arquivo(self, tmp_path: Path) -> None:
        arquivo = tmp_path / "RELATORIO.xlsx"
        arquivo.write_bytes(gerar_xlsx([linha()]))
        assert len(ler_relatorio(arquivo)) == 1
        assert len(ler_relatorio(str(arquivo))) == 1


class TestAgruparPorConta:
    def test_separa_por_conta_mantendo_a_ordem(self) -> None:
        transacoes = ler(
            linha(conta="BANCO A", docum=1),
            linha(conta="BANCO B", docum=2),
            linha(conta="BANCO A", docum=3),
        )
        grupos = agrupar_por_conta(transacoes)
        assert list(grupos) == ["BANCO A", "BANCO B"]
        assert [t.documento for t in grupos["BANCO A"]] == ["1", "3"]


class TestOutroSistema:
    def test_mapa_de_colunas_configuravel(self) -> None:
        colunas = ["Data", "Valor", "Historico", "Banco"]
        conteudo = gerar_xlsx(
            [[datetime(2024, 2, 5), -50, "TARIFA", "BANCO C"]], colunas=colunas
        )
        mapa = MapaColunas(
            data="Data",
            valor="Valor",
            descricao="Historico",
            conta="Banco",
            documento=None,
            natureza=None,
        )
        [t] = ler_relatorio_bytes(conteudo, nome="outro.xlsx", mapa=mapa)
        assert (t.valor, t.descricao, t.conta) == (
            Decimal("-50.00"),
            "TARIFA",
            "BANCO C",
        )


class TestErros:
    def test_coluna_obrigatoria_faltando(self) -> None:
        colunas = [c for c in COLUNAS if not c.startswith("$Vlpag")]
        conteudo = gerar_xlsx([], colunas=colunas)
        with pytest.raises(LeituraInvalida, match=r"\$Vlpag"):
            ler_relatorio_bytes(conteudo, nome="relatorio.xlsx")

    def test_valor_ilegivel_informa_a_linha(self) -> None:
        with pytest.raises(LeituraInvalida, match=r"relatorio\.xlsx.*linha 3"):
            ler(linha(), linha(valor="abc", crdeb="D"))

    def test_valor_vazio(self) -> None:
        with pytest.raises(LeituraInvalida, match="linha 2"):
            ler(linha(valor=None, crdeb="D"))

    def test_sinal_diferente_da_coluna_credito_debito(self) -> None:
        # Débito com valor positivo: melhor parar do que conciliar errado.
        with pytest.raises(LeituraInvalida, match=r"linha 2.*CrDeb"):
            ler(linha(valor=100.0, crdeb="D"))

    def test_nao_e_uma_planilha(self) -> None:
        with pytest.raises(LeituraInvalida, match=r"ruim\.xlsx"):
            ler_relatorio_bytes(b"isto nao e xlsx", nome="ruim.xlsx")

    def test_planilha_vazia(self) -> None:
        import io

        from openpyxl import Workbook

        saida = io.BytesIO()
        Workbook().save(saida)
        with pytest.raises(LeituraInvalida, match="cabeçalho"):
            ler_relatorio_bytes(saida.getvalue(), nome="vazia.xlsx")

    def test_arquivo_inexistente(self, tmp_path: Path) -> None:
        with pytest.raises(LeituraInvalida, match=r"nao_existe\.xlsx"):
            ler_relatorio(tmp_path / "nao_existe.xlsx")
