# Spec Delta

## MODIFIED Requirements

### Requirement: Viewport acelerado por hardware via OpenGL
O sistema SHALL utilizar por padrão raster de software nativo com suporte a subpixel anti-aliasing na visualização principal da topologia e permitir alternância sob demanda para aceleração por hardware (OpenGL) via tecla de atalho.

#### Scenario: Inicialização com suporte a OpenGL
- **WHEN** o canvas de topologia é inicializado em ambiente com suporte gráfico
- **THEN** o viewport utiliza o widget raster nativo por padrão com antialiasing habilitado e disponibiliza ativação de OpenGL sob demanda

#### Scenario: Falha ou ausência de aceleração gráfica
- **WHEN** a inicialização do contexto OpenGL falha ou não é suportada pelo ambiente
- **THEN** o sistema mantém ou reverte transparentemente para o viewport raster padrão sem erros para o usuário

#### Scenario: Alternância dinâmica de modo de renderização
- **WHEN** o usuário pressiona a tecla F11 com a visualização de topologia ativa
- **THEN** o sistema alterna o viewport entre o raster nativo e aceleração OpenGL em tempo de execução sem reiniciar a aplicação

## ADDED Requirements

### Requirement: Medição e exibição de taxa de quadros (FPS)
O sistema SHALL fornecer um medidor de taxa de quadros (FPS) em tempo real posicionado no canto superior direito do canvas de topologia, ativado e desativado sob demanda via tecla de atalho.

#### Scenario: Ativação do medidor de FPS
- **WHEN** o usuário pressiona a tecla F12
- **THEN** o sistema alterna a visibilidade do overlay de FPS no canto superior direito do canvas, exibindo a taxa calculada de quadros e o modo de renderização ativo

#### Scenario: Desativação do medidor de FPS
- **WHEN** o medidor de FPS está visível e o usuário pressiona a tecla F12 novamente
- **THEN** o overlay de FPS é ocultado e o cálculo de amostragem de quadros é suspenso

### Requirement: Feedback visual de alternância na tela
O sistema SHALL exibir uma notificação visual flutuante (toast) centralizada no topo do mapa ao alternar o modo gráfico ou o medidor de FPS.

#### Scenario: Notificação ao alternar modo gráfico
- **WHEN** o usuário aciona a tecla F11 para alternar entre raster nativo e OpenGL
- **THEN** um aviso visual flutuante surge no topo do canvas indicando o modo gráfico atual e desaparece automaticamente após um breve intervalo

#### Scenario: Notificação ao alternar medidor de FPS
- **WHEN** o usuário aciona a tecla F12
- **THEN** um aviso visual flutuante surge no topo do canvas indicando se o contador de FPS foi ativado ou desativado
