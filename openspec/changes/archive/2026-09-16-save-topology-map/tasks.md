# Tasks: save-topology-map

## 1. Serialização do grafo

- [x] 1.1 Adicionar `to_dict()`/`from_dict()` em `Device` e `PortLink` de `cetuslib/topology/models.py`, persistindo apenas campos de identidade (id, ip, hostname, role, vendor, model, chassis_id, status, layer) e excluindo interfaces, vizinhos LLDP, CPU/memória e taxas. Verificar com `python3 -m py_compile cetuslib/topology/models.py` e um round-trip manual `Device.from_dict(d.to_dict())`
- [x] 1.2 Adicionar `to_dict()`/`from_dict()` em `TopologyGraph` (devices + links). Verificar com round-trip manual de um grafo de demo (`cetuslib/topology/demo.py`) preservando devices e links

## 2. Persistência completa em `persistence.py`

- [x] 2.1 Adicionar `default_map_path()` (`~/.config/cetus/topology_map.json`) e `save_map(graph, positions, path, group_positions)`/`load_map(path)` no formato `{version: 3, devices, links, positions, groups}`, descartando posições cujo ID não existe no grafo. Verificar salvando/recarregando um grafo de demo e conferindo `topology_map.json` no disco
- [x] 2.2 Manter `save_layout`/`load_layout` (formato v2) para compatibilidade com o modo standalone/demo. Verificar com `python3 -m py_compile cetuslib/topology/persistence.py` e execução do `demo_gui --save`

## 3. Auto-save no `TopologyView`

- [x] 3.1 Registrar objetos manuais no grafo persistido: `TopologyScene.add_manual_device` cria/usa `self.graph` e insere o `Device` em `graph.devices`; derivar `_manual_counter` do maior `manual-N` ao carregar. Verificar adicionando um dispositivo da paleta e conferindo que aparece em `graph.devices`
- [x] 3.2 Trocar `save_layout` por `save_map` no `TopologyView` (grafo completo + posições + grupos) e apontar o debounce existente para `save_map`. Verificar movendo um nó e conferindo que `topology_map.json` é atualizado após ~800 ms
- [x] 3.3 Disparar `_schedule_save` ao adicionar objeto manual. Verificar arrastando um dispositivo da paleta e conferindo que o mapa salva automaticamente
- [x] 3.4 Implementar `remove_node` no `TopologyScene`/`TopologyView` (remove `NodeItem`, `Device` do grafo e links que o tocam) e disparar `_schedule_save`. Verificar removendo um nó e conferindo que ele e seus links somem do arquivo salvo
- [x] 3.5 Adicionar gatilho de remoção na UI: tecla `Delete` (`keyPressEvent`) com item selecionado e item "Remover" no menu de contexto do nó. Verificar removendo um nó via tecla Delete e via menu de contexto

## 4. Edição de propriedades

- [x] 4.1 Tornar a aba "Identity" de `DeviceDetailDialog` editável (hostname, ip, role, vendor, model, status, layer) com botão "Apply" que muta o `Device` e emite sinal `device_changed`. Verificar editando o hostname de um nó e conferindo que ele atualiza no mapa
- [x] 4.2 Conectar `device_changed` do diálogo a `_schedule_save` no `TopologyView` e repintar o nó após `Apply`. Verificar editando uma propriedade e conferindo que o mapa salva automaticamente após ~800 ms

## 5. Auto-load no startup

- [x] 5.1 Implementar `TopologyView.load_saved_map()`: lê `load_map(default_map_path())` e, se houver devices, popula a scene com as posições salvas como autoritativas (sem `TopologyEngine`, sem monitor). Verificar com `python3 -m py_compile cetuslib/topology/gui/view.py`
- [x] 5.2 Chamar `load_saved_map()` no `TopologyTab.__init__` após `set_layout_path`. Verificar abrindo o Cetus com um mapa salvo e conferindo que a aba Topology exibe o último mapa

## 6. UI e integração

- [x] 6.1 Renomear "Save Layout" para "Save Map" na aba Settings e apontar para `self.view.save_map()`. Verificar clicando em "Save Map" e conferindo que o arquivo é gravado imediatamente
- [x] 6.2 Garantir que "Export PNG" permanece inalterado. Verificar exportando um PNG e conferindo a imagem

## 7. Validação final

- [x] 7.1 Regressão: `python3 -m py_compile cetuslib/topology/models.py cetuslib/topology/persistence.py cetuslib/topology/gui/view.py cetuslib/topology/gui/detail.py cetuslib/topology/tab.py` e regenerar `dist/cetus` via `python3 scripts/bundle-monolith.py`
- [x] 7.2 Teste de ciclo completo: adicionar objetos manuais, mover nós, editar propriedades, remover um nó, fechar e reabrir o Cetus — o mapa reaparece idêntico (objetos, posições, propriedades) e cada modificação foi salva automaticamente
