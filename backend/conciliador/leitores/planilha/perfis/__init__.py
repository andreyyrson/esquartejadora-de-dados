"""Perfis de planilha embutidos: um arquivo .toml por banco ou sistema."""

from __future__ import annotations

import functools
from importlib import resources

from conciliador.leitores.planilha.perfil import Perfil, carregar_perfil


@functools.cache
def perfis_embutidos() -> dict[str, Perfil]:
    pasta = resources.files(__package__)
    perfis = (
        carregar_perfil(arquivo.read_text(encoding="utf-8"))
        for arquivo in sorted(pasta.iterdir(), key=lambda a: a.name)
        if arquivo.name.endswith(".toml")
    )
    return {perfil.nome: perfil for perfil in perfis}


def perfil_embutido(nome: str) -> Perfil:
    return perfis_embutidos()[nome]


def identificar_perfil(conteudo: bytes) -> Perfil | None:
    """Primeiro perfil cujos textos de reconhecimento aparecem na planilha."""
    return next((p for p in perfis_embutidos().values() if p.reconhece(conteudo)), None)
