## 1. Modelo de dados

- [x] 1.1 Adicionar `layers: set[str]` ao `Device` em `models.py` (default vazio)
- [x] 1.2 Serializar `layers` em `Device.to_dict` / restaurar em `from_dict` (leitura tolerante a arquivos antigos)

## 2. Descoberta nomeada

- [x] 2.1 Adicionar campo de nome da camada no formulário de discovery (`tab.py`)
- [x] 2.2 Propagar o nome da descoberta ao `TopologyDiscoveryWorker`
- [x] 2.3 Atribuir camadas no worker/collector: `<nome>` (semente) e `<nome>-<N>` (vizinho LLDP, salto N)

## 3. Merge em vez de substituir

- [x] 3.1 Remover o `clear_scene()` do `start_discovery` e fazer `_on_finished` mesclar no grafo existente
- [x] 3.2 Implementar dedup por `chassis_id` no merge (fundir nó, somar links e camadas)
- [x] 3.3 Reconstruir a cena a partir do grafo mesclado preservando posições existentes

## 4. Posicionamento espacial

- [x] 4.1 Posicionar os novos dispositivos à direita do bounding box atual (offset por descoberta)
- [x] 4.2 Preservar a sub-hierarquia (sementes acima, vizinhos abaixo) dentro da nova região

## 5. Painel de camadas e visibilidade

- [x] 5.1 Construir o painel de camadas listando as camadas presentes no grafo
- [x] 5.2 Implementar filtro de visibilidade por camada (dispositivo visível se alguma camada visível; aresta se ambos os extremos visíveis)
- [x] 5.3 Atualizar o painel quando novas camadas são adicionadas pelo merge

## 6. Monitor (fix do crash)

- [x] 6.1 Parar o monitor antigo antes do merge, garantindo a finalização da thread (sem descartar thread em execução)
- [x] 6.2 Iniciar um novo monitor cobrindo todos os dispositivos do grafo mesclado

## 7. Persistência

- [x] 7.1 Persistir `layers` no `save_map` e restaurar no `load_map`/`load_saved_map`

## 8. Verificação

- [x] 8.1 `python3 -m py_compile` nos arquivos alterados
- [ ] 8.2 Testar: múltiplas descobertas acumulam sem crash e sem substituir o mapa
- [ ] 8.3 Testar: ocultar/exibir camadas filtra a exibição corretamente
- [ ] 8.4 Testar: reiniciar o app restaura o mapa acumulado com as camadas
