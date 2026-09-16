## Context

A cor/estado do link hoje é derivada de `Interface.oper_status` (estado) e `Interface.speed_mbps` (cor), via `EdgeItem.refresh_state()` e `EdgeItem.link_speed()`. O mapa já persiste `PortLink` em `topology_map.json` (`PortLink.to_dict`/`from_dict`). O menu de contexto de nós/grupos já existe (`TopologyScene.node_context_menu_requested`, tratado em `TopologyActions`).

Ver motivação no `proposal.md`.

## Goals / Non-Goals

**Goals:**
- Override manual por link de estado (up/down) e velocidade (presets).
- Prioridade do override sobre a detecção automática.
- Persistência + reload dos overrides.
- Menu de contexto no próprio link (com área de acerto alargada).

**Non-Goals:**
- Não expor override por interface (é por link).
- Não adicionar campo de velocidade livre/arbitrária (só presets + Auto).
- Não invalidar a detecção automática quando o override for removido.

## Decisions

### D1 — Override no `PortLink` (nível de link)
`PortLink` ganha:
- `override_status: Optional[str] = None` (`None`=auto, `'up'`, `'down'`).
- `override_speed: Optional[float] = None` (`None`=auto, Mbps).

`to_dict`/`from_dict` incluem os campos (chaves `override_status`/`override_speed`), preservando a compatibilidade com mapas antigos (ausente → `None`).

- **Alternativa rejeitada**: override em `Interface` → exigiria mapear o lado do link e editar por interface; o pedido é por link.

### D2 — Prioridade no cálculo, não no dado
O monitor continua atualizando `oper_status`/`speed_mbps` normalmente; a prioridade é aplicada no ponto de leitura:
- `refresh_state()`: se `link.override_status == 'down'` → `'down'`; se `'up'` → `'active'`; senão deriva do oper_status.
- `link_speed()`: se `link.override_speed is not None` → retorna override; senão `min` das interfaces.

- **Alternativa rejeitada**: pular a atualização automática quando há override → complexidade desnecessária; ler com prioridade é suficiente.

### D3 — Menu de contexto no EdgeItem
`EdgeItem` vira interativo para clique direito (flag `ItemIsSelectable` não é necessário; só `contextMenuEvent`). Para clicabilidade, `shape()` retorna um `QPainterPathStroker` com pen de ~8px sobre o path, enquanto `paint()` mantém o traço fino. `EdgeItem` emite `context_menu_requested(edge)`; `TopologyScene` re-emite como `edge_context_menu_requested(edge)`.

O menu (Estado / Velocidade com submenu + Auto) é construído e tratado em `TopologyView` (não envolve outros módulos), com checkmark na opção ativa. Após aplicar, chama `edge.refresh_state()`, `edge.update()` e agenda save (`_schedule_save`) para persistir.

### D4 — Marcador visual de override
Quando `override_status` ou `override_speed` não é `None`, `paint()` desenha um pequeno "M" no canto do rótulo do link para indicar ajuste manual.

### D5 — Sem novas dependências
Apenas Qt6 e estruturas existentes.

## Risks / Trade-offs

- **[Override some na re-descoberta]** → Uma nova descoberta reconstrói o grafo do zero e perde overrides (só persistem no arquivo de mapa). Mitigação: documentado; re-descoberta já recria o mapa por design.
- **[Área de acerto alargada pode capturar cliques indesejados]** → shape de ~8px só afeta a seleção/clique do link. Mitigação: pen de acerto razoável e `setZValue` baixo (link atrás dos nós).
- **[Presets podem não cobrir todas as velocidades]** → 10M/100M/1G/10G cobrem o essencial; "Auto" cobre o resto. Mitigação: presets fáceis de estender.

## Migration Plan

Sem migração de dados: mapas antigos sem os campos → `None` (auto). Ao arquivar, a capability `topology-link-override` é copiada para `openspec/specs/`.

## Open Questions

Nenhuma que mude spec/design/tasks.
