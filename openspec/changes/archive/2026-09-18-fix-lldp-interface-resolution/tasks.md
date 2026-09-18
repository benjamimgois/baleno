# Tasks

## 1. Coleta e Fallback de Nomes de Porta Local (collector.py)

- [x] 1.1 Atualizar assinatura de `_collect_neighbors` para receber `device: Device` e passar `device` a partir de `collect_async`
- [x] 1.2 Implementar resolução de fallback de `local_port` via `device.interfaces` (por `ifIndex` e por índice ordinal de portas físicas)
- [x] 1.3 Adicionar leitura e fallback de `OID_LOC_PORT_DESC` quando `OID_LOC_PORT_ID` for nulo ou não cobrir todas as portas
- [x] 1.4 Testar unitariamente coleta de vizinhos simulando tabela LLDP com índices numéricos locais e walk parcial

## 2. Normalização de Portas e Reconciliação Recíproca (engine.py)

- [x] 2.1 Expandir `_PORT_ALIASES` em `balenolib/topology/engine.py` com `xgigabitethernet`, `xge`, `twentyfivegige` e `hundredgige`
- [x] 2.2 Implementar reconciliação de links recíprocos em `TopologyEngine.build()` correlacionando anúncios bidirecionais assimétricos
- [x] 2.3 Garantir que links reconciliados não gerem enlaces duplicados nem falsos grupos LAG

## 3. Verificação Integrada e Empacotamento

- [x] 3.1 Criar teste automatizado simulando o cenário real de `CORE_CAMG` (porta 35) e `CORE_PRODEMGE` (XGE0/0/3) verificando link único com nome canônico
- [x] 3.2 Executar `python3 -m py_compile` em todos os módulos afetados e validar execução limpa
- [x] 3.3 Re-gerar o executável monolítico `dist/baleno` via `scripts/bundle-monolith.py` e validar compilação
