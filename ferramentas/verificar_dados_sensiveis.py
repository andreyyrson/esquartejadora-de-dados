"""Impede que dados de clientes cheguem ao GitHub.

Procura, nos arquivos rastreados e nas mensagens de commit:

- CPF e CNPJ com dígito verificador válido;
- extratos e planilhas (.ofx, .xlsx, .xls, .csv, .pdf) fora de
  ``backend/tests/dados_ficticios/``;
- termos da lista local ``.dados-sensiveis.txt`` (um por linha, ex.:
  nomes de clientes). Esse arquivo nunca é versionado.

Uma linha com o comentário ``dados-sensiveis: exemplo`` é ignorada
(para números de exemplo fictícios nos próprios testes).

Uso:
    python -m ferramentas.verificar_dados_sensiveis           # tudo
    python -m ferramentas.verificar_dados_sensiveis --staged  # pre-commit
    python -m ferramentas.verificar_dados_sensiveis --mensagem ARQ  # commit-msg
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

EXTENSOES_PROIBIDAS = {".ofx", ".xlsx", ".xls", ".csv", ".pdf"}
PASTA_PERMITIDA = "backend/tests/dados_ficticios/"
ARQUIVO_DE_TERMOS = ".dados-sensiveis.txt"
MARCADOR_EXEMPLO = "dados-sensiveis: " + "exemplo"

_CPF = re.compile(r"(?<![0-9])[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}(?![0-9])")
_CNPJ = re.compile(r"(?<![0-9])[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}(?![0-9])")
_CNPJ_COLADO = re.compile(r"CNPJ\s*:?\s*([0-9]{14})(?![0-9])", re.IGNORECASE)


@dataclass(frozen=True)
class Achado:
    local: str
    linha: int
    tipo: str
    trecho: str


def cpfs(texto: str) -> list[str]:
    return [m for m in _CPF.findall(texto) if _cpf_valido(_digitos(m))]


def cnpjs(texto: str) -> list[str]:
    achados = [m for m in _CNPJ.findall(texto) if _cnpj_valido(_digitos(m))]
    achados += [m for m in _CNPJ_COLADO.findall(texto) if _cnpj_valido(m)]
    return achados


def arquivo_proibido(caminho: str | Path) -> bool:
    posix = PurePosixPath(Path(caminho).as_posix())
    return posix.suffix.lower() in EXTENSOES_PROIBIDAS and not str(posix).startswith(
        PASTA_PERMITIDA
    )


def termos_encontrados(texto: str, termos: Iterable[str]) -> list[str]:
    normalizado = _normalizar(texto)
    return sorted(
        termo
        for termo in termos
        if re.search(rf"\b{re.escape(_normalizar(termo))}\b", normalizado)
    )


def verificar(
    caminhos: Iterable[Path],
    *,
    raiz: Path,
    termos: Iterable[str] = (),
    mensagens: dict[str, str] | None = None,
) -> list[Achado]:
    termos = set(termos)
    achados: list[Achado] = []
    for caminho in caminhos:
        local = _relativo(caminho, raiz)
        if arquivo_proibido(local):
            achados.append(Achado(local, 0, "arquivo proibido", caminho.suffix.lower()))
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        achados += _no_texto(local, texto, termos)
    for sha, mensagem in (mensagens or {}).items():
        achados += _no_texto(f"commit {sha}", mensagem, termos)
    return achados


def _no_texto(local: str, texto: str, termos: set[str]) -> list[Achado]:
    achados: list[Achado] = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if MARCADOR_EXEMPLO in linha:
            continue
        achados += [Achado(local, numero, "CPF", x) for x in cpfs(linha)]
        achados += [Achado(local, numero, "CNPJ", x) for x in cnpjs(linha)]
        achados += [
            Achado(local, numero, "termo proibido", t)
            for t in termos_encontrados(linha, termos)
        ]
    return achados


def _digitos(texto: str) -> str:
    return re.sub(r"[^0-9]", "", texto)


def _cpf_valido(numero: str) -> bool:
    if len(set(numero)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d) * (tamanho + 1 - i) for i, d in enumerate(numero[:tamanho]))
        if (soma * 10 % 11) % 10 != int(numero[tamanho]):
            return False
    return True


def _cnpj_valido(numero: str) -> bool:
    if len(set(numero)) == 1:
        return False
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for tamanho, pesos_da_vez in ((12, pesos), (13, [6, *pesos])):
        resto = sum(int(d) * p for d, p in zip(numero[:tamanho], pesos_da_vez)) % 11
        if (0 if resto < 2 else 11 - resto) != int(numero[tamanho]):
            return False
    return True


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore")
    return sem_acento.decode("ascii").casefold()


def _relativo(caminho: Path, raiz: Path) -> str:
    try:
        return caminho.relative_to(raiz).as_posix()
    except ValueError:
        return caminho.as_posix()


def _mascarar(achado: Achado) -> str:
    # Nunca repete o dado inteiro no terminal ou no log público do CI.
    trecho = achado.trecho
    if achado.tipo in ("CPF", "CNPJ", "termo proibido") and len(trecho) > 4:
        trecho = trecho[:2] + "*" * (len(trecho) - 4) + trecho[-2:]
    return f"{achado.local}:{achado.linha}: {achado.tipo}: {trecho}"


def _git(*argumentos: str, raiz: Path) -> str:
    return subprocess.run(
        ["git", *argumentos], cwd=raiz, check=True, capture_output=True, text=True
    ).stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--staged", action="store_true", help="só arquivos do commit")
    parser.add_argument("--mensagem", type=Path, help="arquivo da mensagem de commit")
    args = parser.parse_args(argv)

    raiz = Path(_git("rev-parse", "--show-toplevel", raiz=Path.cwd()).strip())
    arquivo_termos = raiz / ARQUIVO_DE_TERMOS
    termos = set()
    if arquivo_termos.exists():
        linhas = arquivo_termos.read_text(encoding="utf-8").splitlines()
        termos = {t.strip() for t in linhas if t.strip() and not t.startswith("#")}

    mensagens: dict[str, str] = {}
    if args.mensagem:
        caminhos: list[Path] = []
        mensagens["novo"] = args.mensagem.read_text(encoding="utf-8")
    elif args.staged:
        nomes = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", raiz=raiz)
        caminhos = [raiz / n for n in nomes.splitlines()]
    else:
        caminhos = [raiz / n for n in _git("ls-files", raiz=raiz).splitlines()]
        historico = _git("log", "--all", "--format=%H%x00%B%x1e", raiz=raiz)
        for registro in historico.split("\x1e"):
            if "\x00" in registro:
                sha, mensagem = registro.strip("\n").split("\x00", 1)
                mensagens[sha[:12]] = mensagem

    achados = verificar(caminhos, raiz=raiz, termos=termos, mensagens=mensagens)
    for achado in achados:
        print(_mascarar(achado), file=sys.stderr)
    if achados:
        print(
            f"\n{len(achados)} possível(is) dado(s) sensível(is). Nada de dados de "
            "clientes no repositório: troque por dados fictícios.",
            file=sys.stderr,
        )
        return 1
    print(f"ok: {len(caminhos)} arquivo(s) e {len(mensagens)} mensagem(ns) verificados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
