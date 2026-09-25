from decimal import Decimal
from pathlib import Path

import pytest

from conciliador.leitores.erros import LeituraInvalida
from conciliador.leitores.pdf.leitor import identificar_banco, ler_pdf, ler_pdf_bytes
from tests.apoio.pdf import gerar_pdf
from tests.unit.leitores.pdf.bancos.test_itau import EXTRATO as ITAU
from tests.unit.leitores.pdf.bancos.test_sicoob import CURTO


def test_identifica_o_banco_pelo_texto() -> None:
    assert identificar_banco(CURTO) == "sicoob"


def test_identifica_o_itau() -> None:
    assert identificar_banco(ITAU) == "itau"


def test_banco_desconhecido() -> None:
    assert identificar_banco("EXTRATO DE UM BANCO QUALQUER") is None


def test_le_pdf_do_sicoob_de_ponta_a_ponta(tmp_path: Path) -> None:
    # Divide o extrato em duas páginas, como no PDF real.
    linhas = CURTO.splitlines()
    arquivo = tmp_path / "extrato.pdf"
    arquivo.write_bytes(gerar_pdf([linhas[:8], linhas[8:]]))
    [extrato] = ler_pdf(arquivo)
    assert len(extrato.transacoes) == 5
    assert extrato.saldo_final == Decimal("4037.10")
    assert extrato.transacoes[0].arquivo == "extrato.pdf"


def test_aceita_caminho_como_texto(tmp_path: Path) -> None:
    arquivo = tmp_path / "extrato.pdf"
    arquivo.write_bytes(gerar_pdf([CURTO.splitlines()]))
    [extrato] = ler_pdf(str(arquivo))
    assert len(extrato.transacoes) == 5


def test_banco_nao_suportado() -> None:
    conteudo = gerar_pdf([["EXTRATO DE UM BANCO QUALQUER", "01/02 X 10,00D"]])
    with pytest.raises(LeituraInvalida, match="banco não reconhecido"):
        ler_pdf_bytes(conteudo, nome="outro.pdf")


def test_arquivo_inexistente(tmp_path: Path) -> None:
    with pytest.raises(LeituraInvalida, match=r"nao_existe\.pdf"):
        ler_pdf(tmp_path / "nao_existe.pdf")
