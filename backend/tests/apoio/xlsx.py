"""Gera planilhas de teste no formato do relatório do sistema."""

from __future__ import annotations

import io
from datetime import datetime

from openpyxl import Workbook

# Nomes de coluna com espaços sobrando, como o sistema exporta.
COLUNAS = [
    "$Cr   ",
    "Docum   ",
    "Descr        ",
    "dtpag      ",
    "$Vlpag      ",
    "Compl     ",
    "CrDeb  ",
    "Descricao     ",
    "Conta          ",
]


def linha(
    data: datetime = datetime(2024, 2, 5),
    valor: float | int | str | None = -123.4,
    descr: str = "FORNECEDOR EXEMPLO LTDA",
    docum: int | str | None = 1001,
    crdeb: str | None = None,
    conta: str = "BANCO A",
    compl: str = "-",
    categoria: str = "DESPESA EXEMPLO",
) -> list[object]:
    if crdeb is None:
        crdeb = "D" if isinstance(valor, (int, float)) and valor < 0 else "C"
    return ["", docum, descr, data, valor, compl, crdeb, categoria, conta]


def gerar_xlsx(linhas: list[list[object]], colunas: list[str] = COLUNAS) -> bytes:
    livro = Workbook()
    planilha = livro.active
    planilha.append(colunas)
    for valores in linhas:
        planilha.append(valores)
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()
