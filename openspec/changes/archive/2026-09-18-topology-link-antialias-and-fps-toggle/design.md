# Design

## Context

Atualmente, `TopologyGraphicsView` (em `balenolib/topology/gui/view.py`) instancia um `QOpenGLWidget` como viewport por padrão com `FullViewportUpdate`. Conforme investigado, no Linux/Mesa o FBO do Qt frequentemente opera com 0 amostras de MSAA, degradando linhas vetoriais inclinadas e causando efeito escada (*aliasing*) acentuado durante a marcha de traços das conexões ativas.

Além disso, o rasterizador nativo (`QWidget`) com `BoundingRectViewportUpdate` mostrou-se ~37% mais veloz em benchmarks de alta densidade (200 nós / 300 links) porque atualiza estritamente os retângulos delimitadores dos traços em movimento (culling seletivo), em vez de redesenhar a tela inteira a cada quadro.

## Goals / Non-Goals

**Goals:**
- Adotar o rasterizador nativo (`QWidget`) com `BoundingRectViewportUpdate` e `RenderHint.Antialiasing` como viewport padrão da topologia.
- Prover alternância dinâmica entre viewport raster nativo e `QOpenGLWidget` via atalho `F11`.
- Prover medidor de FPS em tempo real no canto superior direito do canvas acionado via atalho `F12`.
- Exibir feedback visual flutuante (Toast overlay) no topo central do mapa ao acionar `F11` ou `F12`.
- Suavizar as pontas dos segmentos tracejados dos links ativos aplicando `RoundCap` no `QPen`.

**Non-Goals:**
- Modificar o sistema de cache de nós (`DeviceCoordinateCache`) ou a renderização de rótulos de portas.
- Tornar o medidor de FPS uma métrica persistente em disco (o recurso é uma ferramenta de inspeção e teste sob demanda).

## Decisions

### 1. Viewport Padrão e Alternância Dinâmica (F11)
- **Decisão**: Inicializar `TopologyGraphicsView` com viewport nativo padrão (`QWidget()`) e modo de atualização `BoundingRectViewportUpdate`. Criar o método `toggle_opengl()` associado ao atalho `F11`.
- **Implementação**:
  - Ao alternar para OpenGL: instancia `QOpenGLWidget()`, configura `QSurfaceFormat` com `samples=4` e aplica `setViewport(gl_widget)` com `FullViewportUpdate`.
  - Ao alternar para Raster: instancia `QWidget()` e aplica `setViewport(widget)` com `BoundingRectViewportUpdate`.
  - Re-aplica `RenderHint.Antialiasing` e atualiza a referência dos overlays.
- **Alternativas consideradas**:
  - *Manter OpenGL forçado e tentar ajustar flags de driver*: Inviável de forma consistente em diferentes GPUs/compositors Wayland e X11 no Linux.

### 2. Medição de FPS em Tempo Real (F12) e `FpsOverlay`
- **Decisão**: Implementar a classe `FpsOverlay(QLabel)` posicionada no canto superior direito do viewport (`self.width() - overlay.width() - 14, 14`).
- **Implementação**:
  - O overlay monitora o timestamp de cada repintura (`paintEvent` no viewport ou hook no loop de animação).
  - Mantém uma janela deslizante (buffer) dos últimos 30 quadros e calcula: `fps = len(times) / (times[-1] - times[0])`.
  - Exibe texto formatado com badge estilizado (ex.: `🟢 60 FPS • Raster` ou `🟠 58 FPS • OpenGL`).
  - Oculto por padrão; a tecla `F12` alterna a visibilidade e ativa/pausa a amostragem de dados para economizar ciclos quando desligado.

### 3. Notificações Visuais Flutuantes (`ToastOverlay`)
- **Decisão**: Implementar `ToastOverlay(QWidget)` centralizado horizontalmente no topo do canvas (`(self.width() - toast.width()) // 2, 20`).
- **Implementação**:
  - Design dark semi-transparente (`#161B22EE`, borda `#30363D`, cantos arredondados `8px`, texto legível com ícone).
  - Acionado sempre que `F11` ou `F12` forem pressionados (ex.: *"Modo de Renderização: Raster Nativo (Anti-aliased)"*, *"Contador de FPS: Ativado"*).
  - Utiliza um `QTimer` de ~1.8 segundos com animação sutil de opacidade/fade para desaparecer suavemente sem bloquear interação.
  - Atributo `WA_TransparentForMouseEvents` habilitado para não interceptar cliques ou arrastos no mapa.

### 4. Estilização de Traços com `RoundCap`
- **Decisão**: Em `EdgeItem._pen()`, definir `pen.setCapStyle(Qt.PenCapStyle.RoundCap)`.
- **Implementação**:
  - Transforma os traços retangulares de corte reto em segmentos com pontas circulares suaves, eliminando cantos serrilhados quando desenhados em ângulos diagonais.

## Risks / Trade-offs

- **[Risco]** Troca de viewport em tempo de execução pode desordenar z-order de overlays flutuantes.
  - **Mitigação**: O método `_place_overlays()` (ou chamada em `resizeEvent`) re-invoca `.raise_()` em `minimap`, `_legend`, `nav_dock`, `_fps_overlay` e `_toast` após `setViewport()`.
- **[Risco]** Instanciação de `QOpenGLWidget` pode falhar em ambientes com drivers corrompidos ou bibliotecas ausentes.
  - **Mitigação**: O chaveamento em `toggle_opengl()` é protegido por bloco `try/except`; em caso de erro, reverte automaticamente para o raster nativo e exibe toast explicativo (*"Falha ao iniciar OpenGL — mantendo Raster"*).
- **[Risco]** Interceptação de eventos de mouse pelos overlays.
  - **Mitigação**: Ambos `FpsOverlay` e `ToastOverlay` recebem `setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)`.
