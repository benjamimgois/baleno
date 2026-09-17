## Purpose

Define os arranjos (layouts) de nós disponíveis no mapa de topologia, como o usuário os seleciona e como cada modo reorganiza os dispositivos do grafo carregado.

## ADDED Requirements

### Requirement: Seleção de layout por botões-ícone
O sistema SHALL apresentar os modos de layout disponíveis como uma fileira de botões-ícone de seleção exclusiva, substituindo o seletor textual, de modo que apenas um modo esteja ativo por vez.

#### Scenario: Fileira de ícones visível
- **WHEN** a aba Topology está aberta com um mapa carregado
- **THEN** cada modo de layout disponível é exibido como um botão com ícone, e exatamente um está marcado como ativo

#### Scenario: Seleção exclusiva
- **WHEN** o usuário clica em um botão de layout diferente do ativo
- **THEN** o novo modo fica ativo e o anterior é desmarcado

### Requirement: Aplicar layout ao grafo carregado
O sistema SHALL reorganizar imediatamente as posições dos dispositivos do grafo carregado ao selecionar um modo de layout, sem alterar devices, links ou demais propriedades.

#### Scenario: Reorganização imediata
- **WHEN** o usuário seleciona um modo de layout com um grafo carregado
- **THEN** as posições de todos os dispositivos visíveis são recalculadas e o mapa é reenquadrado

#### Scenario: Grafo preservado
- **WHEN** o usuário troca de modo de layout
- **THEN** o conjunto de dispositivos, links e propriedades permanece idêntico

### Requirement: Layout concêntrico por nível
O sistema SHALL oferecer um layout em que os dispositivos são dispostos em anéis concêntricos conforme o nível de hop, com o núcleo (core/router) no centro e os níveis mais profundos em anéis mais externos.

#### Scenario: Núcleo no centro
- **WHEN** o usuário aplica o layout concêntrico a um grafo com dispositivos de núcleo identificáveis
- **THEN** os dispositivos de núcleo ficam posicionados próximos ao centro

#### Scenario: Anéis por nível
- **WHEN** o usuário aplica o layout concêntrico
- **THEN** dispositivos de mesmo nível de hop ficam distribuídos no mesmo anel, e níveis mais profundos ficam em anéis mais externos

### Requirement: Layout em árvore BFS
O sistema SHALL oferecer um layout que distribui os dispositivos em camadas por distância de busca em largura a partir de uma raiz escolhida.

#### Scenario: Camadas por profundidade
- **WHEN** o usuário aplica o layout BFS a um grafo
- **THEN** os dispositivos são posicionados em camadas, uma por nível de profundidade a partir da raiz

### Requirement: Grupos colapsados em todos os modos
O sistema SHALL atribuir posição válida aos grupos colapsados em todos os modos de layout, incluindo os novos.

#### Scenario: Grupo posicionado no modo concêntrico
- **WHEN** um modo de layout é aplicado a um grafo que contém grupo colapsado
- **THEN** o círculo do grupo recebe uma posição que não colide com os nós individuais visíveis

### Requirement: Ícones de layout desenhados programaticamente
O sistema SHALL desenhar os ícones dos modos de layout programaticamente, sem depender de arquivos de imagem externos.

#### Scenario: Ícones sem assets
- **WHEN** os botões de layout são renderizados
- **THEN** cada botão exibe um ícone distinto desenhado em código, sem carregar arquivos de imagem
