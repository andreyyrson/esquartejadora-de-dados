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
