# Design: accelerate-topology-traffic

## Context

O `TrafficMonitor` (`cetuslib/topology/monitor.py`) é um `QThread` que, em `run()`, itera `for device in self.devices` chamando `_poll_device()` → `LldpCollector(creds).poll(ip)` (`collector.py:208`), que por sua vez faz `asyncio.run(poll_async(host))`. Cada `poll_async` cria um `SnmpEngine()` novo, lê CPU/memória (até 4 walks) e só depois os contadores (2–4 walks), com `timeout=2.0, retries=1` (`collector.py:195`). O resultado é um custo de setup (event loop + engine) e 4 walks irrelevantes pagos N vezes por ciclo, sequencialmente.

A discovery (`worker.py:79`) já usa `concurrent.futures.ThreadPoolExecutor(max_workers=8)`, provando que a concorrência é o padrão esperado. O backend `pysnmp.hlapi.v3arch.asyncio` já é usado em todo o `collector.py` — engine e transport são projetados para uso de longa duração num único event loop.

## Goals / Non-Goals

**Goals:**

- Latência do rótulo de tráfego (Mbps) deixa de escalar linearmente com o número de dispositivos.
- Coleta de contadores não é mais atrasada pelos walks de CPU/memória.
- Eliminar o custo de criar/destruir `SnmpEngine` e event loop a cada coleta.
- Mesmos sinais e payloads para a UI (`updated`, `status_updated`, `speed_updated`) — nenhuma mudança no `view.py`.

**Non-Goals:**

- Exibir taxa no 1º ciclo (warm-up de duas amostras permanece; ver Open Questions).
- Mudar a cadência de status/speed (ifOperStatus/ifHighSpeed) de 60 s.
- Substituir SNMP por outra telemetria (gNMI, streaming, NetFlow).
- Alterar a renderização visual das linhas.

## Decisions

### D1: Concorrência via asyncio nativo, não threads

O monitor passa a manter um único event loop `asyncio` no seu thread e, por ciclo, executa `asyncio.gather` sobre as coletas de todos os dispositivos. Justificativa: o backend já é `v3arch.asyncio`, o custo é I/O-bound (UDP), e isso elimina overhead de threads e permite reuso natural de engine/transport. Alternativa considerada: `ThreadPoolExecutor` como na discovery — descartada porque manteria o custo de `asyncio.run()` + engine nova por call (falharia no objetivo C) e introduziria o problema de engine por thread.

Limite de concorrência: um `asyncio.Semaphore` (ex.: 16) evita rajadas de UDP contra subredes grandes; acima do limite, as coletas são escalonadas em ondas.

### D2: Reuso de engine e transport por dispositivo (objetivo C)

No setup, para cada dispositivo com `status == 'up'` e `ip` válido, criar uma vez:

- um `SnmpEngine()`,
- um `UdpTransportTarget.create(...)` com `timeout`/`retries` fixos (reduzidos — ver D4),
- o objeto de auth (`CommunityData`/`UsmUserData`).

Esses três ficam num dict `{device_id: Session}` reutilizado a cada ciclo; `close_dispatcher()`/fechamento acontece apenas em `stop()`. Isso é o uso pretendido da API asyncio do pysnmp (engine de longa duração). Riscos mitigados em "Risks".

### D3: Desacoplamento contadores × CPU/memória (objetivo B)

Novo `LldpCollector.poll_counters_async(engine, auth, target)` que lê **somente** `OID_IF_HC_IN_OCTETS`/`OID_IF_HC_OUT_OCTETS` (fallback 32-bit), devolvendo `{ifIndex: [in, out]}` — reusando a lógica de `_read_counters` (`collector.py:493`) mas como método público.

Cadências:
- **contadores**: a cada `interval` (5 s), via `gather` de `poll_counters_async`.
- **CPU/memória**: a cada `perf_interval` (novo parâmetro, default 60 s), reusando `_read_cpu_mem` nos mesmos engines — fora do caminho do Mbps.
- **status/speed** (ifOperStatus/ifHighSpeed): mantidos a cada `status_interval` (60 s), também no loop asyncio, reusando os mesmos engines.

