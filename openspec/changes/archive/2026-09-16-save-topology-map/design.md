# Design: save-topology-map

## Context

Motivação e escopo na proposta (`proposal.md`) e comportamento nas specs (`specs/topology-map-persistence/spec.md`).

Estado atual relevante:

- `cetuslib/topology/persistence.py` só salva **posições** (`save_layout`/`load_layout`), formato `{version: 2, positions, groups}`, filtrado por `graph.devices`. Arquivo em `~/.config/cetus/topology_layout.json`.
- `TopologyView` já tem debounce de 800 ms (`_save_timer` → `save_layout`) disparado **apenas** pelo sinal `moved` de nós/grupos (`view.py:751-754, 776-778, 795-803`).
- Objetos manuais (paleta) vivem só na scene (`node_items`), **não** em `graph.devices` (`view.py:688-694`). Por isso suas posições já são descartadas hoje pelo filtro de `save_layout`.
- Não há **remoção** de objetos nem **edição** de propriedades: `DeviceDetailDialog` é read-only (`detail.py`).
- A aba Topology abre vazia; só há grafo após `Discover` (`tab.py:389`).

## Goals / Non-Goals

**Goals:**

- Persistir e restaurar o mapa completo (grafo + objetos manuais + posições) em JSON, sem nova dependência.
- Auto-load no startup e auto-save em add/remove/move/edit, reusando o debounce existente.
- Manter compatibilidade com o arquivo de layout antigo sem quebrar o export PNG.

**Non-Goals:**

- Persistir dados efêmeros (taxas de tráfego, CPU/memória, vizinhos LLDP, interfaces em tempo real).
- Serializar o resultado de descoberta como fonte viva de monitoramento — o mapa carregado é um instantâneo estático; o monitor de tráfego (`TrafficMonitor`) não re-inicia automaticamente sobre o mapa restaurado.
- Versionamento/histórico de mapas, undo/redo, ou múltiplos mapas nomeados.

## Decisions

### D1: Serialização via `to_dict`/`from_dict` nos dataclasses de `models.py`
Adicionar `Device.to_dict()`/`Device.from_dict()`, `PortLink.to_dict()`/`PortLink.from_dict()` e `TopologyGraph.to_dict()`/`TopologyGraph.from_dict()`. Campos persistidos do `Device`: `id, ip, hostname, role, vendor, model, chassis_id, status, layer`. Excluir `interfaces`, `lldp_neighbors`, `cpu_usage`, `memory_usage`, `in_rate_bps`, `out_rate_bps`, `uptime`, `latency_ms`, `extra` (dados efêmeros/derivados). Alternativa: serializar tudo — descartada: gravaria lixo de runtime e incharia o arquivo.

### D2: Objetos manuais entram no grafo persistido
`TopologyScene.add_manual_device` passa a registrar o `Device` criado em `self.graph.devices` (criando um `TopologyGraph` vazio se `self.graph is None`). `_manual_counter` é persistido indiretamente pelo maior sufixo `manual-N` no load, para não colidir IDs. Alternativa: manter manuais fora do grafo e serializar à parte — descartada: duplicaria caminhos de serialização.

### D3: Novo arquivo `topology_map.json` (formato version 3)
Novas funções em `persistence.py`: `default_map_path()` → `~/.config/cetus/topology_map.json`; `save_map(graph, positions, path, group_positions)`; `load_map(path) -> (TopologyGraph, positions, group_positions)`. Formato:

```json
{
  "version": 3,
  "devices": { "<id>": { ...Device.to_dict()... } },
  "links":   [ { ...PortLink.to_dict()... } ],
  "positions": { "<id>": [x, y] },
  "groups":    { "<parent_id>": [x, y] }
}
```

O arquivo antigo `topology_layout.json` deixa de ser escrito pelo caminho principal; `save_layout`/`load_layout` permanecem para o modo standalone/demo e são mantidos para compatibilidade. Alternativa: estender o formato v2 no mesmo arquivo — descartada: misturar grafo e layout num arquivo com semântica de "só posições" confunde e dificulta migração futura.

