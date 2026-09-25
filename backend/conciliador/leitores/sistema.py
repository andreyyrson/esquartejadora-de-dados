"""Leitor do relatório de lançamentos do sistema (planilha xlsx).

O mapa de colunas padrão segue o relatório do sistema atual (``dtpag``,
``$Vlpag``, ``Descr``, ``Docum``, ``CrDeb``, ``Conta``); outro sistema
só precisa de outro ``MapaColunas``.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import openpyxl

from conciliador.leitores.erros import LeituraInvalida
from conciliador.transacao import Origem, Transacao, TransacaoInvalida
from conciliador.valores import ValorInvalido, parse_valor

_CENTAVO = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class MapaColunas:
    """Nome da coluna da planilha para cada campo (sem os espaços)."""

    data: str = "dtpag"
    valor: str = "$Vlpag"
    descricao: str = "Descr"
    conta: str = "Conta"
    documento: str | None = "Docum"
    # Coluna C/D usada só para conferir o sinal do valor.
    natureza: str | None = "CrDeb"


MAPA_PADRAO = MapaColunas()


def ler_relatorio(
    caminho: str | Path, *, mapa: MapaColunas = MAPA_PADRAO
) -> list[Transacao]:
    caminho = Path(caminho)
    try:
        conteudo = caminho.read_bytes()
    except OSError as exc:
        raise LeituraInvalida(f"{caminho.name}: não foi possível ler ({exc})") from exc
    return ler_relatorio_bytes(conteudo, nome=caminho.name, mapa=mapa)


def ler_relatorio_bytes(
    conteudo: bytes, *, nome: str, mapa: MapaColunas = MAPA_PADRAO
) -> list[Transacao]:
    try:
        livro = openpyxl.load_workbook(
            io.BytesIO(conteudo), read_only=True, data_only=True
        )
    except Exception as exc:
        raise LeituraInvalida(f"{nome}: planilha inválida ({exc})") from exc
    try:
        linhas = livro.worksheets[0].iter_rows(values_only=True)
        colunas = _indices(next(linhas, None), mapa, nome)
        return [
            _transacao(valores, colunas, mapa, nome, numero)
            for numero, valores in enumerate(linhas, start=2)
            if not _vazia(valores)
        ]
    finally:
        livro.close()


def agrupar_por_conta(transacoes: Iterable[Transacao]) -> dict[str, list[Transacao]]:
    grupos: dict[str, list[Transacao]] = {}
    for transacao in transacoes:
        grupos.setdefault(transacao.conta or "", []).append(transacao)
    return grupos


def _indices(
    cabecalho: Sequence[object] | None, mapa: MapaColunas, nome: str
) -> dict[str, int]:
    if cabecalho is None or _vazia(cabecalho):
        raise LeituraInvalida(f"{nome}: planilha sem cabeçalho")
    indices = {str(c).strip(): i for i, c in enumerate(cabecalho) if c is not None}
    exigidas = [mapa.data, mapa.valor, mapa.descricao, mapa.conta]
    exigidas += [c for c in (mapa.documento, mapa.natureza) if c is not None]
    faltando = [c for c in exigidas if c not in indices]
    if faltando:
        raise LeituraInvalida(f"{nome}: colunas não encontradas: {', '.join(faltando)}")
    return {coluna: indices[coluna] for coluna in exigidas}


def _transacao(
    valores: Sequence[object],
    colunas: dict[str, int],
    mapa: MapaColunas,
    nome: str,
    numero: int,
) -> Transacao:
    def celula(coluna: str | None) -> object:
        if coluna is None or colunas[coluna] >= len(valores):
            return None
        return valores[colunas[coluna]]

    try:
        valor = _valor(celula(mapa.valor))
        _conferir_sinal(valor, celula(mapa.natureza), mapa.natureza)
        return Transacao.criar(
            data=celula(mapa.data),
            valor=valor,
            descricao=_texto(celula(mapa.descricao)),
            origem=Origem.SISTEMA,
            documento=_texto(celula(mapa.documento)),
            conta=_texto(celula(mapa.conta)),
            arquivo=nome,
            linha=numero,
        )
    except (ValorInvalido, TransacaoInvalida) as exc:
        raise LeituraInvalida(f"{nome}, linha {numero}: {exc}") from exc


def _valor(celula: object) -> Decimal:
    # O Excel guarda números como float binário: arredonda para centavos.
    if isinstance(celula, float):
        return Decimal(repr(celula)).quantize(_CENTAVO)
    return parse_valor(celula).quantize(_CENTAVO)


def _conferir_sinal(valor: Decimal, natureza: object, coluna: str | None) -> None:
    marca = _texto(natureza)
    marca = marca.upper() if marca else None
    if (marca == "D" and valor > 0) or (marca == "C" and valor < 0):
        raise ValorInvalido(f"valor {valor} não bate com {coluna} = {marca!r}")


def _texto(celula: object) -> str | None:
    if celula is None:
        return None
    return str(celula).strip() or None


def _vazia(valores: Sequence[object]) -> bool:
    return all(c is None or (isinstance(c, str) and not c.strip()) for c in valores)
