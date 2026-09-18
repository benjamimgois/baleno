# Proposal

## Why

As linhas animadas de conexão (links) no mapa de topologia estão apresentando serrilhamento perceptível (*aliasing* / degraus visíveis) durante a movimentação da marcha de traços quando renderizadas sobre `QOpenGLWidget` no Linux. Isso ocorre porque o Framebuffer Object (FBO) padrão do Qt em OpenGL opera frequentemente com 0 amostras de MSAA para stroking de curvas, enquanto o rasterizador nativo (`QWidget`) fornece interpolação subpixel de 484+ graduações com custo computacional inferior graças ao descarte por viewport e culling seletivo.

Esta alteração elimina o serrilhamento adotando o raster nativo como padrão visual de alta qualidade, introduz estilo arredondado nas pontas dos traços (`RoundCap`), e adiciona atalhos de diagnóstico (`F11` para alternar aceleração OpenGL e `F12` para exibir medidor de FPS em tempo real com feedback visual na tela) para facilitar testes comparativos de desempenho e fidelidade gráfica.

## What Changes

- **Rasterizador Nativo por Padrão**: Define o viewport padrão de `TopologyGraphicsView` como `QWidget` nativo com `RenderHint.Antialiasing` e `BoundingRectViewportUpdate`, eliminando o serrilhamento severo das linhas animadas.
- **Alternância Dinâmica de GPU (F11)**: Adiciona a tecla de atalho `F11` para alternar em tempo de execução entre renderização por software (`QWidget`) e aceleração por hardware (`QOpenGLWidget`).
- **Contador de FPS em Tempo Real (F12)**: Adiciona a tecla de atalho `F12` para exibir/ocultar um widget de overlay no canto superior direito da tela medindo frames por segundo (FPS) e modo de renderização ativo.
- **Feedback Visual na Tela (Toast)**: Exibe uma notificação flutuante suave (Toast) no topo central do canvas informando o novo estado sempre que `F11` ou `F12` forem pressionados.
- **Traços Arredondados nos Links**: Atualiza o método `_pen()` de `EdgeItem` para aplicar `Qt.PenCapStyle.RoundCap`, gerando traços suaves e orgânicos sem cantos pontiagudos.

## Capabilities

### Modified Capabilities
- `topology-performance`: Altera o modo padrão do viewport para raster nativo de software, adiciona atalho `F11` para alternar dinamicamente para OpenGL, adiciona contador de FPS em tempo real ativado por `F12` e feedback visual em overlay na tela.
- `topology-link-visualization`: Atualiza a estilização de `QPen` nas linhas ativas de conexão para utilizar estilo de terminação arredondado (`RoundCap`), eliminando pontas serrilhadas nos segmentos tracejados.

## Impact

- **Código Afetado**:
  - `balenolib/topology/gui/view.py`: `TopologyGraphicsView` (inicialização de viewport, métodos de toggle, classes de overlay `FpsOverlay` e `ToastOverlay`, atalhos de teclado `F11`/`F12`, posicionamento em `resizeEvent`) e `EdgeItem._pen()` (aplicação de `RoundCap`).
- **Dependências / APIs**: Utiliza widgets padrão do PyQt6 (`QWidget`, `QLabel`, `QShortcut`, `QTimer`, `QOpenGLWidget`). Nenhuma dependência externa adicional.
- **Compatibilidade**: Retrocompatível e resiliente; opera mesmo em ambientes sem suporte a OpenGL ou headless/offscreen.
