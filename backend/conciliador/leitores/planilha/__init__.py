"""Leitor genérico de planilhas (.xls e .xlsx) configurado por perfil.

Cada banco (ou sistema) é um perfil TOML: nomes das colunas, rótulos de
saldo, marcador de fim, linhas ignoradas. Banco novo é perfil novo, sem
código.
"""

from conciliador.leitores.planilha.leitor import ler_planilha
from conciliador.leitores.planilha.perfil import Perfil, PerfilInvalido, carregar_perfil

__all__ = ["Perfil", "PerfilInvalido", "carregar_perfil", "ler_planilha"]
