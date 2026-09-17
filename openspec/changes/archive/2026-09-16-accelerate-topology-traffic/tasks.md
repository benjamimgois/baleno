# Tasks: accelerate-topology-traffic

## 1. Collector — caminho leve de contadores (objetivo B)

- [x] 1.1 Adicionar `LldpCollector.poll_counters_async(engine, auth, target) -> dict[int, list[int]]` que lê somente `ifHCInOctets`/`ifHCOutOctets` (fallback 32-bit), reusando a lógica de `_read_counters` (`collector.py:493`). Verificar com `python3 -m py_compile cetuslib/topology/collector.py`.
- [x] 1.2 Refatorar `_read_counters` para ser chamável com engine/transport externos (sem criar engine própria), mantendo `collect()` intacto. Verificar que a discovery continua passando em `python3 -m py_compile` e num run manual contra 1 host.

## 2. Monitor — setup único de sessões (objetivo C)

- [x] 2.1 Criar estrutura de sessão por dispositivo (`{device_id: (engine, target, auth)}`) no início de `run()`, com `SnmpEngine()` + `UdpTransportTarget.create()` (timeout reduzido 1 s, retries 1) + auth, reutilizada a cada ciclo; `close_dispatcher()` em `stop()`. Verificar com `python3 -m py_compile cetuslib/topology/monitor.py`.
- [x] 2.2 Resolver a comunidade SNMP de cada dispositivo uma única vez no setup (probe `get` de `OID_LOC_CHASSIS_ID` na ordem de `_ordered_communities`), gravando a vencedora via `config.set_snmp_ip_community`; dispositivo sem comunidade válida marcado `unreachable` para retry só no próximo `status_interval`. Verificar com teste manual contra 2–3 hosts v2c com comunidades diferentes.

## 3. Monitor — loop asyncio concorrente (objetivo A)

- [x] 3.1 Reescrever `run()` para um loop `asyncio` único: por ciclo, `asyncio.gather` de `poll_counters_async` sobre todas as sessões (com `asyncio.Semaphore` limitando concorrência, default 16), respeitando `self._stop` entre ondas. Verificar com `python3 -m py_compile cetuslib/topology/monitor.py`.
- [x] 3.2 Mover `_apply` (deltas + emissão de `updated`) para o fim do ciclo, com um único `now`; preservar os shapes de payload atuais. Verificar com execução contra uma topologia real e conferência do rótulo de Mbps nas linhas.

## 4. Monitor — cadência CPU/memória e status/speed

- [x] 4.1 Coletar CPU/memória (`_read_cpu_mem`) apenas a cada `perf_interval` (default 60 s), reusando os mesmos engines, e emitir via `updated` (mesclando cpu/mem com os contadores do ciclo). Verificar que o tooltip de CPU/Mem atualiza a cada ~60 s.
- [x] 4.2 Manter status/speed a cada `status_interval` (60 s) no mesmo loop asyncio (reusando engines), emitindo `status_updated`/`speed_updated` como hoje. Verificar que queda/retorno de interface ainda reflete no mapa dentro de ~1 min.

## 5. Limpeza e validação final

- [x] 5.1 Remover (ou marcar obsoletos) os wrappers síncronos `poll`/`poll_status`/`poll_speed` se nenhum outro chamador restar; garantir que `collect()` da discovery segue intacto. Verificar com `python3 -m py_compile cetuslib/topology/*.py`.
- [x] 5.2 Regressão: `python3 -m py_compile cetuslib/topology/monitor.py cetuslib/topology/collector.py`, regenerar `dist/cetus` (`python3 scripts/bundle-monolith.py`), executar `./cetus`, descobrir uma rede e observar que o tráfego em Mbps aparece nas linhas no 2º ciclo (≈10 s) independentemente do número de dispositivos.
