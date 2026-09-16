## ADDED Requirements

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
