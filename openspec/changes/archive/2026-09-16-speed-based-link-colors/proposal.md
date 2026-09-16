## Why

As linhas do mapa de topologia hoje só distinguem "ativo" (verde tracejado) de "offline" (vermelho). O operador não enxerga a velocidade de operação de cada link — um backbone 10G e um uplink 100M parecem idênticos. Colorir por velocidade dá leitura instantânea da capacidade do enlace e revela gargalos e mismatch de negociação.

## What Changes

- A cor de um link ativo passa a refletir a velocidade operacional do link (mínimo entre as duas interfaces):
  - ≥ 10 Gbps → verde
  - 1 Gbps a < 10 Gbps → azul claro
  - > 0 a < 1 Gbps (inclui 100 Mbps ou inferior) → laranja
  - velocidade desconhecida (0) → cinza neutro
- Links "down" continuam **sólidos vermelhos**, ignorando a velocidade.
- O estilo (tracejado animado = up) permanece o sinal de "vivo"; a cor passa a codificar velocidade.
- A velocidade (ifHighSpeed, com fallback ifSpeed) passa a ser re-verificada **uma vez por minuto** junto do oper_status, atualizando as cores dinamicamente.
- Velocidade do link = `min(speed_mbps` das duas pontas`)`.
- Uma legenda compacta no canvas explica o mapa de cores.

## Capabilities

### New Capabilities
<!-- Nenhuma — a visualização de links já existe. -->

### Modified Capabilities
- `topology-link-visualization`: a cor da linha de um link ativo passa a refletir a velocidade (antes fixa em verde); adiciona re-verificação periódica de velocidade e legenda de cores.

## Impact

- `cetuslib/topology/gui/view.py` — `EdgeItem` (cor por velocidade, `min` das pontas), helper `speed_color()`, legenda no `TopologyView`.
- `cetuslib/topology/collector.py` — `LldpCollector.poll_speed()` (ifHighSpeed + fallback ifSpeed).
- `cetuslib/topology/monitor.py` — `TrafficMonitor` re-verifica velocidade a cada minuto (sinal `speed_updated`).
- `cetuslib/topology/tab.py` — conexão `speed_updated` → `view.update_speeds`.
- Sem novas dependências externas.
