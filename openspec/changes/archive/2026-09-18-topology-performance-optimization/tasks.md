# Tasks: topology-performance-optimization

## 1. Animação e Viewport Culling

- [x] 1.1 Implementar frustum/viewport culling em `TopologyView._tick_animation()`, restringindo chamadas de `edge.update()` estritamente às conexões que intersectam o retângulo visível da câmera com margem de segurança.
- [x] 1.2 Implementar suspensão temporária do timer de animação de linhas durante eventos de arraste de mouse (pan e movimentação de nós) em `TopologyView`.

## 2. Desacoplamento e Otimização do Minimap

- [x] 2.1 Remover o timer contínuo de 100 ms do `Minimap`, conectando a atualização do retângulo de visualização aos scrollbars da visão principal e o enquadramento apenas a mudanças estruturais da cena.
- [x] 2.2 Garantir que o `Minimap` renderize conexões em modo estático, sem executar cálculos de avanço de fase de traços.

## 3. Aceleração de Hardware e Caching de Itens

- [x] 3.1 Configurar `QOpenGLWidget` como viewport de `TopologyView` com proteção transparente de fallback para raster em caso de falha de inicialização.
- [x] 3.2 Habilitar `DeviceCoordinateCache` em `NodeItem` para eliminar repintura vetorial de nós durante movimentação da câmera.

## 4. Level of Detail (LOD) e Controle Manual

- [x] 4.1 Implementar simplificação por nível de detalhe (LOD) em `EdgeItem.paint()`, suprimindo texto de portas e tráfego quando o fator de zoom estiver abaixo de 0.5.
- [x] 4.2 Adicionar chave `topology_animate_links` no `ConfigManager` e botão de alternância de animação na barra de ferramentas superior da aba de topologia.

## 5. Testes e Empacotamento

- [x] 5.1 Criar testes unitários em `tests/test_topology_performance.py` validando o comportamento de culling do timer, pausa durante pan, fallback de viewport e alternância de animação.
- [x] 5.2 Validar compilação com `python3 -m py_compile`, rodar a suíte de testes unitários e reconstruir o bundle monolítico `dist/baleno`.
