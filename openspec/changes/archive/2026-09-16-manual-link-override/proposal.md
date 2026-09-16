## Why

A detecção automática de velocidade e estado de um link (via SNMP `ifHighSpeed`/`ifOperStatus`) pode falhar — LLDP com número de porta não mapeado a ifIndex, agentes sem ifXTable, contador ifSpeed estourado. Nesses casos o mapa mostra cor/estado errados e o operador não tem como corrigir. Um ajuste manual por link dá controle quando a automação falha.

## What Changes

- Clicar com o botão direito sobre um link abre um menu de contexto com:
  - **Estado**: Auto / Up / Down.
  - **Velocidade**: Auto / 10 Mbps / 100 Mbps / 1 Gbps / 10 Gbps.
- O ajuste manual tem **prioridade sobre o automático**: com override ativo, o estado/cor do link usa o valor manual e ignora `oper_status`/`speed_mbps` da descoberta e do monitor.
- `PortLink` ganha campos de override (`override_status`, `override_speed`), persistidos no mapa (`topology_map.json`) e restaurados no reload.
- Links com override exibem um marcador sutil ("M") para indicar que estão com ajuste manual; "Auto" remove o override e volta ao automático.
- Para clicabilidade, a área de acerto do link é alargada (shape com pen largo), sem alterar o traço visual.

## Capabilities

### New Capabilities
- `topology-link-override`: ajuste manual de estado e velocidade por link, com prioridade sobre a detecção automática e persistência.

### Modified Capabilities
<!-- Nenhuma capability existente muda de requisito: o override é uma camada por cima de topology-link-visualization. -->

## Impact

- `cetuslib/topology/models.py` — `PortLink` (`override_status`, `override_speed`, `to_dict`/`from_dict`).
- `cetuslib/topology/gui/view.py` — `EdgeItem` (context menu, shape de acerto, marcador de override, `refresh_state`/`link_speed` consultando override), `TopologyScene`/`TopologyView` (sinal e menu).
- `cetuslib/topology/tab.py` — conexão do menu de contexto de link (ou manipulação direta na view).
- Sem novas dependências externas.
