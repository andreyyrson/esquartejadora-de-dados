# Esquartejadora de Dados — Conciliador Bancário

Lê extratos bancários (OFX, PDF, CSV/Excel) de vários bancos e concilia
contra o extrato do sistema.

## Arquitetura

```
backend/
  conciliador/   núcleo em Python puro (regra de negócio, sem web)
  tests/         unit/ (exemplos) e propriedades/ (hypothesis)
frontend/        Next.js (fase posterior)
```

## Desenvolvimento (TDD)

Toda funcionalidade começa por um teste que falha (`test:`), depois o
mínimo de código para passar (`feat:`), depois refatoração (`refactor:`).

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest          # testes + cobertura (mínimo 95%)
ruff check . && ruff format --check .
mypy
```

## Dados de clientes

Nunca versione extratos, relatórios ou qualquer dado real de clientes. Ative
os hooks que bloqueiam isso antes do commit:

```bash
git config core.hooksPath .githooks
```

Para bloquear também nomes de clientes, liste-os (um por linha) em
`.dados-sensiveis.txt` na raiz. Esse arquivo é ignorado pelo git. Para
verificar tudo manualmente:

```bash
python3 -m ferramentas.verificar_dados_sensiveis
```
