# Proposal

## Why

Nem toda rede corporativa possui SNMP ou LLDP habilitado em todos os ativos, tornando varreduras profundas desnecessárias ou lentas quando o operador deseja apenas mapear nós ativos rapidamente. Além disso, mapas com múltiplas camadas e dezenas de nós tornam-se difíceis de distinguir visualmente sem diferenciação de cores. Por fim, nós descobertos ou desenhados frequentemente precisam de ajustes manuais de classificação (ex.: um roteador identificado como host genérico) ou de reorganização entre camadas, o que atualmente exige intervenção manual no arquivo JSON ou recriação do elemento.

## What Changes

- **Seletor de Modo de Descoberta**: Adição de opção no painel de Descoberta para alternar entre:
  - **Profundo (ICMP + LLDP)**: Fluxo completo com ping, consultas SNMP (IF-MIB/LLDP) e expansão recursiva de vizinhos.
  - **Básico (ICMP apenas)**: Varredura rápida apenas por ping ICMP, cadastrando hosts ativos diretamente na camada informada com papel padrão `Host` e desabilitando campos de credenciais SNMP.
- **Cores Personalizadas de Camada**:
  - Campo seletor de cor no formulário de Descoberta com paleta predefinida e diálogo de cor personalizada (`QColorDialog`).
  - Herança automática de cor para subcamadas de saltos LLDP pertencentes ao mesmo grupo de descoberta.
  - Exibição de indicador colorido (`●`) nos itens da árvore de camadas (`LayerTreeWidget`) e ação no menu de contexto para alterar a cor de qualquer camada existente.
  - Persistência das cores das camadas no JSON do mapa (`layer_colors`).
- **Referência Visual de Camada no Nó**:
  - Renderização de anel de destaque com a cor da camada associada ao redor do círculo do ícone do dispositivo (`NodeItem`), facilitando a identificação imediata do segmento de rede.
- **Menu de Contexto Aprimorado para Nós**:
  - Submenu **Device Type** permitindo alterar dinamicamente o papel do nó (`Router`, `Switch`, `Core Switch`, `Access Switch`, `Firewall`, `Server`, `AP`, `Camera`, `Host`, `Phone`, etc.), atualizando instantaneamente o ícone, rótulo e cor no canvas.
  - Submenu **Layer** permitindo mover o dispositivo para uma camada existente ou criar uma nova camada diretamente pelo diálogo de contexto.

## Capabilities

### New Capabilities
*(Nenhuma nova capability independente)*

### Modified Capabilities
- `topology-map-layers`: Adiciona suporte a modos de descoberta (Básico ICMP vs Profundo LLDP), atribuição/persistência de cores a camadas e indicador visual nos ícones de dispositivos.
- `node-context-actions`: Adiciona submenus no menu de contexto do nó para alteração de tipo de dispositivo (`DeviceRole`) e alteração de camada de pertencimento (`Layer`).

## Impact

- `balenolib/topology/tab.py`: Ajuste no formulário de descoberta (modo básico/profundo, campo de cor), integração com novos parâmetros do worker e delegação de ações de contexto.
- `balenolib/topology/worker.py`: Ramificação do `TopologyDiscoveryWorker` para execução em modo básico (ICMP-only) sem consultas SNMP.
- `balenolib/topology/gui/layers.py`: Suporte a cores de camadas, renderização de badges coloridos na árvore e ação de contexto "Set Layer Color...".
- `balenolib/topology/gui/view.py`: Renderização do anel colorido nos nós e métodos para atualizar papel e camada do dispositivo.
- `balenolib/topology/actions.py`: Implementação dos submenus `Device Type` e `Layer` com callbacks para atualização de nós e camadas.
- `balenolib/topology/persistence.py`: Serialização e desserialização de `layer_colors` no JSON do mapa (formato v3 retrocompatível).
