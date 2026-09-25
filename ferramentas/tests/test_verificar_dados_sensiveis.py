"""Testes do verificador de dados sensíveis.

Os CPFs e CNPJs abaixo são gerados só para teste (dígitos verificadores
calculados sobre números sequenciais), não pertencem a ninguém.
"""

from pathlib import Path

import pytest

from ferramentas.verificar_dados_sensiveis import (
    Achado,
    arquivo_proibido,
    cnpjs,
    cpfs,
    termos_encontrados,
    verificar,
)

CPF_VALIDO = "123.456.789-09"
CNPJ_VALIDO = "11.222.333/0001-81"


class TestCpf:
    def test_encontra_cpf_formatado_valido(self) -> None:
        assert cpfs(f"PIX ENVIADO FULANO {CPF_VALIDO}") == [CPF_VALIDO]

    def test_ignora_cpf_com_digito_invalido(self) -> None:
        assert cpfs("123.456.789-00") == []

    def test_ignora_sequencia_repetida(self) -> None:
        assert cpfs("111.111.111-11") == []

    def test_ignora_numero_sem_formato(self) -> None:
        # Sem pontuação, 11 dígitos são comuns (FITID, documento).
        assert cpfs("12345678909") == []


class TestCnpj:
    def test_encontra_cnpj_formatado_valido(self) -> None:
        assert cnpjs(f"PAGAMENTO EMPRESA {CNPJ_VALIDO}") == [CNPJ_VALIDO]

    def test_encontra_cnpj_sem_pontuacao_depois_da_palavra_cnpj(self) -> None:
        assert cnpjs("CONSORCIO CNPJ11222333000181") == ["11222333000181"]

    def test_ignora_cnpj_com_digito_invalido(self) -> None:
        assert cnpjs("11.222.333/0001-00") == []


class TestArquivoProibido:
    @pytest.mark.parametrize(
        "caminho",
        [
            "extrato.ofx",
            "Bradesco.OFX",
            "backend/relatorio.xlsx",
            "planilha.xls",
            "dados.csv",
            "extrato.pdf",
        ],
    )
    def test_extratos_e_planilhas_sao_proibidos(self, caminho: str) -> None:
        assert arquivo_proibido(caminho)

    @pytest.mark.parametrize(
        "caminho",
        [
            "backend/tests/dados_ficticios/extrato.ofx",
            "backend/tests/dados_ficticios/sub/relatorio.xlsx",
            "backend/conciliador/leitores/ofx.py",
            "README.md",
        ],
    )
    def test_codigo_e_dados_ficticios_sao_permitidos(self, caminho: str) -> None:
        assert not arquivo_proibido(caminho)


class TestTermosProibidos:
    def test_encontra_termo_ignorando_maiusculas_e_acentos(self) -> None:
        termos = {"Fornecedor Secreto", "JOSÉ DA SILVA"}
        texto = "pagamento a fornecedor secreto e a Jose da Silva"
        assert termos_encontrados(texto, termos) == [
            "Fornecedor Secreto",
            "JOSÉ DA SILVA",
        ]

    def test_so_palavra_inteira(self) -> None:
        assert termos_encontrados("CARLOSALBERTO", {"CARLOS"}) == []

    def test_sem_termos(self) -> None:
        assert termos_encontrados("qualquer coisa", set()) == []


class TestVerificar:
    def test_arquivo_limpo(self, tmp_path: Path) -> None:
        arquivo = tmp_path / "codigo.py"
        arquivo.write_text("valor = parse_valor('1.500,00')\n")
        assert verificar([arquivo], raiz=tmp_path) == []

    def test_aponta_arquivo_e_linha(self, tmp_path: Path) -> None:
        arquivo = tmp_path / "teste.py"
        arquivo.write_text(f"ok\ndescricao = 'PIX {CPF_VALIDO}'\n")
        assert verificar([arquivo], raiz=tmp_path) == [
            Achado("teste.py", 2, "CPF", CPF_VALIDO)
        ]

    def test_arquivo_proibido(self, tmp_path: Path) -> None:
        arquivo = tmp_path / "extrato.ofx"
        arquivo.write_text("<OFX>")
        assert verificar([arquivo], raiz=tmp_path) == [
            Achado("extrato.ofx", 0, "arquivo proibido", ".ofx")
        ]

    def test_termo_proibido(self, tmp_path: Path) -> None:
        arquivo = tmp_path / "teste.py"
        arquivo.write_text("descr = 'FORNECEDOR SECRETO LTDA'\n")
        achados = verificar([arquivo], raiz=tmp_path, termos={"fornecedor secreto"})
        assert achados == [Achado("teste.py", 1, "termo proibido", "fornecedor secreto")]

    def test_mensagens_de_commit(self, tmp_path: Path) -> None:
        achados = verificar(
            [], raiz=tmp_path, mensagens={"abc1234": f"feat: x\n\nCNPJ {CNPJ_VALIDO}"}
        )
        assert achados == [Achado("commit abc1234", 3, "CNPJ", CNPJ_VALIDO)]

    def test_arquivo_binario_ou_inexistente_e_ignorado(self, tmp_path: Path) -> None:
        binario = tmp_path / "imagem.png"
        binario.write_bytes(b"\x89PNG\x00\xff\xfe")
        assert verificar([binario, tmp_path / "sumiu.py"], raiz=tmp_path) == []
