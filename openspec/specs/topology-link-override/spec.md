# topology-link-override Specification

## Purpose
Permite ao operador ajustar manualmente o estado (up/down) e a velocidade de um link no mapa de topologia, com prioridade sobre a detecção automática, para uso quando a automação falha.

## Requirements

### Requirement: Ajuste manual de estado por link
O sistema SHALL permitir, via menu de contexto sobre um link, definir manualmente o estado do link como "up", "down" ou "Auto".

#### Scenario: Forçar link como down
- **WHEN** o usuário clica com o botão direito em um link e escolhe Estado → Down
- **THEN** o link é desenhado como offline (vermelho) independentemente do oper_status das interfaces

#### Scenario: Forçar link como up
- **WHEN** o usuário escolhe Estado → Up em um link cuja interface está "down"
- **THEN** o link é desenhado como ativo (tracejado animado)

#### Scenario: Voltar ao automático
- **WHEN** o usuário escolhe Estado → Auto
- **THEN** o link volta a usar o oper_status das interfaces para determinar o estado

### Requirement: Ajuste manual de velocidade por link
O sistema SHALL permitir, via menu de contexto sobre um link, definir manualmente a velocidade do link para um valor predefinido ou "Auto".

#### Scenario: Definir velocidade manual
- **WHEN** o usuário escolhe uma velocidade (ex.: 10 Gbps) no menu do link
- **THEN** a cor do link reflete a velocidade escolhida, ignorando o `speed_mbps` detectado

#### Scenario: Voltar à velocidade automática
- **WHEN** o usuário escolhe Velocidade → Auto
- **THEN** o link volta a usar o menor `speed_mbps` das duas interfaces para definir a cor

### Requirement: Ajuste manual tem prioridade sobre o automático
O sistema SHALL aplicar o ajuste manual com prioridade sobre qualquer valor detectado automaticamente (descoberta ou monitor periódico).

#### Scenario: Monitor não sobrescreve override
- **WHEN** um link tem override manual de estado/velocidade e o monitor atualiza oper_status/speed automaticamente
- **THEN** o override manual permanece aplicado no desenho do link

### Requirement: Ajuste manual é persistido
O sistema SHALL persistir os overrides de estado e velocidade junto do mapa de topologia e restaurá-los ao recarregar.

#### Scenario: Override sobrevive ao reload
- **WHEN** um link tem override manual e o mapa é salvo e recarregado
- **THEN** o override é restaurado e o link é desenhado conforme o valor manual
