"""Extração do texto de cada página de um PDF, com o pdfplumber."""

from __future__ import annotations

import io

import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect

from conciliador.leitores.erros import LeituraInvalida


class PdfSemTexto(LeituraInvalida):
    """O PDF não tem texto selecionável (escaneado): precisa de OCR."""


def extrair_paginas(conteudo: bytes, *, nome: str) -> list[str]:
    """Devolve o texto de cada página; página sem texto vira ``""``."""
    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            paginas = [pagina.extract_text() or "" for pagina in pdf.pages]
    except Exception as exc:
        causa = exc.args[0] if exc.args else exc
        if isinstance(causa, PDFPasswordIncorrect):
            raise LeituraInvalida(f"{nome}: PDF protegido por senha") from exc
        raise LeituraInvalida(f"{nome}: PDF inválido ({causa})") from exc
    if not any(pagina.strip() for pagina in paginas):
        raise PdfSemTexto(
            f"{nome}: PDF sem texto selecionável (escaneado?); precisa de OCR"
        )
    return paginas
