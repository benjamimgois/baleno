# Proposal: save-topology-map

## Why

Hoje o mapa de topologia (Network Topology Mapper) só persiste as **coordenadas** dos nós (`topology_layout.json`). O grafo em si — devices, links, objetos manuais adicionados pela paleta e suas propriedades — é perdido ao fechar o Cetus. Ao abrir o aplicativo, a aba Topology inicia vazia, obrigando o usuário a redescobrir a rede e reajustar o mapa toda vez. O usuário quer que o último mapa visualizado reapareça automaticamente e que qualquer edição seja salva sem clicar em nada.

## What Changes

- **Salvar o mapa completo**: persistir o grafo de topologia (devices com propriedades, links, objetos manuais) além das posições, em arquivo JSON no diretório de config (`~/.config/cetus/topology_map.json`), ampliando o formato atual do layout.
- **Auto-load no startup**: a aba Topology carrega e exibe automaticamente o último mapa salvo ao abrir o Cetus, sem necessidade de redescobrir a rede.
- **Auto-save em toda modificação**: salvar automaticamente (com debounce) quando o mapa é alterado — adicionar objeto, remover objeto, mover nó, mover grupo e editar propriedades de um dispositivo — não apenas ao mover nós.
- **Botão "Save Map" na aba Settings**: renomear/ampliar a ação manual existente ("Save Layout") para salvar o mapa completo, mantendo o "Export PNG" inalterado.

## Capabilities

### New Capabilities

- `topology-map-persistence`: Persistência do mapa de topologia — salvar o grafo completo (devices, links, objetos manuais e propriedades) junto com as posições, carregar automaticamente o último mapa no startup e salvar automaticamente a cada modificação do mapa.

### Modified Capabilities

Nenhum. Nenhuma capability existente tem requisitos alterados; a mudança é aditiva e evolui a persistência interna da aba Topology.

## Impact

- **Código modificado**: `cetuslib/topology/persistence.py` (novas funções `save_map`/`load_map` para serializar/deserializar o `TopologyGraph` completo + posições; manter compatibilidade com `topology_layout.json`), `cetuslib/topology/gui/view.py` (auto-save em add/remove/property, auto-load), `cetuslib/topology/tab.py` (botão "Save Map", carregamento inicial do mapa salvo).
- **Código novo**: possivelmente funções `to_dict`/`from_dict` nos dataclasses de `cetuslib/topology/models.py` para serialização limpa do grafo.
- **Config**: novo arquivo `~/.config/cetus/topology_map.json` (mapa completo); `topology_layout.json` continua existindo para compatibilidade ou é absorvido pelo novo formato.
- **Dependências**: nenhuma nova (JSON stdlib).
- **Empacotamento**: `dist/cetus` regenerado via `scripts/bundle-monolith.py`; nada muda nas receitas .deb/AppImage/Flatpak.
- **Dados**: propriedades derivadas/efêmeras (taxas de tráfego, CPU/memória em tempo real, vizinhos LLDP) não são persistidas — apenas identidade, posição, papel e conexões manuais.
