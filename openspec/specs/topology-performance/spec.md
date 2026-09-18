# topology-performance Specification

## Purpose
Define mecanismos de otimização de performance e renderização acelerada por hardware para mapas de topologia com alta densidade de dispositivos e conexões.

## Requirements

### Requirement: Viewport acelerado por hardware via OpenGL
O sistema SHALL utilizar renderização acelerada por GPU na visualização principal da topologia com fallback automático para raster de software caso o contexto gráfico não esteja disponível.

#### Scenario: Inicialização com suporte a OpenGL
- **WHEN** o canvas de topologia é inicializado em ambiente com suporte gráfico
- **THEN** o viewport utiliza QOpenGLWidget para acelerar a rasterização de traços e curvas

#### Scenario: Falha ou ausência de aceleração gráfica
- **WHEN** a inicialização do contexto OpenGL falha ou não é suportada pelo ambiente
- **THEN** o sistema reverte transparentemente para o viewport raster padrão sem erros para o usuário

### Requirement: Cache de renderização nos nós de dispositivo
O sistema SHALL utilizar cache em coordenadas de dispositivo (DeviceCoordinateCache) nos nós da topologia para evitar recálculos vetoriais em repinturas.

#### Scenario: Pan ou movimentação do mapa
- **WHEN** o usuário desloca o mapa pelo viewport
- **THEN** os nós existentes utilizam a imagem em cache na memória sem reexecutar desenho de fontes, SVG ou ícones

#### Scenario: Atualização de atributos do dispositivo
- **WHEN** um dispositivo tem status, seleção ou identificação alterada
- **THEN** o cache do nó correspondente é invalidado e redesenhado com os novos dados

### Requirement: Simplificação por nível de detalhe (LOD) em zoom distante
O sistema SHALL ocultar etiquetas de texto de portas e tráfego nas conexões quando o nível de zoom estiver excessivamente reduzido.

#### Scenario: Zoom afastado além do limiar
- **WHEN** o fator de escala da cena estiver abaixo de 0.5 (nível de detalhe reduzido)
- **THEN** as etiquetas de texto das conexões são suprimidas na renderização para poupar cálculos de fonte
