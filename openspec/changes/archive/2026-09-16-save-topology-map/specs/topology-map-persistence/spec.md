# topology-map-persistence

## Purpose

Persistir o mapa de topologia de rede completo (devices, links, objetos manuais, propriedades e posições) e restaurá-lo automaticamente, salvando sem intervenção manual a cada modificação.

## ADDED Requirements

### Requirement: Salvar o mapa completo
O sistema SHALL persistir o mapa de topologia — dispositivos com suas propriedades, links, objetos adicionados manualmente e as posições dos nós e grupos — em um arquivo JSON no diretório de configuração do Cetus.

#### Scenario: Mapa salvo em arquivo
- **WHEN** o usuário modifica o mapa e o salva (manual ou automático)
- **THEN** um arquivo JSON contendo devices, links, objetos manuais e posições existe no diretório de configuração

#### Scenario: Propriedades preservadas
- **WHEN** um dispositivo tem identidade persistível (id, ip, hostname, papel, vendor, modelo, status, camada)
- **THEN** essas propriedades são preservadas ao recarregar o mapa

#### Scenario: Dados efêmeros não persistidos
- **WHEN** um dispositivo possui valores de tempo real (taxas de tráfego, CPU, memória) ou vizinhos LLDP
- **THEN** esses valores não são gravados no arquivo persistido

### Requirement: Restaurar o último mapa no startup
O sistema SHALL carregar e exibir automaticamente o último mapa salvo quando o Cetus é aberto, sem exigir nova descoberta de rede.

#### Scenario: Abertura com mapa salvo
- **WHEN** o Cetus é aberto e existe um mapa salvo
- **THEN** a aba Topology exibe os devices, links, objetos manuais e posições do último mapa salvo

#### Scenario: Abertura sem mapa salvo
- **WHEN** o Cetus é aberto e não existe mapa salvo
- **THEN** a aba Topology inicia vazia sem erro

#### Scenario: Arquivo corrompido
- **WHEN** o arquivo do mapa está corrompido ou inválido
- **THEN** o sistema inicia a aba vazia sem travar e sem sobrescrever o arquivo até a próxima modificação

### Requirement: Salvar automaticamente a cada modificação
O sistema SHALL salvar o mapa automaticamente (com atraso de debounce) sempre que o mapa for alterado por qualquer das ações de edição.

#### Scenario: Adicionar objeto
- **WHEN** o usuário adiciona um objeto manual ao mapa (arrastar da paleta)
- **THEN** o mapa é salvo automaticamente após um curto intervalo

#### Scenario: Remover objeto
- **WHEN** o usuário remove um objeto do mapa
- **THEN** o mapa é salvo automaticamente após um curto intervalo

#### Scenario: Mover nó ou grupo
- **WHEN** o usuário move um nó ou grupo de posição
- **THEN** o mapa é salvo automaticamente após um curto intervalo

#### Scenario: Editar propriedade
- **WHEN** o usuário edita uma propriedade persistível de um dispositivo
- **THEN** o mapa é salvo automaticamente após um curto intervalo

### Requirement: Ação manual "Save Map"
O sistema SHALL disponibilizar na aba Settings da Topologia uma ação "Save Map" que salva o mapa completo imediatamente, mantendo a exportação PNG existente inalterada.

#### Scenario: Salvar manualmente
- **WHEN** o usuário clica em "Save Map" com um mapa carregado
- **THEN** o mapa completo é gravado imediatamente no arquivo de configuração

#### Scenario: Exportação PNG preservada
- **WHEN** o usuário clica em "Export PNG"
- **THEN** a imagem PNG é gerada como antes, sem mudança de comportamento
