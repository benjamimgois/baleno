# Spec Delta

## MODIFIED Requirements

### Requirement: Desacoplamento entre contadores e CPU/memória
O sistema SHALL coletar os contadores de tráfego a cada ciclo curto (intervalo de tráfego) e coletar CPU e memória em cadência de performance desacoplada de 120 segundos, sem que a coleta de CPU/memória atrase a coleta dos contadores de tráfego.

#### Scenario: Caminho de contadores independente
- **WHEN** o monitor coleta contadores de um dispositivo
- **THEN** a coleta lê apenas os octetos de entrada/saída (ifHCInOctets/ifHCOutOctets, com fallback 32-bit), sem executar consultas de CPU/memória na mesma chamada

#### Scenario: CPU/memória em cadência lenta
- **WHEN** o intervalo de performance (default 120 s) não foi atingido
- **THEN** o monitor não realiza consultas de CPU/memória, e os valores de CPU/memória reportados na UI permanecem os da última coleta válida

#### Scenario: Disparo imediato no primeiro ciclo
- **WHEN** o monitor de topologia é iniciado
- **THEN** a primeira coleta de CPU e memória é disparada imediatamente sem aguardar o decurso dos 120 segundos iniciais

## ADDED Requirements

### Requirement: Coleta multivendor de CPU e memória com cache de OID
O sistema SHALL consultar métricas de utilização de CPU e memória suportando múltiplos fabricantes conforme lista de prioridade ordenada (Huawei, HP, Aruba, Cisco, TP-Link, Juniper, MikroTik, Linux/Host-Resources), armazenando a OID funcional em cache por dispositivo para os ciclos subsequentes.

#### Scenario: Resolução prioritária de OID funcional
- **WHEN** um dispositivo com SNMP ativo é consultado pela primeira vez para métricas de CPU e memória
- **THEN** o sistema testa as OIDs dos fabricantes na ordem de prioridade até obter resposta válida, ou inicia pelo fabricante identificado pelo dispositivo se conhecido

#### Scenario: Reuso da OID funcional em cache
- **WHEN** o ciclo de 120 segundos dispara para um dispositivo que já teve OID funcional identificada
- **THEN** o sistema consulta diretamente a OID em cache, sem testar a cascata de fabricantes

#### Scenario: Invalidação de cache em caso de falha consecutiva
- **WHEN** a consulta da OID em cache falhar por dois ciclos consecutivos
- **THEN** o cache daquele dispositivo é invalidado e a busca por cascata é reexecutada no próximo ciclo

### Requirement: Visualização de minibarras de CPU e memória no nó
O sistema SHALL renderizar graficamente duas minibarras com percentuais de consumo de CPU e memória logo abaixo da marca e modelo em cada nó do mapa de topologia.

#### Scenario: Exibição de métricas válidas
- **WHEN** o dispositivo possui percentual válido de CPU e memória reportado pelo monitor
- **THEN** o nó exibe rótulos textuais legíveis com percentual e minibarras coloridas com cantos arredondados, preenchidas proporcionalmente ao valor de 0% a 100%

#### Scenario: Cores baseadas em limiares de criticidade
- **WHEN** a métrica está abaixo de 70%
- **THEN** a barra é preenchida na cor verde
- **WHEN** a métrica está entre 70% e 89%
- **THEN** a barra é preenchida na cor laranja ou amarelo
- **WHEN** a métrica atinge ou ultrapassa 90%
- **THEN** a barra é preenchida na cor vermelha

#### Scenario: Dispositivo sem métricas disponíveis
- **WHEN** o dispositivo não suporta SNMP ou ainda não retornou leitura válida
- **THEN** o nó exibe traço indicativo ou barra neutra sem cor de alerta, preservando o layout visual do card
