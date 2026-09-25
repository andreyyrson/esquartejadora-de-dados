"""Gera PDFs de teste com reportlab (texto selecionável, como os bancos)."""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def gerar_pdf(paginas: list[list[str]], senha: str | None = None) -> bytes:
    """Uma lista de linhas por página. Página sem linhas fica em branco."""
    saida = io.BytesIO()
    pdf = canvas.Canvas(saida, pagesize=A4, encrypt=senha)
    _, altura = A4
    for linhas in paginas:
        y = altura - 50
        for linha in linhas:
            pdf.drawString(40, y, linha)
            y -= 14
        pdf.showPage()
    pdf.save()
    return saida.getvalue()
