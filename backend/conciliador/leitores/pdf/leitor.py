"""Leitor de PDF: extrai o texto, identifica o banco e aplica o layout."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from conciliador.extrato import Extrato
from conciliador.leitores.erros import LeituraInvalida
from conciliador.leitores.pdf.bancos import bradesco, caixa, itau, sicoob
from conciliador.leitores.pdf.texto import extrair_paginas


class _Layout(Protocol):
    NOME: str

    def reconhece(self, texto: str) -> bool: ...

    def extrair(self, texto: str, *, arquivo: str) -> Extrato: ...


# Ordem importa: detectores mais específicos antes dos mais frouxos.
_LAYOUTS: tuple[_Layout, ...] = (sicoob, itau, bradesco, caixa)


def identificar_banco(texto: str) -> str | None:
    layout = _layout_para(texto)
    return layout.NOME if layout else None


def ler_pdf(caminho: str | Path) -> list[Extrato]:
    caminho = Path(caminho)
    try:
        conteudo = caminho.read_bytes()
    except OSError as exc:
        raise LeituraInvalida(f"{caminho.name}: não foi possível ler ({exc})") from exc
    return ler_pdf_bytes(conteudo, nome=caminho.name)


def ler_pdf_bytes(conteudo: bytes, *, nome: str) -> list[Extrato]:
    texto = "\n".join(extrair_paginas(conteudo, nome=nome))
    layout = _layout_para(texto)
    if layout is None:
        raise LeituraInvalida(f"{nome}: banco não reconhecido no PDF")
    return [layout.extrair(texto, arquivo=nome)]


def _layout_para(texto: str) -> _Layout | None:
    return next((layout for layout in _LAYOUTS if layout.reconhece(texto)), None)
