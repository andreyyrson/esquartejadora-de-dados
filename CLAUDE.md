# Regras do projeto

## Dados de clientes: proibido no repositório

O repositório é público. Nenhum dado vindo de arquivos reais de clientes
(extratos, relatórios do sistema) pode entrar em código, testes, commits,
mensagens de commit, descrições de PR ou comentários no GitHub:

- nomes de pessoas e empresas, CPF, CNPJ, números de conta ou agência,
  nomes de contas do sistema, valores, datas, descrições de lançamentos,
  nomes de arquivos e totais ou contagens tirados desses arquivos;
- arquivos reais servem só para validar localmente; testes usam dados
  inventados (ex.: "FORNECEDOR EXEMPLO", "BANCO A", valores redondos);
- extratos e planilhas fictícios ficam em `backend/tests/dados_ficticios/`.

Travas: `.gitignore`, hooks em `.githooks/` e o job `dados-sensiveis` do
CI (`ferramentas/verificar_dados_sensiveis.py`). Termos a bloquear (ex.:
nomes de clientes) vão em `.dados-sensiveis.txt`, que nunca é versionado.

## Desenvolvimento

TDD sempre: commit `test:` (falhando) antes do `feat:`. Um branch por
funcionalidade, com PR e CI verde.