O tooltip de CPU/Mem passa a atualizar a cada 60 s (antes era a cada 5 s). Trade-off aceito: são métricas lentas; a responsividade do tráfego é o objetivo.

### D4: Resolução de comunidade uma única vez (no setup)

Hoje `_poll_device` tenta `_ordered_communities()` a cada ciclo (`monitor.py:142-152`), pagando timeout por comunidade errada repetidamente. No setup, para v2c, resolve-se a comunidade de cada dispositivo uma vez (probe `get` de `OID_LOC_CHASSIS_ID` na ordem de `_ordered_communities`), grava-se em `ConfigManager` (`set_snmp_ip_community`) e usa-se apenas a vencedora daí em diante. Dispositivos já descobertos via SNMP já têm a comunidade lembrada — o probe costuma acertar de primeira. Dispositivo sem comunidade válida: marcado `unreachable`, re-tentado só no próximo `status_interval` (evita pagar timeout todo ciclo).

### D5: `_apply` inalterado, um único `now` por ciclo

A computação de taxas (deltas entre duas amostras) permanece como está (`monitor.py:159-190`): usa um único `now = time.monotonic()` no fim do ciclo. Como `gather` amostra todos os dispositivos no mesmo instante lógico, `dt` fica consistente. Primeiro ciclo continua sendo baseline (sem taxa) — ver Open Questions.

### D6: Novas assinaturas em `collector.py` sem quebrar a discovery

`collect()` (usado pela discovery) e seus helpers permanecem intocados. Adicionam-se métodos async que recebem `engine, auth, target` como parâmetros (`poll_counters_async`), em vez de recriá-los. Os wrappers síncronos `poll`/`poll_status`/`poll_speed` deixam de ser chamados pelo monitor; mantidos ou removidos conforme varredura de uso (só o monitor os usava hoje).

### D7: Sinais preservados

`updated`, `status_updated`, `speed_updated` continuam emitindo os mesmos shapes (`{device_id: {...}}`). A única diferença observável na UI é a latência e a cadência do CPU/Mem no tooltip.

## Risks / Trade-offs

- [Engine reutilizada atravessa falha de walk — dispatcher entra em estado inconsistente após timeout] → `walk_cmd` com erro/timeout não corrompe o engine na API asyncio (o estado é descartado por chamada); em caso de exceção, logar e seguir. Se um device ficar persistentemente inalcançável, ele é rebaixado para retry no próximo `status_interval` (D4), não a cada ciclo.
- [`UdpTransportTarget.create()` mantém socket UDP aberto por dispositivo] → 250 dispositivos ≈ 250 sockets, aceitável; `close_dispatcher()` + fechamento do transport em `stop()` garantem liberação no encerramento.
- [Concorrência total vs. rajada UDP] → `asyncio.Semaphore` (D1) limita; padrão 16 é conservador.
- [Timeout/retries fixos no transport reutilizado] → usar timeout reduzido (D2/D4) de 1 s com 1 retry no caminho de contadores; se um device demorar, o `gather` espera `max(timeout)` e não `sum` — ganho mesmo no pior caso.
- [Config write no setup, não no caminho quente] → `set_snmp_ip_community` só no setup, resolvendo a thread-safety herdada (hoje é chamado dentro do loop do monitor).
- [Mudança de cadência de CPU/Mem no tooltip pode ser percebida como regressão] → métricas lentas; documentar no README se necessário.

## Migration Plan

Sem migração de dados. Deploy = reescrever `monitor.py`, adicionar `poll_counters_async` em `collector.py`, `python3 -m py_compile` nos dois e regenerar `dist/cetus`. Rollback = reverter os dois arquivos — a UI (`tab.py`/`view.py`) não muda.

## Open Questions

- **Warm-up de duas amostras**: manter o rótulo vazio no 1º ciclo, ou exibir "0 Mbps"/"—" até a 2ª amostra? Fora do escopo A/B/C; decidir separadamente.
- **`perf_interval` configurável via `ConfigManager`** ou constante? Sugestão: constante 60 s na v1, chave de config depois.
- **Valor do `MAX_CONCURRENT`** (semáforo): 16 proposto; calibrar com redes reais grandes.
