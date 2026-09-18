# Spec Delta: topology-link-visualization

## MODIFIED Requirements

### Requirement: Linha de link com ambas as interfaces up é tracejada e animada
O sistema SHALL desenhar como linha tracejada animada (marcha de traços em movimento) o link cujas duas interfaces estão em estado "up", quando a animação global estiver habilitada, aplicando a animação estritamente aos links visíveis na área da câmera (viewport culling).

#### Scenario: Link com ambas as interfaces up
- **WHEN** um link tem as duas interfaces em estado "up"
- **THEN** a linha é desenhada tracejada com os traços em movimento contínuo e sutil quando visível no viewport

#### Scenario: Interface com estado desconhecido ou não resolvido
- **WHEN** a interface de um lado do link tem estado "unknown" ou não pôde ser resolvida
- **THEN** o link é tratado como ativo (a ausência de "down" não desativa o link)

#### Scenario: Link fora do viewport da câmera
- **WHEN** um link ativo está posicionado fora da área atualmente visível no viewport do mapa
- **THEN** o sistema não dispara repaints periódicos de animação para este link até que ele entre no campo de visão

#### Scenario: Animação pausada ou desabilitada
- **WHEN** a animação de links estiver desativada globalmente pelo usuário
- **THEN** os links ativos são renderizados com traço estático sem avanço de fase ou timers periódicos

## ADDED Requirements

### Requirement: Pausa interativa da animação durante movimentação
O sistema SHALL pausar os ciclos de atualização de animação de linhas enquanto o usuário estiver executando operações de pan pelo mapa ou arrastando nós.

#### Scenario: Usuário arrasta o mapa ou nós
- **WHEN** o usuário clica e move o mouse para pan ou para reposicionar nós na cena
- **THEN** o timer de marcha das linhas é suspenso, retomando automaticamente ao soltar o mouse

### Requirement: Minimap não renderiza animação contínua de traços
O sistema SHALL renderizar as conexões no minimap sem animação periódica de traços e sem polling contínuo da cena.

#### Scenario: Exibição no minimap
- **WHEN** o mapa possui conexões ativas com animação em execução na visualização principal
- **THEN** o minimap desenha as conexões em formato estático e não dispara repaints a cada ciclo do timer de animação

### Requirement: Controle manual de ativação da animação
O sistema SHALL fornecer um botão de alternância na interface da topologia permitindo ligar e desligar a animação dos links.

#### Scenario: Usuário clica no botão de animação
- **WHEN** o usuário clica no botão de alternância de animação na barra de ferramentas da topologia
- **THEN** o sistema alterna o estado de animação, atualiza o ícone do botão e persiste a preferência nas configurações do usuário
