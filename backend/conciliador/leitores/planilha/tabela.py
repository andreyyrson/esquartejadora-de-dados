"""Leitura das linhas da primeira aba de um .xls ou .xlsx."""

from __future__ import annotations

import io
from datetime import datetime

import openpyxl
import xlrd

from conciliador.leitores.erros import LeituraInvalida

_ASSINATURA_XLSX = b"PK"
_ASSINATURA_XLS = b"\xd0\xcf\x11\xe0"

Linha = tuple[object, ...]


def linhas_da_primeira_aba(conteudo: bytes, *, nome: str) -> list[Linha]:
    try:
        if conteudo.startswith(_ASSINATURA_XLS):
            return _linhas_xls(conteudo)
        if conteudo.startswith(_ASSINATURA_XLSX):
            return _linhas_xlsx(conteudo)
    except Exception as exc:
        raise LeituraInvalida(f"{nome}: planilha inválida ({exc})") from exc
    raise LeituraInvalida(f"{nome}: não é uma planilha .xls ou .xlsx")


def primeiras_linhas_em_texto(conteudo: bytes, quantidade: int = 20) -> str | None:
    """Texto normalizado do topo da planilha, para reconhecer o perfil."""
    from conciliador.leitores.planilha.perfil import normalizar

    try:
        linhas = linhas_da_primeira_aba(conteudo, nome="")
    except LeituraInvalida:
        return None
    celulas = (c for linha in linhas[:quantidade] for c in linha if c is not None)
    return normalizar(" ".join(str(c) for c in celulas))


def _linhas_xlsx(conteudo: bytes) -> list[Linha]:
    livro = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    try:
        return [
            tuple(linha) for linha in livro.worksheets[0].iter_rows(values_only=True)
        ]
    finally:
        livro.close()


def _linhas_xls(conteudo: bytes) -> list[Linha]:
    livro = xlrd.open_workbook(file_contents=conteudo)
    aba = livro.sheet_by_index(0)
    linhas: list[Linha] = []
    for i in range(aba.nrows):
        linha: list[object] = []
        for celula in aba.row(i):
            if celula.ctype == xlrd.XL_CELL_DATE:
                linha.append(xlrd.xldate_as_datetime(celula.value, livro.datemode))
            elif celula.ctype == xlrd.XL_CELL_EMPTY:
                linha.append(None)
            else:
                linha.append(celula.value)
        linhas.append(tuple(linha))
    return linhas


__all__ = ["Linha", "datetime", "linhas_da_primeira_aba", "primeiras_linhas_em_texto"]