### D4: Auto-save unificado no `TopologyView`
Reusar `_save_timer`/`_schedule_save`. `save_layout` vira `save_map` (usa o grafo completo + posições + grupos). Novos gatilhos de `_schedule_save`:
- `add_manual_device` (após adicionar o nó ao grafo).
- remoção de nó (nova ação `remove_node`).
- edição de propriedade (sinal emitido pelo diálogo de detalhe).

`moved` continua como hoje. Alternativa: salvar sincronamente a cada evento — descartada: arrastar emite dezenas de `moved`; debounce já resolve.

### D5: Remoção de objeto
Adicionar `remove_node` no `TopologyScene`/`TopologyView`: remover o `NodeItem`, o `Device` do grafo e links que o tocam, disparar `_schedule_save`. Disparo via tecla `Delete` no `TopologyView` (`keyPressEvent`) com o item selecionado, e item "Remover" no menu de contexto do nó. Alternativa: só tecla Delete — descartada: descoberta é ruim; contexto é o padrão do usuário de rede.

### D6: Edição de propriedades no `DeviceDetailDialog`
A aba "Identity" deixa de ser read-only: `hostname`, `ip`, `role` (combobox), `vendor`, `model`, `status` (combobox), `layer` viram campos editáveis com botão "Apply". Ao aplicar, muta o `Device` e emite um sinal `device_changed` que o `TopologyView` conecta a `_schedule_save`. Alternativa: salvar a cada keystroke — descartada: barulhento e arriscado em campos parciais.

### D7: Auto-load no startup
`TopologyTab.__init__` chama `self.view.load_saved_map()` após `set_layout_path`. `TopologyView.load_saved_map()` lê `load_map(default_map_path())`; se houver dispositivos, popula a scene via um novo `TopologyScene.set_graph_from_persisted(graph, positions, groups)` (equivalente a `set_graph` sem depender de `TopologyEngine` para layout — usa as posições salvas como autoritativas). Sem monitor de tráfego. Se o arquivo não existir/for inválido, não faz nada (aba vazia).

### D8: `TopologyTab` expõe "Save Map"
Na aba Settings, o botão "Save Layout" é renomeado para "Save Map" e passa a chamar `self.view.save_map()` (salva o grafo completo). "Export PNG" inalterado.

## Risks / Trade-offs

- [Posições salvas referenciam IDs que não existem mais no grafo (mapa editado à mão ou corrompido)] → `load_map` descarta posições cujo ID não está em `devices`; `save_map` idem (já é o comportamento atual do filtro).
- [`_manual_counter` reinicia e gera IDs duplicados após recarregar] → no load, derivar o contador do maior `manual-N` presente.
- [Mapa carregado no startup parece "vivo" mas não monitora] → status persistido ('up'/'down'/'unknown') é exibido; documentar que é instantâneo. Sem `TrafficMonitor`.
- [Arquivo maior com muitos dispositivos] → JSON indentado é aceitável; mapa típico é pequeno. Não é problema de escala.
- [Edição de `role` em `Device` pode dessincronizar ícone e paleta] → `DeviceRole` é enum estável; `node.update()` após `Apply` repinta o ícone.
- [Salvar durante `Discover` (graph sendo substituído)] → `clear_scene` antes da descoberta já reseta a scene; salvar o novo grafo ao final via `moved`/add é natural; sem estado intermediário persistido.

## Migration Plan

- Adicionar `to_dict`/`from_dict` e `save_map`/`load_map` sem tocar no formato v2 existente.
- `TopologyTab`/`TopologyView` passam a apontar para `topology_map.json`.
- Primeira execução após a mudança: nenhum `topology_map.json` → aba vazia (comportamento atual preservado). Nenhuma migração de dados necessária.
- Rollback: reverter `default_map_path` para o comportamento antigo; arquivo novo é ignorado. Nada existente muda de comportamento além da aba Topology.
- Deploy: regenerar `dist/cetus` via `python3 scripts/bundle-monolith.py`.

## Open Questions

Nenhuma. Escopo fechado: persistência do instantâneo do mapa, sem monitoramento ao vivo do mapa restaurado.
