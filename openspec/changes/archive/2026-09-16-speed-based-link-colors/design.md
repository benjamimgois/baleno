## Context

O mapa de topologia já coloria links por estado (verde tracejado = up, vermelho sólido = down), decisão da change `2026-09-16-animate-topology-links`. A velocidade já é coletada no discovery via `ifHighSpeed` em `Interface.speed_mbps` (`collector.py:439`), mas nunca é re-verificada nem usada para cor.

Ver motivação no `proposal.md`.

## Goals / Non-Goals

**Goals:**
- Cor de link ativo = f(velocidade); estilo continua = f(estado) (tracejado animado up, sólido vermelho down).
- Velocidade re-verificada a cada minuto (mesma cadência do oper_status).
- Velocidade do link = `min` das duas pontas.
- Legenda compacta de cores no canvas.

**Non-Goals:**
- Não mudar a semântica de down (vermelho sólido vence a velocidade).
- Não detectar mismatch de velocidade como defeito distinto (fora de escopo; só `min`).
- Não usar tráfego para cor.

## Decisions

### D1 — Mapa de velocidade → cor (limiares)
```
speed_mbps >= 10000          → verde     (UP,     QColor(63, 185, 80))
1000 <= speed_mbps < 10000   → azul claro(ACCENT, QColor(88, 166, 255))
0 < speed_mbps < 1000        → laranja   (novo QColor laranja, ex. (230, 126, 34))
speed_mbps <= 0              → cinza     (EDGE,   QColor(139, 148, 158))
```
Helper `speed_color(mbps) -> QColor` em `view.py`.

- **Alternativa rejeitada**: cores próprias para 2.5G/5G/25G/40G/100G → muitas categorias, pouco ganho; limiares agrupam de forma legível.

### D2 — Velocidade do link = min das duas pontas
`EdgeItem.link_speed()` = `min(source_interface().speed_mbps, target_interface().speed_mbps)`. Se uma interface não resolve, usa a outra; se ambas falham, 0 (cinza).

- **Alternativa rejeitada**: só a origem → esconde o gargalo real do enlace.

### D3 — Cor só quando up; down continua vermelho
`EdgeItem._pen()`: se `state == 'down'` → vermelho sólido; senão → `speed_color(link_speed())` tracejado animado. Estilo (tracejado animado) continua sendo o sinal de "vivo".

### D4 — Re-verificação de velocidade a cada minuto
Estender o bloco de 1/min já existente no `TrafficMonitor` (`_refresh_statuses_if_due`):
- `LldpCollector.poll_speed(host) -> {ifIndex: mbps}` (walk de `ifHighSpeed`; fallback `ifSpeed` bps/1e6 quando `ifHighSpeed` vazio).
- `TrafficMonitor` emite `speed_updated = {device_id: {ifIndex: mbps}}` na mesma cadência de 60s.
- `TopologyView.update_speeds()` aplica em `Interface.speed_mbps` e chama `refresh_state()` + `update()`.
- `tab.py` conecta `speed_updated` → `update_speeds`.

- **Alternativa rejeitada**: ler velocidade a cada poll de 5s → desnecessário; velocidade muda raramente.

### D5 — Legenda compacta
Um pequeno widget/overlay no `TopologyView` (ex. canto inferior esquerdo) listando: verde = 10G+, azul = 1G, laranja ≤ 1G, cinza = desconhecido, vermelho = down, tracejado = up. Reutiliza a paleta existente.

## Risks / Trade-offs

- **[Velocidade desconhecida vira cinza]** → Agentes sem ifXTable/ifSpeed deixam link cinza (não laranja). Mitigação: cinza = "desconhecido", evita falso alarme de gargalo.
- **[Mismatch de velocidade não sinalizado]** → Duas pontas diferentes resultam na cor da mais lenta, sem alertar o mismatch em si. Mitigação: `min` é o comportamento documentado; mismatch pode virar feature futura.
- **[Latência de até 1 min]** → Mudança de velocidade só reflete no próximo ciclo. Mitigação: aceitável; mesma cadência do oper_status.

## Migration Plan

Sem migração de dados. A change modifica a capability `topology-link-visualization`; o delta é mesclado no spec principal ao arquivar.

## Open Questions

Nenhuma que mude spec/design/tasks.
