import pytest

from conciliador.leitores.erros import LeituraInvalida
from conciliador.leitores.pdf.texto import PdfSemTexto, extrair_paginas
from tests.apoio.pdf import gerar_pdf


def test_extrai_o_texto_de_cada_pagina() -> None:
    conteudo = gerar_pdf(
        [
            ["EXTRATO CONTA CORRENTE", "01/02 PIX RECEBIDO 150,00C"],
            ["02/02 TARIFA 12,90D"],
        ]
    )
    paginas = extrair_paginas(conteudo, nome="extrato.pdf")
    assert len(paginas) == 2
    assert paginas[0].splitlines() == [
        "EXTRATO CONTA CORRENTE",
        "01/02 PIX RECEBIDO 150,00C",
    ]
    assert paginas[1].splitlines() == ["02/02 TARIFA 12,90D"]


def test_preserva_acentos() -> None:
    conteudo = gerar_pdf([["SALDO ANTERIOR", "PAGTO CONCEIÇÃO SÃO JOSÉ"]])
    [pagina] = extrair_paginas(conteudo, nome="extrato.pdf")
    assert "PAGTO CONCEIÇÃO SÃO JOSÉ" in pagina


def test_pagina_em_branco_no_meio_vira_texto_vazio() -> None:
    conteudo = gerar_pdf([["PAGINA 1"], [], ["PAGINA 3"]])
    paginas = extrair_paginas(conteudo, nome="extrato.pdf")
    assert [p.strip() for p in paginas] == ["PAGINA 1", "", "PAGINA 3"]


def test_pdf_sem_nenhum_texto_e_escaneado() -> None:
    # Sem texto selecionável: precisa de OCR, não é erro de leitura comum.
    conteudo = gerar_pdf([[], []])
    with pytest.raises(PdfSemTexto, match=r"escaneado\.pdf"):
        extrair_paginas(conteudo, nome="escaneado.pdf")


def test_pdf_sem_texto_tambem_e_leitura_invalida() -> None:
    assert issubclass(PdfSemTexto, LeituraInvalida)


@pytest.mark.parametrize("conteudo", [b"", b"isto nao e um pdf", b"%PDF-1.4 quebrado"])
def test_arquivo_que_nao_e_pdf(conteudo: bytes) -> None:
    with pytest.raises(LeituraInvalida, match=r"ruim\.pdf"):
        extrair_paginas(conteudo, nome="ruim.pdf")


def test_pdf_protegido_por_senha() -> None:
    conteudo = gerar_pdf([["SEGREDO"]], senha="1234")
    with pytest.raises(LeituraInvalida, match="senha"):
        extrair_paginas(conteudo, nome="protegido.pdf")
