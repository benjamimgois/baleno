# Proposal: accelerate-topology-traffic

## Why

As linhas do mapa de topologia demoram para exibir o tráfego em Mbps porque o monitor ao vivo (`TrafficMonitor`) coleta os contadores SNMP de forma estritamente sequencial e recria um `SnmpEngine` + event loop a cada dispositivo a cada ciclo. Além disso, a coleta de CPU/memória (irrelevante para o Mbps) acontece *antes* dos contadores na mesma chamada, e cada walk tem timeout de 2 s com 1 retry. Com N dispositivos, o tempo de ciclo vira ~N × (custo de CPU/mem + contadores + setup de engine), e o rótulo de tráfego só aparece no 2º ciclo (necessidade de duas amostras).

A discovery já resolveu esse problema com `ThreadPoolExecutor(max_workers=8)`; o monitor é o único ponto que não herdou a concorrência.

## What Changes

- **A — Coleta concorrente**: o `TrafficMonitor` passa a coletar os contadores de todos os dispositivos concorrentemente, usando o backend `asyncio` do pysnmp (um único event loop no thread do monitor), em vez do `for` sequencial.
- **C — Reuso de engine/transporte**: cada dispositivo ganha um `SnmpEngine` + `UdpTransportTarget` criados uma única vez e reutilizados em todos os ciclos, eliminando `asyncio.run()` + criação/destruição de engine por coleta.
- **B — Desacoplamento contadores × CPU/memória**: novo método leve `poll_counters_async` que lê apenas `ifHCInOctets`/`ifHCOutOctets` (com fallback 32-bit). Contadores a cada ciclo curto (padrão 5 s); CPU/memória em cadência lenta (padrão 60 s), fora do caminho do Mbps.
- Resolução da comunidade SNMP por dispositivo feita uma única vez no setup (não mais a cada ciclo), reaproveitando a comunidade já lembrada em `ConfigManager` pela discovery.

## Capabilities

### New Capabilities

- `topology-live-monitoring`: monitoramento ao vivo de tráfego (contadores de octetos por interface), CPU e memória dos dispositivos do mapa de topologia — coleta concorrente com reuso de engine SNMP, desacoplamento de cadências entre contadores e CPU/memória, e emissão de taxas em bps por ciclo.

### Modified Capabilities

- `topology-link-visualization`: nenhum requisito de renderização muda. O monitor continua emitindo os mesmos sinais (`updated`, `status_updated`, `speed_updated`) com o mesmo formato de payload; apenas a *origem* e a *latência* dos dados mudam.

## Impact

- **Código modificado**: `cetuslib/topology/monitor.py` — reescrever `run()` para um loop `asyncio` com `gather`, setup único de engines por dispositivo, resolução de comunidade no setup, e cadências separadas para contadores vs CPU/memória. `cetuslib/topology/collector.py` — adicionar `poll_counters_async` e métodos async leves que aceitam engine/transport pré-existentes (assinaturas novas, sem quebrar `collect()` usado pela discovery).
- **Código não modificado**: `cetuslib/topology/gui/view.py` (renderização/labels), `cetuslib/topology/tab.py` (conexão de sinais), `cetuslib/topology/worker.py` (discovery).
- **Dependências**: nenhuma nova (`asyncio`, `concurrent.futures` e pysnmp já em uso).
- **Config**: nenhuma chave nova obrigatória; o par `interval`/`status_interval` existente continua, e um `perf_interval` opcional para CPU/memória pode ser adicionado ao `ConfigManager`.
- **Empacotamento**: regenerar `dist/cetus` via `scripts/bundle-monolith.py`; nada muda nas receitas .deb/AppImage/Flatpak.
