"""Perfil de leitura de uma planilha, carregado de TOML."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass

from conciliador.transacao import Origem


class PerfilInvalido(ValueError):
    """O perfil TOML não tem o formato esperado."""


@dataclass(frozen=True)
class Perfil:
    nome: str
    origem: Origem
    # Colunas: data aceita alternativas (a primeira preenchida vale).
    datas: tuple[str, ...]
    descricoes: tuple[str, ...]
    valor: str | None = None
    natureza: str | None = None  # coluna C/D
    credito: str | None = None
    debito: str | None = None
    documento: str | None = None
    banco: str | None = None
    reconhecer: tuple[str, ...] = ()
    saldo_inicial: tuple[str, ...] = ()
    saldo_final: tuple[str, ...] = ()
    marcadores_de_fim: tuple[str, ...] = ()
    ignorar_coluna: str | None = None
    ignorar_valores: tuple[str, ...] = ()
    periodo: re.Pattern[str] | None = None
    inverter_sinal: bool = False

    def colunas(self) -> tuple[str, ...]:
        opcionais = (self.valor, self.natureza, self.credito, self.debito)
        extras = (self.documento, self.ignorar_coluna)
        return (
            *self.datas,
            *self.descricoes,
            *(c for c in (*opcionais, *extras) if c is not None),
        )

    def reconhece(self, conteudo: bytes) -> bool:
        from conciliador.leitores.planilha.tabela import primeiras_linhas_em_texto

        if not self.reconhecer:
            return False
        texto = primeiras_linhas_em_texto(conteudo)
        return texto is not None and all(
            normalizar(marca) in texto for marca in self.reconhecer
        )


def carregar_perfil(texto: str) -> Perfil:
    try:
        dados = tomllib.loads(texto)
        colunas = dados["colunas"]
        origem = Origem(dados["origem"])
        datas = tuple(colunas["data"])
        descricoes = tuple(colunas["descricao"])
    except (tomllib.TOMLDecodeError, KeyError, ValueError, TypeError) as exc:
        raise PerfilInvalido(f"perfil inválido: {exc}") from exc
    tem_valor = "valor" in colunas or "credito" in colunas or "debito" in colunas
    if not datas or not descricoes or not tem_valor:
        raise PerfilInvalido("perfil precisa de data, descrição e valor")
    saldos = dados.get("saldos", {})
    ignorar = dados.get("ignorar", {})
    periodo = dados.get("periodo")
    return Perfil(
        nome=dados.get("nome", "sem nome"),
        origem=origem,
        datas=datas,
        descricoes=descricoes,
        valor=colunas.get("valor"),
        natureza=colunas.get("natureza"),
        credito=colunas.get("credito"),
        debito=colunas.get("debito"),
        documento=colunas.get("documento"),
        banco=dados.get("banco"),
        reconhecer=tuple(dados.get("reconhecer", ())),
        saldo_inicial=tuple(saldos.get("inicial", ())),
        saldo_final=tuple(saldos.get("final", ())),
        marcadores_de_fim=tuple(dados.get("fim", {}).get("marcadores", ())),
        ignorar_coluna=ignorar.get("coluna"),
        ignorar_valores=tuple(ignorar.get("valores", ())),
        periodo=re.compile(periodo) if periodo else None,
        inverter_sinal=bool(dados.get("inverter_sinal", False)),
    )


def normalizar(texto: object) -> str:
    """Para comparar nomes: sem acento, minúsculo, espaços compactados."""
    import unicodedata

    base = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore")
    return " ".join(base.decode("ascii").casefold().split())
