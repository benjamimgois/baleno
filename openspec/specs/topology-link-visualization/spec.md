# topology-link-visualization Specification

## Purpose
Define como as linhas do mapa de topologia refletem visualmente o estado das interfaces do link (ativo ou offline) e como a animação de tráfego é aplicada às linhas ativas.

## Requirements

### Requirement: Linha de link com ambas as interfaces up é tracejada e animada
O sistema SHALL desenhar como linha tracejada animada (marcha de traços em movimento) o link cujas duas interfaces estão em estado "up", quando a animação global estiver habilitada, aplicando a animação estritamente aos links visíveis na área da câmera (viewport culling).

#### Scenario: Link com ambas as interfaces up
- **WHEN** um link tem as duas interfaces em estado "up"
- **THEN** a linha é desenhada tracejada com os traços em movimento contínuo e sutil quando visível no viewport

#### Scenario: Interface com estado desconhecido ou não resolvido
- **WHEN** a interface de um lado do link tem estado "unknown" ou não pôde ser resolvida
- **THEN** o link é tratado como ativo (a ausência de "down" não desativa o link)

#### Scenario: Link fora do viewport da câmera
- **WHEN** um link ativo está posicionado fora da área atualmente visível no viewport do mapa
- **THEN** o sistema não dispara repaints periódicos de animação para este link até que ele entre no campo de visão

#### Scenario: Animação pausada ou desabilitada
- **WHEN** a animação de links estiver desativada globalmente pelo usuário
- **THEN** os links ativos são renderizados com traço estático sem avanço de fase ou timers periódicos

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

### Requirement: Cor do link ativo reflete a velocidade operacional
O sistema SHALL colorir a linha de um link ativo conforme a velocidade operacional do link, mapeando os limiares de velocidade para cores fixas.

#### Scenario: Link de 10 Gbps ou superior
- **WHEN** a velocidade do link é maior ou igual a 10 Gbps
- **THEN** a linha é desenhada em verde

#### Scenario: Link de 1 Gbps a menos de 10 Gbps
- **WHEN** a velocidade do link está entre 1 Gbps (inclusive) e menos de 10 Gbps
- **THEN** a linha é desenhada em azul claro

#### Scenario: Link abaixo de 1 Gbps
- **WHEN** a velocidade do link é maior que zero e menor que 1 Gbps (incluindo 100 Mbps ou inferior)
- **THEN** a linha é desenhada em laranja

#### Scenario: Velocidade desconhecida
- **WHEN** a velocidade do link é zero ou não pôde ser determinada
- **THEN** a linha é desenhada em cinza neutro

### Requirement: Velocidade do link é a menor das duas interfaces
O sistema SHALL considerar a velocidade operacional do link como o menor valor de `speed_mbps` entre as interfaces dos dois lados.

#### Scenario: Interfaces com velocidades diferentes
- **WHEN** as duas interfaces de um link operam em velocidades diferentes (ex.: 1 Gbps e 100 Mbps)
- **THEN** a cor do link reflete a velocidade da interface mais lenta

### Requirement: Velocidade das portas é atualizada periodicamente
O sistema SHALL re-verificar a velocidade operacional (ifHighSpeed, com fallback para ifSpeed) das interfaces dos dispositivos monitorados a cada minuto, para que as cores dos links sejam ajustadas dinamicamente sem nova descoberta.

#### Scenario: Velocidade renegociada após a descoberta
- **WHEN** a velocidade de uma interface muda depois da descoberta e o ciclo de verificação executa
- **THEN** o `speed_mbps` da interface é atualizado e a cor do link é ajustada no próximo redesenho

### Requirement: Legenda de cores de velocidade
O sistema SHALL exibir uma legenda compacta no mapa de topologia explicando o mapeamento entre cor e velocidade (e o vermelho para link down).

#### Scenario: Legenda visível no mapa
- **WHEN** o mapa de topologia é exibido
- **THEN** uma legenda mostrando as cores de velocidade (verde/azul claro/laranja/cinza) e o vermelho de down está visível

### Requirement: Pausa interativa da animação durante movimentação
O sistema SHALL pausar os ciclos de atualização de animação de linhas enquanto o usuário estiver executando operações de pan pelo mapa ou arrastando nós.

#### Scenario: Usuário arrasta o mapa ou nós
- **WHEN** o usuário clica e move o mouse para pan ou para reposicionar nós na cena
- **THEN** o timer de marcha das linhas é suspenso, retomando automaticamente ao soltar o mouse

### Requirement: Minimap não renderiza animação contínua de traços
O sistema SHALL renderizar as conexões no minimap sem animação periódica de traços e sem polling contínuo da cena.

#### Scenario: Exibição no minimap
- **WHEN** o mapa possui conexões ativas com animação em execução na visualização principal
- **THEN** o minimap desenha as conexões em formato estático e não dispara repaints a cada ciclo do timer de animação

### Requirement: Controle manual de ativação da animação
O sistema SHALL fornecer um botão de alternância na interface da topologia permitindo ligar e desligar a animação dos links.

#### Scenario: Usuário clica no botão de animação
- **WHEN** o usuário clica no botão de alternância de animação na barra de ferramentas da topologia
- **THEN** o sistema alterna o estado de animação, atualiza o ícone do botão e persiste a preferência nas configurações do usuário
