# Design

## Context

A aba de topologia atualmente posiciona o painel de camadas à direita e mantém campos de descoberta na barra superior. Para evoluir para uma experiência de modelagem fluida como o Draw.io, movemos a barra de ferramentas para a esquerda com seções retráteis (Accordion), transformamos a barra superior em uma barra de ferramentas operacionais (com histórico Undo/Redo e zoom), e adicionamos uma ferramenta de busca rápida de dispositivos com foco visual.

## Goals / Non-Goals

**Goals:**
- Posicionar a barra lateral à esquerda com seções retráteis (Accordion) para Objetos, Camadas e Descoberta.
- Implementar barra superior enxuta com ferramentas de arquivo, edição, navegação por zoom e busca.
- Implementar sistema de Undo/Redo (`QUndoStack`) para movimentos de nós e criação de conexões.
- Implementar busca de dispositivos com realce visual em tempo real e foco de câmera (`focus_device`) ao pressionar Enter.

**Non-Goals:**
- Undo/Redo para edição de dados internos de dispositivos (apenas ações espaciais e estruturais do canvas).
- Busca remota por SNMP ou na rede (a busca é estritamente sobre o grafo atual em memória).

## Decisions

### D1 — Barra lateral à esquerda com componente `CollapsibleSection`
A barra lateral é movida para a esquerda do canvas. É implementado um componente reutilizável `CollapsibleSection(QWidget)` composto por:
- Um botão de cabeçalho estilizado com texto em caixa alta e ícone indicador de estado (`▾` expandido, `▸` colapsado).
- Um container de conteúdo interno cuja visibilidade é alternada com animação ou toggle instantâneo.
- Uma `QScrollArea` que empilha as seções verticalmente com `addStretch(1)` no final.

- **Alternativa rejeitada**: abas verticais (`QTabWidget` lateral) — força o usuário a ver uma coisa de cada vez, enquanto o accordion permite manter Objetos e Camadas abertos simultaneamente.

### D2 — Ordem das Seções: Objetos (1º), Camadas (2º), Descoberta (3º)
- **Objetos**: primeiro item, facilitando o arraste contínuo para o canvas ao centro.
- **Camadas**: segundo item, permitindo alternar visibilidade e isolar redes com a árvore GIMP.
- **Descoberta**: terceiro item, mantido recolhido por padrão após a varredura inicial para poupar espaço vertical.

### D3 — Barra Superior Operacional e Busca Rápida
A topbar torna-se uma régua de ferramentas (~36px) dividida em grupos lógicos:
1. `[☷ Painel]` (toggle de visibilidade da sidebar inteira).
2. Arquivo: `[💾 Salvar]`, `[📷 Exportar PNG]`.
3. Histórico: `[↶ Desfazer]` (Ctrl+Z), `[↷ Refazer]` (Ctrl+Y).
4. Conexão: `[⚡ Criar Link]`.
5. Zoom: `[-]`, `[ 100% ]` (reset), `[+]`, `[⛶ Fit]`.
6. Seletor de layout: `[ Layout: Tree ▾ ]`.
7. Busca rápida: `QLineEdit` com ícone de lupa. Ao digitar, calcula os nós correspondentes e aplica um anel/halo de realce no canvas. Ao pressionar Enter, invoca `view.centerOn(item)` com escala ajustada.

### D4 — Pilha de Histórico (`QUndoStack`)
É integrada uma `QUndoStack` do PyQt6 no `TopologyView`:
- `MoveNodeCommand`: registra `(old_pos, new_pos)` do nó movido.
- `AddDeviceCommand`: gerencia inclusão e exclusão de nós manuais.
- `AddLinkCommand` / `RemoveLinkCommand`: gerencia criação e exclusão de arestas.
Os botões da barra superior conectam-se a `undoStack.canUndoChanged` e `canRedoChanged` para habilitar/desabilitar dinamicamente.

## Risks / Trade-offs

- **[Múltiplos nós movidos simultaneamente]** Arrastar seleção múltipla pode gerar muitos comandos isolados → Mitigação: usar macro (`beginMacro`/`endMacro`) para agrupar movimentações conjuntas em um único passo de desfazer.
- **[Largura da sidebar na esquerda]** Em telas menores, a sidebar pode consumir espaço horizontal → Mitigação: botão de toggle `[☷ Painel]` com atalho para ocultar a sidebar completamente e botão de colapso rápido de seções.
