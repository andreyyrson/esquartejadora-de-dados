# Esquartejadora de Dados — Conciliador Bancário

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
