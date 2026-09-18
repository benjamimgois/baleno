# Tasks

## 1. Suavização das Conexões (Anti-aliasing de Traços)

- [x] 1.1 Atualizar `EdgeItem._pen()` em `balenolib/topology/gui/view.py` para definir `pen.setCapStyle(Qt.PenCapStyle.RoundCap)` e verificar a suavização das extremidades dos traços animados

## 2. Viewport Nativo Padrão e Chaveamento OpenGL

- [x] 2.1 Configurar o viewport padrão de `TopologyGraphicsView` como `QWidget` nativo com `BoundingRectViewportUpdate` e `RenderHint.Antialiasing`
- [x] 2.2 Implementar o método `toggle_opengl()` em `TopologyGraphicsView` permitindo alternância dinâmica e segura entre `QWidget` e `QOpenGLWidget`

## 3. Overlays de Diagnóstico e Feedback Visual

- [x] 3.1 Criar a classe `FpsOverlay(QLabel)` no canto superior direito para cálculo e exibição em tempo real da taxa de quadros e modo ativo
- [x] 3.2 Criar a classe `ToastOverlay(QWidget)` no topo central para exibição de mensagens flutuantes temporizadas sem captura de cliques do mouse
- [x] 3.3 Integrar posicionamento de `FpsOverlay` e `ToastOverlay` em `resizeEvent` e após trocas de viewport

## 4. Atalhos de Teclado e Acionamento

- [x] 4.1 Conectar atalho `F11` para alternar modo gráfico e exibir toast indicando o novo modo (Raster Nativo vs OpenGL)
- [x] 4.2 Conectar atalho `F12` para alternar a visibilidade do medidor de FPS com feedback visual via toast

## 5. Validação e Verificação

- [x] 5.1 Validar integridade sintática de `balenolib/` com `python3 -m py_compile`
- [x] 5.2 Executar suíte de testes de topologia e verificar em script de teste o funcionamento dos atalhos F11 e F12, transição de viewports e cálculo de FPS
