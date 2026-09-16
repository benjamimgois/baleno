## Purpose

Define como as linhas do mapa de topologia refletem visualmente o estado das interfaces do link (ativo ou offline) e como a animação de tráfego é aplicada às linhas ativas.

## ADDED Requirements

### Requirement: Linha de link com ambas as interfaces up é tracejada e animada
O sistema SHALL desenhar como linha tracejada animada (marcha de traços em movimento) o link cujas duas interfaces estão em estado "up".

#### Scenario: Link com ambas as interfaces up
- **WHEN** um link tem as duas interfaces em estado "up"
- **THEN** a linha é desenhada tracejada com os traços em movimento contínuo e sutil

#### Scenario: Interface com estado desconhecido ou não resolvido
- **WHEN** a interface de um lado do link tem estado "unknown" ou não pôde ser resolvida
- **THEN** o link é tratado como ativo (a ausência de "down" não desativa o link)

### Requirement: Linha de link com interface down é vermelha
O sistema SHALL desenhar como linha sólida vermelha o link em que pelo menos uma das interfaces está em estado "down".

#### Scenario: Interface down no lado de origem
- **WHEN** a interface do lado de origem do link está em estado "down"
- **THEN** a linha é desenhada sólida em vermelho

#### Scenario: Interface down no lado de destino
- **WHEN** a interface do lado de destino do link está em estado "down"
- **THEN** a linha é desenhada sólida em vermelho

### Requirement: Estado do link independe de tráfego
O sistema SHALL determinar o estado do link exclusivamente pelo estado operacional das interfaces, sem considerar as taxas de tráfego.

#### Scenario: Link ativo sem tráfego
- **WHEN** um link tem as duas interfaces "up" e taxa de tráfego igual a zero
- **THEN** o link permanece desenhado como ativo (tracejado animado)

### Requirement: Status das portas é atualizado periodicamente
O sistema SHALL re-verificar o estado operacional (ifOperStatus) das interfaces dos dispositivos monitorados a cada minuto, para que o mapa reflita a realidade sem exigir nova descoberta.

#### Scenario: Interface cai após a descoberta
- **WHEN** uma interface cai depois da descoberta e o próximo ciclo de verificação de status executa
- **THEN** o oper_status da interface é atualizado e o link passa a ser desenhado em vermelho

#### Scenario: Interface volta após a descoberta
- **WHEN** uma interface que estava "down" volta a ficar "up" e o ciclo de verificação executa
- **THEN** o oper_status da interface é atualizado e o link volta a ser desenhado como ativo

