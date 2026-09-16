## Why

Hoje as linhas do mapa de topologia só refletem o nível hierárquico dos nós (verde = backbone, cinza = vizinho). O operador não consegue distinguir visualmente um link saudável de um link com interface derrubada. Isso obriga a inspecionar cada interface para saber o que está vivo ou quebrado.

## What Changes

- Links com as duas interfaces em estado "up" passam a ser desenhados como linha **tracejada animada** (marching ants), dando a impressão de que estão vivos e funcionando.
- Links com qualquer interface em estado "down" passam a ser desenhados como linha **sólida vermelha**, chamando atenção para possível defeito.
- O estado do link passa a depender **apenas** do `Interface.oper_status` dos dois lados (tráfego é ignorado).
- O estado operacional (ifOperStatus) das interfaces passa a ser re-verificado **uma vez por minuto** pelo monitor, mantendo o mapa fiel à realidade sem re-descoberta.
- A animação usa um único `QTimer` compartilhado na cena/view, animando apenas as edges ativas.

## Capabilities

### New Capabilities
- `topology-link-visualization`: definição de como as linhas do mapa de topologia refletem o estado das interfaces do link (ativo/offline) e da animação de tráfego.

### Modified Capabilities
<!-- Nenhuma capability existente tem requisito de comportamento alterado. -->

## Impact

- `cetuslib/topology/gui/view.py` — `EdgeItem` (estilo por estado, animação), `TopologyScene`/`TopologyView` (QTimer compartilhado, resolução de interface target, `update_statuses`).
- `cetuslib/topology/collector.py` — `LldpCollector.poll_status` (walk leve de ifOperStatus).
- `cetuslib/topology/monitor.py` — `TrafficMonitor` (re-verificação de status a cada minuto via sinal `status_updated`).
- `cetuslib/topology/tab.py` — conexão `status_updated` → `view.update_statuses`.
- Sem novas dependências externas; usa `QPen.setDashPattern`/`setDashOffset` do Qt6.

