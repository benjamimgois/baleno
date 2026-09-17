# Proposal: add-manual-link

## Why

Hoje o mapa de topologia só contém links descobertos por LLDP/SNMP. Quando a descoberta não encontra um enlace (equipamento não gerenciado, link silencioso, adjacência que não responde SNMP), o operador não tem como representá-lo no mapa sem refazer o discovery. Permitir criar um link manualmente — escolhendo os dois endpoints, as portas e a velocidade — fecha essa lacuna e mantém o mapa fiel à realidade.

## What Changes

- Novo ícone **"Link"** na aba Objects, fixo e **sempre o primeiro** da paleta; é um botão *toggle* que entra/sai do modo de criação de link (não é arrastável, diferente dos `DevicePaletteButton`).
- **Modo de criação de link**:
  - Cursor vira cruz enquanto o modo está ativo.
  - Primeiro clique num dispositivo/grupo = **source**, com destaque **amarelo forte**.
  - Linha tracejada de *preview* segue o mouse até o alvo.
  - Segundo clique noutro dispositivo/grupo = cria o link.
  - Cancelamento via **Esc**, clique no **vazio**, ou clique no **próprio objeto**.
- **Diálogo de configuração do link** (`LinkCreationDialog`): lista de interfaces do source à esquerda, do target à direita; quando um lado não tem interfaces, campo de texto livre para digitar a porta. Um combobox de **velocidade** com padrão **AUTO**.
- **AUTO** = sem override (`override_status=None`, `override_speed=None`): o SNMP/monitor continua detectando status e velocidade. Sem interface para medir velocidade, o link é desenhado **cinza** (comportamento já existente de `speed_color(0)`).
- **Links duplicados** (mesmos endpoints + mesmas portas) exibem **mensagem de erro** e não são criados. Self-loop bloqueado.
- **Link grupo ↔ dispositivo** suportado (o grupo resolve para o dispositivo pai do cluster).
- O link manual é **persistido** no mapa e restaurado ao recarregar.

## Capabilities

### New Capabilities
- `topology-manual-link`: Criação manual de links entre dispositivos (e entre grupo colapsado e dispositivo) — modo de seleção de endpoints, configuração de portas e velocidade (AUTO por padrão), prevenção de duplicatas, renderização e persistência do link.

### Modified Capabilities

Nenhum. O contrato de AUTO/override já é coberto por `topology-link-override`; nenhum requisito existente muda — o recurso é aditivo.

## Impact

- **Código novo**: `LinkCreationDialog` em `cetuslib/topology/gui/detail.py`; `LinkButton` (toggle) em `cetuslib/topology/tab.py`; estado de modo de link e método `add_manual_link` em `cetuslib/topology/gui/view.py`.
- **Código modificado**: `cetuslib/topology/gui/view.py` — `NodeItem`/`GroupNodeItem` (destaque amarelo + clique em modo link), cena/view (preview, cancelamento, criação de `EdgeItem`), extração de helper de offset de links paralelos (hoje duplicado em `set_graph` e `set_graph_from_persisted`); `cetuslib/topology/tab.py` — paleta Objects (ícone Link fixo no início).
- **Modelo**: sem mudanças (`PortLink` já suporta tudo; velocidade via `override_speed`).
- **Assets**: nenhum novo (ícone Link desenhado programaticamente).
- **Dependências**: nenhuma nova.
- **Empacotamento**: `dist/cetus` regenerado via `scripts/bundle-monolith.py`; receitas .deb/AppImage/Flatpak inalteradas.
