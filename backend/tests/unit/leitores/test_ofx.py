from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from conciliador.leitores.ofx import LeituraInvalida, ler_ofx, ler_ofx_bytes
from conciliador.transacao import Origem

CABECALHO_SGML = (
    "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\n"
    "ENCODING:USASCII\nCHARSET:1252\nCOMPRESSION:NONE\n"
    "OLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
)
CABECALHO_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<?OFX OFXHEADER="200" VERSION="211" SECURITY="NONE" '
    'OLDFILEUID="NONE" NEWFILEUID="NONE"?>\n'
)


def lancamento(
    valor: str = "-1500.00",
    data: str = "20240201",
    memo: str | None = "PAGTO ALUGUEL",
    nome: str | None = None,
    checknum: str | None = None,
    fitid: str = "1",
) -> str:
    """Um <STMTTRN> no estilo SGML (sem tags de fechamento), como os bancos."""
    partes = [
        "<STMTTRN>",
        "<TRNTYPE>OTHER",
        f"<DTPOSTED>{data}",
        f"<TRNAMT>{valor}",
        f"<FITID>{fitid}",
    ]
    if checknum is not None:
        partes.append(f"<CHECKNUM>{checknum}")
    if nome is not None:
        partes.append(f"<NAME>{nome}")
    if memo is not None:
        partes.append(f"<MEMO>{memo}")
    partes.append("</STMTTRN>")
    return "\n".join(partes)


def conta(
    *lancamentos: str,
    banco: str = "0341",
    numero: str = "12345-6",
    saldo: str = "8500.00",
) -> str:
    return (
        "<STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>"
        "<STMTRS><CURDEF>BRL"
        f"<BANKACCTFROM><BANKID>{banco}<ACCTID>{numero}<ACCTTYPE>CHECKING"
        "</BANKACCTFROM>"
        "<BANKTRANLIST><DTSTART>20240201<DTEND>20240229\n"
        + "\n".join(lancamentos)
        + "\n</BANKTRANLIST>"
        f"<LEDGERBAL><BALAMT>{saldo}<DTASOF>20240229</LEDGERBAL>"
        "</STMTRS></STMTTRNRS>"
    )


def ofx(*contas: str, cabecalho: str = CABECALHO_SGML) -> str:
    return (
        cabecalho + "<OFX><BANKMSGSRSV1>" + "".join(contas) + ("</BANKMSGSRSV1></OFX>")
    )


def gravar(tmp_path: Path, texto: str, encoding: str = "cp1252") -> Path:
    caminho = tmp_path / "extrato.ofx"
    caminho.write_bytes(texto.encode(encoding))
    return caminho


class TestLeituraBasica:
    def test_le_transacoes_da_conta(self, tmp_path: Path) -> None:
        arquivo = gravar(
            tmp_path,
            ofx(
                conta(
                    lancamento("-1500.00", "20240201", "PAGTO ALUGUEL", fitid="1"),
                    lancamento("2000.50", "20240205", "TED RECEBIDA", fitid="2"),
                )
            ),
        )
        [extrato] = ler_ofx(arquivo)
        primeira, segunda = extrato.transacoes
        assert primeira.data == date(2024, 2, 1)
        assert primeira.valor == Decimal("-1500.00")
        assert primeira.descricao == "PAGTO ALUGUEL"
        assert segunda.data == date(2024, 2, 5)
        assert segunda.valor == Decimal("2000.50")

    def test_transacoes_tem_origem_banco_e_rastreio(self, tmp_path: Path) -> None:
        arquivo = gravar(tmp_path, ofx(conta(lancamento(), lancamento(fitid="2"))))
        [extrato] = ler_ofx(arquivo)
        for posicao, t in enumerate(extrato.transacoes, start=1):
            assert t.origem is Origem.BANCO
            assert t.conta == "12345-6"
            assert t.arquivo == "extrato.ofx"
            assert t.linha == posicao

    def test_dados_da_conta_saldo_e_periodo(self, tmp_path: Path) -> None:
        arquivo = gravar(tmp_path, ofx(conta(lancamento(), saldo="8500.00")))
        [extrato] = ler_ofx(arquivo)
        assert extrato.banco == "0341"
        assert extrato.conta == "12345-6"
        assert extrato.saldo_final == Decimal("8500.00")
        assert extrato.data_saldo == date(2024, 2, 29)
        assert extrato.inicio == date(2024, 2, 1)
        assert extrato.fim == date(2024, 2, 29)

    def test_aceita_caminho_como_texto(self, tmp_path: Path) -> None:
        arquivo = gravar(tmp_path, ofx(conta(lancamento())))
        [extrato] = ler_ofx(str(arquivo))
        assert len(extrato.transacoes) == 1

    def test_le_de_bytes_para_upload(self) -> None:
        conteudo = ofx(conta(lancamento())).encode("cp1252")
        [extrato] = ler_ofx_bytes(conteudo, nome="upload.ofx")
        assert extrato.transacoes[0].arquivo == "upload.ofx"

    def test_conta_sem_lancamentos(self, tmp_path: Path) -> None:
        [extrato] = ler_ofx(gravar(tmp_path, ofx(conta())))
        assert extrato.transacoes == ()

    def test_varias_contas_no_mesmo_arquivo(self, tmp_path: Path) -> None:
        arquivo = gravar(
            tmp_path,
            ofx(
                conta(lancamento(), numero="111"),
                conta(lancamento(), lancamento(fitid="2"), numero="222"),
            ),
        )
        extratos = ler_ofx(arquivo)
        assert [e.conta for e in extratos] == ["111", "222"]
        assert [len(e.transacoes) for e in extratos] == [1, 2]


