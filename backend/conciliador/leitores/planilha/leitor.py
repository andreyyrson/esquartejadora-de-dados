"""Aplica um perfil às linhas de uma planilha e devolve o Extrato."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from conciliador.datas import DataInvalida, parse_data
from conciliador.extrato import Extrato
from conciliador.leitores.erros import LeituraInvalida
from conciliador.leitores.planilha.perfil import Perfil, normalizar
from conciliador.leitores.planilha.tabela import Linha, linhas_da_primeira_aba
from conciliador.transacao import Transacao, TransacaoInvalida
from conciliador.valores import ValorInvalido, parse_valor

_CENTAVO = Decimal("0.01")


def ler_planilha(conteudo: bytes, *, nome: str, perfil: Perfil) -> Extrato:
    linhas = linhas_da_primeira_aba(conteudo, nome=nome)
    inicio, fim = _periodo(linhas, perfil, nome)
    numero_cabecalho, indices = _cabecalho(linhas, perfil, nome)

    saldo_inicial: Decimal | None = None
    saldo_final: Decimal | None = None
    transacoes: list[Transacao] = []
    saldos: list[tuple[int, str, Decimal, Decimal | None]] = []
    for numero, linha in enumerate(
        linhas[numero_cabecalho:], start=numero_cabecalho + 1
    ):

        def celula(coluna: str | None, linha: Linha = linha) -> object:
            if coluna is None or indices[coluna] >= len(linha):
                return None
            return linha[indices[coluna]]

        if _vazia(linha):
            continue
        if normalizar(linha[0]) in {normalizar(m) for m in perfil.marcadores_de_fim}:
            break
        if perfil.ignorar_coluna and normalizar(celula(perfil.ignorar_coluna)) in {
            normalizar(v) for v in perfil.ignorar_valores
        }:
            continue
        descricao = " - ".join(
            str(texto).strip()
            for texto in (celula(c) for c in perfil.descricoes)
            if texto is not None and str(texto).strip()
        )
        try:
            valor = _valor(perfil, celula)
            saldo_da_linha = _numero(celula(perfil.saldo))
            chave = normalizar(descricao)
            informado = valor if valor is not None else saldo_da_linha
            if any(chave.startswith(normalizar(s)) for s in perfil.saldo_inicial):
                if saldo_inicial is None:
                    saldo_inicial = informado
                continue
            if any(chave.startswith(normalizar(s)) for s in perfil.saldo_final):
                saldo_final = informado
                continue
            if valor is None:
                continue
            saldos.append((numero, descricao, valor, saldo_da_linha))
            data = _data(perfil, celula, inicio, fim)
            documento = celula(perfil.documento)
            transacoes.append(
                Transacao.criar(
                    data=data,
                    valor=-valor if perfil.inverter_sinal else valor,
                    descricao=descricao,
                    origem=perfil.origem,
                    documento=_texto(documento),
                    arquivo=nome,
                    linha=numero,
                )
            )
        except (ValorInvalido, DataInvalida, TransacaoInvalida) as exc:
            raise LeituraInvalida(f"{nome}, linha {numero}: {exc}") from exc

    avisos: tuple[str, ...] = ()
    if perfil.saldo is not None:
        saldo_inicial, saldo_final, avisos = _sequencia_de_saldos(
            saldos, saldo_inicial, saldo_final, nome
        )
    return Extrato(
        transacoes=tuple(transacoes),
        banco=perfil.banco,
        avisos=avisos,
        saldo_inicial=saldo_inicial,
        saldo_final=saldo_final,
        inicio=inicio,
        fim=fim,
    )


def _sequencia_de_saldos(
    saldos: Sequence[tuple[int, str, Decimal, Decimal | None]],
    saldo_inicial: Decimal | None,
    saldo_final: Decimal | None,
    nome: str,
) -> tuple[Decimal | None, Decimal | None, tuple[str, ...]]:
    """Confere cada lançamento contra o saldo impresso na linha."""
    com_saldo = [s for s in saldos if s[3] is not None]
    if not com_saldo:
        return saldo_inicial, saldo_final, ()
    if saldo_inicial is None:
        _, _, valor, saldo = saldos[0]
        if saldo is not None:
            saldo_inicial = saldo - valor
    if saldo_final is None:
        saldo_final = com_saldo[-1][3]
    avisos: list[str] = []
    corrente = saldo_inicial
    for numero, descricao, valor, saldo in saldos:
        if corrente is None:
            break
        esperado = corrente + valor
        if saldo is not None and saldo != esperado:
            avisos.append(
                f"{nome}, linha {numero}: saldo não fecha em '{descricao}': "
                f"{corrente} + {valor} = {esperado}, mas a planilha mostra "
                f"{saldo} (diferença {saldo - esperado}); algum lançamento "
                "pode ter ficado de fora."
            )
        corrente = saldo if saldo is not None else esperado
    return saldo_inicial, saldo_final, tuple(avisos)


def _cabecalho(
    linhas: Sequence[Linha], perfil: Perfil, nome: str
) -> tuple[int, dict[str, int]]:
    procuradas = perfil.colunas()
    for numero, linha in enumerate(linhas, start=1):
        posicoes = {normalizar(c): i for i, c in enumerate(linha) if c is not None}
        if all(normalizar(c) in posicoes for c in procuradas):
            return numero, {c: posicoes[normalizar(c)] for c in procuradas}
    raise LeituraInvalida(
        f"{nome}: cabeçalho não encontrado (colunas: {', '.join(procuradas)})"
    )


def _periodo(
    linhas: Sequence[Linha], perfil: Perfil, nome: str
) -> tuple[date | None, date | None]:
    if perfil.periodo is None:
        return None, None
    for linha in linhas:
        for celula in linha:
            if isinstance(celula, str) and (achado := perfil.periodo.search(celula)):
                try:
                    return parse_data(achado.group(1)), parse_data(achado.group(2))
                except DataInvalida as exc:
                    raise LeituraInvalida(f"{nome}: {exc}") from exc
    return None, None


def _data(
    perfil: Perfil, celula: object, inicio: date | None, fim: date | None
) -> date:
    for coluna in perfil.datas:
        bruto = celula(coluna)  # type: ignore[operator]
        if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
            continue
        texto = str(bruto).strip()
        # Data sem ano (DD/MM): o ano vem do período do extrato.
        if isinstance(bruto, str) and len(texto) == 5 and inicio and fim:
            dia, mes = texto.split("/")
            ano = inicio.year if int(mes) >= inicio.month else fim.year
            return parse_data(f"{dia}/{mes}/{ano}")
        return parse_data(bruto)
    raise DataInvalida("data vazia")


def _valor(perfil: Perfil, celula: object) -> Decimal | None:
    if perfil.valor is not None:
        valor = _numero(celula(perfil.valor))  # type: ignore[operator]
        if valor is None:
            return None
        if perfil.natureza is not None:
            marca = normalizar(celula(perfil.natureza)).upper()  # type: ignore[operator]
            if marca not in ("C", "D"):
                raise ValorInvalido(f"natureza {marca!r} não é C nem D")
            return -abs(valor) if marca == "D" else abs(valor)
        return valor
    credito = _numero(celula(perfil.credito))  # type: ignore[operator]
    debito = _numero(celula(perfil.debito))  # type: ignore[operator]
    if credito is not None:
        return abs(credito)
    if debito is not None:
        return -abs(debito)
    return None


def _numero(bruto: object) -> Decimal | None:
    if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
        return None
    if isinstance(bruto, float):
        return Decimal(repr(bruto)).quantize(_CENTAVO)
    return parse_valor(bruto.strip() if isinstance(bruto, str) else bruto).quantize(
        _CENTAVO
    )


def _texto(bruto: object) -> str | None:
    if bruto is None:
        return None
    if isinstance(bruto, float) and bruto.is_integer():
        bruto = int(bruto)
    return str(bruto).strip() or None


def _vazia(linha: Linha) -> bool:
    return all(c is None or (isinstance(c, str) and not c.strip()) for c in linha)
