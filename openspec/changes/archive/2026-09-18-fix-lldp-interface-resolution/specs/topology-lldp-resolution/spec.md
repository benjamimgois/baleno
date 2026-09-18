# Spec Delta

## Purpose

Garante a correta resolução de nomes de interfaces locais a partir do IF-MIB e a reconciliação recíproca de enlaces LLDP para evitar o desenho de portas inexistentes e falsos grupos de agregação (LAG).

## ADDED Requirements

### Requirement: Resolução de nome de interface local via IF-MIB fallback
O sistema SHALL resolver o nome textual da interface local para cada vizinho LLDP, recorrendo às informações da MIB de interfaces (ifName ou ifDescr indexados por ifIndex ou posição física no chassi) caso a consulta a lldpLocPortTable esteja incompleta, inacessível ou retorne apenas identificadores numéricos locais.

#### Scenario: Tradução de porta física para nome textual quando tabela LLDP é parcial
- **WHEN** uma varredura de nomes locais de portas LLDP não contém a porta ou retorna valor puramente numérico
- **THEN** o sistema consulta o inventário de interfaces do dispositivo para preencher o nome canônico da porta em vez de deixar apenas o número de chassi

#### Scenario: Fallback para descrição de porta local
- **WHEN** a tabela lldpLocPortId retorna vazia ou inacessível mas lldpLocPortDesc está disponível
- **THEN** o sistema extrai o nome da interface da descrição local da porta

### Requirement: Normalização abrangente de nomes de portas de alta velocidade
O sistema SHALL normalizar nomes e abreviações de interfaces de 10Gbps e superiores, incluindo variações como XGigabitEthernet e XGE, permitindo correspondência canônica entre descrições completas e compactas.

#### Scenario: Comparação canônica entre XGigabitEthernet e XGE
- **WHEN** duas interfaces são comparadas contendo variações de prefixos XGigabitEthernet ou XGE
- **THEN** o normalizador produz a mesma chave canônica para ambos os lados

### Requirement: Reconciliação e desduplicação de links recíprocos
O sistema SHALL correlacionar conexões LLDP bidirecionais entre o mesmo par de nós para fundir as visões de ambos os lados em uma única conexão física, mesmo quando uma das pontas informou identificador de porta numérico ou incompleto.

#### Scenario: Fusão de link recíproco com identificador local numérico
- **WHEN** o nó A registra uma conexão para o nó B com porta local numérica e porta remota nominal, e o nó B registra uma conexão para o nó A na mesma porta remota
- **THEN** o sistema reconcilia os dois registros em um único enlace físico rotulado com os nomes completos das interfaces em vez de criar conexões duplicadas ou falso LAG