class TestArquivosDeBancosBrasileiros:
    def test_acento_em_cp1252(self, tmp_path: Path) -> None:
        arquivo = gravar(tmp_path, ofx(conta(lancamento(memo="PAGTO SÃO JOÃO"))))
        [extrato] = ler_ofx(arquivo)
        assert extrato.transacoes[0].descricao == "PAGTO SÃO JOÃO"

    def test_cabecalho_diz_1252_mas_arquivo_e_utf8(self, tmp_path: Path) -> None:
        # Comum: o banco declara USASCII/1252 e grava UTF-8.
        arquivo = gravar(
            tmp_path, ofx(conta(lancamento(memo="PAGTO SÃO JOÃO"))), "utf-8"
        )
        [extrato] = ler_ofx(arquivo)
        assert extrato.transacoes[0].descricao == "PAGTO SÃO JOÃO"

    def test_ofx_versao_2_em_xml_utf8(self, tmp_path: Path) -> None:
        xml = (
            "<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20240201</DTPOSTED>"
            "<TRNAMT>-2.50</TRNAMT><FITID>1</FITID>"
            "<MEMO>CAFÉ CONCEIÇÃO</MEMO></STMTTRN>"
        )
        arquivo = gravar(tmp_path, ofx(conta(xml), cabecalho=CABECALHO_XML), "utf-8")
        [extrato] = ler_ofx(arquivo)
        assert extrato.transacoes[0].descricao == "CAFÉ CONCEIÇÃO"
        assert extrato.transacoes[0].valor == Decimal("-2.50")

    @pytest.mark.parametrize(
        "data_ofx", ["20240201230000[-3:BRT]", "20240201235959.999[-3:BRT]"]
    )
    def test_lancamento_a_noite_nao_muda_de_dia(
        self, tmp_path: Path, data_ofx: str
    ) -> None:
        # Convertendo para UTC, 23h de Brasília viraria o dia seguinte.
        arquivo = gravar(tmp_path, ofx(conta(lancamento(data=data_ofx))))
        [extrato] = ler_ofx(arquivo)
        assert extrato.transacoes[0].data == date(2024, 2, 1)

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [("-1500,00", "-1500.00"), ("-1.500,00", "-1500.00"), ("10", "10")],
    )
    def test_valor_com_virgula(self, tmp_path: Path, texto: str, esperado: str) -> None:
        [extrato] = ler_ofx(gravar(tmp_path, ofx(conta(lancamento(valor=texto)))))
        assert extrato.transacoes[0].valor == Decimal(esperado)


class TestDescricaoEDocumento:
    def test_usa_memo(self, tmp_path: Path) -> None:
        arquivo = gravar(
            tmp_path, ofx(conta(lancamento(nome="FULANO", memo="PIX RECEBIDO")))
        )
        assert ler_ofx(arquivo)[0].transacoes[0].descricao == "PIX RECEBIDO"

    def test_sem_memo_usa_nome(self, tmp_path: Path) -> None:
        arquivo = gravar(tmp_path, ofx(conta(lancamento(nome="FULANO", memo=None))))
        assert ler_ofx(arquivo)[0].transacoes[0].descricao == "FULANO"

    def test_documento_vem_do_checknum(self, tmp_path: Path) -> None:
        arquivo = gravar(tmp_path, ofx(conta(lancamento(checknum="000555"))))
        assert ler_ofx(arquivo)[0].transacoes[0].documento == "000555"

    def test_sem_checknum_documento_fica_vazio(self, tmp_path: Path) -> None:
        arquivo = gravar(tmp_path, ofx(conta(lancamento())))
        assert ler_ofx(arquivo)[0].transacoes[0].documento is None


class TestArquivosInvalidos:
    @pytest.mark.parametrize(
        "conteudo",
        [
            b"",
            b"isto nao e um ofx",
            (CABECALHO_SGML + "<OFX></OFX>").encode(),  # nenhuma conta
        ],
    )
    def test_arquivo_invalido(self, conteudo: bytes) -> None:
        with pytest.raises(LeituraInvalida, match=r"ruim\.ofx"):
            ler_ofx_bytes(conteudo, nome="ruim.ofx")

    def test_valor_ilegivel(self) -> None:
        conteudo = ofx(conta(lancamento(valor="abc"))).encode()
        with pytest.raises(LeituraInvalida, match=r"ruim\.ofx"):
            ler_ofx_bytes(conteudo, nome="ruim.ofx")

    def test_arquivo_inexistente(self, tmp_path: Path) -> None:
        with pytest.raises(LeituraInvalida, match=r"nao_existe\.ofx"):
            ler_ofx(tmp_path / "nao_existe.ofx")
