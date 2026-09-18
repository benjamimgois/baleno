# Proposal

## Why

Os operadores e engenheiros de rede precisam visualizar rapidamente o consumo de recursos críticos (CPU e Memória RAM) de cada dispositivo diretamente no mapa de topologia, sem a necessidade de abrir janelas modais ou sessões de terminal. Em ambientes corporativos heterogêneos, a coleta dessas informações depende de OIDs proprietárias de diversos fabricantes. Este recurso provê visibilidade imediata de gargalos de desempenho com baixo consumo de banda e CPU, operando em cadência de 120 segundos e com cache de OIDs por dispositivo.

## What Changes

- **Visualização de Minibarras nos Nós (`NodeItem`)**:
  - Exibição de duas minibarras compactas logo abaixo da marca e modelo do dispositivo (CPU e Memória).
  - Rótulos textuais com porcentagem (`CPU 38%`, `MEM 74%`) ou traço (`—`) quando indisponível.
  - Coloração dinâmica baseada em limiares: Verde (<70%), Laranja/Amarelo (70%-89%) e Vermelho crítico (≥90%).
  - Repintura suave via `node.update()` quando novas métricas chegarem da thread de monitoramento.
- **Suporte Multivendor com Priorização de OIDs**:
  - Suporte nativo a 8 famílias de fabricantes na ordem de prioridade definida:
    1. **Huawei** (hwEntityCpuUsage / hwEntityMemUsage)
    2. **HP** (H3C/Comware & ProCurve)
    3. **Aruba** (AOS-S & AOS-CX)
    4. **Cisco** (cpmCPUTotal5minRev / avgBusy5 & ciscoMemoryPool)
    5. **TP-Link** (tpSysMonitorCpuUtilization & tpSysMonitorMemoryUtilization)
    6. **Juniper** (jnxOperatingCPU & jnxOperatingBuffer)
    7. **MikroTik** (mtxrProcessorLoad & hrStorage)
    8. **Linux / Genérico** (hrProcessorLoad, UCD-SNMP ssCpuIdle & memTotalReal / hrStorage)
  - Priorização pelo vendor detectado na descoberta, se disponível.
- **Cache de OIDs Funcionais por Dispositivo**:
  - Armazenamento das OIDs de CPU e memória que responderam com sucesso para cada dispositivo, evitando buscas repetitivas em todos os ciclos.
  - Invalidação e re-descoberta automática caso a OID em cache falhe por 2 ciclos consecutivos.
- **Ajuste de Cadência de Polling de Performance**:
  - Alteração da cadência de coleta de métricas de performance (`perf_interval`) para 120 segundos (2 minutos), reduzindo a carga em dispositivos de rede e enlaces.
  - Disparo da primeira consulta imediatamente no início do monitoramento (tempo inicial 0.0s).

## Capabilities

### Modified Capabilities
- `topology-live-monitoring`: Atualiza a cadência de coleta de métricas de performance para 120 segundos, expande o suporte de coleta de CPU e memória para múltiplos fabricantes com mecanismo de cache de OID funcional, e introduz os requisitos de exibição visual das minibarras de recursos no nó da topologia.

## Impact

- `balenolib/topology/collector.py`: Implementação da resolução em cascata de OIDs multivendor e retorno estruturado de CPU e Memória em `_read_cpu_mem` e `poll_cpu_mem_async`.
- `balenolib/topology/monitor.py`: Adição do cache de OIDs por dispositivo (`_working_oids`), ajuste do default de `perf_interval` para 120.0s, e despacho reativo de métricas.
- `balenolib/topology/tab.py`: Garantia do parâmetro `perf_interval=120.0` no início do monitor.
- `balenolib/topology/gui/view.py`: Renderização das minibarras e rótulos em `NodeItem.paint()` e invalidação de cache de desenho em `TopologyView.update_traffic()`.
- Sem quebra de compatibilidade com versões anteriores ou formatos de arquivo de mapa.
