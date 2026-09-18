# Tasks

## 1. Modos de Descoberta (Básico ICMP vs Profundo LLDP)

- [x] 1.1 Adicionar parâmetro `mode: str = 'deep'` ao `TopologyDiscoveryWorker` em `balenolib/topology/worker.py` (executando apenas ICMP e criando nós com papel `Host` quando `mode == 'basic'`)
- [x] 1.2 Adicionar seletor de modo (Deep / Basic) no formulário de descoberta em `balenolib/topology/tab.py` e desabilitar controles de SNMP quando no modo básico
- [x] 1.3 Validar unitariamente a execução do worker no modo básico verificando que nenhuma consulta SNMP é disparada e dispositivos são criados com status UP

## 2. Cores de Camadas e Persistência

- [x] 2.1 Adicionar suporte a `layer_colors: dict[str, str]` em `TopologyGraph` (`models.py`) e serialização/desserialização em `persistence.py`
- [x] 2.2 Adicionar botão seletor de cor com paleta pré-configurada e `QColorDialog` no formulário de descoberta em `tab.py`
- [x] 2.3 Atualizar `LayerTreeWidget` em `layers.py` para renderizar indicadores coloridos (`●`) nas camadas e ação de contexto "Set Layer Color..."
- [x] 2.4 Implementar lógica de herança de cor da camada semente para subcamadas de saltos LLDP pertencentes ao mesmo grupo

## 3. Referência Visual nos Ícones dos Dispositivos

- [x] 3.1 Atualizar `NodeItem.paint` em `balenolib/topology/gui/view.py` para renderizar anel de destaque com a cor da camada ao redor do círculo do ícone
- [x] 3.2 Implementar método no `TopologyView` para propagar alterações de cores de camadas para todos os nós visíveis em tempo real

## 4. Submenus de Contexto no Nó (Device Type e Layer)

- [x] 4.1 Implementar submenu `Device Type` em `TopologyActions._show_menu` (`actions.py`) listando membros de `DeviceRole` com ícones e checkmark no papel atual
- [x] 4.2 Implementar submenu `Layer` em `TopologyActions._show_menu` com lista de camadas existentes e opção `+ Move to New Layer...`
- [x] 4.3 Conectar callbacks no `TopologyView` para aplicar a alteração de papel (`role`) e camada (`layer`) com atualização do canvas, contadores da árvore e salvamento automático do mapa

## 5. Verificação Integrada e Build

- [x] 5.1 Criar testes automatizados cobrindo modo básico de descoberta, persistência de `layer_colors` e troca dinâmica de papel/camada
- [x] 5.2 Executar `python3 -m py_compile` em todos os módulos modificados e validar execução limpa
- [x] 5.3 Re-gerar o executável monolítico `dist/baleno` via `scripts/bundle-monolith.py` e validar compilação
