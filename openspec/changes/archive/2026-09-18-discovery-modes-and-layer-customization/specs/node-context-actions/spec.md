# Spec Delta

## ADDED Requirements

### Requirement: Submenu de alteração de tipo de dispositivo (Device Type)
O sistema SHALL fornecer no menu de contexto do nó de dispositivo um submenu `Device Type` permitindo alterar dinamicamente o papel (`DeviceRole`) do equipamento.

#### Scenario: Listagem de papéis disponíveis
- **WHEN** o usuário abre o submenu `Device Type` no menu de contexto de um dispositivo
- **THEN** o sistema exibe os papéis de rede suportados (Router, Switch, Core Switch, Access Switch, Firewall, Server, AP, Camera, Cloud, Host, Phone) com ícones representativos e indicador de seleção no papel atual

#### Scenario: Alteração imediata de papel no canvas
- **WHEN** o usuário clica em um novo papel no submenu `Device Type`
- **THEN** o dispositivo assume o novo papel, seu ícone, rótulo de tipo e cor temáticos são atualizados imediatamente no canvas e a alteração é persistida no mapa

### Requirement: Submenu de alteração de camada do dispositivo (Layer)
O sistema SHALL fornecer no menu de contexto do nó de dispositivo um submenu `Layer` permitindo reatribuir ou mover o equipamento entre camadas do mapa.

#### Scenario: Listagem e seleção de camada existente
- **WHEN** o usuário abre o submenu `Layer` no menu de contexto de um dispositivo
- **THEN** o sistema lista as camadas conhecidas no mapa, marcando a camada atual em que o nó se encontra, e ao clicar em uma camada diferente, move o nó para a camada selecionada

#### Scenario: Mover para nova camada
- **WHEN** o usuário aciona a opção "+ Move to New Layer..." dentro do submenu `Layer`
- **THEN** o sistema solicita o nome da nova camada e sua cor, cria a camada na árvore lateral, move o dispositivo para ela e atualiza a referência visual de cor no nó
