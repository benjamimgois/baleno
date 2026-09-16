## Context

O mapa de topologia é renderizado por `TopologyScene` / `TopologyView` (`cetuslib/topology/gui/view.py`). Cada link vira um `EdgeItem` (subclasse de `QGraphicsPathItem`), cujo estilo hoje depende apenas do nível hierárquico dos nós.

Os dados já existem:
- `Interface.oper_status` — `'up' | 'down' | 'unknown'`, preenchido no discovery (`collector.py:394`).
- `PortLink` guarda `source_ifindex` (resolve interface de origem); o lado de destino só tem `target_port` (nome), sem ifindex.

Ver motivação no `proposal.md`.

## Goals / Non-Goals

**Goals:**
- Dois estados visuais de link, derivados só do `oper_status`: ativo (tracejado animado), offline (sólido vermelho).
- Uma fonte única de animação (um `QTimer`) para não multiplicar timers por edge.
- `oper_status` atualizado a cada minuto para refletir quedas/recuperações sem re-descoberta.

**Non-Goals:**
- Não usar tráfego para decidir estado (pedido explícito do usuário).
- Não mudar o esquema de cores dos nós nem a persistência do mapa.

## Decisions

### D1 — Animação por `QPen.setDashPattern` + `setDashOffset`, com um timer compartilhado
`EdgeItem` ativo usa `QPen` tracejado (ex. `[6, 4]`). Um único `QTimer` (~40ms) na `TopologyView` incrementa uma fase global e, a cada tick, faz `edge._dash_offset = fase` + `edge.update()` apenas nas edges ativas.

- **Alternativa rejeitada**: um `QTimer` por edge → N timers, custo de scheduling e cleanup.

### D2 — Máquina de estados de dois níveis por link
```
offline = oper_status('down') em qualquer lado
ativo   = caso contrário (up, unknown ou interface não resolvida)
```
- `offline` → `QPen` sólido, cor `DOWN` (vermelho, `view.py:50`).
- `ativo` → `QPen` tracejado animado, cor `UP` (verde).

Tráfego é deliberadamente ignorado (requisito "Estado do link independe de tráfego").

### D3 — Resolução da interface de destino por nome
Para checar down nos dois lados, o lado de destino é resolvido por `normalize_port(target_port)` contra `device.interfaces` (mesmo mecanismo de `EdgeItem.source_interface()`). Se não resolver, o lado é tratado como "up" (não força offline).

### D4 — Re-verificação de oper_status a cada minuto
`TrafficMonitor` mantém um `status_interval` (60 s). A cada ciclo, se o tempo desde a última verificação de status exceder o intervalo, ele percorre os devices e chama `LldpCollector.poll_status(host)` (walk leve de `OID_IF_OPER_STATUS`), emitindo `status_updated = {device_id: {ifIndex: status}}`. A view aplica em `Interface.oper_status` e chama `refresh_state()`.

- **Alternativa rejeitada**: re-ler ifOperStatus a cada poll de 5s → walk extra desnecessário; 1/min é suficiente para a latência do mapa.
- **Alternativa rejeitada**: re-descoberta completa → pesada (LLDP + IF-MIB inteiro).

### D5 — Sem novas dependências
Apenas Qt6 (`QPen.setDashPattern`, `setDashOffset`) e estruturas já existentes. Nenhum pacote externo novo.

## Risks / Trade-offs

- **[Latência de até 1 min]** → Uma interface que cai pode levar até `status_interval` para refletir no mapa. Mitigação: 60 s é aceitável para um mapa de topologia; ajustável via `status_interval`.
- **[Interface não resolvida vira ativo]** → Link cujo `target_port` não bate com nenhuma interface não será marcado offline. Mitigação: `normalize_port` normaliza aliases; falha → tratado como "up" (sem falso vermelho).
- **[Perf da animação]** → Um tick por frame re-desenha apenas edges ativas. Para dezenas/centenas de links é barato.

## Migration Plan

Sem migração de dados. Mudança é só de renderização. Ao arquivar, a capability `topology-link-visualization` é copiada para `openspec/specs/`.

## Open Questions

Nenhuma que mude spec/design/tasks.
