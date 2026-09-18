# Design

## Context

Atualmente o monitoramento de topologia (`TrafficMonitor` em `balenolib/topology/monitor.py`) roda em uma thread dedicada separada da interface do usuário. Contadores de tráfego de interface são coletados a cada 5 segundos (`interval = 5.0`), enquanto métricas de performance (`_refresh_perf`) rodam em cadência desacoplada (`perf_interval`).

No estado atual:
1. `collector.py` (`_read_cpu_mem`) apenas implementa queries para Cisco e Host Resources (RFC 2790). Ambientes com equipamentos Huawei, HP, Aruba, TP-Link, Juniper e MikroTik ficam sem métricas de uso de CPU e memória.
2. `NodeItem` (`balenolib/topology/gui/view.py`) renderiza o card do dispositivo com ícone, marca, modelo e badge de saltos, mas não exibe barras de recursos graficamente. As métricas de CPU/Memória só são visíveis se o usuário passar o mouse para abrir o tooltip.
3. A cadência de performance está definida em 60s, necessitando ajuste para 120s conforme requisito operacional.

## Goals / Non-Goals

**Goals:**
- Implementar cascata de OIDs multivendor em `balenolib/topology/collector.py` com suporte aos 8 fabricantes na ordem de prioridade: Huawei, HP, Aruba, Cisco, TP-Link, Juniper, MikroTik e Linux/Host-Resources.
- Implementar cache de OIDs funcionais por dispositivo (`working_oids`) em `balenolib/topology/collector.py` / `monitor.py`, reduzindo a carga para 1-2 requisições diretas em estado de regime.
- Invalidação automática de cache após 2 falhas consecutivas para resiliência contra reinicializações ou mudanças de firmware.
- Configurar cadência de 120 segundos (`perf_interval = 120.0s`) com primeira consulta disparada imediatamente (`t = 0.0s`).
- Renderizar no card `NodeItem` duas minibarras arredondadas com rótulos `CPU XX%` e `MEM XX%`, coloração dinâmica (<70% verde, 70-89% amarelo/laranja, ≥90% vermelho) e fallback discreto (`—`) para nós sem dados.
- Conectar a atualização de tráfego com `node.update()` para redesenho reativo sem flickering.

**Non-Goals:**
- Armazenamento de histórico de séries temporais ou gráficos em linha de evolução ao longo do tempo (as minibarras representam o ponto atual).
- Disparo de alarmes ou notificações em pop-up de desktop por uso excessivo de recursos.

## Decisions

### Decisão 1: Cache de OID por dispositivo (`working_oids`)
- **Escolha**: Armazenar o par `(cpu_oid, mem_oid)` funcional por `device_id` no coletor/monitor.
- **Racional**: Uma varredura cega por 8 fabricantes geraria até 16 consultas SNMP por nó a cada ciclo. Em uma rede com 50 dispositivos, seriam centenas de pacotes UDP adicionais e atrasos acumulados. Com o cache, após o primeiro ciclo cada dispositivo requer apenas 2 GETs diretos.
- **Alternativas consideradas**:
  - *Varredura completa a cada ciclo*: Descartada por alto consumo de banda e aumento desnecessário do tempo de coleta.
  - *Configuração manual do fabricante pelo usuário*: Descartada por quebrar a facilidade de uso do descobrimento automático da topologia.

### Decisão 2: Resolução guiada pelo Vendor do Dispositivo
- **Escolha**: Se o dispositivo já tiver `vendor` detectado durante a descoberta LLDP/SysDescr (ex: "Huawei" ou "Cisco"), o coletor testa as OIDs desse fabricante antes de percorrer a lista padrão de prioridades.
- **Racional**: Agiliza a convergência no primeiro ciclo (`t = 0`), diminuindo o tempo de resposta da primeira renderização das barras.

### Decisão 3: Integração visual dentro do espaço existente do card
- **Escolha**: Posicionar as duas barras na região vertical entre `y = 56px` e `y = 80px` (logo abaixo do nome do modelo e acima do rodapé), mantendo as dimensões atuais do card (`130px × 95px`).
- **Dimensões das barras**: Largura `44px`, altura `4px`, cantos com raio de curvatura `2px`.
- **Racional**: Não altera o bounding box do nó nem a geometria de conexões de links já salvas em mapas existentes.

### Decisão 4: Mecanismo de invalidação de renderização (`node.update()`)
- **Escolha**: No método `TopologyView.update_traffic()`, ao aplicar os novos valores de `cpu_usage` e `memory_usage`, invocar `node.update()`.
- **Racional**: Invalida a região do nó no `QGraphicsScene`, disparando uma chamada a `NodeItem.paint()` de forma eficiente e gerenciada pelo motor gráfico do Qt, sem sobrecarregar o loop principal.

## Risks / Trade-offs

- **[Risco] Dispositivos com SNMP sem permissão para OIDs corporativas (ex: apenas MIB-II pública disponível)**
  → *Mitigação*: A cascata termina com fallback para Host-Resources (`hrProcessorLoad`, `hrStorage`) e UCD-SNMP. Se nenhuma responder, `cpu_usage` e `memory_usage` permanecem `None` e o nó renderiza `CPU —` / `MEM —` sem quebrar o layout.

- **[Risco] Dispositivos modulares com múltiplas CPUs/slots (ex: switches chassis Huawei ou Cisco com múltiplos boards)**
  → *Mitigação*: A rotina de parsing extrai a média ponderada ou o valor do processador principal (Board/Routing Engine principal), descartando índices secundários que reportem 0% ou valor de standby.

- **[Risco] Impacto de performance gráfica com muitas barras visíveis**
  → *Mitigação*: As barras são desenhadas utilizando operações simples e otimizadas de `QPainter` (`drawRoundedRect`) sem gradientes complexos ou sombras pesadas, aproveitando o cache de coordenadas do nó.
