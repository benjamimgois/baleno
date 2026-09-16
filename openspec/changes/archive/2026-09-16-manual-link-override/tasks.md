## 1. Modelo — override no PortLink

- [x] 1.1 Adicionar `override_status` e `override_speed` a `PortLink` e incluir em `to_dict`/`from_dict`. Verificar com `python3 -m py_compile cetuslib/topology/models.py`.

## 2. Prioridade do override no EdgeItem

- [x] 2.1 Ajustar `refresh_state()` para respeitar `override_status` (down/up) antes do oper_status. Verificar que um link com interface down vira ativo com override "up".
- [x] 2.2 Ajustar `link_speed()` para retornar `override_speed` quando definido. Verificar que a cor muda conforme o override.

## 3. Menu de contexto no link

- [x] 3.1 Tornar `EdgeItem` clicável (shape alargada) e emitir `context_menu_requested`. Adicionar `edge_context_menu_requested` na `TopologyScene` e conectar. Verificar com `py_compile`.
- [x] 3.2 Construir e tratar o menu (Estado: Auto/Up/Down; Velocidade: Auto/10M/100M/1G/10G) em `TopologyView`, aplicando override + refresh + save. Verificar visualmente no demo.

## 4. Marcador e persistência

- [x] 4.1 Desenhar marcador "M" no rótulo de links com override. Verificar no demo.
- [x] 4.2 Verificar que salvar e recarregar o mapa preserva o override (via `save_map`/`load_map`).

## 5. Validação

- [x] 5.1 Rodar `python3 -m py_compile` em `view.py`, `models.py`, `tab.py`, `demo.py` e `openspec validate manual-link-override`.
