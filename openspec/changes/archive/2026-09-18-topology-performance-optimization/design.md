# Design: topology-performance-optimization

## Context

Ver `proposal.md`. A renderização gráfica no `TopologyView` (`balenolib/topology/gui/view.py`) opera sobre `QGraphicsScene`. Quando a topologia cresce para centenas de nós e conexões, o custo computacional da animação das linhas (timer de 40 ms iterando todos os `EdgeItem`), a atualização periódica do `Minimap` (timer de 100 ms computando `itemsBoundingRect()`) e a renderização puramente em software raster da CPU provocam quedas acentuadas na taxa de quadros e atrasos nas respostas de mouse.

## Goals / Non-Goals

**Goals:**
- Manter taxa de quadros fluida (60 FPS) durante pan, zoom e seleção em mapas densos.
- Eliminar repaints desnecessários de conexões fora da tela durante a animação de marching-ants.
- Suspender a concorrência da animação durante manipulação direta (arraste de nós e pan com mouse).
- Isolar o `Minimap` para não renderizar animação contínua nem recalcular limites a cada 100 ms.
- Habilitar aceleração de GPU com `QOpenGLWidget` mantendo compatibilidade total com ambientes sem OpenGL.
- Permitir ao usuário ligar ou desligar a animação das conexões conforme preferência.

**Non-Goals:**
- Não reescrever o motor de física/layout do NetworkX.
- Não alterar as regras de cores ou semântica de link speeds.
- Não remover recursos visuais (como status dots ou badges) de nós em zoom normal.

## Decisions

### D1: Viewport Culling na animação de marching-ants
- **Abordagem**: Em `TopologyView._tick_animation()`, obter o retângulo da cena correspondente à área visível da viewport (`self.mapToScene(self.viewport().rect()).boundingRect()`). Apenas conexões cujo `boundingRect()` ou forma intersectem esse retângulo recebem atualização de `_dash_offset` e chamada a `edge.update()`.
- **Alternativas consideradas**:
  - *Filtrar via `scene.items(rect)`*: `items(rect)` pode envolver verificações poligonais finas para todos os itens; checagem de bounding rect na lista de edges em memória é rápida e direta em Python.
  - *Desativar animação automaticamente*: Usuários preferem manter o efeito visual nas conexões que estão efetivamente observando.

### D2: Pausa dinâmica durante Pan e Drag
- **Abordagem**: Interceptar `mousePressEvent` e `mouseReleaseEvent` no `TopologyView`. Se o botão do meio for pressionado (pan) ou se a interação envolver arrastar itens/canvas, pausar o `_anim_timer` (ou ignorar os ticks de animação). Ao soltar o botão, retomar o timer.
- **Alternativas consideradas**:
  - *Reduzir o FPS da animação durante pan*: Ainda gera interferência e disputa na fila de eventos da GUI. Pausar durante o movimento de 1-2 segundos é imperceptível para traços marchantes e garante fluidez máxima.

### D3: Desacoplamento e modo estático no Minimap
- **Abordagem**:
  1. No `Minimap`, remover o `_timer` de 100 ms que chamava `_refresh()` e `itemsBoundingRect()`.
  2. Atualizar o enquadramento do `Minimap` apenas sob demanda: quando um grafo é carregado, nós são adicionados/removidos, ou no término de arraste de nós.
  3. No `Minimap`, ignorar eventos de atualização de animação de traços (renderizar linhas em estilo sólido ou ignorar `_dash_offset`).
  4. O retângulo de visualização (`drawForeground`) é atualizado conectando-se ao sinal de scroll/mudança de viewport da visão principal (`horizontalScrollBar().valueChanged`, `verticalScrollBar().valueChanged`).

### D4: Viewport OpenGL com Fallback Transparente
- **Abordagem**:
  ```python
  try:
      from PyQt6.QtOpenGLWidgets import QOpenGLWidget
      gl_widget = QOpenGLWidget()
      self.setViewport(gl_widget)
  except Exception:
      pass  # Mantém QWidget raster padrão
  ```
  Adicionar proteção para reverter para raster caso ocorra falha de inicialização de driver ou contexto.

### D5: DeviceCoordinateCache em NodeItem
- **Abordagem**: Configurar `self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)` em `NodeItem.__init__`.
- **Invalidação**: O cache é automaticamente redesenhado pelo Qt quando `node.update()` é acionado (ex.: seleção, mudança de status ou rótulo).

### D6: Level of Detail (LOD) para etiquetas de conexões
- **Abordagem**: Em `EdgeItem.paint()`, verificar o nível de detalhe do transformador:
  ```python
  lod = option.levelOfDetailFromTransform(painter.worldTransform())
  if lod >= 0.5:
      # Desenha texto das portas (ex: Gi0/1 ⟷ Gi0/24) e taxa
  ```
  Em zoom afastado, suprime caixas de texto e `QFontMetricsF`.

### D7: Botão de Alternância de Animação e Configuração
- **Abordagem**:
  - Adicionar botão de alternância `btn_anim` na barra superior de navegação da topologia com ícone/tooltip apropriado.
  - Adicionar chave `topology_animate_links: bool = True` em `ConfigManager.defaults`.
  - Conectar botão para pausar/retomar `_anim_timer` e salvar a preferência.

## Risks / Trade-offs

- **[Risco: Incompatibilidade de driver OpenGL em algumas distros/Wayland]** → Mitigado com bloco `try/except` seguro que mantém o rasterizador de software caso o `QOpenGLWidget` falhe ao instanciar ou renderizar.
- **[Risco: Textos borrados com DeviceCoordinateCache em zoom extremo]** → `DeviceCoordinateCache` re-renderiza o bitmap na resolução nativa da tela atual sempre que a escala da viewport muda, garantindo nitidez.
- **[Risco: Conexões nas bordas da tela cortando animação abruptamente]** → A área de culling é expandida com uma margem de segurança (ex.: 50px de padding ao redor do viewport rect) para que conexões entrando na tela já estejam ativas.
