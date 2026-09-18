# Proposal: topology-performance-optimization

## Why

Em topologias com centenas de conexões e dispositivos (por exemplo, mais de 450 links), a aplicação Baleno sofre de lentidão severa. O timer de animação de linhas ("marching ants") dispara repaints para todas as conexões da cena 25 vezes por segundo — inclusive as que estão fora da tela —, enquanto o Minimap repinta a cena inteira a cada 100 ms via CPU software raster. A ausência de aceleração por GPU e de cache de bitmaps nos nós transforma operações comuns de pan, zoom e seleção em tarefas lentas e com alto consumo de processador.

## What Changes

- **Viewport Culling na Animação**: O ciclo de animação passa a iterar e atualizar exclusivamente as conexões que estão visíveis no viewport da câmera, eliminando milhares de repaints inúteis por segundo de itens fora da tela.
- **Pausa da Animação durante Interação**: Ao arrastar o mapa (pan com botão do meio ou modo pan) ou ao movimentar nós, a animação de linhas é pausada temporariamente para garantir taxa fluida de 60 FPS durante o movimento.
- **Desativação de Animações e Polling Contínuo no Minimap**: O Minimap não renderiza mais a marcha de traços das conexões nem executa timer contínuo de 100 ms com `itemsBoundingRect()`. Ele passa a atualizar seu preview apenas quando nós são adicionados/movidos e quando a câmera se move.
- **Aceleração por Hardware (OpenGL)**: A visualização principal do `TopologyView` adota `QOpenGLWidget` como viewport nativo com fallback seguro para raster, descarregando a rasterização de traços anti-aliasing e curvas bezier para a GPU.
- **Cache de Coordenadas de Dispositivos (`DeviceCoordinateCache`)**: Os nós (`NodeItem`) passam a utilizar cache em bitmap na memória, evitando reexecutar layout de fontes, SVG e vetores a cada repintura de cena ou pan.
- **Controle Manual da Animação (Botão Liga/Desliga)**: Adicionado botão na barra superior da topologia para permitir pausar ou retomar a animação de tráfego/linhas sob demanda, com persistência na configuração.
- **Level of Detail (LOD) nos Links**: Em níveis de zoom muito distantes (`lod < 0.5`), as etiquetas de texto das portas nos links são ocultadas para poupar medição de fontes e renderização de caixas de texto ilegíveis.

## Capabilities

### New Capabilities
- `topology-performance`: Aceleração de renderização por hardware (OpenGL), cache de dispositivos em coordenadas de tela e simplificação visual por nível de detalhe (LOD).

### Modified Capabilities
- `topology-link-visualization`: Otimização do ciclo de animação das linhas ativas com suporte a viewport culling, pausa interativa durante pan, desativação de animação no minimap e opção de ligar/desligar animação globalmente.

## Impact

- **Código modificado**:
  - `balenolib/topology/gui/view.py`: `TopologyView`, `Minimap`, `EdgeItem`, `NodeItem` e timers de animação/viewport.
  - `balenolib/topology/tab.py`: Adição do botão de alternância de animação na barra de ferramentas.
  - `balenolib/config.py`: Persistência do estado de animação ativa (`topology_animate_links`).
- **Dependências**: Nenhuma dependência externa nova (`PyQt6.QtOpenGLWidgets` faz parte do pacote PyQt6 padrão já instalado).
- **Compatibilidade**: Fallback automático para raster em ambientes gráficos ou VMs onde OpenGL não esteja disponível.
