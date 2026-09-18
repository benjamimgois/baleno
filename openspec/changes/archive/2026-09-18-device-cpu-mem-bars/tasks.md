# Tasks

## 1. SNMP Multivendor Collector & OID Cascading

- [x] 1.1 Mapear o catálogo de OIDs multivendor em `balenolib/topology/collector.py` para as 8 famílias de fabricantes (Huawei, HP, Aruba, Cisco, TP-Link, Juniper, MikroTik, Linux/Host-Resources) com ordenação de prioridade.
- [x] 1.2 Implementar rotinas de extração e conversão percentual (0% a 100%) em `collector.py` para formatos diretos (inteiros) e compostos (bytes usados / livres ou pools de buffer).
- [x] 1.3 Implementar cache de OIDs funcionais por dispositivo com detecção inicial guiada pelo vendor e mecanismo de invalidação após 2 falhas consecutivas.

## 2. Monitor Cadence & Cycle Timing

- [x] 2.1 Atualizar o intervalo padrão de performance `perf_interval` para 120.0 segundos em `balenolib/topology/monitor.py` e `balenolib/topology/tab.py`.
- [x] 2.2 Garantir que o primeiro ciclo de performance execute de forma imediata (`t = 0.0s`) na inicialização do monitoramento assíncrono.
- [x] 2.3 Validar que o payload emitido no sinal `updated` e repassado para `TopologyView.update_traffic` contém as chaves `cpu` e `memory` atualizadas.

## 3. NodeItem Mini-Bar Graphic Rendering

- [x] 3.1 Implementar a renderização gráfica das duas minibarras e rótulos (`CPU` e `MEM`) no método `NodeItem.paint()` em `balenolib/topology/gui/view.py`.
- [x] 3.2 Aplicar coloração dinâmica nas barras conforme os limiares (<70% verde `#3FB950`, 70-89% amarelo `#D29922`, ≥90% vermelho `#F85149`) e formato neutro para dados ausentes (`—`).
- [x] 3.3 Adicionar chamada a `node.update()` no processamento de tráfego de `TopologyView.update_traffic()` para forçar o redesenho dos cards com novos dados de performance.

## 4. Validation & Packaging

- [x] 4.1 Executar compilação e verificação de sintaxe (`python3 -m py_compile`) em todos os módulos alterados.
- [x] 4.2 Executar script de teste automatizado simulando respostas SNMP dos 8 fabricantes e verificando o cache de OID.
- [x] 4.3 Validar a renderização gráfica dos nós gerando imagem de teste do card com as minibarras preenchidas.
