# Proposal: add-layout-modes

## Why

O mapa de topologia só oferece dois arranjos de nós (árvore hierárquica e force-directed) escondidos num `QComboBox` pouco descobrível. Engenheiros de rede frequentemente querem outras leituras do mesmo grafo — ver a *profundidade* em relação ao núcleo ou a *largura* da descoberta — e um seletor textual não comunica o efeito de cada opção. Adicionar modos de layout com botões-ícone autoexplicativos melhora a exploração sem alterar a topologia em si.

## What Changes

- Dois novos algoritmos de layout de nós:
  - **Concentric/Radial** — nós dispostos em anéis concêntricos por nível de hop, com o núcleo (core/router) no centro.
  - **BFS tree** — árvore em largura a partir de uma raiz, expondo o `_layout_by_bfs` já existente (hoje só usado como fallback interno).
- Substituição do `QComboBox` de layout por uma **fileira de botões-ícone** (exclusivos), um por modo: Tree, Force-directed, Concentric e BFS tree.
- Ícones **desenhados programaticamente com QPainter** (sem novos assets SVG).
- Dispatch de layout via **registro** `{modo → callable}` no engine, no lugar do `if layout_mode == 'force'` atual.
- Os dois modos existentes (hierarchical e force) passam a usar o mesmo mecanismo, sem mudança de comportamento.
- **Sem persistência** do modo de layout nesta iteração (o modo não é salvo/restaurado).

## Capabilities

### New Capabilities
- `topology-layout-modes`: Seleção e aplicação de arranjos de nós no mapa de topologia — modos de layout disponíveis, botões-ícone para escolha, aplicação imediata ao grafo carregado e representação correta de grupos colapsados em cada modo.

### Modified Capabilities

Nenhum. Nenhum requisito existente muda; os modos existentes mantêm o mesmo comportamento.

## Impact

- **Código novo**: funções `layout_concentric` e `layout_bfs_tree` em `cetuslib/topology/engine.py`; classe de botão-ícone de layout e renderização programática dos ícones em `cetuslib/topology/gui/view.py` (ou `tab.py`).
- **Código modificado**: `cetuslib/topology/gui/view.py` — `_apply_layout` passa a consultar o registro de layouts; `cetuslib/topology/tab.py` — `row1` da página Discovery troca o `QComboBox` pela fileira de botões.
- **Assets**: nenhum novo (ícones via QPainter).
- **Dependências**: nenhuma nova.
- **Empacotamento**: `dist/cetus` regenerado via `scripts/bundle-monolith.py`; receitas .deb/AppImage/Flatpak inalteradas.
