# topology-live-monitoring Specification

## Purpose
Monitoramento ao vivo do mapa de topologia: coleta de contadores de tráfego (octetos por interface), CPU e memória dos dispositivos, com concorrência, reuso de engine SNMP e cadências independentes entre contadores e métricas de performance, emitindo taxas em bps por ciclo para a UI.

## Requirements

### Requirement: Coleta concorrente de contadores
O sistema SHALL coletar os contadores de octetos de todas as interfaces de todos os dispositivos monitorados concorrentemente em um único ciclo, em vez de sequencialmente, de modo que o tempo de ciclo não cresça linearmente com o número de dispositivos.

#### Scenario: Múltiplos dispositivos responsivos
- **WHEN** o monitor executa um ciclo com N dispositivos responsivos
- **THEN** as coletas dos N dispositivos são disparadas concorrentemente e o ciclo termina em tempo próximo ao de um único dispositivo, e não em N vezes esse tempo

#### Scenario: Limite de concorrência
- **WHEN** o número de dispositivos excede o limite de concorrência configurado
- **THEN** as coletas são escalonadas em ondas, sem exceder o limite de operações simultâneas

### Requirement: Reuso de engine e transporte SNMP
O sistema SHALL criar um `SnmpEngine` e um `UdpTransportTarget` por dispositivo uma única vez e reutilizá-los em ciclos sucessivos, em vez de criar e destruir a engine e o event loop a cada coleta.

#### Scenario: Ciclos sucessivos
- **WHEN** o monitor executa múltiplos ciclos consecutivos
- **THEN** a mesma engine e o mesmo transporte são reutilizados por dispositivo, e nenhum `asyncio.run()` ou engine nova é criado por coleta

#### Scenario: Encerramento do monitor
- **WHEN** o monitor é parado
- **THEN** as engines e os transportes abertos são fechados e seus recursos liberados

### Requirement: Desacoplamento entre contadores e CPU/memória
O sistema SHALL coletar os contadores de tráfego a cada ciclo curto (intervalo de tráfego) e coletar CPU e memória em cadência mais lenta, sem que a coleta de CPU/memória atrase a coleta dos contadores.

#### Scenario: Caminho de contadores independente
- **WHEN** o monitor coleta contadores de um dispositivo
- **THEN** a coleta lê apenas os octetos de entrada/saída (ifHCInOctets/ifHCOutOctets, com fallback 32-bit), sem executar walks de CPU/memória na mesma chamada

#### Scenario: CPU/memória em cadência lenta
- **WHEN** o intervalo de performance (default 60 s) não foi atingido
- **THEN** o monitor não realiza walks de CPU/memória, e os valores de CPU/memória reportados permanecem os da última coleta

### Requirement: Resolução de comunidade uma única vez
O sistema SHALL resolver a comunidade SNMP de cada dispositivo uma única vez, no início do monitoramento, e reutilizá-la nos ciclos seguintes, em vez de tentar múltiplas comunidades a cada ciclo.

#### Scenario: Comunidade lembrada pela descoberta
- **WHEN** um dispositivo já tem comunidade SNMP lembrada em configuração
- **THEN** o monitor usa essa comunidade diretamente, sem re-tentar outras a cada ciclo

#### Scenario: Dispositivo sem comunidade válida
- **WHEN** nenhuma comunidade testada responde para um dispositivo
- **THEN** o dispositivo é marcado como inalcançável e re-tentado apenas no próximo ciclo de status, sem pagar timeout de comunidade a cada ciclo de tráfego

### Requirement: Emissão de taxas por ciclo
O sistema SHALL emitir, a cada ciclo, as taxas em bits por segundo por interface e por dispositivo, calculadas a partir da diferença entre duas amostras consecutivas de contadores, com o mesmo formato de payload consumido pela UI.

#### Scenario: Primeiro ciclo
- **WHEN** o monitor coleta a primeira amostra de um dispositivo
- **THEN** nenhuma taxa é emitida para esse dispositivo (amostra é baseline), e a taxa passa a ser emitida a partir do segundo ciclo

#### Scenario: Cálculo da taxa
- **WHEN** duas amostras consecutivas existem para um dispositivo
- **THEN** a taxa por interface é `(octetos_atuais − octetos_anteriores) × 8 / intervalo`, e a taxa por dispositivo é a soma das interfaces
