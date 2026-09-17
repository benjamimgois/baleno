## 1. Layouts no engine

- [x] 1.1 Adicionar `TopologyEngine.layout_concentric(g, clusters)` retornando `(node_pos, group_pos)` com centro via `_pick_roots` e anéis por nível de hop; verificar com `python3 -m py_compile cetuslib/topology/engine.py`
- [x] 1.2 Adicionar `TopologyEngine.layout_bfs_tree(g, clusters)` reutilizando `_layout_by_bfs` e derivando `group_pos` por média dos membros; verificar com `python3 -m py_compile cetuslib/topology/engine.py`
- [x] 1.3 Adicionar registro `LAYOUTS` no engine mapeando `hierarchical`, `force`, `concentric`, `bfs` às funções; verificar que todas as chaves resolvem para callable

## 2. Dispatch no view

- [x] 2.1 Refatorar `TopologyScene._apply_layout` para consultar `LAYOUTS` em vez do `if layout_mode == 'force'`, mantendo a derivação de `group_pos` para layouts que não o devolvem; verificar com `python3 -m py_compile cetuslib/topology/gui/view.py`
- [x] 2.2 Garantir que trocar para `concentric` e `bfs` via `switch_layout` reenquadra o mapa sem erro; verificar manualmente com `python3 -m cetuslib.topology` (demo) e alternar os 4 modos

## 3. Fileira de botões-ícone

- [x] 3.1 Criar `LayoutButton(QToolButton)` (checkable, molde de `DevicePaletteButton`) com `paintEvent` desenhando ícone + rótulo; verificar compilação
- [x] 3.2 Adicionar `draw_layout_icon(painter, mode, rect)` com desenhos distintos para tree, force, concentric e bfs; verificar renderização sem crash
- [x] 3.3 Em `tab.py`, substituir o `QComboBox` de layout por um `QButtonGroup` de `LayoutButton` ligando `buttonClicked` → `view.switch_layout(mode)`, removendo `_on_layout_changed`; verificar com `python3 -m py_compile cetuslib/topology/tab.py`

## 4. Verificação final

- [x] 4.1 Rodar `python3 -m py_compile` em todos os arquivos alterados e regenerar `dist/cetus` com `python3 scripts/bundle-monolith.py`
- [x] 4.2 Validar a change com `openspec validate add-layout-modes` e conferir que os 4 modos aparecem como ícones e reorganizam o mapa na demo
