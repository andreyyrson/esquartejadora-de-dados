"""Tratamento dos lançamentos entre a leitura e a conciliação.

- RF11: descrição limpa (sem prefixos do banco, datas, códigos, CPF/CNPJ
  e acentos) e contraparte (nome e CPF/CNPJ com dígito válido);
- RF12: tipo do lançamento (PIX, TED, tarifa, estorno...);
- RF13: o que não precisa ser conciliado (estorno com o lançamento que
  ele anula, valor zero e tipos escolhidos pelo usuário).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import Enum

from conciliador.transacao import Transacao


class TipoLancamento(Enum):
    PIX = "pix"
    TED = "ted"
    DOC = "doc"
    BOLETO = "boleto"
    CARTAO = "cartao"
    TARIFA = "tarifa"
    IMPOSTO = "imposto"
    CHEQUE = "cheque"
    DEPOSITO = "deposito"
    SAQUE = "saque"
    APLICACAO = "aplicacao"
    TRANSFERENCIA = "transferencia"
    ESTORNO = "estorno"
    OUTROS = "outros"


@dataclass(frozen=True, slots=True)
class Contraparte:
    nome: str | None
    # Só dígitos, e só quando o dígito verificador confere.
    documento: str | None


@dataclass(frozen=True, slots=True)
class Tratamento:
    transacao: Transacao
    tipo: TipoLancamento
    descricao_limpa: str
    contraparte: Contraparte
    conciliar: bool = True
    motivo: str | None = None
    # Lançamento que este anula (estorno e estornado apontam um para o outro).
    anula: Transacao | None = None


# RF12: a primeira regra que casar vence (tarifa de PIX é tarifa).
_REGRAS_DE_TIPO: tuple[tuple[TipoLancamento, re.Pattern[str]], ...] = tuple(
    (tipo, re.compile(padrao))
    for tipo, padrao in (
        (TipoLancamento.ESTORNO, r"\b(?:ESTORNO|DEVOLUCAO|DEV)\b|^EST\b"),
        (TipoLancamento.TARIFA, r"\bTARIFAS?\b|^TAR\b|\bCESTA\b"),
        (
            TipoLancamento.IMPOSTO,
            r"\b(?:DARF|IMPOSTOS?|ICMS|INSS|FGTS|GPS|IPTU|IPVA|SEFAZ?|DAE)\b",
        ),
        (
            TipoLancamento.CARTAO,
            r"\b(?:REDE|CIELO|GETNET|STONE|RSHOP|CARTAO|MAQUININHA)\b",
        ),
        (TipoLancamento.PIX, r"\bPIX\b"),
        (TipoLancamento.TED, r"\bTED\b"),
        (TipoLancamento.DOC, r"\bDOC\b"),
        (
            TipoLancamento.BOLETO,
            r"\b(?:BOLETO|COBRANCA)\b|\bPAGTO ELETRON\b|^PAGAMENTO EFETUADO\b",
        ),
        (TipoLancamento.CHEQUE, r"\b(?:CHEQUE|CHQ)\b"),
        (TipoLancamento.DEPOSITO, r"\b(?:DEP|DEPOSITO)\b"),
        (TipoLancamento.SAQUE, r"\bSAQUE\b"),
        (
            TipoLancamento.APLICACAO,
            r"\b(?:APLIC|APLICACAO|RESGATE|RDC|INVEST|POUP|POUPANCA)\b",
        ),
        (TipoLancamento.TRANSFERENCIA, r"\b(?:TRANSF|TRANSFERENCIA)\b"),
    )
)

# RF11: documentos em qualquer formato visto nos bancos.
_DOCUMENTOS = re.compile(
    r"[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}"  # CNPJ formatado
    r"|[0-9]{3}\.[0-9]{3}\.[0-9]{3}[- ][0-9]{2}"  # CPF (com hífen ou espaço)
    r"|\b[0-9]{14}\b|\b[0-9]{11}\b"  # só dígitos
)
_DATAS_E_HORAS = re.compile(
    r"\b[0-9]{2}/[0-9]{2}(?:/[0-9]{2,4})?\b|\b[0-9]{2}:[0-9]{2}(?::[0-9]{2})?\b"
)
_NUMEROS_SOLTOS = re.compile(r"\b[0-9]+\b")
# Rótulos que os bancos põem antes da contraparte.
_ROTULO = re.compile(
    r"^(?:"
    r"PIX\s*-?\s*(?:ENVIADO|RECEBIDO)(?:\s+SAFRAPAY)?"
    r"|TRANSF(?:ERENCIA)?\s+PIX\s+(?:ENVIADA|RECEBIDA)"
    r"|PGTO\s+QR\s+CODE\s+PIX"
    r"|PAGAMENTO\s+EFETUADO|PAGAMENTOS?"
    r"|TED\s*-?\s*CREDITO\s+EM\s+CONTA"
    r"|REM|DES|CP"
    r")\b"
)
_SEPARADORES_INICIAIS = re.compile(r"^[\s:\-]+")


def tratar(transacao: Transacao) -> Tratamento:
    """RF11 e RF12 para um lançamento."""
    texto = _normalizar(transacao.descricao)
    return Tratamento(
        transacao=transacao,
        tipo=_tipo(texto),
        descricao_limpa=_limpar(texto)[0],
        contraparte=_contraparte(texto),
    )


def tratar_todos(
    transacoes: Sequence[Transacao],
    *,
    ignorar_tipos: Iterable[TipoLancamento] = (),
    janela_estorno_dias: int = 3,
) -> list[Tratamento]:
    """RF11, RF12 e RF13 para uma lista, na mesma ordem."""
    ignorados = set(ignorar_tipos)
    tratados = [tratar(t) for t in transacoes]
    for i, tratado in enumerate(tratados):
        if tratado.transacao.valor == 0:
            tratados[i] = replace(tratado, conciliar=False, motivo="valor zero")
        elif tratado.tipo in ignorados:
            motivo = f"tipo {tratado.tipo.value} ignorado"
            tratados[i] = replace(tratado, conciliar=False, motivo=motivo)
    _anular_estornos(tratados, janela_estorno_dias)
    return tratados


def _anular_estornos(tratados: list[Tratamento], janela: int) -> None:
    for i, estorno in enumerate(tratados):
        if estorno.tipo is not TipoLancamento.ESTORNO or not estorno.conciliar:
            continue
        candidatos = [
            j
            for j, outro in enumerate(tratados)
            if j != i
            and outro.conciliar
            and outro.transacao.origem is estorno.transacao.origem
            and outro.transacao.valor == -estorno.transacao.valor
            and abs((outro.transacao.data - estorno.transacao.data).days) <= janela
        ]
        if not candidatos:
            continue
        j = min(
            candidatos,
            key=lambda k: (
                abs((tratados[k].transacao.data - estorno.transacao.data).days),
                k,
            ),
        )
        par = tratados[j]
        tratados[i] = replace(
            estorno, conciliar=False, motivo=_motivo(par.transacao), anula=par.transacao
        )
        tratados[j] = replace(
            par,
            conciliar=False,
            motivo=_motivo(estorno.transacao),
            anula=estorno.transacao,
        )


def _motivo(outro: Transacao) -> str:
    return f"anula '{outro.descricao}' de {outro.data:%d/%m/%Y}"


def _tipo(texto: str) -> TipoLancamento:
    return next(
        (tipo for tipo, regra in _REGRAS_DE_TIPO if regra.search(texto)),
        TipoLancamento.OUTROS,
    )


def _contraparte(texto: str) -> Contraparte:
    documento = next(
        (d for d in (_digitos(m) for m in _DOCUMENTOS.findall(texto)) if _valido(d)),
        None,
    )
    limpa, tinha_rotulo = _limpar(texto)
    nome = limpa if limpa and (tinha_rotulo or documento) else None
    return Contraparte(nome=nome, documento=documento)


def _limpar(texto: str) -> tuple[str, bool]:
    """Descrição sem documentos, datas, números e rótulos do banco."""
    sem_ruido = _DOCUMENTOS.sub(" ", texto)
    sem_ruido = _DATAS_E_HORAS.sub(" ", sem_ruido)
    sem_ruido = _NUMEROS_SOLTOS.sub(" ", sem_ruido.replace('"', " "))
    resto = _compactar(sem_ruido)
    tinha_rotulo = False
    while True:
        sem_rotulo = _SEPARADORES_INICIAIS.sub("", _ROTULO.sub("", resto, count=1))
        if sem_rotulo == resto:
            break
        tinha_rotulo = True
        resto = sem_rotulo
    return _compactar(resto).strip(" -:"), tinha_rotulo


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore")
    return _compactar(sem_acento.decode("ascii").upper())


def _compactar(texto: str) -> str:
    return " ".join(texto.split())


def _digitos(texto: str) -> str:
    return re.sub(r"[^0-9]", "", texto)


def _valido(numero: str) -> bool:
    if len(set(numero)) == 1:
        return False
    if len(numero) == 11:
        pesos = [list(range(10, 1, -1)), list(range(11, 1, -1))]
        return all(
            (
                sum(int(d) * p for d, p in zip(numero[: len(peso)], peso, strict=True))
                * 10
                % 11
            )
            % 10
            == int(numero[len(peso)])
            for peso in pesos
        )
    pesos_cnpj = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for peso in (pesos_cnpj, [6, *pesos_cnpj]):
        resto = (
            sum(int(d) * p for d, p in zip(numero[: len(peso)], peso, strict=True)) % 11
        )
        if (0 if resto < 2 else 11 - resto) != int(numero[len(peso)]):
            return False
    return True
