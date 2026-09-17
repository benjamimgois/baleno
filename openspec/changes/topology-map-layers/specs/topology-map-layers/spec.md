## ADDED Requirements

### Requirement: Nome da descoberta
O sistema SHALL permitir ao usuário informar um nome para cada descoberta de rede, usado como base para as camadas geradas por aquela descoberta.

#### Scenario: Descoberta nomeada
- **WHEN** o usuário inicia uma descoberta informando o nome "Rede-A"
- **THEN** os dispositivos descobertos são associados a camadas cujo nome deriva de "Rede-A"

#### Scenario: Descoberta sem nome
- **WHEN** o usuário inicia uma descoberta sem informar nome
- **THEN** o sistema usa um nome padrão (ex.: o primeiro CIDR da descoberta) como base das camadas

### Requirement: Atribuição de camadas por profundidade
O sistema SHALL atribuir cada dispositivo descoberto a uma camada nomeada conforme a profundidade: `<nome>` para dispositivos descobertos diretamente pelo endereço IP (sementes) e `<nome>-<N>` para vizinhos identificados via LLDP no salto N, preservando a profundidade real.

#### Scenario: Semente
- **WHEN** um dispositivo é descoberto diretamente pelo endereço IP na descoberta "Rede-A"
- **THEN** o dispositivo pertence à camada "Rede-A"

#### Scenario: Vizinho LLDP de primeiro salto
- **WHEN** um dispositivo é descoberto como vizinho LLDP de primeiro salto na descoberta "Rede-A"
- **THEN** o dispositivo pertence à camada "Rede-A-2"

#### Scenario: Profundidade real preservada
- **WHEN** um dispositivo é descoberto como vizinho LLDP de salto 3 na descoberta "Rede-A"
- **THEN** o dispositivo pertence à camada "Rede-A-3"

### Requirement: Mesclar descobertas em vez de substituir
O sistema SHALL mesclar os dispositivos e links de uma nova descoberta ao mapa existente, em vez de limpar e substituir o mapa atual.

#### Scenario: Descoberta adicional
- **WHEN** o usuário executa uma nova descoberta com um mapa já populado
- **THEN** os dispositivos e links já existentes permanecem, e os novos são adicionados

#### Scenario: Reinício preserva o acumulado
- **WHEN** o aplicativo é reiniciado após múltiplas descobertas
- **THEN** todos os dispositivos e links acumulados são restaurados

### Requirement: Deduplicação por chassis_id
O sistema SHALL fundir em um único dispositivo os resultados de descobertas diferentes que compartilham o mesmo `chassis_id`, somando os links e as camadas associadas.

#### Scenario: Mesmo dispositivo em duas descobertas
- **WHEN** o mesmo dispositivo físico (mesmo `chassis_id`) é descoberto pelo backbone e por uma rede
- **THEN** existe um único nó no mapa, com os links de ambos os lados, e o dispositivo pertence às camadas de ambas as descobertas

### Requirement: Pertinência a múltiplas camadas
O sistema SHALL permitir que um dispositivo pertença a mais de uma camada nomeada.

#### Scenario: Dispositivo compartilhado
- **WHEN** um dispositivo é descoberto por duas descobertas distintas
- **THEN** o dispositivo pertence às camadas de ambas as descobertas

### Requirement: Painel de camadas e visibilidade
O sistema SHALL exibir um painel listando as camadas presentes no mapa e permitir exibir/ocultar cada camada individualmente.

#### Scenario: Ocultar uma rede
- **WHEN** o usuário oculta a camada "Rede-A" (e "Rede-A-2") no painel
- **THEN** os dispositivos que pertencem apenas a essas camadas deixam de ser exibidos

#### Scenario: Dispositivo em camada visível e oculta
- **WHEN** um dispositivo pertence a uma camada visível e a uma oculta
- **THEN** o dispositivo permanece visível (é visível se qualquer uma de suas camadas estiver visível)

#### Scenario: Aresta entre camadas
- **WHEN** uma aresta liga dois dispositivos
- **THEN** a aresta é exibida somente quando ambos os extremos estão visíveis

### Requirement: Posicionamento espacial não sobreposto
O sistema SHALL posicionar os dispositivos de uma nova descoberta em uma região espacial à direita da área já ocupada, sem sobrepor os dispositivos existentes.

#### Scenario: Nova descoberta à direita
- **WHEN** uma descoberta é mesclada a um mapa já populado
- **THEN** os novos dispositivos são posicionados à direita do bounding box atual, preservando a sub-hierarquia (sementes acima, vizinhos abaixo) dentro da nova região

### Requirement: Reinício do monitor sem crash
O sistema SHALL parar corretamente o monitor de performance existente antes de mesclar uma nova descoberta, sem destruir uma thread em execução, e iniciar um novo monitor cobrindo todos os dispositivos mesclados.

#### Scenario: Merge com monitor ativo
- **WHEN** uma descoberta termina enquanto o monitor anterior está ativo
- **THEN** o monitor anterior é encerrado com sucesso (thread finalizada) e um novo monitor cobre o grafo mesclado, sem encerrar o aplicativo
