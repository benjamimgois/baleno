## Why

O usuário monitora um backbone conectado a várias redes distintas. Hoje, iniciar uma nova descoberta **substitui** o mapa atual (a cena é limpa em `start_discovery`) e pode **fechar o aplicativo** (o `TrafficMonitor` antigo é destruído ainda em execução). O usuário precisa acumular múltiplas descobertas num **único mapa**, organizadas como **camadas nomeadas** (à la editor de imagens), com visibilidade por rede, para alternar contextos de visualização.

## What Changes

- O formulário de discovery ganha um campo **nome da camada** (ex.: `Rede-A`).
- Uma nova descoberta **mescla** (não substitui) o mapa existente.
- Dispositivos são atribuídos a camadas nomeadas: `<nome>` (sementes descobertas por IP) e `<nome>-<N>` (vizinhos LLDP, com profundidade real preservada — `Rede-A-2`, `Rede-A-3`, …).
- Um mesmo dispositivo físico (mesmo `chassis_id`) encontrado por várias descobertas é **fundido** em um único nó, com links somados, e **pertence a múltiplas camadas**.
- Um **painel de camadas** permite exibir/ocultar cada camada individualmente.
- Posicionamento espacial: os dispositivos de cada descoberta são posicionados **à direita** da região já ocupada (não sobrepostos), com a sub-hierarquia (profundidade) preservada dentro da região.
- **Correção de ciclo de vida**: o monitor antigo é parado corretamente antes do merge (sem `QThread` destruído em execução).
- Persistência: nomes de camadas e associações por dispositivo são salvos no arquivo do mapa.

## Capabilities

### New Capabilities
- `topology-map-layers`: Camadas nomeadas por descoberta — nome da camada, atribuição `<nome>`/`<nome>-<N>`, pertinência múltipla, painel de visibilidade, merge/dedup por `chassis_id` e posicionamento espacial não sobreposto.

### Modified Capabilities
- `topology-map-persistence`: o arquivo do mapa passa a persistir as camadas nomeadas e as associações por dispositivo (novo dado persistível).

## Impact

- `balenolib/topology/models.py` — `Device` ganha associações de camadas (conjunto de nomes de camada).
- `balenolib/topology/tab.py` — fluxo de discovery (mesclar em vez de limpar), campo de nome da camada, painel de camadas, ciclo de vida do monitor.
- `balenolib/topology/gui/view.py` — mescla no grafo/cena, filtro de visibilidade por camada, posicionamento por região.
- `balenolib/topology/worker.py` — propagar o nome da camada para os dispositivos descobertos.
- `balenolib/topology/persistence.py` — serializar/desserializar camadas e associações.
- `balenolib/topology/monitor.py` — parada correta antes do merge (fix do crash).
