# Design: add-layout-modes

## Context

Hoje a escolha de layout é um `QComboBox` com dois itens (`tab.py:286-291`) e o dispatch é um `if layout_mode == 'force'` dentro de `TopologyScene._apply_layout` (`view.py:776-811`). Cada layout é uma função do `TopologyEngine` que retorna `(node_pos, group_pos)` — `layout_tree` (`engine.py:305`) e `layout_force` (`engine.py:452`). Já existe um `_layout_by_bfs` (`engine.py:414`) usado como fallback interno, e `_pick_roots` (`engine.py:512`) para escolher raiz/núcleo.

Constraints relevantes:
- Todo layout novo precisa tratar `clusters` (grupos colapsados) devolvendo `group_pos`, senão o círculo "N devices" quebra.
- Órfãos (ICMP-only, sem nível de hop) precisam de posição em qualquer modo.
- O padrão de botão-ícone já existe: `DevicePaletteButton` (`tab.py:122`), um `QToolButton` com `paintEvent` custom.

## Goals / Non-Goals

**Goals:**
- Adicionar os modos `concentric` e `bfs` e uniformizar os 4 modos num registro.
- Trocar o combo por fileira de botões-ícone com ícones desenhados em código.

**Non-Goals:**
- Persistência do modo de layout (fica fora desta iteração, conforme decisão do usuário).
- Estilo de arestas (ortogonal/esquemático) — só posição de nós.
- Remover ou alterar o comportamento dos modos `hierarchical`/`force` existentes.

## Decisions

### 1. Registro de layouts no engine

Substituir o `if/else` de `_apply_layout` por um dicionário de fábricas:

```python
LAYOUTS = {
    'hierarchical': TopologyEngine.layout_tree,
    'force':        TopologyEngine.layout_force,
    'concentric':   TopologyEngine.layout_concentric,
    'bfs':          TopologyEngine.layout_bfs_tree,
}
```

- **Alternativa considerada**: manter `if/elif` encadeado. Rejeitada — o registro evita tocar o dispatch a cada modo novo e mantém um só lugar para a lista de modos.
- O dispatch de `_apply_layout` chama a função registrada e, quando ela não devolve `group_pos`, deriva por média dos membros (mesma lógica já usada no ramo `force`, `view.py:785-797`).

### 2. Layout concêntrico (`layout_concentric`)

- Centro = raízes de `_pick_roots` (core/router; senão nó de maior grau). Múltiplas raízes ficam agrupadas no centro num pequeno arco.
- Raio do anel = `nivel_hop * SPACING` (reusa `SPACING = 180`). Nós do mesmo nível são distribuídos uniformemente por ângulo, ordenados por `label` para estabilidade.
- Órfãos/nós sem nível usam nível = máximo+1 (anel mais externo).
- Grupos colapsados: derivados por média dos membros (mesmo padrão do force), não como slots dedicados.
- **Alternativa considerada**: raio constante único ("anel puro"). Rejeitada — achata redes multi-nível; o concêntrico generaliza estrela+anel.

### 3. Layout BFS (`layout_bfs_tree`)

- Reaproveita o `_layout_by_bfs` existente, mas exposto como modo `bfs` com assinatura `(g, clusters) → (pos, group_pos)`.
- `_layout_by_bfs` hoje devolve só `pos`; adicionar derivação de `group_pos` por média dos membros (ou slot na camada do grupo).
- **Alternativa considerada**: novo algoritmo próprio. Rejeitada — o BFS já existe e funciona; expor com o mínimo de código.

### 4. Fileira de botões-ícone

- Nova classe `LayoutButton(QToolButton)` (no molde de `DevicePaletteButton`): `setCheckable(True)`, `paintEvent` desenha ícone + rótulo curto, agrupados num `QButtonGroup` exclusivo.
- Remove o `QComboBox` e `_on_layout_changed`; o grupo conecta `buttonClicked` → `view.switch_layout(mode)`.
- Os 4 modos com rótulos: Tree, Force, Concentric, BFS.

### 5. Ícones programáticos

- Função `draw_layout_icon(painter, mode, rect)` em `view.py`, no estilo do `draw_device_icon` existente. Desenhos simples (nós como círculos, arestas como linhas):
  - **Tree**: nós em pirâmide com arestas pai→filho.
  - **Force**: nós dispersos com arestas formando malha.
  - **Concentric**: círculos concêntricos com um nó central.
  - **BFS**: camadas horizontais de nós.
- **Alternativa considerada**: SVGs em `assets/icons/`. Rejeitada — zero assets, nítido em qualquer escala e tematizável (decisão do usuário).

## Risks / Trade-offs

- **[Órfãos sem nível]** → risco de posicionamento estranho no concêntrico; mitigação: nível = máximo+1 no anel externo.
- **[Muitos nós num anel]** → concêntrico pode sobrepor rótulos em níveis populosos; mitigação: espaçamento por ângulo usa `SPACING`, e o usuário ainda pode arrastar manualmente (comportamento atual preservado).
- **[Grupos colapsados]** → média dos membros pode coincidir com outro nó; mitigação: mesma heurística já aceita no `force`, sem regressão.
- **[networkx opcional]** → BFS/concentric são puramente sobre `graph.links` (sem `networkx`), então não dependem de `HAS_NETWORKX`.
- **[Sem persistência]** → ao trocar de aba/reiniciar, o modo volta ao padrão (`hierarchical`); aceito nesta iteração.
