## 1. Modelo e resolução de interface

- [x] 1.1 Adicionar `EdgeItem.target_interface()` para resolver a interface de destino via `normalize_port(target_port)` (análogo a `source_interface`). Verificar com `python3 -m py_compile cetuslib/topology/gui/view.py`.
- [x] 1.2 Adicionar `EdgeItem.refresh_state()` que calcula o estado do link só pelo `oper_status` das duas interfaces (`down` se qualquer lado down, senão `active`). Verificar que retorna `down` quando qualquer lado está "down".

## 2. Estilo por estado no EdgeItem

- [x] 2.1 Refatorar `EdgeItem` para aplicar pen por estado: tracejado animado (ativo), sólido vermelho (offline). Verificar com o demo e com `py_compile`.

## 3. Animação compartilhada

- [x] 3.1 Adicionar um `QTimer` único em `TopologyView` (~40ms) que incrementa uma fase global e atualiza `dashOffset` + `edge.update()` apenas nas edges ativas. Verificar que apenas links ativos animam.
- [x] 3.2 Garantir que o timer é filho da view (auto-limpo) e não vaza ao fechar a aba.

## 4. Re-verificação de status a cada minuto

- [x] 4.1 Adicionar `LldpCollector.poll_status()` (walk leve de `ifOperStatus`). Verificar com `py_compile`.
- [x] 4.2 Em `TrafficMonitor`, re-verificar `oper_status` a cada `status_interval` (60s) e emitir `status_updated`. Verificar que o sinal só dispara após o intervalo.
- [x] 4.3 Em `TopologyView.update_statuses`, aplicar os status nas interfaces e chamar `refresh_state()`. Conectar `status_updated` na tab. Verificar que um link muda de cor ao alternar up/down.

## 5. Integração e validação

- [x] 5.1 Conectar o fluxo completo (monitor → `update_traffic`/`update_statuses` → `refresh_state` → estilo/animação) e verificar com um gráfico de teste que os estados renderizam corretamente.
- [x] 5.2 Rodar `python3 -m py_compile` em `view.py`, `monitor.py`, `collector.py`, `models.py`, `tab.py` e `openspec validate animate-topology-links` para confirmar sintaxe e artefatos válidos.
