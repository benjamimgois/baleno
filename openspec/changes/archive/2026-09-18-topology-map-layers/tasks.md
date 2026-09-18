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

## 5. Painel de camadas estilo GIMP e ações contextuais

- [x] 5.1 Criar `LayerTreeWidget` com agrupamento hierárquico por prefixo e nós expansíveis/colapsáveis
- [x] 5.2 Implementar alternância de visibilidade por ícone de olho com atualização em cascata para grupos
- [x] 5.3 Exibir contadores de nós por camada e agregados por grupo
- [x] 5.4 Implementar menu de contexto (botão direito): *Solo (Isolar)*, *Enquadrar no mapa*, *Exibir/Ocultar grupo* e *Remover camada*
- [x] 5.5 Implementar método `fit_layer` na `TopologyView` para centralizar o zoom nos nós da camada

## 6. Reestruturação da UI (Layout Studio / CAD)

- [x] 6.1 Implementar barra superior compacta de linha única (~38px) com inputs de descoberta e ações rápidas
- [x] 6.2 Criar popover de configurações SNMP (`[ ⚙ SNMP: v2c ▾ ]`) para versão, comunidade e v3
- [x] 6.3 Construir painel lateral retrátil (Sidebar) à direita integrando `LayerTreeWidget` e paleta de objetos arrastáveis
- [x] 6.4 Implementar mini-dock flutuante no canvas com `Zoom In`, `Zoom Out`, `Fit In View` e `Link Tool`
- [x] 6.5 Remover abas legadas da Ribbon e conectar atalhos/toggles do painel lateral

## 7. Monitor (fix do crash)

- [x] 7.1 Parar o monitor antigo antes do merge, garantindo a finalização da thread (sem descartar thread em execução)
- [x] 7.2 Iniciar um novo monitor cobrindo todos os dispositivos do grafo mesclado

## 8. Persistência

- [x] 8.1 Persistir `layers` no `save_map` e restaurar no `load_map`/`load_saved_map`

## 9. Verificação

- [x] 9.1 `python3 -m py_compile` nos arquivos alterados
- [x] 9.2 Testar: agrupamento e expansão/colapso de camadas na árvore estilo GIMP
- [x] 9.3 Testar: ação Solo e Enquadrar no mapa via menu de contexto
- [x] 9.4 Testar: abertura/fechamento do painel lateral e arraste de objetos da paleta
- [x] 9.5 Testar: popover SNMP altera versão e credenciais corretamente
- [x] 9.6 Testar: reinício do app restaura o mapa acumulado com as camadas e estado de visibilidade
