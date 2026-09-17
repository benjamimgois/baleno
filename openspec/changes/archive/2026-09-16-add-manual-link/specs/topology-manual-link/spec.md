## Purpose

Permite ao operador criar manualmente um link entre dois dispositivos (ou entre um grupo colapsado e um dispositivo) no mapa de topologia, definindo as portas e a velocidade, para representar enlaces que a descoberta automática não encontrou.

## ADDED Requirements

### Requirement: Ícone "Link" fixo na paleta
O sistema SHALL exibir um ícone "Link" sempre na primeira posição da aba Objects, como um botão de alternância que entra e sai do modo de criação de link.

#### Scenario: Ícone sempre primeiro
- **WHEN** a aba Objects está aberta
- **THEN** o botão "Link" é o primeiro item da paleta, antes dos botões de dispositivos

#### Scenario: Alternar modo
- **WHEN** o usuário clica no botão "Link"
- **THEN** o modo de criação de link é ativado e o botão indica visualmente o estado ativo; um segundo clique desativa o modo

### Requirement: Seleção de endpoints com destaque
O sistema SHALL permitir, no modo de criação de link, selecionar dois endpoints por clique, tratando o primeiro clique como source, e destacando-o em amarelo forte enquanto aguarda o alvo.

#### Scenario: Cursor de cruz
- **WHEN** o modo de criação de link está ativo
- **THEN** o cursor do mouse é exibido como cruz

#### Scenario: Source destacado em amarelo
- **WHEN** o usuário clica em um dispositivo ou grupo no modo de link
- **THEN** esse objeto é destacado em amarelo forte, indicando que foi selecionado como source

#### Scenario: Linha de preview
- **WHEN** um source está selecionado e o mouse se move sobre o mapa
- **THEN** uma linha tracejada de preview é desenhada do source até a posição do cursor

### Requirement: Cancelamento do modo de link
O sistema SHALL cancelar o modo de criação de link quando o usuário pressiona Esc, clica em uma área vazia do mapa, ou clica no mesmo objeto já selecionado como source.

#### Scenario: Cancelar com Esc
- **WHEN** o modo de link está ativo (com ou sem source selecionado) e o usuário pressiona Esc
- **THEN** o modo é desativado e o destaque amarelo é removido

#### Scenario: Cancelar clicando no vazio
- **WHEN** o usuário clica em uma área vazia do mapa no modo de link
- **THEN** o modo é desativado sem criar link

#### Scenario: Cancelar clicando no próprio objeto
- **WHEN** o usuário clica no mesmo objeto que já é o source
- **THEN** o modo é desativado sem criar link

### Requirement: Configurar portas e velocidade
O sistema SHALL, ao selecionar o segundo endpoint, abrir um diálogo com a lista de interfaces de cada lado e um seletor de velocidade com padrão AUTO.

#### Scenario: Listas de interfaces
- **WHEN** o diálogo de link é aberto com dispositivos que possuem interfaces
- **THEN** as interfaces do source são listadas à esquerda e as do target à direita

#### Scenario: Porta livre quando sem interfaces
- **WHEN** um dos lados não possui interfaces conhecidas
- **THEN** o diálogo permite digitar manualmente o nome da porta desse lado

#### Scenario: Velocidade padrão AUTO
- **WHEN** o diálogo de link é aberto
- **THEN** o seletor de velocidade está em AUTO por padrão

### Requirement: Criação e renderização do link
O sistema SHALL criar o link ao confirmar o diálogo e desenhá-lo no mapa, usando AUTO para deixar status e velocidade serem detectados automaticamente.

#### Scenario: Link criado
- **WHEN** o usuário confirma o diálogo com portas escolhidas e velocidade AUTO
- **THEN** o link aparece no mapa conectando os dois endpoints, sem override de status ou velocidade

#### Scenario: Link sem interface conhecida fica cinza
- **WHEN** um link é criado com AUTO e nenhuma das interfaces tem velocidade conhecida
- **THEN** o link é desenhado na cor cinza de velocidade desconhecida

### Requirement: Prevenção de duplicatas e self-loop
O sistema SHALL recusar a criação de um link duplicado (mesmos endpoints e portas) ou de um link de um objeto consigo mesmo, exibindo mensagem de erro.

#### Scenario: Link duplicado rejeitado
- **WHEN** o usuário tenta criar um link idêntico a um já existente
- **THEN** uma mensagem de erro é exibida e nenhum novo link é criado

#### Scenario: Self-loop bloqueado
- **WHEN** o usuário tenta criar um link de um objeto para ele mesmo
- **THEN** o link não é criado

### Requirement: Link entre grupo e dispositivo
O sistema SHALL permitir criar um link entre um grupo colapsado e um dispositivo.

#### Scenario: Grupo como endpoint
- **WHEN** o usuário seleciona um grupo colapsado como um dos endpoints e um dispositivo como o outro
- **THEN** o link é criado, resolvendo o grupo para o dispositivo pai do cluster

### Requirement: Persistência do link manual
O sistema SHALL persistir o link criado manualmente junto do mapa e restaurá-lo ao recarregar.

#### Scenario: Link sobrevive ao reload
- **WHEN** um link manual é criado e o mapa é salvo e recarregado
- **THEN** o link manual aparece novamente no mapa com suas portas e velocidade
